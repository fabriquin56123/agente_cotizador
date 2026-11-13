"""Prueba de extremo a extremo (determinista, sin red) con 3 solicitudes de cliente:

- SOL-001: aprobación para cuenta Interbank (0.75 × tasa más alta).
- SOL-004: **múltiples giros** (5812, 5814) → giro principal por mayor volumen, zona premium.
- SOL-006: rechazo por RUC 10.
"""
import pytest

from src.herramientas import Contexto, FuenteLocal, ejecutar_herramienta

from .conftest import FECHA_REF


@pytest.fixture()
def ctx(tmp_path):
    return Contexto(fuente=FuenteLocal(), fecha_ref=FECHA_REF, ruta_decisiones=tmp_path / "d.csv")


def flujo(sid, ctx):
    leida = ejecutar_herramienta("leer_solicitud", {"id_solicitud": sid}, ctx)["datos"]
    resumen = ejecutar_herramienta("consultar_transacciones_cliente", {"ruc": leida["ruc"]}, ctx)["datos"]
    decision = ejecutar_herramienta("evaluar_solicitud", {"id_solicitud": sid}, ctx)["datos"]
    return leida, resumen, decision


def test_sol_001_interbank_aprobada(ctx):
    leida, resumen, dec = flujo("SOL-001", ctx)
    assert leida["banco_afiliado"] == "INTERBANK" and resumen["meses_con_datos"] == 6
    assert (dec["flag_decision"], dec["giro_principal"], dec["tasa_final_pct"]) == ("APRUEBA", "5411", "2.25")
    assert dec["tasa_referencia_competencia_pct"] == "3.00"  # la más alta de BBVA 2.80 / BCP 3.00


def test_sol_004_multigiro_giro_principal_es_el_de_mayor_volumen(ctx):
    leida, resumen, dec = flujo("SOL-004", ctx)
    assert leida["codigos_giro"] == ["5812", "5814"]
    volumenes = {g["codigo_giro"]: g["volumen_total_pen"] for g in resumen["giros"]}
    assert volumenes["5814"] > volumenes["5812"] and volumenes["5814"] < 3 * volumenes["5812"]
    assert dec["giro_principal"] == "5814" and dec["zona_premium"] is True
    assert (dec["flag_decision"], dec["tasa_final_pct"]) == ("APRUEBA", "2.80")


def test_sol_006_ruc10_rechazada(ctx):
    leida, _, dec = flujo("SOL-006", ctx)
    assert leida["ruc"].startswith("10")
    assert (dec["flag_decision"], dec["motivo"], dec["tasa_final_pct"]) == ("RECHAZA", "RUC10_NO_PERMITIDO", None)


def test_guardado_de_las_3_requiere_confirmacion(ctx):
    for sid in ("SOL-001", "SOL-004", "SOL-006"):
        assert ejecutar_herramienta("guardar_decision", {"id_solicitud": sid}, ctx)["error"] == "CONFIRMACION_REQUERIDA"
    assert not ctx.ruta_decisiones.exists()
    for sid in ("SOL-001", "SOL-004", "SOL-006"):
        assert ejecutar_herramienta("guardar_decision", {"id_solicitud": sid}, ctx, confirmador=lambda n, s: True)["ok"]
    assert len(ctx.ruta_decisiones.read_text(encoding="utf-8").strip().splitlines()) == 4
