"""
generate_data.py
=================
Genera datos sintéticos de créditos para una financiera de PYMES en México.

Utiliza la librería Faker para producir ~5,000 registros realistas que simulan
un archivo mensual de originación de créditos.

Problemas de calidad incluidos intencionalmente:
  - Valores nulos en id_credito, monto y fecha_originacion (~2% cada uno)
  - Montos negativos (~1.5%)
  - Fechas inválidas (~1%, ej. 2024-02-30, 2024-13-05)
  - IDs de crédito duplicados (~1%)

Salida:
  creditos_mes.csv — archivo CSV con los datos generados.
"""

import csv
import os
import random
import sys
from datetime import datetime, timedelta

from faker import Faker

import logging

logging.basicConfig(
    filename=r'..\challenge_medium_data_engineer\logs\generate_data.log',
    filemode='a',
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
# ── Configuración ────────────────────────────────────────────────────────────
NUM_RECORDS = 5_000
OUTPUT_FILE = r"..\challenge_medium_data_engineer\data\raw\creditos_mes.csv"

# Probabilidades de problemas de calidad
P_NULL_ID_CREDITO = 0.02
P_NULL_MONTO = 0.02
P_NULL_FECHA = 0.02
P_NEGATIVO_MONTO = 0.015
P_FECHA_INVALIDA = 0.01
P_DUPLICADO_ID = 0.01

# Faker con locale español (México).  Si no está disponible, cae a español
# genérico o inglés.
try:
    fake = Faker("es_MX")
except AttributeError:
    try:
        fake = Faker("es")
    except AttributeError:
        fake = Faker()

random.seed(2025)
Faker.seed(2025)

# ── Catálogos ────────────────────────────────────────────────────────────────

INDUSTRIAS = [
    "Comercio",
    "Manufactura",
    "Servicios",
    "Construcción",
    "Agricultura",
    "Tecnología",
    "Alimentos y Bebidas",
    "Salud",
    "Transporte",
    "Educación",
]

CANALES = ["Sucursal", "Web", "App Móvil", "Call Center", "Promotor"]

ESTATUS_PAGO = ["A Tiempo", "Tardío"]

# Pesos para que ~75% estén a tiempo, ~25% tardío (refleja cartera con algo de mora)
PESOS_ESTATUS = [0.75, 0.25]

# ── Funciones auxiliares ─────────────────────────────────────────────────────


def generar_id_credito(i: int) -> str:
    """Genera un ID de crédito con formato CRED-XXXXX."""
    return f"CRED-{i:05d}"


def generar_id_cliente() -> str:
    """Genera un ID de cliente único con formato CLI-XXXXX."""
    return f"CLI-{fake.unique.random_int(min=1, max=99_999):05d}"


def generar_fecha_originacion() -> str:
    """
    Genera una fecha de originación dentro de los últimos 90 días.
    ~1% de las veces devuelve una fecha inválida.
    """
    if random.random() < P_FECHA_INVALIDA:
        return _fecha_invalida()
    dias_atras = random.randint(0, 90)
    fecha = datetime.now() - timedelta(days=dias_atras)
    return fecha.strftime("%Y-%m-%d")


def _fecha_invalida() -> str:
    """Genera una fecha inválida deliberadamente."""
    tipo = random.choice(["mes_13", "dia_30_feb", "formato_raro"])
    if tipo == "mes_13":
        return f"2024-13-{random.randint(1, 28):02d}"
    elif tipo == "dia_30_feb":
        return "2024-02-30"
    else:
        return f"{random.randint(1, 28):02d}/{random.randint(1, 12):02d}/2024"


def generar_monto() -> float | None:
    """
    Genera un monto de crédito entre $1,000 y $5,000,000 MXN.
    ~1.5% de las veces devuelve un monto negativo.
    ~2% de las veces devuelve None (nulo).
    """
    if random.random() < P_NULL_MONTO:
        return None
    monto = round(random.uniform(1_000, 5_000_000), 2)
    if random.random() < P_NEGATIVO_MONTO:
        monto = -monto
    return monto


def generar_plazo_meses() -> int:
    """Genera un plazo entre 3 y 60 meses (típico para créditos PYME)."""
    return random.choice([3, 6, 9, 12, 18, 24, 36, 48, 60])


def generar_estatus_pago() -> str | None:
    """
    Genera el estatus del primer pago.
    ~75% A Tiempo, ~25% Tardío.
    Un pequeño porcentaje puede ser nulo (pago aún no registrado).
    """
    return random.choices(ESTATUS_PAGO, weights=PESOS_ESTATUS, k=1)[0]


# ── Generación principal ─────────────────────────────────────────────────────


def generar_registros(n: int) -> list[dict]:
    """Genera n registros de créditos sintéticos."""
    registros = []
    ids_vistos: set[str] = set()

    for i in range(1, n + 1):
        id_credito = generar_id_credito(i)

        # Inyectar duplicados: ~1% de los registros reutilizan un ID ya generado
        if random.random() < P_DUPLICADO_ID and ids_vistos:
            id_credito = random.choice(list(ids_vistos))

        ids_vistos.add(id_credito)

        # Nulos en campos clave
        if random.random() < P_NULL_ID_CREDITO:
            id_credito = None
        if random.random() < P_NULL_FECHA:
            fecha_originacion = None
        else:
            fecha_originacion = generar_fecha_originacion()

        monto = generar_monto()
        plazo = generar_plazo_meses()
        industria = random.choice(INDUSTRIAS)
        canal = random.choice(CANALES)
        estatus = generar_estatus_pago()
        id_cliente = generar_id_cliente()
        nombre_cliente = fake.name()

        registros.append(
            {
                "id_credito": id_credito if id_credito is not None else "",
                "fecha_originacion": fecha_originacion if fecha_originacion is not None else "",
                "id_cliente": id_cliente,
                "nombre_cliente": nombre_cliente,
                "industria": industria,
                "monto": monto if monto is not None else "",
                "plazo_meses": plazo,
                "canal": canal,
                "estatus_primer_pago": estatus,
            }
        )

    return registros


def escribir_csv(registros: list[dict], archivo: str) -> None:
    """Escribe los registros a un archivo CSV."""
    campos = [
        "id_credito",
        "fecha_originacion",
        "id_cliente",
        "nombre_cliente",
        "industria",
        "monto",
        "plazo_meses",
        "canal",
        "estatus_primer_pago",
    ]

    with open(archivo, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(registros)


# ── Reporte de generación ────────────────────────────────────────────────────


def imprimir_reporte(registros: list[dict]) -> None:
    """Imprime un resumen de los datos generados en consola."""
    total = len(registros)
    nulos_id = sum(1 for r in registros if r["id_credito"] == "")
    nulos_monto = sum(1 for r in registros if r["monto"] == "")
    nulos_fecha = sum(1 for r in registros if r["fecha_originacion"] == "")
    negativos = sum(
        1 for r in registros if r["monto"] != "" and float(r["monto"]) < 0
    )
    fechas_invalidas = sum(
        1
        for r in registros
        if r["fecha_originacion"] != ""
        and not _es_fecha_valida(r["fecha_originacion"])
    )
    ids_unicos = len({r["id_credito"] for r in registros if r["id_credito"] != ""})
    duplicados = (total - sum(1 for r in registros if r["id_credito"] == "")) - ids_unicos

    logging.info("=" * 55)
    logging.info("  GENERACIÓN DE DATOS SINTÉTICOS — REPORTE")
    logging.info("=" * 55)
    logging.info(f"  Registros generados:        {total:,}")
    logging.info(f"  Archivo de salida:          {OUTPUT_FILE}")
    logging.info("-" * 55)
    logging.info("  Problemas de calidad inyectados:")
    logging.info(f"    - Nulos en id_credito:       {nulos_id:>4}  ({nulos_id/total*100:.1f}%)")
    logging.info(f"    - Nulos en monto:            {nulos_monto:>4}  ({nulos_monto/total*100:.1f}%)")
    logging.info(f"    - Nulos en fecha_originacion:{nulos_fecha:>4}  ({nulos_fecha/total*100:.1f}%)")
    logging.info(f"    - Montos negativos:          {negativos:>4}  ({negativos/total*100:.1f}%)")
    logging.info(f"    - Fechas inválidas:          {fechas_invalidas:>4}  ({fechas_invalidas/total*100:.1f}%)")
    logging.info(f"    - IDs duplicados:            {duplicados:>4}")
    logging.info("=" * 55)


def _es_fecha_valida(fecha_str: str) -> bool:
    """Verifica si una cadena de fecha tiene formato YYYY-MM-DD válido."""
    try:
        datetime.strptime(fecha_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


# ── Punto de entrada ─────────────────────────────────────────────────────────


def main() -> None:
    logging.info("Generando datos sintéticos de créditos...")
    registros = generar_registros(NUM_RECORDS)
    escribir_csv(registros, OUTPUT_FILE)
    imprimir_reporte(registros)
    logging.info("\n[OK] Datos sinteticos generados exitosamente.")


if __name__ == "__main__":
    main()
