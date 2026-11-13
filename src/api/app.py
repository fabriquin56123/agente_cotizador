"""API FastAPI de solo lectura sobre la base transaccional de prueba.

Local:   uvicorn src.api.app:app --reload
Docs:    http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import re
import time
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from ..logging_seguro import fijar_correlation_id, registrar_llamada, sanear
from ..validacion import ErrorValidacion
from .rutas import router

_RE_CID = re.compile(r"^[A-Za-z0-9\-]{8,64}$")

app = FastAPI(title="Izipay Pricing - Transacciones (prueba)", version="1.0.0")
app.include_router(router)


@app.exception_handler(ErrorValidacion)
async def manejar_validacion(_: Request, exc: ErrorValidacion) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def correlation_id_entrante(valor: str | None) -> str | None:
    """Acepta el X-Correlation-ID del cliente solo si es seguro (evita inyección en logs)."""
    return valor if valor and _RE_CID.match(valor) else None


def plantilla_de_ruta(request: Request) -> str:
    """Ruta con parámetros sin sustituir (/clientes/{ruc}/resumen) para no registrar RUC."""
    ruta = request.scope.get("route")
    return str(getattr(ruta, "path", "desconocida"))


@app.middleware("http")
async def registrar_peticion(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    cid = fijar_correlation_id(correlation_id_entrante(request.headers.get("X-Correlation-ID")))
    inicio = time.perf_counter()
    try:
        respuesta = await call_next(request)
    except Exception as exc:
        ms = (time.perf_counter() - inicio) * 1000
        registrar_llamada(f"api {request.method}", ms, "error", type(exc).__name__)
        raise
    ms = (time.perf_counter() - inicio) * 1000
    herramienta = sanear(f"api {request.method} {plantilla_de_ruta(request)}")
    fallo = respuesta.status_code >= 400
    registrar_llamada(herramienta, ms, "error" if fallo else "ok",
                      f"HTTP {respuesta.status_code}" if fallo else None)
    respuesta.headers["X-Correlation-ID"] = cid
    return respuesta
