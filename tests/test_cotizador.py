from decimal import Decimal

import pytest

from src.cotizador import (
    aplicar_limites, descuento_por_volumen, redondear, tasa_interbank,
    tasa_referencia_similares, tasa_tarifaria,
)
from src.modelos import ParametrosPolitica

from .conftest import PERIODOS, TARIFARIO, historial

P = ParametrosPolitica()


@pytest.mark.parametrize("vol,desc", [
    ("0", "0.00"), ("79999.99", "0.00"), ("80000", "0.10"), ("200000", "0.25"),
    ("499999", "0.25"), ("500000", "0.40"), ("9000000", "0.40"),
])
def test_descuento_por_volumen(vol, desc):
    assert descuento_por_volumen(Decimal(vol)) == Decimal(desc)


@pytest.mark.parametrize("entrada,esperado", [
    ("0.50", "1.40"), ("1.40", "1.40"), ("3.456", "3.46"), ("5.00", "5.00"), ("7.25", "5.00"),
])
def test_limites_1_40_a_5_00(entrada, esperado):
    assert aplicar_limites(Decimal(entrada), P) == Decimal(esperado)


def test_redondeo_half_up():
    assert redondear(Decimal("2.225")) == Decimal("2.23")


def test_tasa_interbank_es_075_de_la_mas_alta():
    assert tasa_interbank((Decimal("2.80"), Decimal("3.00")), P) == Decimal("2.25")


def test_tasa_interbank_respeta_piso_y_techo():
    assert tasa_interbank((Decimal("1.30"),), P) == Decimal("1.40")   # 0.975 → piso
    assert tasa_interbank((Decimal("8.00"),), P) == Decimal("5.00")   # 6.00 → techo


def test_tasa_interbank_sin_competencia():
    assert tasa_interbank((), P) is None


def test_tasa_tarifaria_y_mcc_desconocido():
    assert tasa_tarifaria("5812", TARIFARIO, Decimal("250000")) == Decimal("2.65")
    assert tasa_tarifaria("9999", TARIFARIO, Decimal("250000")) is None


def test_similares_promedia_comercios_con_6_meses():
    todos = historial("20111111111", PERIODOS, "5812", "100000")      # 2.90 - 0.10
    todos += historial("20222222222", PERIODOS, "5812", "300000")     # 2.90 - 0.25
    assert tasa_referencia_similares("5812", todos, TARIFARIO, PERIODOS) == Decimal("2.73")


def test_similares_ignora_comercios_incompletos_y_al_propio_cliente():
    todos = historial("20111111111", PERIODOS[:3], "5812", "900000")   # 3 meses: no cuenta
    todos += historial("20222222222", PERIODOS, "5812", "100000")
    assert tasa_referencia_similares("5812", todos, TARIFARIO, PERIODOS, "20222222222") == Decimal("2.90")


def test_similares_ignora_personas_naturales():
    todos = historial("10222222222", PERIODOS, "5812", "900000")
    assert tasa_referencia_similares("5812", todos, TARIFARIO, PERIODOS) == Decimal("2.90")
