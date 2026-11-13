"""Pruebas de la API. Se omiten si fastapi/httpx no están instalados (pip install -r requirements-dev.txt)."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.app import app  # noqa: E402

cliente = TestClient(app)
RUC = "20512345671"


def test_health():
    r = cliente.get("/health")
    assert r.status_code == 200 and r.json() == {"estado": "ok"}
    assert r.headers["X-Correlation-ID"]


def test_correlation_id_entrante_valido_se_propaga_e_invalido_se_reemplaza():
    assert cliente.get("/health", headers={"X-Correlation-ID": "abc-12345678"}).headers["X-Correlation-ID"] == "abc-12345678"
    r = cliente.get("/health", headers={"X-Correlation-ID": "malo\nlinea falsa"})
    assert r.headers["X-Correlation-ID"] != "malo\nlinea falsa"


def test_transacciones_filtra_y_pagina():
    r = cliente.get("/transacciones", params={"ruc": RUC, "limite": 4})
    cuerpo = r.json()
    assert r.status_code == 200 and cuerpo["total"] == 10 and len(cuerpo["items"]) == 4
    assert {i["ruc"] for i in cuerpo["items"]} == {RUC}


def test_resumen_cliente_sin_pii():
    r = cliente.get(f"/clientes/{RUC}/resumen")
    assert r.status_code == 200 and RUC not in r.text and r.json()["meses_con_datos"] == 6


def test_comercios_similares():
    r = cliente.get("/comercios-similares/5812")
    assert r.status_code == 200 and r.json()["comercios_comparables"] >= 2


def test_tarifario_y_politica():
    assert cliente.get("/tarifario").json()["5812"] == "2.90"
    assert cliente.get("/politica/buscar", params={"q": "RUC 10 rechazar"}).json()["resultados"]


@pytest.mark.parametrize("ruta", [
    "/transacciones?ruc=123", "/transacciones?limite=0", "/transacciones?limite=101",
    "/transacciones?periodo=2026-13", "/transacciones?codigo_giro=58",
    "/clientes/abc/resumen", f"/clientes/{RUC}/resumen?meses=13", "/comercios-similares/58",
    "/politica/buscar?q=", "/politica/buscar?q=ok&top_k=9",
])
def test_parametros_invalidos_devuelven_422(ruta):
    assert cliente.get(ruta).status_code == 422


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_api_es_de_solo_lectura(metodo):
    for ruta in ("/transacciones", "/tarifario", "/health"):
        assert getattr(cliente, metodo)(ruta).status_code == 405
