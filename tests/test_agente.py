import json
from types import SimpleNamespace

import pytest

from src.agente import ejecutar_turno, parsear_argumentos
from src.crear_agente import construir_plan, main as crear_main
from src.herramientas import Contexto, FuenteLocal

from .conftest import FECHA_REF


def llamada(nombre, args, call_id="c1"):
    return SimpleNamespace(type="function_call", name=nombre, arguments=json.dumps(args), call_id=call_id)


def respuesta(*items, texto=""):
    return SimpleNamespace(output=list(items), output_text=texto)


class RespuestasFalsas:
    """Simula `openai.responses`: devuelve respuestas en orden y guarda lo enviado."""

    def __init__(self, *respuestas):
        self.pendientes, self.enviados = list(respuestas), []

    def create(self, **kwargs):
        self.enviados.append(kwargs)
        return self.pendientes.pop(0)


@pytest.fixture()
def ctx(tmp_path):
    return Contexto(fuente=FuenteLocal(), fecha_ref=FECHA_REF, ruta_decisiones=tmp_path / "d.csv")


def test_turno_ejecuta_tool_y_devuelve_texto_final(ctx):
    r = RespuestasFalsas(respuesta(llamada("evaluar_solicitud", {"id_solicitud": "SOL-001"})),
                         respuesta(texto="Aprobada a 2.25%"))
    assert ejecutar_turno(r, "conv-1", "evalúa SOL-001", ctx, None) == "Aprobada a 2.25%"
    salida = r.enviados[1]["input"][0]
    assert salida["type"] == "function_call_output" and salida["call_id"] == "c1"
    assert json.loads(salida["output"])["datos"]["tasa_final_pct"] == "2.25"
    assert r.enviados[1]["conversation"] == "conv-1"


def test_escritura_pedida_por_el_modelo_sin_confirmacion_queda_bloqueada(ctx):
    r = RespuestasFalsas(respuesta(llamada("guardar_decision", {"id_solicitud": "SOL-001"})),
                         respuesta(texto="No se guardó"))
    ejecutar_turno(r, "conv-1", "guarda", ctx, confirmador=lambda n, s: False)
    assert json.loads(r.enviados[1]["input"][0]["output"])["error"] == "CONFIRMACION_REQUERIDA"
    assert not ctx.ruta_decisiones.exists()


def test_argumentos_json_invalidos_no_rompen_el_turno(ctx):
    mala = SimpleNamespace(type="function_call", name="evaluar_solicitud", arguments="{no es json", call_id="c9")
    r = RespuestasFalsas(respuesta(mala), respuesta(texto="ok"))
    assert ejecutar_turno(r, "c", "x", ctx, None) == "ok"
    assert json.loads(r.enviados[1]["input"][0]["output"])["error"] == "ARGUMENTOS_INVALIDOS"


def test_limite_de_rondas_de_tools(ctx):
    infinita = [respuesta(llamada("buscar_politica", {"consulta": "tasa"})) for _ in range(20)]
    with pytest.raises(RuntimeError):
        ejecutar_turno(RespuestasFalsas(*infinita), "c", "x", ctx, None)


def test_parsear_argumentos():
    assert parsear_argumentos('{"a": 1}') == {"a": 1}
    assert parsear_argumentos("") == {}
    assert parsear_argumentos("{x") is None


# ---------- crear_agente: dry-run por defecto ----------
def test_dry_run_no_toca_la_nube_ni_imprime_endpoint(monkeypatch, capsys):
    monkeypatch.setattr("src.crear_agente.cargar_entorno", lambda: None)
    monkeypatch.setenv("PROJECT_ENDPOINT", "https://secreto.example/api/projects/p")
    monkeypatch.setenv("AGENT_NAME", "agente-demo")
    monkeypatch.setenv("MODEL_DEPLOYMENT_NAME", "modelo-demo")

    def prohibido(*a, **k):
        raise AssertionError("no debe crear nada en dry-run")

    monkeypatch.setattr("src.crear_agente.crear_en_foundry", prohibido)
    assert crear_main([]) == 0
    salida = capsys.readouterr().out
    assert "agente-demo" in salida and "guardar_decision" in salida and "secreto.example" not in salida


def test_apply_sin_confirmacion_no_crea(monkeypatch):
    monkeypatch.setattr("src.crear_agente.cargar_entorno", lambda: None)
    monkeypatch.setattr("src.config.cargar_entorno", lambda: None)
    for k, v in {"PROJECT_ENDPOINT": "https://x", "AGENT_NAME": "ag", "MODEL_DEPLOYMENT_NAME": "m"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr("builtins.input", lambda _: "otro-nombre")
    monkeypatch.setattr("src.crear_agente.crear_en_foundry", lambda c: (_ for _ in ()).throw(AssertionError()))
    assert crear_main(["--apply"]) == 1


def test_plan_reporta_variables_faltantes(monkeypatch):
    monkeypatch.setattr("src.crear_agente.cargar_entorno", lambda: None)
    for k in ("PROJECT_ENDPOINT", "AGENT_NAME", "MODEL_DEPLOYMENT_NAME"):
        monkeypatch.delenv(k, raising=False)
    assert set(construir_plan()["variables_faltantes"]) == {"PROJECT_ENDPOINT", "MODEL_DEPLOYMENT_NAME", "AGENT_NAME"}
