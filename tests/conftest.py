from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.modelos import RegistroTx, Solicitud
from src.repositorio import ventana_periodos

FECHA_REF = date(2026, 11, 12)
PERIODOS = ventana_periodos(FECHA_REF, 6)  # 2026-05 … 2026-10
TARIFARIO = {"5411": Decimal("2.10"), "5812": Decimal("2.90"), "5814": Decimal("2.70"),
             "5651": Decimal("3.10"), "5732": Decimal("2.60"), "7011": Decimal("3.20")}


def reg(ruc: str, periodo: str, mcc: str, total: str = "100000", moneda: str = "PEN") -> RegistroTx:
    """Registro con el total repartido en partes iguales entre los tres bancos."""
    parte = Decimal(total) / 3
    return RegistroTx(f"TX-{ruc}-{periodo}-{mcc}", "C000", ruc, "Empresa Demo SAC", periodo, mcc,
                      moneda, parte, parte, parte)


def historial(ruc: str, periodos: tuple[str, ...], mcc: str = "5812", total: str = "100000") -> list[RegistroTx]:
    return [reg(ruc, p, mcc, total) for p in periodos]


def solicitud(**cambios: object) -> Solicitud:
    base = dict(
        id_solicitud="SOL-001", ruc="20111111111", razon_social="Empresa Demo SAC",
        codigos_giro=("5812",), nombres_giro=("Restaurantes",), banco_afiliado="BBVA",
        moneda_cuenta="PEN", departamento="Lima", provincia="Lima", distrito="Ate",
        direccion="Av. Demo 123", bancos_competencia=("BCP",), tasas_competencia=(Decimal("3.20"),),
    )
    base.update(cambios)
    return Solicitud(**base)  # type: ignore[arg-type]


@pytest.fixture()
def tarifario() -> dict[str, Decimal]:
    return dict(TARIFARIO)


@pytest.fixture()
def fecha_ref() -> date:
    return FECHA_REF
