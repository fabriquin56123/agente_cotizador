"""Logging estructurado seguro: correlation_id, herramienta, latencia, resultado, error.

Nunca registra secretos ni datos personales: los valores se sanean antes de escribirse.
"""
from __future__ import annotations

import functools
import json
import logging
import os
import re
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Callable, TypeVar

NOMBRE_LOGGER = "izipay.agente"
REDACTADO = "[REDACTADO]"

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="sin-correlacion")

_CLAVES_SENSIBLES = (
    "token", "secret", "secreto", "password", "clave", "key", "authorization",
    "credential", "razon_social", "direccion", "nombre", "email", "correo", "telefono",
)
_CLAVES_RUC = ("ruc", "dni", "documento")

_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_RE_BEARER = re.compile(r"(?i)bearer\s+[\w.\-]+")
_RE_DOC = re.compile(r"(?<!\d)(\d{11}|\d{8})(?!\d)")
_RE_URL_CLAVE = re.compile(r"(?i)(sig|key|token|code)=[^&\s]+")

T = TypeVar("T")


def nuevo_correlation_id() -> str:
    return uuid.uuid4().hex[:16]


def fijar_correlation_id(valor: str | None = None) -> str:
    """Fija (o genera) el correlation_id del contexto actual y lo devuelve."""
    cid = valor or nuevo_correlation_id()
    _correlation_id.set(cid)
    return cid


def obtener_correlation_id() -> str:
    return _correlation_id.get()


def enmascarar_documento(valor: str) -> str:
    """Conserva 2 primeros y 2 últimos dígitos: 20*******71."""
    if len(valor) <= 4:
        return "*" * len(valor)
    return valor[:2] + "*" * (len(valor) - 4) + valor[-2:]


def _sanear_texto(texto: str) -> str:
    texto = _RE_EMAIL.sub(REDACTADO, texto)
    texto = _RE_BEARER.sub("Bearer " + REDACTADO, texto)
    texto = _RE_URL_CLAVE.sub(lambda m: m.group(1) + "=" + REDACTADO, texto)
    return _RE_DOC.sub(lambda m: enmascarar_documento(m.group(1)), texto)


def _es_clave(nombre: str, lista: tuple[str, ...]) -> bool:
    bajo = nombre.lower()
    return any(c in bajo for c in lista)


def sanear(valor: Any, clave: str = "", profundidad: int = 0) -> Any:
    """Redacta recursivamente claves sensibles, enmascara documentos y limpia textos."""
    if profundidad > 6:
        return REDACTADO
    if _es_clave(clave, _CLAVES_SENSIBLES):
        return REDACTADO
    if isinstance(valor, dict):
        return {str(k): sanear(v, str(k), profundidad + 1) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [sanear(v, clave, profundidad + 1) for v in valor[:20]]
    if isinstance(valor, str):
        if _es_clave(clave, _CLAVES_RUC):
            return enmascarar_documento(valor)
        return _sanear_texto(valor)[:300]
    if isinstance(valor, (int, float, bool)) or valor is None:
        return valor
    return _sanear_texto(str(valor))[:300]


class _FormatoJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "payload", {"mensaje": _sanear_texto(record.getMessage())})
        return json.dumps(payload, ensure_ascii=False, default=str)


def configurar_logging(nivel: int = logging.INFO) -> logging.Logger:
    """Configura el logger una sola vez (stderr; archivo solo si LOG_ARCHIVO)."""
    logger = logging.getLogger(NOMBRE_LOGGER)
    if logger.handlers:
        return logger
    logger.setLevel(nivel)
    logger.propagate = False
    destinos: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    ruta = os.environ.get("LOG_ARCHIVO")
    if ruta:
        destinos.append(logging.FileHandler(ruta, encoding="utf-8"))
    for h in destinos:
        h.setFormatter(_FormatoJson())
        logger.addHandler(h)
    return logger


def construir_evento(
    herramienta: str,
    latencia_ms: float,
    resultado: str,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Arma el evento ya saneado (función pura, fácil de probar)."""
    evento: dict[str, Any] = {
        "correlation_id": obtener_correlation_id(),
        "herramienta": herramienta,
        "latencia_ms": round(latencia_ms, 2),
        "resultado": resultado,
        "error": _sanear_texto(error) if error else None,
    }
    if extra:
        evento["extra"] = sanear(extra)
    return evento


def registrar_llamada(
    herramienta: str,
    latencia_ms: float,
    resultado: str,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evento = construir_evento(herramienta, latencia_ms, resultado, error, extra)
    nivel = logging.ERROR if error else logging.INFO
    configurar_logging().log(nivel, "tool", extra={"payload": evento})
    return evento


def con_registro(herramienta: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorador: mide latencia y registra resultado/error de la función envuelta."""

    def decorador(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def envoltura(*args: Any, **kwargs: Any) -> T:
            inicio = time.perf_counter()
            try:
                salida = func(*args, **kwargs)
            except Exception as exc:
                ms = (time.perf_counter() - inicio) * 1000
                registrar_llamada(herramienta, ms, "error", f"{type(exc).__name__}: {exc}")
                raise
            ms = (time.perf_counter() - inicio) * 1000
            registrar_llamada(herramienta, ms, "ok")
            return salida

        return envoltura

    return decorador
