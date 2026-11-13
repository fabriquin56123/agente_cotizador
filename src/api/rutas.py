"""Rutas de la API (SOLO LECTURA: únicamente GET). Validan parámetros antes de ejecutar."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Path, Query

from ..rag import buscar_politica
from ..repositorio import cargar_tarifario
from ..servicios import listar_transacciones, resumen_cliente, similares_por_mcc

router = APIRouter()

PATRON_DOC = r"^(\d{8}|\d{11})$"
PATRON_MCC = r"^\d{4}$"
PATRON_PERIODO = r"^\d{4}-(0[1-9]|1[0-2])$"


@router.get("/health")
def health() -> dict[str, str]:
    return {"estado": "ok"}


@router.get("/transacciones")
def transacciones(
    ruc: str | None = Query(None, pattern=PATRON_DOC, description="DNI (8) o RUC (11)"),
    periodo: str | None = Query(None, pattern=PATRON_PERIODO, description="AAAA-MM"),
    codigo_giro: str | None = Query(None, pattern=PATRON_MCC),
    limite: int = Query(50, ge=1, le=100),
    desde: int = Query(0, ge=0, le=1_000_000),
) -> dict[str, Any]:
    return listar_transacciones(ruc, periodo, codigo_giro, limite, desde)


@router.get("/clientes/{ruc}/resumen")
def resumen(
    ruc: str = Path(..., pattern=PATRON_DOC),
    meses: int = Query(6, ge=1, le=12),
) -> dict[str, Any]:
    return resumen_cliente(ruc, meses)


@router.get("/comercios-similares/{mcc}")
def comercios_similares(mcc: str = Path(..., pattern=PATRON_MCC)) -> dict[str, Any]:
    return similares_por_mcc(mcc)


@router.get("/tarifario")
def tarifario() -> dict[str, str]:
    return {mcc: f"{tasa:.2f}" for mcc, tasa in cargar_tarifario().items()}


@router.get("/politica/buscar")
def politica(
    q: str = Query(..., min_length=2, max_length=300),
    top_k: int = Query(3, ge=1, le=5),
) -> dict[str, Any]:
    return {"resultados": buscar_politica(q, top_k)}
