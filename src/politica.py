"""Motor de reglas de la política de pricing (puro y sin I/O).

Orden de evaluación (la primera regla que aplica decide):
documento → cartera inactiva → giros → cálculo de tasa → comparación con competencia.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from .cotizador import (
    aplicar_limites, redondear, tasa_interbank, tasa_referencia_similares,
    tasa_tarifaria, volumen_mensual_giro,
)
from .modelos import (
    APRUEBA, EVALUA_EXPERTO, RECHAZA, Decision, ParametrosPolitica, RegistroTx, Solicitud,
)
from .repositorio import (
    en_ventana, meses_con_datos, transacciones_de_ruc, ventana_periodos, volumen_por_giro,
)
from .validacion import DOC_DNI, DOC_OTRO, DOC_RUC10, normalizar, tipo_documento

DISTRITOS_PREMIUM_LIMA = frozenset({"miraflores", "san isidro", "barranco", "san borja"})
PROVINCIAS_PREMIUM = frozenset({"trujillo", "arequipa", "cusco"})


def es_zona_premium(departamento: str, provincia: str, distrito: str) -> bool:
    """Lima: solo 4 distritos; Trujillo, Arequipa y Cusco: por provincia."""
    if normalizar(provincia) in PROVINCIAS_PREMIUM:
        return True
    es_lima = normalizar(departamento) == "lima" and normalizar(provincia) == "lima"
    return es_lima and normalizar(distrito) in DISTRITOS_PREMIUM_LIMA


_MOTIVOS_DOCUMENTO = {
    DOC_DNI: "DNI_NO_PERMITIDO",
    DOC_RUC10: "RUC10_NO_PERMITIDO",
    DOC_OTRO: "DOCUMENTO_NO_VALIDO",
}


def motivo_rechazo_documento(ruc: str) -> str | None:
    """Motivo de rechazo por tipo de documento; None si es RUC de empresa."""
    return _MOTIVOS_DOCUMENTO.get(tipo_documento(ruc))


def es_cartera_inactiva(registros_ruc: list[RegistroTx], en_ventana_ruc: list[RegistroTx]) -> bool:
    """Existe en la base pero sin transacciones en los últimos 6 meses."""
    return bool(registros_ruc) and not en_ventana_ruc


def resolver_giro_principal(
    codigos: tuple[str, ...], en_ventana_ruc: list[RegistroTx], params: ParametrosPolitica
) -> tuple[str | None, str | None]:
    """Devuelve (giro_principal, motivo_rechazo). Giro declarado primero = principal declarado."""
    declarado = codigos[0]
    if len(codigos) == 1:
        return declarado, None
    vols = volumen_por_giro(en_ventana_ruc)
    vol_decl = vols.get(declarado, Decimal(0))
    for secundario in codigos[1:]:
        vol_sec = vols.get(secundario, Decimal(0))
        if vol_sec > 0 and vol_sec >= params.ratio_giro_dominante * vol_decl:
            return None, "GIRO_SECUNDARIO_DOMINANTE"
    if not any(vols.get(c, Decimal(0)) > 0 for c in codigos):
        return declarado, None
    principal = max(codigos, key=lambda c: (vols.get(c, Decimal(0)), -codigos.index(c)))
    return principal, None


def calcular_tasa_no_interbank(
    mcc: str,
    registros_ruc: list[RegistroTx],
    todos: tuple[RegistroTx, ...] | list[RegistroTx],
    tarifario: dict[str, Decimal],
    periodos: tuple[str, ...],
    ruc: str,
) -> Decimal | None:
    """Tasa tarifaria propia (6 meses) o de comercios similares (< 6 meses); sin prima ni límites."""
    if meses_con_datos(registros_ruc) >= len(periodos):
        return tasa_tarifaria(mcc, tarifario, volumen_mensual_giro(registros_ruc, mcc))
    return tasa_referencia_similares(mcc, todos, tarifario, periodos, excluir_ruc=ruc)


def decidir_por_competencia(
    tasa: Decimal, referencia: Decimal, premium: bool, params: ParametrosPolitica
) -> tuple[str, str]:
    """Aplica la tabla de tolerancias. Devuelve (flag, motivo)."""
    diff = tasa - referencia
    if diff < 0:
        return APRUEBA, "TASA_MENOR_COMPETENCIA"
    if premium:
        if diff <= params.tolerancia_pp:
            return APRUEBA, "TASA_EQUIPARABLE_ZONA_PREMIUM"
        if diff <= params.tolerancia_pp + params.tolerancia_premium_extra_pp:
            return EVALUA_EXPERTO, "SOBRE_COMPETENCIA_ZONA_PREMIUM"
        return RECHAZA, "SIN_MARGEN_SOBRE_COMPETENCIA"
    if diff <= params.tolerancia_pp:
        return EVALUA_EXPERTO, "SOBRE_COMPETENCIA_DENTRO_TOLERANCIA"
    return RECHAZA, "SIN_MARGEN_SOBRE_COMPETENCIA"


def _rechazo(sol: Solicitud, motivo: str) -> Decision:
    return Decision(id_solicitud=sol.id_solicitud, flag=RECHAZA, motivo=motivo)


def evaluar_solicitud(
    sol: Solicitud,
    todos: tuple[RegistroTx, ...] | list[RegistroTx],
    tarifario: dict[str, Decimal],
    fecha_ref: date,
    params: ParametrosPolitica | None = None,
) -> Decision:
    """Evalúa una solicitud contra la política y devuelve la decisión."""
    params = params or ParametrosPolitica()
    motivo_doc = motivo_rechazo_documento(sol.ruc)
    if motivo_doc:
        return _rechazo(sol, motivo_doc)

    periodos = ventana_periodos(fecha_ref, params.meses_ventana)
    historial = transacciones_de_ruc(todos, sol.ruc)
    ventana = en_ventana(historial, periodos)
    if es_cartera_inactiva(historial, ventana):
        return _rechazo(sol, "CARTERA_SIN_TRANSACCIONES_6M")

    giro, motivo_giro = resolver_giro_principal(sol.codigos_giro, ventana, params)
    if giro is None:
        return _rechazo(sol, motivo_giro or "GIRO_NO_RESUELTO")

    premium = es_zona_premium(sol.departamento, sol.provincia, sol.distrito)
    meses = meses_con_datos(ventana)
    referencia = max(sol.tasas_competencia) if sol.tasas_competencia else None
    tasa = _tasa_calculada(sol, giro, ventana, todos, tarifario, periodos, premium, params)

    def armar(flag: str, motivo: str, final: Decimal | None = None) -> Decision:
        return Decision(
            id_solicitud=sol.id_solicitud, flag=flag, motivo=motivo, giro_principal=giro,
            tasa_referencia_competencia=referencia, tasa_calculada=tasa, tasa_final=final,
            zona_premium=premium, meses_historial=meses,
        )

    if tasa is None:
        sin_ref = referencia is None
        return armar(EVALUA_EXPERTO, "SIN_REFERENCIA_COMPETENCIA" if sin_ref else "MCC_SIN_TARIFA")
    if referencia is None:
        return armar(EVALUA_EXPERTO, "SIN_REFERENCIA_COMPETENCIA")
    flag, motivo = decidir_por_competencia(tasa, referencia, premium, params)
    return armar(flag, motivo, tasa if flag == APRUEBA else None)


def _tasa_calculada(
    sol: Solicitud, giro: str, ventana: list[RegistroTx],
    todos: tuple[RegistroTx, ...] | list[RegistroTx], tarifario: dict[str, Decimal],
    periodos: tuple[str, ...], premium: bool, params: ParametrosPolitica,
) -> Decimal | None:
    """Tasa final-candidata: Interbank (0.75 × competencia) o tarifaria (+ prima premium)."""
    if sol.banco_afiliado == "INTERBANK":
        return tasa_interbank(sol.tasas_competencia, params)
    base = calcular_tasa_no_interbank(giro, ventana, todos, tarifario, periodos, sol.ruc)
    if base is None:
        return None
    prima = params.prima_zona_premium_pp if premium else Decimal(0)
    return aplicar_limites(redondear(base + prima), params)
