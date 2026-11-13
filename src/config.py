"""Configuración central: rutas, constantes de negocio y lectura de entorno.

Nunca se imprimen ni registran los valores de las variables de entorno.
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_DATOS = RAIZ / "data"
DIR_SOLICITUDES = DIR_DATOS / "solicitudes"
DIR_SALIDAS = DIR_DATOS / "salidas"

ARCHIVO_TRANSACCIONES = DIR_DATOS / "transacciones_clientes.csv"
ARCHIVO_TARIFARIO = DIR_DATOS / "tarifario_mcc.csv"
ARCHIVO_CONSOLIDADO = DIR_DATOS / "solicitudes_consolidado.csv"
ARCHIVO_RESULTADOS = DIR_DATOS / "resultados_cotizacion.csv"
ARCHIVO_DECISIONES_AGENTE = DIR_SALIDAS / "decisiones_agente.csv"

# Fecha de referencia fija para que los datos de prueba sean reproducibles.
# Se puede sobrescribir con la variable de entorno FECHA_REFERENCIA (AAAA-MM-DD).
FECHA_REFERENCIA_DEFECTO = date(2026, 11, 12)

TIPO_CAMBIO_USD = Decimal("3.75")
BANCOS_PERMITIDOS = ("INTERBANK", "BBVA", "BCP", "SCOTIABANK")
MONEDAS_PERMITIDAS = ("PEN", "USD")

VARIABLES_FOUNDRY = (
    "PROJECT_ENDPOINT",
    "MODEL_DEPLOYMENT_NAME",
    "AGENT_NAME",
)


def fecha_referencia() -> date:
    """Fecha 'hoy' del negocio; sobrescribible por entorno."""
    valor = os.environ.get("FECHA_REFERENCIA")
    if not valor:
        return FECHA_REFERENCIA_DEFECTO
    return date.fromisoformat(valor)


def cargar_entorno() -> None:
    """Carga `.env` si python-dotenv está disponible (sin imprimir nada)."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dotenv es dependencia normal
        return
    load_dotenv(RAIZ / ".env", override=False)


def variables_faltantes() -> list[str]:
    """Nombres (no valores) de variables de Foundry sin definir."""
    return [n for n in VARIABLES_FOUNDRY if not os.environ.get(n)]


def leer_config_foundry() -> dict[str, str]:
    """Devuelve la configuración de Foundry o lanza error indicando solo nombres."""
    cargar_entorno()
    faltan = variables_faltantes()
    if faltan:
        raise RuntimeError("Faltan variables de entorno: " + ", ".join(faltan))
    return {n: os.environ[n] for n in VARIABLES_FOUNDRY}
