import json
import logging

import pytest

from src import logging_seguro as ls
from src.herramientas import Contexto, FuenteLocal, ejecutar_herramienta

from .conftest import FECHA_REF


class Captura(logging.Handler):
    def __init__(self):
        super().__init__()
        self.eventos = []

    def emit(self, record):
        self.eventos.append(record.payload)


@pytest.fixture()
def captura():
    h = Captura()
    logger = ls.configurar_logging()
    logger.addHandler(h)
    yield h
    logger.removeHandler(h)


def test_enmascara_documento():
    assert ls.enmascarar_documento("20512345671") == "20*******71"
    assert ls.enmascarar_documento("45871236") == "45****36"


def test_sanear_redacta_secretos_y_pii():
    sucio = {"token": "abc", "Authorization": "Bearer xyz", "razon_social": "Mi Empresa SAC",
             "direccion": "Av. X 1", "ruc": "20512345671", "nota": "mail a ana@correo.com ruc 20512345671",
             "anidado": {"api_key": "123", "ok": 5}}
    limpio = json.dumps(ls.sanear(sucio), ensure_ascii=False)
    for secreto in ("abc", "xyz", "Mi Empresa", "Av. X", "ana@correo.com", "20512345671", "123"):
        assert secreto not in limpio
    assert "20*******71" in limpio


def test_evento_tiene_campos_obligatorios():
    cid = ls.fijar_correlation_id("cid-prueba-1234")
    ev = ls.construir_evento("mi_tool", 12.3456, "ok")
    assert ev == {"correlation_id": cid, "herramienta": "mi_tool", "latencia_ms": 12.35,
                  "resultado": "ok", "error": None}


def test_error_se_sanea():
    ev = ls.construir_evento("t", 1, "error", "falló con RUC 20512345671")
    assert "20512345671" not in ev["error"]


def test_decorador_registra_error_y_relanza(captura):
    @ls.con_registro("explota")
    def f():
        raise ValueError("RUC 20512345671 inválido")

    with pytest.raises(ValueError):
        f()
    ev = captura.eventos[-1]
    assert ev["resultado"] == "error" and "20512345671" not in json.dumps(ev)


def test_tool_registra_correlation_id_latencia_resultado_sin_pii(captura):
    ctx = Contexto(fuente=FuenteLocal(), fecha_ref=FECHA_REF)
    ejecutar_herramienta("consultar_transacciones_cliente", {"ruc": "20512345671", "meses": 6},
                         ctx, correlation_id="corr-123456789")
    ev = captura.eventos[-1]
    assert ev["correlation_id"] == "corr-123456789"
    assert ev["herramienta"] == "consultar_transacciones_cliente"
    assert ev["resultado"] == "ok" and ev["latencia_ms"] >= 0 and ev["error"] is None
    assert "20512345671" not in json.dumps(ev) and "Pacífico" not in json.dumps(ev)


def test_error_de_validacion_se_registra_sin_el_valor(captura):
    ctx = Contexto(fuente=FuenteLocal(), fecha_ref=FECHA_REF)
    ejecutar_herramienta("consultar_transacciones_cliente", {"ruc": "123456789012"}, ctx)
    ev = captura.eventos[-1]
    assert ev["resultado"] == "error" and "VALIDACION" in ev["error"]
    assert "123456789012" not in json.dumps(ev)
