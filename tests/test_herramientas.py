import csv

import pytest

from src.herramientas import (
    HERRAMIENTAS, Contexto, definiciones_para_foundry, ejecutar_herramienta,
)

from .conftest import FECHA_REF, FuenteDePrueba


@pytest.fixture()
def ctx(tmp_path):
    return Contexto(fuente=FuenteDePrueba(), fecha_ref=FECHA_REF, ruta_decisiones=tmp_path / "salidas" / "d.csv")


def test_lectura_se_ejecuta_sin_confirmacion(ctx):
    r = ejecutar_herramienta("evaluar_solicitud", {"id_solicitud": "SOL-001"}, ctx)
    assert r["ok"] and r["datos"]["flag_decision"] == "APRUEBA" and r["datos"]["tasa_final_pct"] == "2.25"


def test_escritura_sin_confirmador_queda_bloqueada(ctx):
    r = ejecutar_herramienta("guardar_decision", {"id_solicitud": "SOL-001"}, ctx)
    assert r["ok"] is False and r["error"] == "CONFIRMACION_REQUERIDA"
    assert not ctx.ruta_decisiones.exists()


def test_escritura_con_confirmacion_negada_no_escribe(ctx):
    r = ejecutar_herramienta("guardar_decision", {"id_solicitud": "SOL-001"}, ctx, confirmador=lambda n, s: False)
    assert r["error"] == "CONFIRMACION_REQUERIDA" and not ctx.ruta_decisiones.exists()


def test_el_modelo_no_puede_autoconfirmar(ctx):
    r = ejecutar_herramienta("guardar_decision", {"id_solicitud": "SOL-001", "confirmado": True}, ctx,
                             confirmador=lambda n, s: True)
    assert r["error"] == "VALIDACION" and not ctx.ruta_decisiones.exists()


def test_escritura_confirmada_guarda_y_es_idempotente(ctx):
    vistos = []
    conf = lambda nombre, resumen: vistos.append((nombre, resumen)) or True  # noqa: E731
    for _ in range(2):
        r = ejecutar_herramienta("guardar_decision", {"id_solicitud": "SOL-004"}, ctx, confirmador=conf)
        assert r["ok"] and r["datos"]["guardado"]
    filas = list(csv.DictReader(ctx.ruta_decisiones.open(encoding="utf-8")))
    assert len(filas) == 1 and filas[0]["id_solicitud"] == "SOL-004" and filas[0]["giro_principal"] == "5814"
    assert vistos[0][0] == "guardar_decision"


def test_guardar_decision_rechazada_no_expone_pii(ctx):
    ejecutar_herramienta("guardar_decision", {"id_solicitud": "SOL-006"}, ctx, confirmador=lambda n, s: True)
    contenido = ctx.ruta_decisiones.read_text(encoding="utf-8")
    assert "RUC10_NO_PERMITIDO" in contenido and "10456789012" not in contenido


@pytest.mark.parametrize("nombre,args", [
    ("evaluar_solicitud", {"id_solicitud": "../../etc/passwd"}),
    ("evaluar_solicitud", {"id_solicitud": "SOL-999"}),
    ("evaluar_solicitud", {}),
    ("evaluar_solicitud", {"id_solicitud": "SOL-001", "extra": 1}),
    ("consultar_transacciones_cliente", {"ruc": "123"}),
    ("consultar_transacciones_cliente", {"ruc": "20512345671", "meses": 99}),
    ("consultar_transacciones_cliente", {"ruc": "20512345671", "meses": "6"}),
    ("consultar_comercios_similares", {"mcc": "58"}),
    ("buscar_politica", {"consulta": "x" * 301}),
    ("buscar_politica", {"consulta": "ok", "top_k": 50}),
    ("leer_solicitud", {"id_solicitud": 4}),
])
def test_entradas_invalidas_son_rechazadas_antes_de_ejecutar(ctx, nombre, args):
    r = ejecutar_herramienta(nombre, args, ctx)
    assert r["ok"] is False and r["error"] == "VALIDACION"


def test_herramienta_desconocida_y_argumentos_no_objeto(ctx):
    assert ejecutar_herramienta("borrar_todo", {}, ctx)["error"] == "HERRAMIENTA_DESCONOCIDA"
    assert ejecutar_herramienta("evaluar_solicitud", "SOL-001", ctx)["error"] == "ARGUMENTOS_INVALIDOS"


def test_valores_por_defecto_de_meses_y_top_k(ctx):
    assert ejecutar_herramienta("consultar_transacciones_cliente", {"ruc": "20512345671"}, ctx)["ok"]
    assert ejecutar_herramienta("buscar_politica", {"consulta": "tasa minima"}, ctx)["ok"]


def test_consultas_no_devuelven_pii(ctx):
    r = ejecutar_herramienta("consultar_transacciones_cliente", {"ruc": "20512345671"}, ctx)
    texto = str(r)
    assert "Pacífico" not in texto and "20512345671" not in texto
    assert r["datos"]["existe_en_base"] and r["datos"]["meses_con_datos"] == 6


def test_comercios_similares(ctx):
    r = ejecutar_herramienta("consultar_comercios_similares", {"mcc": "7011"}, ctx)
    assert r["ok"] and r["datos"]["comercios_comparables"] >= 2


def test_solo_una_tool_de_escritura_y_esquemas_estrictos():
    escrituras = [h.nombre for h in HERRAMIENTAS.values() if h.escritura]
    assert escrituras == ["guardar_decision"]
    for d in definiciones_para_foundry():
        p = d["parameters"]
        assert p["additionalProperties"] is False and set(p["required"]) == set(p["properties"])
