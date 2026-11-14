"""Modelos de datos y parámetros de política (sin lógica de I/O)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

RECHAZA = "RECHAZA"
EVALUA_EXPERTO = "EVALUA_EXPERTO"
APRUEBA = "APRUEBA"
FLAGS_VALIDOS = (RECHAZA, EVALUA_EXPERTO, APRUEBA)


@dataclass(frozen=True)
class ParametrosPolitica:
    """Parámetros numéricos de la política (espejo de data/politica_pricing_izipay.txt)."""

    tasa_minima: Decimal = Decimal("1.40")
    tasa_maxima: Decimal = Decimal("5.00")
    factor_interbank: Decimal = Decimal("0.75")
    ratio_giro_dominante: Decimal = Decimal("3")
    meses_ventana: int = 6
    tolerancia_pp: Decimal = Decimal("0.30")
    tolerancia_premium_extra_pp: Decimal = Decimal("0.30")
    prima_zona_premium_pp: Decimal = Decimal("0.20")


@dataclass(frozen=True)
class RegistroTx:
    """Una fila de la base transaccional."""

    id_transaccion: str
    id_cliente: str
    ruc: str
    razon_social: str
    periodo: str
    codigo_giro: str
    moneda: str
    vol_bbva: Decimal
    vol_interbank: Decimal
    vol_bcp: Decimal

    @property
    def volumen_total(self) -> Decimal:
        return self.vol_bbva + self.vol_interbank + self.vol_bcp

    @classmethod
    def desde_dict(cls, d: dict[str, Any]) -> "RegistroTx":
        """Reconstruye un registro desde el JSON de GET /transacciones."""
        return cls(
            id_transaccion=str(d["id_transaccion"]), id_cliente=str(d["id_cliente"]),
            ruc=str(d["ruc"]), razon_social=str(d["razon_social"]), periodo=str(d["periodo"]),
            codigo_giro=str(d["codigo_giro"]), moneda=str(d["moneda"]),
            vol_bbva=Decimal(str(d["volumen_bbva"])), vol_interbank=Decimal(str(d["volumen_interbank"])),
            vol_bcp=Decimal(str(d["volumen_bcp"])),
        )


@dataclass(frozen=True)
class Solicitud:
    """Datos de una solicitud de cotización de un cliente."""

    id_solicitud: str
    ruc: str
    razon_social: str
    codigos_giro: tuple[str, ...]
    nombres_giro: tuple[str, ...]
    banco_afiliado: str
    moneda_cuenta: str
    departamento: str
    provincia: str
    distrito: str
    direccion: str
    bancos_competencia: tuple[str, ...]
    tasas_competencia: tuple[Decimal, ...]


@dataclass(frozen=True)
class Decision:
    """Resultado de evaluar una solicitud contra la política."""

    id_solicitud: str
    flag: str
    motivo: str
    giro_principal: str | None = None
    tasa_referencia_competencia: Decimal | None = None
    tasa_calculada: Decimal | None = None
    tasa_final: Decimal | None = None
    zona_premium: bool = False
    meses_historial: int = 0
