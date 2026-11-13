from decimal import Decimal

import pytest

from src import validacion as v


@pytest.mark.parametrize("valor", ["20123456789", "45871236"])
def test_documento_valido(valor):
    assert v.validar_documento(valor) == valor


@pytest.mark.parametrize("valor", ["", "1234567", "123456789012", "2012345678a", 20123456789, None, "2012 456789"])
def test_documento_invalido(valor):
    with pytest.raises(v.ErrorValidacion):
        v.validar_documento(valor)


def test_error_no_expone_el_valor():
    with pytest.raises(v.ErrorValidacion) as exc:
        v.validar_documento("99999")
    assert "99999" not in str(exc.value)


@pytest.mark.parametrize("valor", ["123", "12345", "abcd", "12 4", None, 5812])
def test_mcc_invalido(valor):
    with pytest.raises(v.ErrorValidacion):
        v.validar_mcc(valor)


def test_lista_mcc_limites():
    assert v.validar_lista_mcc(["5812", "5814"]) == ("5812", "5814")
    with pytest.raises(v.ErrorValidacion):
        v.validar_lista_mcc([])
    with pytest.raises(v.ErrorValidacion):
        v.validar_lista_mcc(["5812"] * 11)


@pytest.mark.parametrize("valor", ["2026-13", "2026-00", "26-01", "1999-05", "2026/05"])
def test_periodo_invalido(valor):
    with pytest.raises(v.ErrorValidacion):
        v.validar_periodo(valor)


def test_periodo_valido():
    assert v.validar_periodo("2026-10") == "2026-10"


def test_listas_permitidas():
    assert v.validar_banco("interbank") == "INTERBANK"
    assert v.validar_moneda("usd") == "USD"
    for malo in ("EUR", "banco falso", "", None):
        with pytest.raises(v.ErrorValidacion):
            v.validar_moneda(malo)
    with pytest.raises(v.ErrorValidacion):
        v.validar_banco("CITIBANK")


def test_enteros_rango_y_tipo():
    assert v.validar_entero(6, "meses", 1, 12) == 6
    for malo in (0, 13, True, "6", 6.0):
        with pytest.raises(v.ErrorValidacion):
            v.validar_entero(malo, "meses", 1, 12)


def test_texto_longitud():
    with pytest.raises(v.ErrorValidacion):
        v.validar_texto("x" * 301, "consulta", 300)
    with pytest.raises(v.ErrorValidacion):
        v.validar_texto("   ", "consulta")


def test_tasas_rango_y_formato():
    assert v.convertir_tasa("3.2%") == Decimal("3.2")
    for malo in (0, 21, "abc", True, None):
        with pytest.raises(v.ErrorValidacion):
            v.convertir_tasa(malo)


def test_id_solicitud():
    assert v.validar_id_solicitud("sol-004") == "SOL-004"
    for malo in ("../etc/passwd", "SOL-4", "SOL-0041", "004"):
        with pytest.raises(v.ErrorValidacion):
            v.validar_id_solicitud(malo)


@pytest.mark.parametrize("ruc,esperado", [
    ("45871236", v.DOC_DNI), ("10456789012", v.DOC_RUC10),
    ("20512345671", v.DOC_EMPRESA), ("30512345671", v.DOC_OTRO),
])
def test_tipo_documento(ruc, esperado):
    assert v.tipo_documento(ruc) == esperado
