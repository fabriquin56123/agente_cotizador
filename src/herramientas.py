"""Registro de tools del agente: esquema + validación + ejecución + registro seguro.

- Lecturas: se ejecutan automáticamente.
- Escrituras: requieren confirmación explícita del usuario vía `confirmador`
  (callback fuera del modelo). Sin confirmación la tool queda bloqueada.
- Toda entrada se valida (tipos, rangos, listas, longitud) ANTES de ejecutar.
"""
from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Protocol

from .config import ARCHIVO_DECISIONES_AGENTE, fecha_referencia
from .logging_seguro import fijar_correlation_id, registrar_llamada
from .modelos import Decision
from .politica import evaluar_solicitud as evaluar_politica
from .rag import buscar_politica as buscar_rag
from .repositorio import cargar_tarifario, cargar_transacciones
from .servicios import resumen_cliente, similares_por_mcc
from .solicitudes import leer_solicitud as leer_solicitud_txt
from .validacion import (
    ErrorValidacion, validar_documento, validar_entero, validar_id_solicitud, validar_mcc,
    validar_texto,
)

Confirmador = Callable[[str, str], bool]
RESULTADO_OK, RESULTADO_ERROR, RESULTADO_BLOQUEADA = "ok", "error", "bloqueada"
CAMPOS_DECISIONES = ["id_solicitud", "flag_decision", "motivo", "giro_principal", "tasa_final_pct", "fecha_ref"]


class FuenteDatos(Protocol):
    def resumen_cliente(self, ruc: str, meses: int) -> dict[str, Any]: ...
    def similares(self, mcc: str) -> dict[str, Any]: ...


class FuenteLocal:
    """Lee el CSV directamente (sin red)."""

    def resumen_cliente(self, ruc: str, meses: int) -> dict[str, Any]:
        return resumen_cliente(ruc, meses)

    def similares(self, mcc: str) -> dict[str, Any]:
        return similares_por_mcc(mcc)


class FuenteApi:
    """Consume la API FastAPI (API_BASE_URL). Solo GET; timeout corto."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url, self.timeout = base_url.rstrip("/"), timeout

    def _get(self, ruta: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        import requests

        resp = requests.get(self.base_url + ruta, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return dict(resp.json())

    def resumen_cliente(self, ruc: str, meses: int) -> dict[str, Any]:
        return self._get(f"/clientes/{ruc}/resumen", {"meses": meses})

    def similares(self, mcc: str) -> dict[str, Any]:
        return self._get(f"/comercios-similares/{mcc}")


def fuente_por_defecto() -> FuenteDatos:
    base = os.environ.get("API_BASE_URL")
    return FuenteApi(base) if base else FuenteLocal()


@dataclass(frozen=True)
class Contexto:
    fuente: FuenteDatos
    fecha_ref: date
    dir_solicitudes: Path | None = None
    ruta_decisiones: Path = ARCHIVO_DECISIONES_AGENTE


def contexto_por_defecto() -> Contexto:
    return Contexto(fuente=fuente_por_defecto(), fecha_ref=fecha_referencia())


@dataclass(frozen=True)
class Herramienta:
    nombre: str
    descripcion: str
    parametros: dict[str, Any]
    escritura: bool
    validar: Callable[[dict[str, Any]], dict[str, Any]]
    ejecutar: Callable[[dict[str, Any], Contexto], dict[str, Any]]


# ---------- validadores (uno por tool) ----------
def _solo_claves(args: dict[str, Any], permitidas: set[str]) -> None:
    extra = set(args) - permitidas
    if extra:
        raise ErrorValidacion("argumentos no permitidos: " + ", ".join(sorted(extra)))


def _v_solicitud(args: dict[str, Any]) -> dict[str, Any]:
    _solo_claves(args, {"id_solicitud"})
    return {"id_solicitud": validar_id_solicitud(args.get("id_solicitud"))}


def _v_transacciones(args: dict[str, Any]) -> dict[str, Any]:
    _solo_claves(args, {"ruc", "meses"})
    return {"ruc": validar_documento(args.get("ruc")),
            "meses": validar_entero(args.get("meses", 6), "meses", 1, 12)}


def _v_mcc(args: dict[str, Any]) -> dict[str, Any]:
    _solo_claves(args, {"mcc"})
    return {"mcc": validar_mcc(args.get("mcc"))}


def _v_politica(args: dict[str, Any]) -> dict[str, Any]:
    _solo_claves(args, {"consulta", "top_k"})
    return {"consulta": validar_texto(args.get("consulta"), "consulta", 300),
            "top_k": validar_entero(args.get("top_k", 3), "top_k", 1, 5)}


# ---------- ejecutores ----------
def _decision_a_dict(d: Decision) -> dict[str, Any]:
    def txt(v: Any) -> Any:
        return None if v is None else f"{v:.2f}"

    return {
        "id_solicitud": d.id_solicitud, "flag_decision": d.flag, "motivo": d.motivo,
        "giro_principal": d.giro_principal, "zona_premium": d.zona_premium,
        "meses_historial": d.meses_historial,
        "tasa_referencia_competencia_pct": txt(d.tasa_referencia_competencia),
        "tasa_calculada_pct": txt(d.tasa_calculada), "tasa_final_pct": txt(d.tasa_final),
    }


def _evaluar(id_solicitud: str, ctx: Contexto) -> Decision:
    sol = leer_solicitud_txt(id_solicitud, ctx.dir_solicitudes)
    return evaluar_politica(sol, cargar_transacciones(), cargar_tarifario(), ctx.fecha_ref)


def _e_leer_solicitud(args: dict[str, Any], ctx: Contexto) -> dict[str, Any]:
    s = leer_solicitud_txt(args["id_solicitud"], ctx.dir_solicitudes)
    return {
        "id_solicitud": s.id_solicitud, "ruc": s.ruc, "razon_social": s.razon_social,
        "codigos_giro": list(s.codigos_giro), "nombres_giro": list(s.nombres_giro),
        "banco_afiliado": s.banco_afiliado, "moneda_cuenta": s.moneda_cuenta,
        "departamento": s.departamento, "provincia": s.provincia, "distrito": s.distrito,
        "bancos_competencia": list(s.bancos_competencia),
        "tasas_competencia_pct": [f"{t:.2f}" for t in s.tasas_competencia],
    }


def _e_transacciones(args: dict[str, Any], ctx: Contexto) -> dict[str, Any]:
    return ctx.fuente.resumen_cliente(args["ruc"], args["meses"])


def _e_similares(args: dict[str, Any], ctx: Contexto) -> dict[str, Any]:
    return ctx.fuente.similares(args["mcc"])


def _e_politica(args: dict[str, Any], ctx: Contexto) -> dict[str, Any]:
    return {"resultados": buscar_rag(args["consulta"], args["top_k"])}


def _e_evaluar(args: dict[str, Any], ctx: Contexto) -> dict[str, Any]:
    return _decision_a_dict(_evaluar(args["id_solicitud"], ctx))


def _e_guardar(args: dict[str, Any], ctx: Contexto) -> dict[str, Any]:
    """ESCRITURA: upsert de la decisión en data/salidas/decisiones_agente.csv."""
    fila = _decision_a_dict(_evaluar(args["id_solicitud"], ctx))
    nueva = {"id_solicitud": fila["id_solicitud"], "flag_decision": fila["flag_decision"],
             "motivo": fila["motivo"], "giro_principal": fila["giro_principal"] or "",
             "tasa_final_pct": fila["tasa_final_pct"] or "", "fecha_ref": ctx.fecha_ref.isoformat()}
    upsert_csv(ctx.ruta_decisiones, nueva)
    return {"guardado": True, "id_solicitud": nueva["id_solicitud"], "flag_decision": nueva["flag_decision"]}


def upsert_csv(ruta: Path, fila: dict[str, str]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    existentes: list[dict[str, str]] = []
    if ruta.is_file():
        with ruta.open(newline="", encoding="utf-8") as f:
            existentes = [r for r in csv.DictReader(f) if r["id_solicitud"] != fila["id_solicitud"]]
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_DECISIONES)
        w.writeheader()
        w.writerows(existentes + [fila])


# ---------- registro ----------
def _esquema(propiedades: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": propiedades, "required": list(propiedades),
            "additionalProperties": False}


_ID = {"type": "string", "description": "Id de solicitud con formato SOL-NNN, p. ej. SOL-004."}

HERRAMIENTAS: dict[str, Herramienta] = {h.nombre: h for h in (
    Herramienta("leer_solicitud", "Lee los datos de una solicitud de cotización.",
                _esquema({"id_solicitud": _ID}), False, _v_solicitud, _e_leer_solicitud),
    Herramienta("consultar_transacciones_cliente",
                "Resume por giro las transacciones de un cliente en los últimos N meses (1 a 12).",
                _esquema({"ruc": {"type": "string", "description": "RUC de 11 dígitos o DNI de 8."},
                          "meses": {"type": "integer", "description": "Meses de ventana, de 1 a 12 (usa 6)."}}),
                False, _v_transacciones, _e_transacciones),
    Herramienta("consultar_comercios_similares",
                "Tasa de referencia de comercios similares (mismo MCC) para clientes nuevos.",
                _esquema({"mcc": {"type": "string", "description": "Código MCC de 4 dígitos."}}),
                False, _v_mcc, _e_similares),
    Herramienta("buscar_politica",
                "Busca en la política de pricing y el informe de zonas (RAG).",
                _esquema({"consulta": {"type": "string", "description": "Pregunta, máximo 300 caracteres."},
                          "top_k": {"type": "integer", "description": "Fragmentos a devolver, de 1 a 5."}}),
                False, _v_politica, _e_politica),
    Herramienta("evaluar_solicitud",
                "Aplica la política de forma determinista y devuelve decisión, giro principal y tasa final.",
                _esquema({"id_solicitud": _ID}), False, _v_solicitud, _e_evaluar),
    Herramienta("guardar_decision",
                "ESCRITURA. Guarda la decisión de una solicitud en data/salidas/decisiones_agente.csv. "
                "Requiere confirmación explícita del usuario.",
                _esquema({"id_solicitud": _ID}), True, _v_solicitud, _e_guardar),
)}


def definiciones_para_foundry() -> list[dict[str, Any]]:
    """Esquemas de las tools tal como se registran en el agente."""
    return [{"name": h.nombre, "description": h.descripcion, "parameters": h.parametros}
            for h in HERRAMIENTAS.values()]


def _error(codigo: str, mensaje: str = "") -> dict[str, Any]:
    return {"ok": False, "error": codigo, "detalle": mensaje}


def ejecutar_herramienta(
    nombre: str, argumentos: Any, ctx: Contexto | None = None,
    confirmador: Confirmador | None = None, correlation_id: str | None = None,
) -> dict[str, Any]:
    """Valida → (confirma si escribe) → ejecuta → registra. Nunca lanza por entrada inválida."""
    if correlation_id:
        fijar_correlation_id(correlation_id)
    inicio = time.perf_counter()
    resultado, salida, error = _despachar(nombre, argumentos, ctx or contexto_por_defecto(), confirmador)
    ms = (time.perf_counter() - inicio) * 1000
    registrar_llamada(nombre, ms, resultado, error, extra={"ok": salida.get("ok")})
    return salida


def _despachar(
    nombre: str, argumentos: Any, ctx: Contexto, confirmador: Confirmador | None
) -> tuple[str, dict[str, Any], str | None]:
    herramienta = HERRAMIENTAS.get(nombre)
    if herramienta is None:
        return RESULTADO_ERROR, _error("HERRAMIENTA_DESCONOCIDA"), "HERRAMIENTA_DESCONOCIDA"
    if not isinstance(argumentos, dict):
        return RESULTADO_ERROR, _error("ARGUMENTOS_INVALIDOS", "se esperaba un objeto"), "ARGUMENTOS_INVALIDOS"
    try:
        validos = herramienta.validar(argumentos)
    except ErrorValidacion as exc:
        return RESULTADO_ERROR, _error("VALIDACION", str(exc)), f"VALIDACION: {exc}"
    if herramienta.escritura and not _confirmada(herramienta, validos, confirmador):
        return (RESULTADO_BLOQUEADA, _error("CONFIRMACION_REQUERIDA", "el usuario no confirmó la escritura"),
                "CONFIRMACION_REQUERIDA")
    return _ejecutar(herramienta, validos, ctx)


def _confirmada(h: Herramienta, args: dict[str, Any], confirmador: Confirmador | None) -> bool:
    if confirmador is None:
        return False
    return bool(confirmador(h.nombre, f"{h.nombre} con {args}"))


def _ejecutar(h: Herramienta, args: dict[str, Any], ctx: Contexto) -> tuple[str, dict[str, Any], str | None]:
    try:
        return RESULTADO_OK, {"ok": True, "datos": h.ejecutar(args, ctx)}, None
    except ErrorValidacion as exc:
        return RESULTADO_ERROR, _error("VALIDACION", str(exc)), f"VALIDACION: {exc}"
    except Exception as exc:  # fallo inesperado: no se filtra el detalle al modelo
        return RESULTADO_ERROR, _error("ERROR_INTERNO", type(exc).__name__), f"{type(exc).__name__}"
