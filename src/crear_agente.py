"""Crea (registra) el agente en Microsoft Foundry.

Por seguridad es DRY-RUN por defecto: solo muestra el plan, no toca la nube.
Con --apply pide confirmación escribiendo el nombre del agente.

Uso:
    python -m src.crear_agente            # muestra el plan
    python -m src.crear_agente --apply    # crea una versión del agente (requiere aprobación)
"""
from __future__ import annotations

import argparse
import os
from typing import Any

from .config import cargar_entorno, leer_config_foundry, variables_faltantes
from .herramientas import definiciones_para_foundry
from .instrucciones import INSTRUCCIONES


def construir_plan() -> dict[str, Any]:
    """Plan del agente a crear (sin secretos; el endpoint nunca se incluye)."""
    cargar_entorno()
    tools = definiciones_para_foundry()
    return {
        "agente": os.environ.get("AGENT_NAME", "<sin definir>"),
        "modelo_deployment": os.environ.get("MODEL_DEPLOYMENT_NAME", "<sin definir>"),
        "tools": [t["name"] for t in tools],
        "caracteres_instrucciones": len(INSTRUCCIONES),
        "variables_faltantes": variables_faltantes(),
        "accion": "project.agents.create_version(...)  [crea una versión del agente en Foundry]",
    }


def mostrar_plan(plan: dict[str, Any]) -> None:
    print("PLAN (nada se ha creado):")
    for clave, valor in plan.items():
        print(f"  - {clave}: {valor}")


def confirmar_aplicacion(nombre_agente: str) -> bool:
    escrito = input(f"Para crear el agente escribe su nombre exacto ({nombre_agente}): ")
    return escrito.strip() == nombre_agente


def crear_en_foundry(config: dict[str, str]) -> None:
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import FunctionTool, PromptAgentDefinition
    from azure.identity import DefaultAzureCredential

    tools = [
        FunctionTool(name=d["name"], parameters=d["parameters"], description=d["description"], strict=True)
        for d in definiciones_para_foundry()
    ]
    definicion = PromptAgentDefinition(
        model=config["MODEL_DEPLOYMENT_NAME"], instructions=INSTRUCCIONES, tools=tools,
    )
    with AIProjectClient(endpoint=config["PROJECT_ENDPOINT"], credential=DefaultAzureCredential()) as proyecto:
        version = proyecto.agents.create_version(agent_name=config["AGENT_NAME"], definition=definicion)
    print(f"Agente creado: {version.name} (versión {version.version})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crear agente en Foundry (dry-run por defecto)")
    parser.add_argument("--apply", action="store_true", help="Crear realmente el agente")
    args = parser.parse_args(argv)
    plan = construir_plan()
    mostrar_plan(plan)
    if not args.apply:
        print("\nDry-run: use --apply para crear (pedirá confirmación).")
        return 0
    config = leer_config_foundry()
    if not confirmar_aplicacion(config["AGENT_NAME"]):
        print("Cancelado: no se creó nada.")
        return 1
    crear_en_foundry(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
