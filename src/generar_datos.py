"""Genera los datos de prueba (ficticios y reproducibles).

Salidas en data/:
- transacciones_clientes.csv  (≥ 20 clientes; multigiro = varias filas por periodo)
- tarifario_mcc.csv
- solicitudes/SOL-001.txt … SOL-015.txt

Uso:  python -m src.generar_datos
"""
from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from pathlib import Path

from .config import ARCHIVO_TARIFARIO, ARCHIVO_TRANSACCIONES, DIR_DATOS, DIR_SOLICITUDES

SEMILLA = 2026
CAMPOS_TX = [
    "id_transaccion", "id_cliente", "ruc", "razon_social", "periodo",
    "codigo_giro", "moneda", "volumen_bbva", "volumen_interbank", "volumen_bcp",
]

# (mcc, nombre del giro, tasa base %)
TARIFARIO: list[tuple[str, str, str]] = [
    ("5411", "Supermercados y abarrotes", "2.10"),
    ("5812", "Restaurantes", "2.90"),
    ("5814", "Comida rápida", "2.70"),
    ("5912", "Farmacias", "2.30"),
    ("5311", "Tiendas por departamento", "2.40"),
    ("5651", "Ropa y accesorios", "3.10"),
    ("7230", "Salones de belleza", "3.40"),
    ("8011", "Servicios médicos", "2.80"),
    ("5541", "Estaciones de servicio", "1.90"),
    ("4121", "Taxis y transporte", "3.60"),
    ("5942", "Librerías", "3.00"),
    ("5732", "Electrónica", "2.60"),
    ("5251", "Ferretería", "2.50"),
    ("7011", "Hoteles", "3.20"),
    ("8211", "Colegios", "2.20"),
    ("5999", "Tiendas varias", "3.30"),
    ("5200", "Materiales de construcción", "2.35"),
    ("4722", "Agencias de viaje", "3.70"),
]
NOMBRE_GIRO = {mcc: nombre for mcc, nombre, _ in TARIFARIO}

_REPARTOS = [(0.50, 0.20, 0.30), (0.30, 0.40, 0.30), (0.20, 0.30, 0.50), (0.40, 0.25, 0.35)]


@dataclass
class ClienteDemo:
    id_cliente: str
    ruc: str
    razon_social: str
    moneda: str
    giros: dict[str, int]
    inicio: str
    fin: str = "2026-10"
    reparto: tuple[float, float, float] = field(default=_REPARTOS[0])


def _c(id_, ruc, razon, giros, inicio, moneda="PEN", fin="2026-10", rep=0):
    return ClienteDemo(id_, ruc, razon, moneda, giros, inicio, fin, _REPARTOS[rep % 4])


CLIENTES: list[ClienteDemo] = [
    # --- clientes de las 15 solicitudes ---
    _c("C001", "20512345671", "Supermercados Pacífico Sur SAC", {"5411": 650000}, "2026-01", rep=1),
    _c("C002", "20498765432", "Restaurante Sabor Criollo EIRL", {"5812": 130000}, "2025-11", rep=0),
    _c("C003", "20534567891", "Farmacias Salud Total SAC", {"5912": 70000}, "2026-01", "USD", rep=2),
    _c("C004", "20601234567", "Inversiones Gourmet del Cusco SAC", {"5812": 90000, "5814": 150000}, "2026-01", rep=3),
    _c("C005", "20587654321", "Moda y Tecnología Arequipa SAC", {"5651": 30000, "5732": 150000}, "2026-01", rep=0),
    _c("C006", "10456789012", "Carlos Mendoza Ríos", {"5942": 20000}, "2026-03", rep=2),
    _c("C007", "45871236", "Rosa Huamán Cáceres", {"7230": 15000}, "2026-04", rep=1),
    _c("C008", "20478901234", "Ferretería El Constructor SRL", {"5251": 110000}, "2025-08", fin="2026-03", rep=3),
    _c("C009", "20623456789", "Café Aroma Barranco SAC", {"5812": 85000}, "2026-10", rep=0),
    _c("C010", "20556789012", "Librería Saber Trujillo SAC", {"5942": 40000}, "2026-09", rep=1),
    _c("C011", "20612345098", "Hotel Plaza Andina SAC", {"7011": 60000}, "2026-08", "USD", rep=2),
    _c("C012", "20598760123", "Boutique Elegance SAC", {"5651": 40000}, "2026-01", rep=3),
    _c("C013", "20587012345", "Salón Bella Vida SAC", {"7230": 45000}, "2026-01", rep=0),
    _c("C014", "20545678123", "Clínica San Borja Salud SAC", {"8011": 420000}, "2026-01", rep=1),
    _c("C015", "20509871234", "Grifo Los Libertadores EIRL", {"5541": 300000}, "2026-01", rep=2),
    # --- comercios comparables (≥ 6 meses de historial) ---
    _c("C016", "20401234501", "Restaurante El Fogón SAC", {"5812": 160000}, "2025-11", rep=0),
    _c("C017", "20401234502", "Cevichería Marea Alta SAC", {"5812": 60000}, "2025-11", rep=1),
    _c("C018", "20401234503", "Hotel Casa del Valle SAC", {"7011": 320000}, "2025-11", rep=2),
    _c("C019", "20401234504", "Posada del Sol SRL", {"7011": 150000}, "2025-11", rep=3),
    _c("C020", "20401234505", "Café La Esquina SAC", {"5814": 70000}, "2025-11", rep=0),
    _c("C021", "20401234506", "Librería Letras SAC", {"5942": 50000}, "2025-11", rep=1),
    _c("C022", "20401234507", "Mercado Fresco SAC", {"5411": 400000}, "2025-11", rep=2),
    _c("C023", "20401234508", "Farmacia Vida Sana SAC", {"5912": 180000}, "2025-11", rep=3),
    _c("C024", "20401234509", "Moda Norte SAC", {"5651": 60000}, "2025-11", rep=0),
]


def rango_periodos(inicio: str, fin: str) -> list[str]:
    """Lista 'AAAA-MM' de inicio a fin, ambos inclusive."""
    anio, mes = map(int, inicio.split("-"))
    anio_f, mes_f = map(int, fin.split("-"))
    salida = []
    while (anio, mes) <= (anio_f, mes_f):
        salida.append(f"{anio:04d}-{mes:02d}")
        mes += 1
        if mes == 13:
            anio, mes = anio + 1, 1
    return salida


def filas_cliente(cli: ClienteDemo, rng: random.Random, contador: int) -> list[dict[str, str]]:
    """Filas de un cliente: una por periodo y giro."""
    filas = []
    for periodo in rango_periodos(cli.inicio, cli.fin):
        for mcc, base in cli.giros.items():
            contador += 1
            total = base * rng.uniform(0.88, 1.12)
            b, i, p = (round(total * s, 2) for s in cli.reparto)
            filas.append({
                "id_transaccion": f"TX-{contador:06d}", "id_cliente": cli.id_cliente,
                "ruc": cli.ruc, "razon_social": cli.razon_social, "periodo": periodo,
                "codigo_giro": mcc, "moneda": cli.moneda,
                "volumen_bbva": f"{b:.2f}", "volumen_interbank": f"{i:.2f}",
                "volumen_bcp": f"{p:.2f}",
            })
    return filas


def generar_transacciones() -> list[dict[str, str]]:
    rng = random.Random(SEMILLA)
    filas: list[dict[str, str]] = []
    for cli in CLIENTES:
        filas.extend(filas_cliente(cli, rng, len(filas)))
    return filas


def escribir_csv(ruta: Path, campos: list[str], filas: list[dict[str, str]]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)


@dataclass(frozen=True)
class SolicitudDemo:
    num: int
    fecha: str
    ruc: str
    razon: str
    mccs: tuple[str, ...]
    banco: str
    cuenta: str
    ubicacion: tuple[str, str, str, str]  # departamento, provincia, distrito, dirección
    competencia: tuple[tuple[str, str], ...]  # (banco, tasa %)


def _s(num, dia, ruc, razon, mccs, banco, cuenta, ubic, comp):
    return SolicitudDemo(num, f"{dia} de noviembre de 2026", ruc, razon, tuple(mccs), banco,
                         cuenta, ubic, tuple(comp))


SOLICITUDES: list[SolicitudDemo] = [
    _s(1, 9, "20512345671", "Supermercados Pacífico Sur SAC", ["5411"], "INTERBANK", "Soles",
       ("Lima", "Lima", "San Isidro", "Av. Camino Real 1450"), [("BBVA", "2.80"), ("BCP", "3.00")]),
    _s(2, 9, "20498765432", "Restaurante Sabor Criollo EIRL", ["5812"], "BBVA", "Soles",
       ("Lima", "Lima", "Miraflores", "Calle Schell 320"), [("BCP", "3.20")]),
    _s(3, 9, "20534567891", "Farmacias Salud Total SAC", ["5912"], "BCP", "Dólares",
       ("Lima", "Lima", "Santiago de Surco", "Av. Primavera 2105"), [("BBVA", "2.20")]),
    _s(4, 10, "20601234567", "Inversiones Gourmet del Cusco SAC", ["5812", "5814"], "BCP", "Soles",
       ("Cusco", "Cusco", "Cusco", "Av. El Sol 580"), [("BBVA", "3.30")]),
    _s(5, 10, "20587654321", "Moda y Tecnología Arequipa SAC", ["5651", "5732"], "SCOTIABANK", "Soles",
       ("Arequipa", "Arequipa", "Arequipa", "Calle Mercaderes 210"), [("BCP", "3.50")]),
    _s(6, 10, "10456789012", "Carlos Mendoza Ríos", ["5942"], "BCP", "Soles",
       ("La Libertad", "Trujillo", "Trujillo", "Jr. Pizarro 455"), [("BBVA", "3.00")]),
    _s(7, 10, "45871236", "Rosa Huamán Cáceres", ["7230"], "BBVA", "Soles",
       ("Lima", "Lima", "San Juan de Lurigancho", "Av. Próceres 1200"), [("BCP", "3.80")]),
    _s(8, 11, "20478901234", "Ferretería El Constructor SRL", ["5251"], "SCOTIABANK", "Soles",
       ("Lima", "Lima", "Ate", "Av. Nicolás Ayllón 3560"), [("BBVA", "2.70")]),
    _s(9, 11, "20623456789", "Café Aroma Barranco SAC", ["5812"], "BBVA", "Soles",
       ("Lima", "Lima", "Barranco", "Av. Grau 340"), [("BCP", "3.40")]),
    _s(10, 11, "20556789012", "Librería Saber Trujillo SAC", ["5942"], "INTERBANK", "Soles",
       ("La Libertad", "Trujillo", "Trujillo", "Av. España 1820"), [("BBVA", "3.20")]),
    _s(11, 11, "20612345098", "Hotel Plaza Andina SAC", ["7011"], "BCP", "Dólares",
       ("Cusco", "Cusco", "Cusco", "Calle Plateros 305"), [("BBVA", "3.00"), ("SCOTIABANK", "3.10")]),
    _s(12, 12, "20598760123", "Boutique Elegance SAC", ["5651"], "BBVA", "Soles",
       ("Lima", "Lima", "Los Olivos", "Av. Alfredo Mendiola 5200"), [("BCP", "2.90")]),
    _s(13, 12, "20587012345", "Salón Bella Vida SAC", ["7230"], "BCP", "Soles",
       ("Lima", "Lima", "Comas", "Av. Túpac Amaru 4300"), [("BBVA", "2.60")]),
    _s(14, 12, "20545678123", "Clínica San Borja Salud SAC", ["8011"], "INTERBANK", "Soles",
       ("Lima", "Lima", "San Borja", "Av. Javier Prado Este 2960"), [("BBVA", "1.90"), ("BCP", "2.00")]),
    _s(15, 12, "20509871234", "Grifo Los Libertadores EIRL", ["5541"], "INTERBANK", "Soles",
       ("Lima", "Lima", "Ate", "Av. Separadora Industrial 790"), [("BBVA", "1.30")]),
]


def redactar_solicitud(s: SolicitudDemo) -> str:
    """Texto formal y breve de una solicitud (formato 'Campo: valor')."""
    dep, prov, dist, direc = s.ubicacion
    bancos = ", ".join(b for b, _ in s.competencia)
    tasas = ", ".join(f"{t}%" for _, t in s.competencia)
    giros = ", ".join(NOMBRE_GIRO[m] for m in s.mccs)
    return (
        f"SOLICITUD DE COTIZACIÓN N.° {s.num:03d}\n"
        f"Lima, {s.fecha}\n\n"
        "Señores\nÁrea de Pricing y Optimización de Precios - Izipay\nPresente.-\n\n"
        f"Por medio de la presente, {s.razon} solicita la cotización de la tasa de comisión "
        "por el procesamiento de pagos con POS, conforme a los datos siguientes:\n\n"
        f"RUC: {s.ruc}\n"
        f"Razón social: {s.razon}\n"
        f"Código(s) de giro (MCC): {', '.join(s.mccs)}\n"
        f"Giro(s) de negocio: {giros}\n"
        f"Banco afiliado: {s.banco}\n"
        f"Cuenta de abono: {s.cuenta}\n"
        f"Departamento: {dep}\n"
        f"Provincia: {prov}\n"
        f"Distrito: {dist}\n"
        f"Dirección: {direc}\n"
        f"Banco(s) competidor(es): {bancos}\n"
        f"Tasa(s) ofertada(s) por la competencia: {tasas}\n\n"
        "Sin otro particular, quedo atento a su respuesta.\n\nAtentamente,\n"
        f"{s.razon}\n"
    )


def escribir_solicitudes(directorio: Path = DIR_SOLICITUDES) -> None:
    directorio.mkdir(parents=True, exist_ok=True)
    for s in SOLICITUDES:
        (directorio / f"SOL-{s.num:03d}.txt").write_text(redactar_solicitud(s), encoding="utf-8")


def main() -> None:
    DIR_DATOS.mkdir(parents=True, exist_ok=True)
    filas = generar_transacciones()
    escribir_csv(ARCHIVO_TRANSACCIONES, CAMPOS_TX, filas)
    escribir_csv(
        ARCHIVO_TARIFARIO, ["mcc", "giro", "tasa_pct"],
        [{"mcc": m, "giro": n, "tasa_pct": t} for m, n, t in TARIFARIO],
    )
    escribir_solicitudes()
    print(f"transacciones: {len(filas)} filas, {len(CLIENTES)} clientes; "
          f"solicitudes: {len(SOLICITUDES)}")


if __name__ == "__main__":
    main()
