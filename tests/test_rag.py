import pytest

from src.rag import buscar_politica, dividir_en_fragmentos, tokenizar
from src.validacion import ErrorValidacion


def test_tokenizar_quita_acentos_stopwords_y_normaliza_genero_y_plural():
    assert tokenizar("La política de Cotización") == tokenizar("politicas cotizacion")
    assert tokenizar("mínima") == tokenizar("minimo")


def test_fragmentos_por_secciones():
    texto = "TITULO\n1. UNO\nlinea a\n2. DOS\nlinea b\nlinea c"
    frags = dividir_en_fragmentos(texto, "x.txt")
    assert [f.texto.splitlines()[0] for f in frags] == ["TITULO", "1. UNO", "2. DOS"]


def test_secciones_largas_se_parten_repitiendo_titulo():
    texto = "1. TITULO\n" + "\n".join(f"linea {i} " + "x" * 100 for i in range(20))
    frags = dividir_en_fragmentos(texto, "x.txt")
    assert len(frags) > 1 and all(f.texto.startswith("1. TITULO") for f in frags)


def test_recupera_regla_de_rechazo_por_ruc10():
    top = buscar_politica("¿qué pasa si el cliente registra su negocio con RUC 10 o DNI?", 2)
    assert top and "RUC 10" in top[0]["fragmento"]
    assert top[0]["fuente"] == "politica_pricing_izipay.txt"


def test_recupera_informe_de_zonas_premium():
    top = buscar_politica("zonas donde se pueden ofrecer tasas superiores a la competencia: Cusco, Arequipa", 3)
    assert any(r["fuente"] == "informe_rentabilidad_zonas.txt" for r in top)


def test_recupera_piso_y_techo():
    top = buscar_politica("tasa mínima y máxima permitida", 1)
    assert "1.40%" in top[0]["fragmento"]


def test_consulta_sin_coincidencias_devuelve_vacio():
    assert buscar_politica("zzzqqq", 3) == []


@pytest.mark.parametrize("consulta,k", [("", 3), ("   ", 3), ("x" * 301, 3), ("ok", 0), ("ok", 6), ("ok", True), (5, 3)])
def test_rechaza_entradas_invalidas(consulta, k):
    with pytest.raises(ErrorValidacion):
        buscar_politica(consulta, k)
