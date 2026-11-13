"""Consolida las solicitudes .txt, aplica la política y escribe los CSV de salida.

Salidas:
- data/solicitudes_consolidado.csv : todas las solicitudes + flag, motivo, giro principal, tasa final
- data/resultados_cotizacion.csv   : solo cotizaciones aprobadas (cotiza = SI) y su tasa final

Uso:  python -m src.consolidar
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from .config import ARCHIVO_CONSOLIDADO, ARCHIVO_RESULTADOS, fecha_referencia
from .generar_datos import escribir_csv
from .modelos import APRUEBA, Decision, Solicitud
from .politica import evaluar_solicitud
from .repositorio import cargar_tarifario, cargar_transacciones
from .solicitudes import leer_todas

CAMPOS_CONSOLIDADO = [
    "id_solicitud", "ruc", "razon_social", "codigos_giro", "nombres_giro", "banco_afiliado",
    "moneda_cuenta", "departamento", "provincia", "distrito", "direccion",
    "bancos_competencia", "tasas_competencia_pct", "flag_decision", "motivo",
    "giro_principal", "tasa_final_pct",
]
CAMPOS_RESULTADOS = ["id_solicitud", "ruc", "razon_social", "cotiza", "giro_principal", "tasa_final_pct"]


def _texto(valor: Decimal | None) -> str:
    return "" if valor is None else f"{valor:.2f}"


def fila_consolidado(sol: Solicitud, dec: Decision) -> dict[str, str]:
    """Fila del consolidado: campos de la solicitud (listas separadas por coma) + decisión."""
    return {
        "id_solicitud": sol.id_solicitud, "ruc": sol.ruc, "razon_social": sol.razon_social,
        "codigos_giro": ",".join(sol.codigos_giro), "nombres_giro": ",".join(sol.nombres_giro),
        "banco_afiliado": sol.banco_afiliado, "moneda_cuenta": sol.moneda_cuenta,
        "departamento": sol.departamento, "provincia": sol.provincia, "distrito": sol.distrito,
        "direccion": sol.direccion, "bancos_competencia": ",".join(sol.bancos_competencia),
        "tasas_competencia_pct": ",".join(f"{t:.2f}" for t in sol.tasas_competencia),
        "flag_decision": dec.flag, "motivo": dec.motivo,
        "giro_principal": dec.giro_principal or "", "tasa_final_pct": _texto(dec.tasa_final),
    }


def fila_resultado(sol: Solicitud, dec: Decision) -> dict[str, str]:
    return {
        "id_solicitud": sol.id_solicitud, "ruc": sol.ruc, "razon_social": sol.razon_social,
        "cotiza": "SI", "giro_principal": dec.giro_principal or "",
        "tasa_final_pct": _texto(dec.tasa_final),
    }


def evaluar_todas(fecha_ref: date | None = None) -> list[tuple[Solicitud, Decision]]:
    fecha = fecha_ref or fecha_referencia()
    registros, tarifario = cargar_transacciones(), cargar_tarifario()
    return [(s, evaluar_solicitud(s, registros, tarifario, fecha)) for s in leer_todas()]


def escribir_salidas(
    pares: list[tuple[Solicitud, Decision]],
    ruta_consolidado: Path = ARCHIVO_CONSOLIDADO,
    ruta_resultados: Path = ARCHIVO_RESULTADOS,
) -> None:
    escribir_csv(ruta_consolidado, CAMPOS_CONSOLIDADO, [fila_consolidado(s, d) for s, d in pares])
    aprobadas = [fila_resultado(s, d) for s, d in pares if d.flag == APRUEBA]
    escribir_csv(ruta_resultados, CAMPOS_RESULTADOS, aprobadas)


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    pares = evaluar_todas()
    escribir_salidas(pares)
    for sol, dec in pares:
        print(f"{sol.id_solicitud}  {dec.flag:<15} {dec.motivo:<38} "
              f"giro={dec.giro_principal or '-':<5} tasa={_texto(dec.tasa_final) or '-'}")


if __name__ == "__main__":
    main()
