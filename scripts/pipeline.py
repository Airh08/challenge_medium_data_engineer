"""
pipeline.py
===========
Pipeline de ingesta, validación y carga al modelo dimensional.

Parte 2 — Calidad de datos:
  - Detección de nulos en id_credito, monto, fecha_originacion
  - Montos fuera de rango ($1,000 – $5,000,000 MXN)
  - Duplicados por id_credito
  - Formato inválido de fechas

Salidas:
  - data/quality/reporte_calidad.xlsx   — Reporte en Excel
  - data/quality/reporte_calidad.md     — Reporte en Markdown
  - data/quality/registros_fallidos.csv — Registros que no pasaron las pruebas
      (columnas: id_credito, regla, motivo)
"""

import csv
import logging
import os
from collections import Counter
from datetime import datetime

import pandas as pd

# ── Configuración de rutas ───────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(BASE_DIR, "data", "raw", "creditos_mes.csv")
QUALITY_DIR = os.path.join(BASE_DIR, "data", "reports")
FAILED_CSV = os.path.join(QUALITY_DIR, "registros_fallidos.csv")
EXCEL_REPORT = os.path.join(QUALITY_DIR, "reporte_calidad.xlsx")
MD_REPORT = os.path.join(QUALITY_DIR, "reporte_calidad.md")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

MONTO_MIN = 1_000
MONTO_MAX = 5_000_000

# ── Logging ──────────────────────────────────────────────────────────────────

os.makedirs(LOGS_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOGS_DIR, "pipeline.log"),
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDACIONES
# ═══════════════════════════════════════════════════════════════════════════════

def _es_fecha_valida(fecha_str: str) -> bool:
    """Verifica que una cadena tenga formato YYYY-MM-DD y sea una fecha real."""
    partes = fecha_str.strip().split("-")
    if len(partes) != 3:
        return False
    if not all(p.isdigit() for p in partes):
        return False
    try:
        datetime.strptime(fecha_str.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validar_nulos(registros: list[dict]) -> list[dict]:
    """Detecta valores nulos o vacíos en id_credito, monto y fecha_originacion."""
    fallos = []
    for i, r in enumerate(registros):
        row_id = r["id_credito"].strip() if r["id_credito"] else f"(fila_{i + 2})"

        if not r["id_credito"] or r["id_credito"].strip() == "":
            fallos.append({
                "id_credito": row_id,
                "regla": "nulo_id_credito",
                "motivo": "El campo id_credito esta vacio o es nulo",
            })

        if not r["monto"] or r["monto"].strip() == "":
            fallos.append({
                "id_credito": row_id,
                "regla": "nulo_monto",
                "motivo": "El campo monto esta vacio o es nulo",
            })

        if not r["fecha_originacion"] or r["fecha_originacion"].strip() == "":
            fallos.append({
                "id_credito": row_id,
                "regla": "nulo_fecha_originacion",
                "motivo": "El campo fecha_originacion esta vacio o es nulo",
            })

    return fallos


def validar_montos_rango(registros: list[dict]) -> list[dict]:
    """Detecta montos fuera del rango [$1,000 – $5,000,000] o no numéricos."""
    fallos = []
    for i, r in enumerate(registros):
        row_id = r["id_credito"].strip() if r["id_credito"] else f"(fila_{i + 2})"

        if not r["monto"] or r["monto"].strip() == "":
            continue  # ya reportado como nulo_monto

        try:
            monto = float(r["monto"])
            if monto < MONTO_MIN:
                fallos.append({
                    "id_credito": row_id,
                    "regla": "monto_fuera_rango",
                    "motivo": (
                        f"Monto ${monto:,.2f} por debajo del minimo "
                        f"(${MONTO_MIN:,})"
                    ),
                })
            elif monto > MONTO_MAX:
                fallos.append({
                    "id_credito": row_id,
                    "regla": "monto_fuera_rango",
                    "motivo": (
                        f"Monto ${monto:,.2f} excede el maximo "
                        f"(${MONTO_MAX:,})"
                    ),
                })
        except ValueError:
            fallos.append({
                "id_credito": row_id,
                "regla": "monto_no_numerico",
                "motivo": f"El valor '{r['monto']}' no se puede interpretar como numero",
            })

    return fallos


def validar_duplicados(registros: list[dict]) -> list[dict]:
    """Detecta id_credito duplicados."""
    ids_no_nulos = [
        r["id_credito"].strip()
        for r in registros
        if r["id_credito"] and r["id_credito"].strip()
    ]
    conteo = Counter(ids_no_nulos)
    duplicados = {id_ for id_, c in conteo.items() if c > 1}

    fallos = []
    for i, r in enumerate(registros):
        id_cred = r["id_credito"].strip() if r["id_credito"] else ""
        if id_cred in duplicados:
            fallos.append({
                "id_credito": id_cred,
                "regla": "duplicado_id",
                "motivo": (
                    f"id_credito={id_cred} aparece {conteo[id_cred]} veces "
                    f"(duplicado)"
                ),
            })

    return fallos


def validar_formato_fecha(registros: list[dict]) -> list[dict]:
    """
    Detecta fechas con formato inválido:
      - No cumplen con el patrón YYYY-MM-DD
      - No son una fecha real del calendario (ej. 2024-02-30)
    """
    fallos = []
    for i, r in enumerate(registros):
        row_id = r["id_credito"].strip() if r["id_credito"] else f"(fila_{i + 2})"

        fecha = r["fecha_originacion"]
        if not fecha or fecha.strip() == "":
            continue  # ya reportado como nulo_fecha_originacion

        if not _es_fecha_valida(fecha):
            fallos.append({
                "id_credito": row_id,
                "regla": "formato_fecha_invalido",
                "motivo": (
                    f"fecha_originacion='{fecha.strip()}' no cumple con el "
                    f"formato YYYY-MM-DD o no es una fecha valida"
                ),
            })

    return fallos


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def cargar_datos(archivo: str) -> list[dict]:
    """Carga los registros desde el CSV fuente."""
    with open(archivo, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ejecutar_validaciones(registros: list[dict]) -> list[dict]:
    """
    Ejecuta todas las reglas de validación.
    Retorna una lista consolidada de fallos (cada fallo es un dict
    con id_credito, regla y motivo).
    """
    logger.info("Ejecutando validaciones de calidad...")

    todas = []

    fallos_nulos = validar_nulos(registros)
    todas.extend(fallos_nulos)
    logger.info("  nulos: %d fallos", len(fallos_nulos))

    fallos_rango = validar_montos_rango(registros)
    todas.extend(fallos_rango)
    logger.info("  monto rango: %d fallos", len(fallos_rango))

    fallos_dup = validar_duplicados(registros)
    todas.extend(fallos_dup)
    logger.info("  duplicados: %d fallos", len(fallos_dup))

    fallos_fecha = validar_formato_fecha(registros)
    todas.extend(fallos_fecha)
    logger.info("  formato fecha: %d fallos", len(fallos_fecha))

    return todas


def generar_estadisticas(
    registros: list[dict], fallos: list[dict]
) -> dict:
    """Calcula estadísticas consolidadas del reporte de calidad."""
    total = len(registros)

    # IDs únicos que tienen al menos un fallo
    ids_con_fallo: set[str] = set()
    for f in fallos:
        ids_con_fallo.add(f["id_credito"])

    conteo_por_regla = Counter(f["regla"] for f in fallos)

    return {
        "total": total,
        "pasaron": total - len(ids_con_fallo),
        "fallaron": len(ids_con_fallo),
        "total_fallos": len(fallos),
        "por_regla": dict(conteo_por_regla),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GENERACIÓN DE REPORTES
# ═══════════════════════════════════════════════════════════════════════════════

def guardar_csv_fallidos(fallos: list[dict], archivo: str) -> None:
    """Guarda los registros fallidos como CSV."""
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    with open(archivo, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id_credito", "regla", "motivo"])
        writer.writeheader()
        writer.writerows(fallos)
    logger.info("CSV de fallidos guardado: %s", archivo)


def guardar_reporte_excel(
    stats: dict, fallos: list[dict], archivo: str
) -> None:
    """Guarda el reporte de calidad en formato Excel (.xlsx) con 3 hojas."""
    os.makedirs(os.path.dirname(archivo), exist_ok=True)

    with pd.ExcelWriter(archivo, engine="openpyxl") as writer:
        # Hoja 1 — Resumen
        df_resumen = pd.DataFrame([
            {"Métrica": "Total de registros evaluados",
             "Valor": stats["total"]},
            {"Métrica": "Registros que pasaron todas las reglas",
             "Valor": stats["pasaron"]},
            {"Métrica": "Registros que fallaron al menos una regla",
             "Valor": stats["fallaron"]},
            {"Métrica": "Total de fallos detectados",
             "Valor": stats["total_fallos"]},
        ])
        df_resumen.to_excel(writer, sheet_name="Resumen", index=False)

        # Hoja 2 — Fallos por regla
        df_reglas = pd.DataFrame([
            {"Regla": regla, "Cantidad de fallos": cant}
            for regla, cant in sorted(
                stats["por_regla"].items(), key=lambda x: -x[1]
            )
        ])
        df_reglas.to_excel(writer, sheet_name="Fallos_por_regla", index=False)

        # Hoja 3 — Detalle de registros fallidos
        df_fallos = pd.DataFrame(fallos)
        df_fallos.to_excel(writer, sheet_name="Detalle_fallos", index=False)

    logger.info("Reporte Excel guardado: %s", archivo)


def guardar_reporte_md(stats: dict, archivo: str) -> None:
    """Guarda el reporte de calidad en formato Markdown."""
    os.makedirs(os.path.dirname(archivo), exist_ok=True)

    lines: list[str] = []
    lines.append("# Reporte de Calidad de Datos")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|------------------------------------------|-------|")
    lines.append(
        f"| Total de registros evaluados            | {stats['total']:,} |"
    )
    lines.append(
        f"| Registros que pasaron todas las reglas   | {stats['pasaron']:,} |"
    )
    lines.append(
        f"| Registros que fallaron al menos una regla| {stats['fallaron']:,} |"
    )
    lines.append(
        f"| Total de fallos detectados               | {stats['total_fallos']:,} |"
    )
    lines.append("")
    lines.append("## Fallos por regla")
    lines.append("")
    lines.append("| Regla | Cantidad de fallos |")
    lines.append("|---------------------------|-------------------|")
    for regla, cant in sorted(stats["por_regla"].items(), key=lambda x: -x[1]):
        lines.append(f"| {regla} | {cant:,} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        f"*Reporte generado automáticamente el "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
    )

    with open(archivo, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    logger.info("Reporte Markdown guardado: %s", archivo)


def imprimir_resumen_consola(stats: dict) -> None:
    """Imprime el resumen del reporte en la terminal."""
    print("\n" + "=" * 55)
    print("  REPORTE DE CALIDAD DE DATOS")
    print("=" * 55)
    print(f"  Total de registros evaluados:           {stats['total']:>6,}")
    print(f"  Registros que pasaron todas las reglas: {stats['pasaron']:>6,}")
    print(f"  Registros que fallaron:                 {stats['fallaron']:>6,}")
    print(f"  Total de fallos detectados:             {stats['total_fallos']:>6,}")
    print("-" * 55)
    print("  Fallos por regla:")
    for regla, cant in sorted(stats["por_regla"].items(), key=lambda x: -x[1]):
        print(f"    - {regla:<32s} {cant:>6,}")
    print("=" * 55)


# ═══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    logger.info("=" * 50)
    logger.info("INICIO DEL PIPELINE DE CALIDAD")

    # 1. Cargar datos
    print("Cargando datos desde data/raw/creditos_mes.csv ...")
    registros = cargar_datos(INPUT_FILE)
    print(f"  -> {len(registros):,} registros cargados.")
    logger.info("Registros cargados: %d", len(registros))

    # 2. Ejecutar validaciones
    print("Ejecutando validaciones de calidad...")
    fallos = ejecutar_validaciones(registros)

    # 3. Generar estadísticas
    stats = generar_estadisticas(registros, fallos)

    # 4. Guardar reportes
    print("Guardando reportes en data/quality/ ...")
    guardar_csv_fallidos(fallos, FAILED_CSV)
    guardar_reporte_excel(stats, fallos, EXCEL_REPORT)
    guardar_reporte_md(stats, MD_REPORT)

    # 5. Resumen en consola
    imprimir_resumen_consola(stats)

    print(f"\nArchivos generados:")
    print(f"  - {FAILED_CSV}")
    print(f"  - {EXCEL_REPORT}")
    print(f"  - {MD_REPORT}")

    logger.info("PIPELINE FINALIZADO EXITOSAMENTE")
    print("\n[OK] Pipeline de calidad completado.")


if __name__ == "__main__":
    main()
