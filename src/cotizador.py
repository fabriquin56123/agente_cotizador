"""Cálculo tentativo de tasas (puro, con Decimal; tasas en puntos porcentuales)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .modelos import ParametrosPolitica, RegistroTx
from .repositorio import en_ventana, meses_con_datos, volumen_pen
from .validacion import DOC_EMPRESA, tipo_documento

_CENTESIMO = Decimal("0.01")
# (volumen mensual mínimo en soles, descuento en pp), de mayor a menor
ESCALA_DESCUENTO: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal("500000"), Decimal("0.40")),
    (Decimal("200000"), Decimal("0.25")),
    (Decimal("80000"), Decimal("0.10")),
)


def redondear(valor: Decimal) -> Decimal:
    return valor.quantize(_CENTESIMO, rounding=ROUND_HALF_UP)


def descuento_por_volumen(volumen_mensual_pen: Decimal) -> Decimal:
    for minimo, descuento in ESCALA_DESCUENTO:
        if volumen_mensual_pen >= minimo:
            return descuento
    return Decimal("0.00")


def aplicar_limites(tasa: Decimal, params: ParametrosPolitica) -> Decimal:
    """Ajusta la tasa al rango [mínimo, máximo] de la política."""
    return redondear(min(max(tasa, params.tasa_minima), params.tasa_maxima))


def tasa_tarifaria(mcc: str, tarifario: dict[str, Decimal], volumen_mensual_pen: Decimal) -> Decimal | None:
    """Tasa base del MCC menos el descuento por volumen; None si el MCC no está tarifado."""
    base = tarifario.get(mcc)
    if base is None:
        return None
    return base - descuento_por_volumen(volumen_mensual_pen)


def tasa_interbank(tasas_competencia: tuple[Decimal, ...], params: ParametrosPolitica) -> Decimal | None:
    """0.75 × tasa más alta de la competencia, dentro de límites; None si no hay competencia."""
    if not tasas_competencia:
        return None
    return aplicar_limites(max(tasas_competencia) * params.factor_interbank, params)


def volumen_mensual_giro(registros: list[RegistroTx], mcc: str) -> Decimal:
    """Volumen mensual promedio (soles) de un giro, sobre los meses con datos."""
    del_giro = [r for r in registros if r.codigo_giro == mcc]
    meses = meses_con_datos(del_giro)
    if meses == 0:
        return Decimal(0)
    return sum((volumen_pen(r) for r in del_giro), Decimal(0)) / meses


def tasas_comercios_similares(
    mcc: str,
    todos: tuple[RegistroTx, ...] | list[RegistroTx],
    tarifario: dict[str, Decimal],
    periodos: tuple[str, ...],
    excluir_ruc: str,
) -> list[Decimal]:
    """Tasa tarifaria de cada comercio-empresa con ventana completa en el mismo MCC."""
    por_ruc: dict[str, list[RegistroTx]] = {}
    for r in en_ventana(list(todos), periodos):
        if r.codigo_giro == mcc and r.ruc != excluir_ruc and tipo_documento(r.ruc) == DOC_EMPRESA:
            por_ruc.setdefault(r.ruc, []).append(r)
    tasas = []
    for regs in por_ruc.values():
        if meses_con_datos(regs) < len(periodos):
            continue
        tasa = tasa_tarifaria(mcc, tarifario, volumen_mensual_giro(regs, mcc))
        if tasa is not None:
            tasas.append(tasa)
    return tasas


def tasa_referencia_similares(
    mcc: str,
    todos: tuple[RegistroTx, ...] | list[RegistroTx],
    tarifario: dict[str, Decimal],
    periodos: tuple[str, ...],
    excluir_ruc: str = "",
) -> Decimal | None:
    """Promedio de la tasa tarifaria de comercios similares; tarifario base si no hay ninguno."""
    tasas = tasas_comercios_similares(mcc, todos, tarifario, periodos, excluir_ruc)
    if tasas:
        return redondear(sum(tasas, Decimal(0)) / len(tasas))
    return tasa_tarifaria(mcc, tarifario, Decimal(0))
