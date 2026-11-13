"""Ejecuta el agente de cotización en Microsoft Foundry (bucle de llamadas a tools).

Uso:
    python -m src.agente                       # chat interactivo
    python -m src.agente --solicitud SOL-004   # evalúa una solicitud y sale

Requiere `python -m src.crear_agente --apply` ejecutado antes (con aprobación).
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Protocol

from .config import leer_config_foundry
from .herramientas import Confirmador, Contexto, contexto_por_defecto, ejecutar_herramienta
from .logging_seguro import fijar_correlation_id

MAX_RONDAS_TOOLS = 8


class ClienteRespuestas(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


def extraer_llamadas(respuesta: Any) -> list[Any]:
    return [item for item in respuesta.output if getattr(item, "type", None) == "function_call"]


def parsear_argumentos(crudo: str) -> Any:
    """JSON de argumentos; si no parsea se devuelve None (la tool lo rechazará)."""
    try:
        return json.loads(crudo or "{}")
    except json.JSONDecodeError:
        return None


def salida_de_llamada(llamada: Any, ctx: Contexto, confirmador: Confirmador | None, cid: str) -> dict[str, str]:
    resultado = ejecutar_herramienta(
        llamada.name, parsear_argumentos(llamada.arguments), ctx, confirmador, correlation_id=cid,
    )
    return {"type": "function_call_output", "call_id": llamada.call_id,
            "output": json.dumps(resultado, ensure_ascii=False)}


def ejecutar_turno(
    respuestas: ClienteRespuestas, conversacion_id: str, texto: str,
    ctx: Contexto, confirmador: Confirmador | None, correlation_id: str | None = None,
) -> str:
    """Un turno del usuario: resuelve llamadas a tools hasta obtener texto final."""
    cid = fijar_correlation_id(correlation_id)
    respuesta = respuestas.create(input=texto, conversation=conversacion_id)
    for _ in range(MAX_RONDAS_TOOLS):
        llamadas = extraer_llamadas(respuesta)
        if not llamadas:
            return str(respuesta.output_text)
        salidas = [salida_de_llamada(ll, ctx, confirmador, cid) for ll in llamadas]
        respuesta = respuestas.create(input=salidas, conversation=conversacion_id)
    raise RuntimeError("Se excedió el máximo de rondas de tools")


def confirmador_interactivo(nombre: str, resumen: str) -> bool:
    """Pide confirmación por consola; cualquier cosa distinta de 's' es un no."""
    respuesta = input(f"\n[ESCRITURA] {resumen}\n¿Confirmas esta escritura? [s/N]: ")
    return respuesta.strip().lower() in ("s", "si", "sí")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Agente de cotización (Foundry)")
    parser.add_argument("--solicitud", help="Id SOL-NNN a evaluar y salir")
    args = parser.parse_args(argv)
    config = leer_config_foundry()

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    ctx = contexto_por_defecto()
    with AIProjectClient(endpoint=config["PROJECT_ENDPOINT"], credential=DefaultAzureCredential()) as proyecto:
        with proyecto.get_openai_client(agent_name=config["AGENT_NAME"]) as openai:
            conversacion = openai.conversations.create()
            try:
                _bucle(openai.responses, conversacion.id, ctx, args.solicitud)
            finally:
                openai.conversations.delete(conversation_id=conversacion.id)


def _bucle(respuestas: ClienteRespuestas, conversacion_id: str, ctx: Contexto, solicitud: str | None) -> None:
    if solicitud:
        pedido = f"Evalúa la solicitud {solicitud} y explica el resultado."
        print("\nAgente:", ejecutar_turno(respuestas, conversacion_id, pedido, ctx, confirmador_interactivo))
    while True:
        texto = input("\nTú (vacío para salir): ").strip()
        if not texto:
            return
        print("\nAgente:", ejecutar_turno(respuestas, conversacion_id, texto, ctx, confirmador_interactivo))

if __name__ == "__main__":
    main()
