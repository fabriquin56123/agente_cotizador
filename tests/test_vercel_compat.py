"""Prueba de compatibilidad con Vercel (sin desplegar nada).

Verifica lo comprobable en local: entrypoint importable, solo GET, sin escrituras a disco,
datos incluidos en el bundle y sintaxis compatible con 3.11 (Vercel ejecuta 3.12+).
"""
import ast
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def test_vercel_json_incluye_datos_y_reescribe_a_la_funcion():
    cfg = json.loads((RAIZ / "vercel.json").read_text(encoding="utf-8"))
    assert cfg["functions"]["api/index.py"]["includeFiles"] == "data/**"
    assert cfg["rewrites"][0]["destination"] == "/api/index"


def test_codigo_fuente_no_escribe_en_disco_en_la_api():
    """El sistema de archivos de Vercel es de solo lectura: la API no debe abrir archivos para escribir."""
    for archivo in (RAIZ / "src" / "api").glob("*.py"):
        assert 'open(' not in archivo.read_text(encoding="utf-8")
    assert "LOG_ARCHIVO" not in (RAIZ / "src" / "api" / "app.py").read_text(encoding="utf-8")


def test_sintaxis_compatible_con_python_311():
    for archivo in list((RAIZ / "src").rglob("*.py")) + list((RAIZ / "api").glob("*.py")):
        ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo), feature_version=(3, 11))


def test_entrypoint_expone_app_y_solo_get():
    pytest.importorskip("fastapi")
    from api.index import app

    metodos = {m for ruta in app.routes for m in getattr(ruta, "methods", set()) or set()}
    assert metodos <= {"GET", "HEAD", "OPTIONS"}


def test_requirements_sin_dependencias_de_azure_en_la_api():
    """La API solo importa fastapi + stdlib; Azure queda del lado del agente (no se empaqueta en la función)."""
    for archivo in (RAIZ / "src" / "api").glob("*.py"):
        assert "azure" not in archivo.read_text(encoding="utf-8")
