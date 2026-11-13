"""Lectura de solicitudes en .txt (formato 'Campo: valor') → `Solicitud` validada."""
from __future__ import annotations

import re
from pathlib import Path

from .config import DIR_SOLICITUDES
from .modelos import Solicitud
from .validacion import (
    ErrorValidacion, MAX_TEXTO, normalizar, validar_banco, validar_documento,
    validar_id_solicitud, validar_lista_mcc, validar_lista_tasas, validar_texto,
)

_RE_PARENTESIS = re.compile(r"\([^)]*\)")
_CUENTAS = {"soles": "PEN", "dolares": "USD", "pen": "PEN", "usd": "USD"}
CAMPOS_OBLIGATORIOS = (
    "ruc", "razon social", "codigo de giro", "giro de negocio", "banco afiliado",
    "cuenta de abono", "departamento", "provincia", "distrito", "direccion",
    "banco competidor", "tasa ofertada por la competencia",
)


def normalizar_clave(clave: str) -> str:
    """'Código(s) de giro (MCC)' → 'codigo de giro'."""
    sin_parentesis = _RE_PARENTESIS.sub("", clave)
    return normalizar(sin_parentesis)


def extraer_campos(texto: str) -> dict[str, str]:
    """Pares 'Campo: valor' del texto (la primera aparición de cada campo gana)."""
    campos: dict[str, str] = {}
    for linea in texto.splitlines():
        if ":" not in linea:
            continue
        clave, _, valor = linea.partition(":")
        campos.setdefault(normalizar_clave(clave), valor.strip())
    return campos


def separar_lista(valor: str) -> list[str]:
    return [parte.strip() for parte in valor.split(",") if parte.strip()]


def convertir_cuenta(valor: str) -> str:
    moneda = _CUENTAS.get(normalizar(valor))
    if moneda is None:
        raise ErrorValidacion("cuenta de abono: use Soles o Dólares")
    return moneda


def id_desde_nombre(nombre_archivo: str) -> str:
    return validar_id_solicitud(Path(nombre_archivo).stem)


def construir_solicitud(id_solicitud: str, campos: dict[str, str]) -> Solicitud:
    faltan = [c for c in CAMPOS_OBLIGATORIOS if not campos.get(c)]
    if faltan:
        raise ErrorValidacion("faltan campos: " + ", ".join(faltan))
    bancos = tuple(validar_banco(b, "banco competidor") for b in separar_lista(campos["banco competidor"]))
    tasas = validar_lista_tasas(separar_lista(campos["tasa ofertada por la competencia"]), "tasa competencia")
    if len(bancos) != len(tasas):
        raise ErrorValidacion("bancos y tasas de la competencia deben tener igual cantidad")
    return Solicitud(
        id_solicitud=validar_id_solicitud(id_solicitud),
        ruc=validar_documento(campos["ruc"]),
        razon_social=validar_texto(campos["razon social"], "razon social"),
        codigos_giro=validar_lista_mcc(separar_lista(campos["codigo de giro"])),
        nombres_giro=tuple(validar_texto(n, "giro", MAX_TEXTO) for n in separar_lista(campos["giro de negocio"])),
        banco_afiliado=validar_banco(campos["banco afiliado"], "banco afiliado"),
        moneda_cuenta=convertir_cuenta(campos["cuenta de abono"]),
        departamento=validar_texto(campos["departamento"], "departamento"),
        provincia=validar_texto(campos["provincia"], "provincia"),
        distrito=validar_texto(campos["distrito"], "distrito"),
        direccion=validar_texto(campos["direccion"], "direccion"),
        bancos_competencia=bancos,
        tasas_competencia=tasas,
    )


def parsear_solicitud(texto: str, id_solicitud: str) -> Solicitud:
    return construir_solicitud(id_solicitud, extraer_campos(texto))


def leer_solicitud(id_solicitud: str, directorio: Path | None = None) -> Solicitud:
    """Lee SOL-NNN.txt del directorio de solicitudes (el id se valida antes de tocar disco)."""
    sid = validar_id_solicitud(id_solicitud)
    ruta = (directorio or DIR_SOLICITUDES) / f"{sid}.txt"
    if not ruta.is_file():
        raise ErrorValidacion("solicitud no encontrada")
    return parsear_solicitud(ruta.read_text(encoding="utf-8"), sid)


def leer_todas(directorio: Path | None = None) -> list[Solicitud]:
    carpeta = directorio or DIR_SOLICITUDES
    return [leer_solicitud(p.stem, carpeta) for p in sorted(carpeta.glob("SOL-*.txt"))]
