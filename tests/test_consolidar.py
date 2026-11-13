import csv
import re
from collections import Counter
from decimal import Decimal

from src import config, generar_datos
from src.consolidar import CAMPOS_CONSOLIDADO, CAMPOS_RESULTADOS, evaluar_todas, escribir_salidas, leer_csv
from src.repositorio import cargar_tarifario
from src.solicitudes import parsear_solicitud, leer_todas

from .conftest import FECHA_REF


def test_tarifario_del_txt_coincide_con_el_csv():
    texto = (config.DIR_DATOS / "politica_pricing_izipay.txt").read_text(encoding="utf-8")
    del_txt = {m: Decimal(t) for m, t in re.findall(r"MCC (\d{4}) \| [^|]+ \| (\d+\.\d+)%", texto)}
    assert del_txt and del_txt == cargar_tarifario()


def test_parametros_de_politica_coinciden_con_el_txt():
    texto = (config.DIR_DATOS / "politica_pricing_izipay.txt").read_text(encoding="utf-8")
    for fragmento in ("1.40%", "5.00%", "0.75 veces", "3 veces", "0.30", "0.60", "0.20 puntos", "3.75"):
        assert fragmento in texto


def test_transacciones_cumplen_formato_y_cantidad():
    filas = leer_csv(config.ARCHIVO_TRANSACCIONES)
    assert list(filas[0]) == generar_datos.CAMPOS_TX
    assert len({f["id_cliente"] for f in filas}) >= 20
    assert {f["moneda"] for f in filas} == {"PEN", "USD"}
    assert len({f["id_transaccion"] for f in filas}) == len(filas)


def test_multigiro_tiene_varias_filas_por_periodo():
    filas = [f for f in leer_csv(config.ARCHIVO_TRANSACCIONES) if f["ruc"] == "20601234567"]
    por_periodo = Counter(f["periodo"] for f in filas)
    assert set(por_periodo.values()) == {2}
    assert {f["codigo_giro"] for f in filas} == {"5812", "5814"}


def test_todos_los_clientes_de_las_solicitudes_estan_en_la_base():
    rucs_base = {f["ruc"] for f in leer_csv(config.ARCHIVO_TRANSACCIONES)}
    assert {s.ruc for s in leer_todas()} <= rucs_base


def test_hay_al_menos_15_solicitudes_txt_con_campos_completos():
    sols = leer_todas()
    assert len(sols) >= 15
    assert any(len(s.codigos_giro) > 1 for s in sols)
    assert all(s.bancos_competencia and len(s.bancos_competencia) == len(s.tasas_competencia) for s in sols)


def test_consolidado_en_disco_coincide_con_la_evaluacion_actual():
    en_disco = leer_csv(config.ARCHIVO_CONSOLIDADO)
    assert list(en_disco[0]) == CAMPOS_CONSOLIDADO and len(en_disco) >= 15
    esperado = {s.id_solicitud: d for s, d in evaluar_todas(FECHA_REF)}
    for fila in en_disco:
        dec = esperado[fila["id_solicitud"]]
        assert fila["flag_decision"] == dec.flag and fila["motivo"] == dec.motivo


def test_multigiro_se_escribe_en_un_solo_campo_separado_por_coma():
    fila = next(f for f in leer_csv(config.ARCHIVO_CONSOLIDADO) if f["id_solicitud"] == "SOL-004")
    assert fila["codigos_giro"] == "5812,5814" and fila["nombres_giro"] == "Restaurantes,Comida rápida"
    assert fila["giro_principal"] == "5814"


def test_tasa_final_y_giro_solo_si_se_aprueba_y_cubre_los_tres_flags():
    filas = leer_csv(config.ARCHIVO_CONSOLIDADO)
    assert {f["flag_decision"] for f in filas} == {"RECHAZA", "EVALUA_EXPERTO", "APRUEBA"}
    for f in filas:
        assert bool(f["tasa_final_pct"]) == (f["flag_decision"] == "APRUEBA")
        if f["tasa_final_pct"]:
            assert Decimal("1.40") <= Decimal(f["tasa_final_pct"]) <= Decimal("5.00")


def test_resultados_solo_incluyen_aprobados():
    consolidado = {f["id_solicitud"]: f for f in leer_csv(config.ARCHIVO_CONSOLIDADO)}
    resultados = leer_csv(config.ARCHIVO_RESULTADOS)
    assert list(resultados[0]) == CAMPOS_RESULTADOS
    assert {r["id_solicitud"] for r in resultados} == {
        k for k, f in consolidado.items() if f["flag_decision"] == "APRUEBA"}
    assert all(r["cotiza"] == "SI" and r["tasa_final_pct"] for r in resultados)


def test_escribir_salidas_es_reproducible(tmp_path):
    pares = evaluar_todas(FECHA_REF)
    escribir_salidas(pares, tmp_path / "c.csv", tmp_path / "r.csv")
    assert (tmp_path / "c.csv").read_text(encoding="utf-8") == config.ARCHIVO_CONSOLIDADO.read_text(encoding="utf-8")
    assert (tmp_path / "r.csv").read_text(encoding="utf-8") == config.ARCHIVO_RESULTADOS.read_text(encoding="utf-8")


def test_generacion_de_datos_es_determinista(tmp_path):
    filas = generar_datos.generar_transacciones()
    generar_datos.escribir_csv(tmp_path / "t.csv", generar_datos.CAMPOS_TX, filas)
    assert (tmp_path / "t.csv").read_bytes() == config.ARCHIVO_TRANSACCIONES.read_bytes()


def test_parser_rechaza_solicitud_incompleta_o_inconsistente():
    import pytest
    from src.validacion import ErrorValidacion

    base = (config.DIR_SOLICITUDES / "SOL-001.txt").read_text(encoding="utf-8")
    with pytest.raises(ErrorValidacion):
        parsear_solicitud(base.replace("RUC: 20512345671", ""), "SOL-001")
    with pytest.raises(ErrorValidacion):  # bancos y tasas desalineados
        parsear_solicitud(base.replace("Banco(s) competidor(es): BBVA, BCP", "Banco(s) competidor(es): BBVA"), "SOL-001")
    with pytest.raises(ErrorValidacion):  # banco fuera de lista
        parsear_solicitud(base.replace("Banco afiliado: INTERBANK", "Banco afiliado: CITIBANK"), "SOL-001")
    with pytest.raises(ErrorValidacion):  # tasa fuera de rango
        parsear_solicitud(base.replace("2.80%, 3.00%", "2.80%, 99%"), "SOL-001")
