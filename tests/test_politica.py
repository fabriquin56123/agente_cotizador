from decimal import Decimal

import pytest

from src.modelos import APRUEBA, EVALUA_EXPERTO, RECHAZA, ParametrosPolitica
from src.politica import (
    decidir_por_competencia, es_zona_premium, evaluar_solicitud, resolver_giro_principal,
)

from .conftest import FECHA_REF, PERIODOS, TARIFARIO, historial, reg, solicitud

P = ParametrosPolitica()
RUC = "20111111111"


def evaluar(sol, regs):
    return evaluar_solicitud(sol, regs, TARIFARIO, FECHA_REF)


# ---------- casos de rechazo ----------
@pytest.mark.parametrize("ruc,motivo", [
    ("45871236", "DNI_NO_PERMITIDO"),
    ("10456789012", "RUC10_NO_PERMITIDO"),
    ("30456789012", "DOCUMENTO_NO_VALIDO"),
])
def test_rechaza_dni_ruc10_y_documento_no_empresa(ruc, motivo):
    dec = evaluar(solicitud(ruc=ruc), [])
    assert (dec.flag, dec.motivo, dec.tasa_final) == (RECHAZA, motivo, None)


def test_rechaza_cartera_sin_transacciones_en_6_meses():
    antiguos = historial(RUC, ("2025-08", "2025-09", "2026-03"))
    dec = evaluar(solicitud(ruc=RUC), antiguos)
    assert (dec.flag, dec.motivo) == (RECHAZA, "CARTERA_SIN_TRANSACCIONES_6M")


def test_rechaza_giro_secundario_3_veces_mayor():
    regs = historial(RUC, PERIODOS, "5651", "30000") + historial(RUC, PERIODOS, "5732", "90000")
    dec = evaluar(solicitud(ruc=RUC, codigos_giro=("5651", "5732")), regs)
    assert (dec.flag, dec.motivo) == (RECHAZA, "GIRO_SECUNDARIO_DOMINANTE")


def test_rechaza_si_principal_declarado_no_tiene_volumen_y_secundario_si():
    regs = historial(RUC, PERIODOS, "5732", "90000")
    dec = evaluar(solicitud(ruc=RUC, codigos_giro=("5651", "5732")), regs)
    assert dec.motivo == "GIRO_SECUNDARIO_DOMINANTE"


def test_rechaza_sin_margen_fuera_de_zona_premium():
    dec = evaluar(solicitud(tasas_competencia=(Decimal("2.40"),)), [])   # 2.90 vs 2.40 = +0.50
    assert (dec.flag, dec.motivo) == (RECHAZA, "SIN_MARGEN_SOBRE_COMPETENCIA")


# ---------- giro principal ----------
def test_multigiro_normal_usa_el_de_mayor_volumen():
    regs = historial(RUC, PERIODOS, "5812", "90000") + historial(RUC, PERIODOS, "5814", "150000")
    giro, motivo = resolver_giro_principal(("5812", "5814"), regs, P)
    assert (giro, motivo) == ("5814", None)


def test_multigiro_sin_datos_usa_el_primero_declarado():
    assert resolver_giro_principal(("5812", "5814"), [], P) == ("5812", None)


def test_un_solo_giro():
    assert resolver_giro_principal(("5411",), [], P) == ("5411", None)


# ---------- historial < 6 meses ----------
def test_cliente_nuevo_usa_comercios_similares():
    otros = historial("20222222222", PERIODOS, "5812", "100000")          # similar: 2.90-0.10 = 2.80
    nuevo = historial(RUC, PERIODOS[-2:], "5812", "5000000")              # 2 meses (volumen enorme, no debe usarse)
    dec = evaluar(solicitud(ruc=RUC, tasas_competencia=(Decimal("3.20"),)), otros + nuevo)
    assert (dec.flag, dec.tasa_final, dec.meses_historial) == (APRUEBA, Decimal("2.80"), 2)


def test_cliente_ausente_de_la_base_es_nuevo_y_no_cartera_inactiva():
    dec = evaluar(solicitud(ruc=RUC), [])
    assert dec.flag == APRUEBA and dec.meses_historial == 0
    assert dec.tasa_final == Decimal("2.90")  # tarifario base: no hay similares


def test_cliente_con_6_meses_usa_su_propio_volumen():
    regs = historial(RUC, PERIODOS, "5812", "300000")                     # 2.90 - 0.25
    assert evaluar(solicitud(ruc=RUC), regs).tasa_final == Decimal("2.65")


# ---------- Interbank ----------
def test_interbank_ofrece_075_de_la_tasa_mas_alta():
    sol = solicitud(banco_afiliado="INTERBANK", tasas_competencia=(Decimal("2.80"), Decimal("3.00")))
    dec = evaluar(sol, [])
    assert (dec.flag, dec.tasa_final) == (APRUEBA, Decimal("2.25"))


def test_interbank_bajo_piso_sube_a_1_40_y_va_a_experto_si_supera_competencia():
    sol = solicitud(banco_afiliado="INTERBANK", tasas_competencia=(Decimal("1.30"),))
    dec = evaluar(sol, [])
    assert (dec.flag, dec.tasa_calculada, dec.tasa_final) == (EVALUA_EXPERTO, Decimal("1.40"), None)


def test_interbank_en_zona_premium_con_piso_se_aprueba():
    sol = solicitud(banco_afiliado="INTERBANK", distrito="San Borja", tasas_competencia=(Decimal("1.30"),))
    assert evaluar(sol, []).flag == APRUEBA


# ---------- tabla de tolerancias ----------
@pytest.mark.parametrize("premium,diff,esperado", [
    (False, "-0.01", APRUEBA), (False, "0.00", EVALUA_EXPERTO), (False, "0.30", EVALUA_EXPERTO),
    (False, "0.31", RECHAZA),
    (True, "0.00", APRUEBA), (True, "0.30", APRUEBA), (True, "0.31", EVALUA_EXPERTO),
    (True, "0.60", EVALUA_EXPERTO), (True, "0.61", RECHAZA),
])
def test_tolerancias_sobre_competencia(premium, diff, esperado):
    ref = Decimal("3.00")
    flag, _ = decidir_por_competencia(ref + Decimal(diff), ref, premium, P)
    assert flag == esperado


def test_zona_premium_suma_prima_de_0_20():
    base = evaluar(solicitud(distrito="Ate"), [])
    prem = evaluar(solicitud(distrito="Miraflores"), [])
    assert prem.tasa_calculada - base.tasa_calculada == Decimal("0.20") and prem.zona_premium


# ---------- zonas ----------
@pytest.mark.parametrize("dep,prov,dist,esperado", [
    ("Lima", "Lima", "Miraflores", True), ("Lima", "Lima", "SAN ISIDRO", True),
    ("Lima", "Lima", "Barranco", True), ("Lima", "Lima", "San Borja", True),
    ("Lima", "Lima", "Surco", False), ("Lima", "Lima", "Ate", False),
    ("La Libertad", "Trujillo", "Trujillo", True), ("Arequipa", "Arequipa", "Cayma", True),
    ("Cusco", "Cusco", "Wanchaq", True), ("Piura", "Piura", "Piura", False),
    ("Cusco", "Urubamba", "Urubamba", False), ("Ica", "Ica", "Miraflores", False),
])
def test_zona_premium(dep, prov, dist, esperado):
    assert es_zona_premium(dep, prov, dist) is esperado


# ---------- casos borde ----------
def test_sin_tasa_de_competencia_va_a_experto():
    dec = evaluar(solicitud(bancos_competencia=(), tasas_competencia=()), [])
    assert (dec.flag, dec.motivo) == (EVALUA_EXPERTO, "SIN_REFERENCIA_COMPETENCIA")
    dec = evaluar(solicitud(banco_afiliado="INTERBANK", bancos_competencia=(), tasas_competencia=()), [])
    assert dec.motivo == "SIN_REFERENCIA_COMPETENCIA"


def test_mcc_sin_tarifa_va_a_experto():
    dec = evaluar(solicitud(codigos_giro=("9999",)), [])
    assert (dec.flag, dec.motivo) == (EVALUA_EXPERTO, "MCC_SIN_TARIFA")


def test_tasa_final_solo_cuando_se_aprueba():
    dec = evaluar(solicitud(tasas_competencia=(Decimal("2.80"),)), [])   # +0.10 fuera de premium
    assert dec.flag == EVALUA_EXPERTO and dec.tasa_final is None and dec.tasa_calculada == Decimal("2.90")


def test_usa_volumen_en_dolares_convertido():
    regs = [reg(RUC, p, "5812", "60000", "USD") for p in PERIODOS]       # 60k USD = 225k PEN
    assert evaluar(solicitud(ruc=RUC), regs).tasa_final == Decimal("2.65")
