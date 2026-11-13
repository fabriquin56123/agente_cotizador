"""Validación de entradas (tipos, rangos, listas permitidas, longitud).

Toda tool debe pasar por estas funciones ANTES de ejecutarse.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

from .config import BANCOS_PERMITIDOS, MONEDAS_PERMITIDAS

MAX_TEXTO = 200
MAX_CONSULTA = 300
MAX_GIROS = 10
MAX_TASAS = 10
TASA_MIN_ENTRADA = Decimal("0.01")
TASA_MAX_ENTRADA = Decimal("20")

_RE_PERIODO = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_RE_ID_SOLICITUD = re.compile(r"^SOL-\d{3}$")
_RE_MCC = re.compile(r"^\d{4}$")
_RE_SOLO_DIGITOS = re.compile(r"^\d+$")

DOC_EMPRESA = "EMPRESA"
DOC_DNI = "DNI"
DOC_RUC10 = "RUC10"
DOC_OTRO = "OTRO"


class ErrorValidacion(ValueError):
    """Entrada inválida; el mensaje no incluye el valor recibido (puede ser PII)."""


def quitar_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y espacios colapsados (para comparar nombres)."""
    return " ".join(quitar_acentos(texto).lower().split())


def validar_texto(valor: Any, campo: str, max_largo: int = MAX_TEXTO) -> str:
    if not isinstance(valor, str):
        raise ErrorValidacion(f"{campo}: debe ser texto")
    limpio = valor.strip()
    if not limpio:
        raise ErrorValidacion(f"{campo}: no puede estar vacío")
    if len(limpio) > max_largo:
        raise ErrorValidacion(f"{campo}: excede {max_largo} caracteres")
    return limpio


def validar_entero(valor: Any, campo: str, minimo: int, maximo: int) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorValidacion(f"{campo}: debe ser un entero")
    if not minimo <= valor <= maximo:
        raise ErrorValidacion(f"{campo}: fuera de rango [{minimo}, {maximo}]")
    return valor


def validar_lista_permitida(valor: Any, campo: str, permitidos: tuple[str, ...]) -> str:
    texto = validar_texto(valor, campo, 30).upper()
    if texto not in permitidos:
        raise ErrorValidacion(f"{campo}: valor fuera de la lista permitida {list(permitidos)}")
    return texto


def validar_banco(valor: Any, campo: str = "banco") -> str:
    return validar_lista_permitida(valor, campo, BANCOS_PERMITIDOS)


def validar_moneda(valor: Any, campo: str = "moneda") -> str:
    return validar_lista_permitida(valor, campo, MONEDAS_PERMITIDAS)


def validar_documento(valor: Any, campo: str = "ruc") -> str:
    """Acepta solo dígitos con 8 (DNI) u 11 (RUC) caracteres."""
    texto = validar_texto(valor, campo, 11)
    if not _RE_SOLO_DIGITOS.match(texto) or len(texto) not in (8, 11):
        raise ErrorValidacion(f"{campo}: debe tener 8 (DNI) u 11 (RUC) dígitos")
    return texto


def validar_mcc(valor: Any, campo: str = "mcc") -> str:
    texto = validar_texto(valor, campo, 4)
    if not _RE_MCC.match(texto):
        raise ErrorValidacion(f"{campo}: debe tener exactamente 4 dígitos")
    return texto


def validar_lista_mcc(valor: Any, campo: str = "codigos_giro") -> tuple[str, ...]:
    if not isinstance(valor, (list, tuple)) or not 1 <= len(valor) <= MAX_GIROS:
        raise ErrorValidacion(f"{campo}: lista de 1 a {MAX_GIROS} códigos")
    return tuple(validar_mcc(v, campo) for v in valor)


def validar_periodo(valor: Any, campo: str = "periodo") -> str:
    texto = validar_texto(valor, campo, 7)
    coincide = _RE_PERIODO.match(texto)
    if not coincide or not 2000 <= int(coincide.group(1)) <= 2100:
        raise ErrorValidacion(f"{campo}: formato AAAA-MM (años 2000-2100)")
    return texto


def validar_id_solicitud(valor: Any, campo: str = "id_solicitud") -> str:
    texto = validar_texto(valor, campo, 7).upper()
    if not _RE_ID_SOLICITUD.match(texto):
        raise ErrorValidacion(f"{campo}: formato SOL-NNN")
    return texto


def convertir_tasa(valor: Any, campo: str = "tasa") -> Decimal:
    """Convierte a Decimal en [0.01, 20] puntos porcentuales; admite '3.2%'."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str, Decimal)):
        raise ErrorValidacion(f"{campo}: tipo no numérico")
    texto = str(valor).strip().rstrip("%").strip()
    try:
        tasa = Decimal(texto)
    except InvalidOperation as exc:
        raise ErrorValidacion(f"{campo}: no es un número") from exc
    if not TASA_MIN_ENTRADA <= tasa <= TASA_MAX_ENTRADA:
        raise ErrorValidacion(f"{campo}: fuera de rango [{TASA_MIN_ENTRADA}, {TASA_MAX_ENTRADA}]")
    return tasa


def validar_lista_tasas(valor: Any, campo: str = "tasas") -> tuple[Decimal, ...]:
    if not isinstance(valor, (list, tuple)) or len(valor) > MAX_TASAS:
        raise ErrorValidacion(f"{campo}: lista de hasta {MAX_TASAS} tasas")
    return tuple(convertir_tasa(v, campo) for v in valor)


def tipo_documento(ruc: str) -> str:
    """Clasifica un documento ya validado: DNI, RUC 10, empresa u otro."""
    if len(ruc) == 8:
        return DOC_DNI
    if ruc.startswith("10"):
        return DOC_RUC10
    if ruc.startswith(("20", "15", "17")):
        return DOC_EMPRESA
    return DOC_OTRO
