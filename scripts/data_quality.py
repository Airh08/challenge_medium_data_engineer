import logging
import os
from datetime import datetime

import pandas as pd
import numpy as np

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
    filename=os.path.join(LOGS_DIR, "data_quality.log"),
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

def ejecutar_validaciones(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ejecuta las validaciones de calidad de datos y genera los reportes correspondientes.
    """
    logger.info("Iniciando validaciones de calidad de datos...")
    try:
        # 1. Crear identificadores de fila para reportar si id_credito es nulo o vacío
        # Usamos el índice + 2 para alinearlo con el número de fila del archivo CSV original
        is_id_empty = df['id_credito'].isna() | (df['id_credito'].astype(str).str.strip() == "")
        row_ids = np.where(
            is_id_empty,
            [f"(fila_{i + 2})" for i in df.index],
            df['id_credito'].astype(str).str.strip()
        )
        
        fallos_list = []
        
        # ──── REGLAS 1, 2, 3: Validación de Nulos ────
        for col, regla in [('id_credito', 'nulo_id_credito'), ('monto', 'nulo_monto'), ('fecha_originacion', 'nulo_fecha_originacion')]:
            is_null = df[col].isna() | (df[col].astype(str).str.strip() == "")
            if is_null.any():
                fallos_list.append(pd.DataFrame({
                    "id_credito": row_ids[is_null],
                    "regla": regla,
                    "motivo": f"El campo {col} esta vacio o es nulo"
                }))

        # ──── REGLAS 4, 5: Validación de Monto ────
        monto_not_null = ~(df['monto'].isna() | (df['monto'].astype(str).str.strip() == ""))
        monto_numeric = pd.to_numeric(df['monto'], errors='coerce')

        # Monto No Numérico
        idx_no_num = monto_not_null & monto_numeric.isna()
        if idx_no_num.any():
            fallos_list.append(pd.DataFrame({
                "id_credito": row_ids[idx_no_num],
                "regla": "monto_no_numerico",
                "motivo": df.loc[idx_no_num, 'monto'].apply(lambda val: f"El valor '{val}' no se puede interpretar como numero")
            }))

        # Monto Bajo el Mínimo
        idx_low = monto_numeric.notna() & (monto_numeric < MONTO_MIN)
        if idx_low.any():
            fallos_list.append(pd.DataFrame({
                "id_credito": row_ids[idx_low],
                "regla": "monto_fuera_rango",
                "motivo": monto_numeric[idx_low].apply(lambda val: f"Monto ${val:,.2f} por debajo del minimo (${MONTO_MIN:,})")
            }))

        # Monto Excede el Máximo
        idx_high = monto_numeric.notna() & (monto_numeric > MONTO_MAX)
        if idx_high.any():
            fallos_list.append(pd.DataFrame({
                "id_credito": row_ids[idx_high],
                "regla": "monto_fuera_rango",
                "motivo": monto_numeric[idx_high].apply(lambda val: f"Monto ${val:,.2f} excede el maximo (${MONTO_MAX:,})")
            }))

        # ──── REGLA 6: Validación de Duplicados de id_credito ────
        id_not_null = ~is_id_empty
        ids_cleaned = df['id_credito'].astype(str).str.strip()
        id_counts = ids_cleaned[id_not_null].value_counts()
        duplicados = id_counts[id_counts > 1].index
        idx_dup = id_not_null & ids_cleaned.isin(duplicados)
        if idx_dup.any():
            fallos_list.append(pd.DataFrame({
                "id_credito": row_ids[idx_dup],
                "regla": "duplicado_id",
                "motivo": ids_cleaned[idx_dup].apply(lambda val: f"id_credito={val} aparece {id_counts[val]} veces (duplicado)")
            }))

        # ──── REGLA 7: Validación de Formato de Fecha (YYYY-MM-DD) ────
        fecha_not_null = ~(df['fecha_originacion'].isna() | (df['fecha_originacion'].astype(str).str.strip() == ""))
        fechas_cleaned = df['fecha_originacion'].astype(str).str.strip()
        # Verifica sintaxis estricta
        regex_match = fechas_cleaned.str.match(r'^\d{4}-\d{2}-\d{2}$') == True
        # Verifica que sea un día real en el calendario (ej: evita 2026-02-30)
        parsed_dates = pd.to_datetime(fechas_cleaned, format='%Y-%m-%d', errors='coerce')
        
        idx_fecha_err = fecha_not_null & (~regex_match | parsed_dates.isna())
        if idx_fecha_err.any():
            fallos_list.append(pd.DataFrame({
                "id_credito": row_ids[idx_fecha_err],
                "regla": "formato_fecha_invalido",
                "motivo": fechas_cleaned[idx_fecha_err].apply(lambda val: f"fecha_originacion='{val}' no cumple con el formato YYYY-MM-DD o no es una fecha valida")
            }))

        # Consolidar todos los DataFrames de fallos
        if fallos_list:
            df_fallos = pd.concat(fallos_list, ignore_index=True)
        else:
            df_fallos = pd.DataFrame(columns=["id_credito", "regla", "motivo"])
            
        # Log de métricas por consola/log
        logger.info("  nulos: %d fallos", len(df_fallos[df_fallos['regla'].str.startswith('nulo_')]))
        logger.info("  monto rango: %d fallos", len(df_fallos[df_fallos['regla'].isin(['monto_no_numerico', 'monto_fuera_rango'])]))
        logger.info("  duplicados: %d fallos", len(df_fallos[df_fallos['regla'] == 'duplicado_id']))
        logger.info("  formato fecha: %d fallos", len(df_fallos[df_fallos['regla'] == 'formato_fecha_invalido']))
        
        return df_fallos
    except Exception as e:
        logger.error(f"Error al ejecutar las validaciones: {e}")
        
def generar_estadisticas(df: pd.DataFrame, df_fallos: pd.DataFrame) -> dict:
    """
    Genera estadísticas de calidad de datos a partir del DataFrame original y el DataFrame de fallos.
    """
    total_registros = len(df)
    total_fallos = len(df_fallos)
    total_validos = total_registros - total_fallos
    porcentaje_fallos = (total_fallos / total_registros) * 100 if total_registros > 0 else 0

    estadisticas = {
        "total_registros": total_registros,
        "total_fallos": total_fallos,
        "total_validos": total_validos,
        "porcentaje_fallos": porcentaje_fallos
    }

    logger.info("Estadísticas generadas: %s", estadisticas)
    return estadisticas

def imprimir_resumen_consola(stats: dict) -> None:
    """Imprime el resumen del reporte en la terminal."""
    print("\n" + "=" * 55)
    print("  REPORTE DE CALIDAD DE DATOS")
    print("=" * 55)
    print(f"  Total de registros evaluados:           {stats['total_registros']:>6,}")
    print(f"  Registros que pasaron todas las reglas: {stats['total_validos']:>6,}")
    print(f"  Total de fallos detectados:             {stats['total_fallos']:>6,}")
    print(f"  Porcentaje de fallos:             {stats['porcentaje_fallos']:>6,}")
    print("=" * 55)

def main() -> None:
    logger.info("=" * 50)
    # 1. Cargar el archivo CSV
    print("Cargando archivo CSV...")
    df = pd.read_csv(INPUT_FILE)
    print(f"Archivo cargado con {len(df)} registros.")
    
    # 2. Ejecutar validaciones
    print("Ejecutando validaciones...")
    df_fallos = ejecutar_validaciones(df)
    
    # 3. Generar estadísticas
    stats = generar_estadisticas(df, df_fallos)
    
    # 4. Guardar resultados
    print("Guardando estadísticas de calidad...")
    df_fallos.to_csv(FAILED_CSV, index=False)
    
    # 5. Resumen en consola
    imprimir_resumen_consola(stats)
    print(f"\nArchivos generados:")
    print(f"  - {FAILED_CSV}")
    
    logger.info("PIPELINE FINALIZADO EXITOSAMENTE")
    print("\n[OK] Pipeline de calidad completado.")
if __name__ == "__main__":
    main()