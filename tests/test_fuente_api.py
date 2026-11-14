"""El agente obtiene las transacciones SOLO por la API (paginando); no lee el CSV.

`requests.get` se reemplaza por una API falsa que responde con la misma lógica del servidor
(`src/servicios.py`) y serializa a JSON, para comprobar paginación y equivalencia de decisiones.
"""
import ast
import json
import math
import re
from decimal import Decimal
from pathlib import Path

import pytest
import requests

from src import herramientas
from src.herramientas import Contexto, FuenteApi, ejecutar_herramienta, fuente_por_defecto
from src.repositorio import cargar_tarifario, cargar_transacciones
from src.servicios import listar_transacciones, resumen_cliente, similares_por_mcc

from .conftest import FECHA_REF, FuenteDePrueba

BASE = "http://api.test"
IDS = [f"SOL-{n:03d}" for n in range(1, 16)]


class RespuestaFalsa:
    def __init__(self, cuerpo):
        self._cuerpo = json.loads(json.dumps(cuerpo))  # ida y vuelta por JSON, como en la red

    def raise_for_status(self):
        return None

    def json(self):
        return self._cuerpo


@pytest.fixture()
def llamadas(monkeypatch):
    registro = []

    def falso_get(url, params=None, timeout=None):
        ruta = url.removeprefix(BASE)
        parametros = dict(params or {})
        registro.append((ruta, parametros))
        if ruta == "/transacciones":
            return RespuestaFalsa(listar_transacciones(None, None, None, parametros["limite"], parametros["desde"]))
        if ruta == "/tarifario":
            return RespuestaFalsa({m: f"{t:.2f}" for m, t in cargar_tarifario().items()})
        coincide = re.fullmatch(r"/clientes/(\d+)/resumen", ruta)
        if coincide:
            return RespuestaFalsa(resumen_cliente(coincide.group(1), parametros["meses"]))
        if ruta.startswith("/comercios-similares/"):
            return RespuestaFalsa(similares_por_mcc(ruta.rsplit("/", 1)[1]))
        raise AssertionError(f"ruta inesperada: {ruta}")

    monkeypatch.setattr(requests, "get", falso_get)
    return registro


def contexto(fuente, tmp_path):
    return Contexto(fuente=fuente, fecha_ref=FECHA_REF, ruta_decisiones=tmp_path / "d.csv")


def test_recorre_todas_las_paginas_y_reconstruye_las_filas(llamadas):
    registros = FuenteApi(BASE).transacciones()
    assert registros == cargar_transacciones()
    paginas = [p for ruta, p in llamadas if ruta == "/transacciones"]
    assert len(paginas) == math.ceil(len(registros) / 100)
    assert [p["desde"] for p in paginas] == [0, 100, 200][: len(paginas)]
    assert all(p["limite"] == 100 for p in paginas)


def test_tarifario_por_api(llamadas):
    assert FuenteApi(BASE).tarifario() == cargar_tarifario()


@pytest.mark.parametrize("id_solicitud", IDS)
def test_evaluar_por_api_da_la_misma_decision_que_con_los_datos_locales(llamadas, tmp_path, id_solicitud):
    por_api = ejecutar_herramienta("evaluar_solicitud", {"id_solicitud": id_solicitud},
                                   contexto(FuenteApi(BASE), tmp_path))
    directa = ejecutar_herramienta("evaluar_solicitud", {"id_solicitud": id_solicitud},
                                   contexto(FuenteDePrueba(), tmp_path))
    assert por_api["ok"] and por_api == directa


def test_consultas_de_las_tools_usan_las_rutas_de_la_api(llamadas, tmp_path):
    ctx = contexto(FuenteApi(BASE), tmp_path)
    assert ejecutar_herramienta("consultar_transacciones_cliente", {"ruc": "20512345671"}, ctx)["ok"]
    assert ejecutar_herramienta("consultar_comercios_similares", {"mcc": "5812"}, ctx)["ok"]
    assert [r for r, _ in llamadas] == ["/clientes/20512345671/resumen", "/comercios-similares/5812"]


def test_el_agente_no_importa_ni_lee_el_csv_directamente():
    arbol = ast.parse(Path(herramientas.__file__).read_text(encoding="utf-8"))
    modulos = {n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and n.module}
    assert not modulos & {"repositorio", "servicios"}  # imports relativos: `from .repositorio import …`
    assert not hasattr(herramientas, "cargar_transacciones") and not hasattr(herramientas, "cargar_tarifario")


def test_evaluar_usa_la_fuente_del_contexto_y_no_el_csv(tmp_path):
    class FuenteVacia(FuenteDePrueba):
        def transacciones(self):
            return ()

    con_csv = ejecutar_herramienta("evaluar_solicitud", {"id_solicitud": "SOL-008"}, contexto(FuenteDePrueba(), tmp_path))
    sin_datos = ejecutar_herramienta("evaluar_solicitud", {"id_solicitud": "SOL-008"}, contexto(FuenteVacia(), tmp_path))
    assert con_csv["datos"]["motivo"] == "CARTERA_SIN_TRANSACCIONES_6M"
    assert sin_datos["datos"]["motivo"] != "CARTERA_SIN_TRANSACCIONES_6M"


def test_sin_api_base_url_falla_con_mensaje_claro(monkeypatch):
    monkeypatch.delenv("API_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="API_BASE_URL"):
        fuente_por_defecto()


def test_con_api_base_url_usa_la_api(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", BASE + "/")
    fuente = fuente_por_defecto()
    assert isinstance(fuente, FuenteApi) and fuente.base_url == BASE


@pytest.mark.parametrize("url", ["ftp://x", "api.test", "file:///etc/passwd"])
def test_rechaza_urls_que_no_son_http(url):
    with pytest.raises(ValueError):
        FuenteApi(url)


def test_tope_de_paginas_evita_bucle_infinito(monkeypatch):
    fila = listar_transacciones(limite=1)["items"][0]
    monkeypatch.setattr(requests, "get", lambda *a, **k: RespuestaFalsa({"total": 10**9, "items": [fila]}))
    monkeypatch.setattr(herramientas, "MAX_PAGINAS", 5)
    with pytest.raises(RuntimeError, match="páginas"):
        FuenteApi(BASE).transacciones()


def test_api_caida_devuelve_error_controlado_y_no_rompe_la_tool(monkeypatch, tmp_path):
    def caida(*a, **k):
        raise requests.ConnectionError("no se pudo conectar a http://api.test con RUC 20512345671")

    monkeypatch.setattr(requests, "get", caida)
    r = ejecutar_herramienta("evaluar_solicitud", {"id_solicitud": "SOL-001"}, contexto(FuenteApi(BASE), tmp_path))
    assert r == {"ok": False, "error": "ERROR_INTERNO", "detalle": "ConnectionError"}


def test_respuesta_numerica_exacta_en_ida_y_vuelta_json():
    fila = listar_transacciones(limite=1)["items"][0]
    reconstruida = herramientas.RegistroTx.desde_dict(json.loads(json.dumps(fila)))
    assert reconstruida == cargar_transacciones()[0] and isinstance(reconstruida.vol_bbva, Decimal)
