"""Acceso de solo lectura a la base transaccional y al tarifario (funciones puras + carga)."""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from .config import ARCHIVO_TARIFARIO, ARCHIVO_TRANSACCIONES, TIPO_CAMBIO_USD
from .modelos import RegistroTx


def _fila_a_registro(fila: dict[str, str]) -> RegistroTx:
    return RegistroTx(
        id_transaccion=fila["id_transaccion"], id_cliente=fila["id_cliente"],
        ruc=fila["ruc"], razon_social=fila["razon_social"], periodo=fila["periodo"],
        codigo_giro=fila["codigo_giro"], moneda=fila["moneda"],
        vol_bbva=Decimal(fila["volumen_bbva"]), vol_interbank=Decimal(fila["volumen_interbank"]),
        vol_bcp=Decimal(fila["volumen_bcp"]),
    )


@lru_cache(maxsize=4)
def _cargar_transacciones(ruta: str) -> tuple[RegistroTx, ...]:
    with open(ruta, newline="", encoding="utf-8") as f:
        return tuple(_fila_a_registro(fila) for fila in csv.DictReader(f))


def cargar_transacciones(ruta: Path | None = None) -> tuple[RegistroTx, ...]:
    return _cargar_transacciones(str(ruta or ARCHIVO_TRANSACCIONES))


@lru_cache(maxsize=4)
def _cargar_tarifario(ruta: str) -> dict[str, Decimal]:
    with open(ruta, newline="", encoding="utf-8") as f:
        return {fila["mcc"]: Decimal(fila["tasa_pct"]) for fila in csv.DictReader(f)}


def cargar_tarifario(ruta: Path | None = None) -> dict[str, Decimal]:
    return dict(_cargar_tarifario(str(ruta or ARCHIVO_TARIFARIO)))


def ventana_periodos(fecha_ref: date, meses: int = 6) -> tuple[str, ...]:
    """Los `meses` meses cerrados previos al mes de `fecha_ref` (en orden cronológico)."""
    anio, mes = fecha_ref.year, fecha_ref.month
    salida: list[str] = []
    for _ in range(meses):
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
        salida.append(f"{anio:04d}-{mes:02d}")
    return tuple(reversed(salida))


def transacciones_de_ruc(registros: tuple[RegistroTx, ...] | list[RegistroTx], ruc: str) -> list[RegistroTx]:
    return [r for r in registros if r.ruc == ruc]


def en_ventana(registros: list[RegistroTx], periodos: tuple[str, ...]) -> list[RegistroTx]:
    permitidos = set(periodos)
    return [r for r in registros if r.periodo in permitidos]


def volumen_pen(registro: RegistroTx) -> Decimal:
    """Volumen total del registro expresado en soles."""
    factor = TIPO_CAMBIO_USD if registro.moneda == "USD" else Decimal(1)
    return registro.volumen_total * factor


def volumen_por_giro(registros: list[RegistroTx]) -> dict[str, Decimal]:
    """Suma de volumen en soles por código de giro."""
    acumulado: dict[str, Decimal] = {}
    for r in registros:
        acumulado[r.codigo_giro] = acumulado.get(r.codigo_giro, Decimal(0)) + volumen_pen(r)
    return acumulado


def meses_con_datos(registros: list[RegistroTx]) -> int:
    return len({r.periodo for r in registros})


def resumen_por_giro(registros: list[RegistroTx], periodos: tuple[str, ...]) -> list[dict[str, object]]:
    """Resumen serializable por giro en la ventana (sin datos personales)."""
    filtrados = en_ventana(registros, periodos)
    vols = volumen_por_giro(filtrados)
    salida = []
    for giro, total in sorted(vols.items(), key=lambda kv: kv[1], reverse=True):
        meses = meses_con_datos([r for r in filtrados if r.codigo_giro == giro])
        salida.append({"codigo_giro": giro, "meses_con_datos": meses,
                       "volumen_total_pen": float(round(total, 2))})
    return salida
