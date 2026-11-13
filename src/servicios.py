"""Servicios de lectura compartidos por la API y las tools (devuelven dicts sin PII)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from .config import fecha_referencia
from .cotizador import tasa_referencia_similares, tasas_comercios_similares
from .modelos import RegistroTx
from .repositorio import (
    cargar_tarifario, cargar_transacciones, en_ventana, meses_con_datos, resumen_por_giro,
    transacciones_de_ruc, ventana_periodos,
)
from .validacion import validar_documento, validar_entero, validar_mcc, validar_periodo

LIMITE_MAXIMO = 100


def resumen_cliente(
    ruc: str, meses: int = 6, fecha_ref: date | None = None,
    registros: tuple[RegistroTx, ...] | None = None,
) -> dict[str, object]:
    """Resumen de transacciones de un cliente en la ventana (sin razón social ni RUC)."""
    doc = validar_documento(ruc)
    n = validar_entero(meses, "meses", 1, 12)
    periodos = ventana_periodos(fecha_ref or fecha_referencia(), n)
    historial = transacciones_de_ruc(registros or cargar_transacciones(), doc)
    ventana = en_ventana(historial, periodos)
    return {
        "existe_en_base": bool(historial),
        "ventana": [periodos[0], periodos[-1]],
        "meses_con_datos": meses_con_datos(ventana),
        "giros": resumen_por_giro(historial, periodos),
    }


def similares_por_mcc(
    mcc: str, fecha_ref: date | None = None, registros: tuple[RegistroTx, ...] | None = None,
) -> dict[str, object]:
    """Tasa de referencia de comercios similares (mismo MCC, 6 meses completos)."""
    codigo = validar_mcc(mcc)
    todos = registros or cargar_transacciones()
    tarifario = cargar_tarifario()
    periodos = ventana_periodos(fecha_ref or fecha_referencia(), 6)
    comparables = tasas_comercios_similares(codigo, todos, tarifario, periodos, "")
    referencia = tasa_referencia_similares(codigo, todos, tarifario, periodos)
    return {
        "mcc": codigo,
        "comercios_comparables": len(comparables),
        "tasa_base_pct": _texto(tarifario.get(codigo)),
        "tasa_referencia_pct": _texto(referencia),
    }


def listar_transacciones(
    ruc: str | None = None, periodo: str | None = None, codigo_giro: str | None = None,
    limite: int = 50, desde: int = 0,
) -> dict[str, object]:
    """Filas de la base filtradas y paginadas (límite máximo 100)."""
    tam = validar_entero(limite, "limite", 1, LIMITE_MAXIMO)
    inicio = validar_entero(desde, "desde", 0, 1_000_000)
    filas = list(cargar_transacciones())
    if ruc is not None:
        filas = [r for r in filas if r.ruc == validar_documento(ruc)]
    if periodo is not None:
        filas = [r for r in filas if r.periodo == validar_periodo(periodo)]
    if codigo_giro is not None:
        filas = [r for r in filas if r.codigo_giro == validar_mcc(codigo_giro, "codigo_giro")]
    pagina = filas[inicio:inicio + tam]
    return {"total": len(filas), "limite": tam, "desde": inicio,
            "items": [_registro_a_dict(r) for r in pagina]}


def _registro_a_dict(r: RegistroTx) -> dict[str, object]:
    return {
        "id_transaccion": r.id_transaccion, "id_cliente": r.id_cliente, "ruc": r.ruc,
        "razon_social": r.razon_social, "periodo": r.periodo, "codigo_giro": r.codigo_giro,
        "moneda": r.moneda, "volumen_bbva": float(r.vol_bbva),
        "volumen_interbank": float(r.vol_interbank), "volumen_bcp": float(r.vol_bcp),
    }


def _texto(valor: Decimal | None) -> str | None:
    return None if valor is None else f"{valor:.2f}"
