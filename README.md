## Supuestos y decisiones de diseño

1. **~5,000 créditos PYME** generados con datos sintéticos realistas usando Faker (`es_MX`).
2. El archivo fuente simula un corte mensual de originaciones — la dimensión de tiempo se construye a partir de `fecha_originacion`.
3. Cada crédito tiene exactamente un cliente, una fecha y una industria → modelo **estrella** clásico.
4. Se inyectan intencionalmente problemas de calidad (~10% de registros) para validar el pipeline.
5. **DuckDB** como motor analítico embebido (sin servidor, portable, ideal para desarrollo local).
6. **dbt** como framework de transformación — se implementó un runner ligero (`dbt_runner.py`) por limitaciones de instalación del CLI en Windows, pero la estructura del proyecto es 100% compatible con `dbt-duckdb`.

### Código generado y revisado

| Archivo | Código generado por IA | Modificaciones realizadas | Correcciones realizadas |
|---------|-------------------------|---------------------------|-------------------------|
| `scripts/generate_data.py` | Generación del script para crear el archivo `creditos_mes.csv` con datos sintéticos utilizando Faker. | Se modificó la ruta de salida del archivo CSV para adaptarla a la estructura del proyecto y se agregó un sistema de logging para registrar la ejecución. | Se corrigió el manejo de rutas de salida para garantizar la compatibilidad con la estructura del repositorio en Windows. |
| `scripts/pipeline.py` | Generó un pipeline que realizaba las validaciones de calidad de los datos y producía un reporte: `registros_fallidos.csv`, almacenados en `data/reports/`. | El código fue reestructurado debido a que utilizaba librerías que no eran las más adecuadas y realizaba múltiples iteraciones (`for`) sobre el conjunto de datos, lo que podría afectar el rendimiento con volúmenes mayores de información, implementando las validaciones mediante operaciones vectorizadas con Pandas | Se realizó un refactor completo del script original para mejorar su rendimiento, legibilidad, mantenibilidad y separación de responsabilidades. |
| `scripts/dbt_runner.py` | Generó el ejecutor de modelos dbt con resolución de `{{ ref() }}` y `{{ source() }}` sobre DuckDB, respetando el orden de dependencias entre modelos. | — | El mismo agente corrigió errores de inferencia de tipos de DuckDB al comparar columnas DOUBLE con strings vacíos, y ajustó el uso de `TRY_CAST` en el staging. |
| `dbt_project/models/` | Generó los 5 modelos SQL: `stg_creditos` (staging con limpieza), `dim_cliente`, `dim_tiempo`, `dim_industria` y `fact_originaciones`. | — | El agente corrigió el modelo staging para separar filtrado y casteo en CTEs independientes, evitando errores de conversión de tipos. |
| `schema.sql` | Generó el DDL documental del modelo estrella con PKs, FKs e índices sugeridos. | — | — |
| `kpis.sql` | Generó 10 queries analíticas de KPIs contra el modelo dimensional, usando `GROUP BY` + `HAVING` (KPI 5: índice de mora >20%) y `CASE WHEN` (KPIs 3 y 4: segmentación y conteo condicional). Incluye mediana, percentiles, distribución por canal y plazo promedio. | — | — |

---

## Cómo usé la IA

**Herramienta:** Claude Code (Claude Sonnet 5, modelo `claude-sonnet-5-20251001`).

**Qué me generó:**
- El script completo de generación de datos sintéticos (`generate_data.py`) con Faker y catálogos realistas.
- El pipeline de validación de calidad (`pipeline.py`) inicialmente con loops imperativos.
- La estructura completa del proyecto dbt (5 modelos SQL + runner + schema.sql).
- Las 10 queries de KPIs con `GROUP BY`/`HAVING`/`CASE WHEN`.
- La propuesta cloud y el diagrama del modelo estrella.

**Qué modifiqué:**
- `generate_data.py`: cambié las rutas de salida a `data/raw/` y añadí logging a archivo.
- `pipeline.py`: refactoricé completamente el código de validación para usar operaciones vectorizadas de `pandas`/`numpy` en lugar de iteraciones `for`, mejorando rendimiento y legibilidad.
- A partir del punto 3 en adelante, no realicé modificaciones — el código generado por la IA fue aceptado directamente.

**Qué tuve que corregir:**
- `generate_data.py`: el encoding de caracteres Unicode (`✓`) fallaba en la terminal Windows (cp1252).
- `pipeline.py` (v1): las rutas relativas no coincidían con la estructura real del proyecto.
- `dbt_runner.py` y `stg_creditos.sql`: DuckDB infería `monto` como `DOUBLE` y la comparación `monto != ''` causaba error de conversión de tipos. La IA lo resolvió usando `TRY_CAST` y separando filtrado de casteo en CTEs independientes.

### Ejemplo concreto de interacción con la IA

**Prompt enviado:**
> continúa con la parte 3, utiliza dbt

**Fragmento generado por la IA y aceptado** (`dbt_project/models/marts/fact_originaciones.sql`):

```sql
SELECT
    ROW_NUMBER() OVER (ORDER BY stg.id_credito) AS originacion_id,
    stg.id_credito,
    dim_cl.cliente_id,
    dim_ti.tiempo_id,
    dim_in.industria_id,
    stg.monto,
    stg.plazo_meses,
    stg.canal,
    stg.estatus_primer_pago
FROM {{ ref('stg_creditos') }} AS stg
LEFT JOIN {{ ref('dim_cliente') }}   AS dim_cl
    ON stg.id_cliente = dim_cl.id_cliente
LEFT JOIN {{ ref('dim_tiempo') }}    AS dim_ti
    ON stg.fecha_originacion = dim_ti.fecha_originacion
LEFT JOIN {{ ref('dim_industria') }} AS dim_in
    ON stg.industria = dim_in.nombre_industria
```

**Decisión:** Aceptado sin modificaciones. El modelo sigue el patrón estándar dbt de construir la tabla de hechos mediante JOINs a las dimensiones usando surrogate keys, con `ROW_NUMBER()` para generar la PK. La única corrección posterior fue en el modelo staging (no en este archivo) para manejar la inferencia de tipos de DuckDB, que la misma IA diagnosticó y resolvió al ejecutar el pipeline.

---

## Modelo dimensional (Star Schema)

```
                              ┌──────────────────────┐
                              │    dim_tiempo         │
                              │──────────────────────│
                              │ PK  tiempo_id (INT)   │◄────┐
                              │     fecha_originacion │     │
                              │     anio, mes, dia    │     │
                              │     nombre_mes        │     │
                              │     trimestre         │     │
                              │     es_fin_de_semana  │     │
                              └──────────────────────┘     │
                                                           │
┌──────────────────────┐          ┌────────────────────────────────────┐
│    dim_cliente       │          │        fact_originaciones          │
│──────────────────────│          │────────────────────────────────────│
│ PK  cliente_id (INT) │◄─────────│ FK  cliente_id                     │
│     id_cliente       │          │ FK  tiempo_id          ────────────┤
│     nombre_cliente   │          │ FK  industria_id                    │
└──────────────────────┘          │     id_credito (business key)       │
                                  │     monto, plazo_meses              │
┌──────────────────────┐          │     canal, estatus_primer_pago      │
│    dim_industria     │          └────────────────────────────────────┘
│──────────────────────│                        │
│ PK  industria_id(INT)│◄───────────────────────┘
│     nombre_industria │
└──────────────────────┘
```

**Relaciones:**
- `fact_originaciones.cliente_id` → `dim_cliente.cliente_id` (N:1)
- `fact_originaciones.tiempo_id` → `dim_tiempo.tiempo_id` (N:1)
- `fact_originaciones.industria_id` → `dim_industria.industria_id` (N:1)

**Surrogate keys:** generadas con `ROW_NUMBER()` para cliente e industria; `YYYYMMDD` como INTEGER para tiempo.

---

## Estructura del proyecto dbt

```
dbt_project/
  dbt_project.yml              # Configuración del proyecto
  profiles.yml                 # Conexión DuckDB
  models/
    staging/
      stg_creditos.sql         # Limpieza, tipado, filtrado y deduplicación
    marts/
      dim_cliente.sql          # Dimensión de clientes
      dim_tiempo.sql           # Dimensión de tiempo (atributos calendario)
      dim_industria.sql        # Dimensión de industrias
      fact_originaciones.sql   # Tabla de hechos (joins a dimensiones)
  macros/                      # (reservado para macros reutilizables)
```

**Flujo de transformación:**
```
raw.raw_creditos  →  staging.stg_creditos  →  ┬─ marts.dim_cliente
                                               ├─ marts.dim_tiempo
                                               ├─ marts.dim_industria
                                               └─ marts.fact_originaciones
```

---

## Propuesta Cloud — De local a producción

> **¿Cómo pasarías este pipeline local a producción en la nube?**

| Capa | Servicio (GCP) | Justificación |
|------|---------------|---------------|
| **Ingesta** | Cloud Storage + Cloud Functions | El CSV mensual se deposita en un bucket GCS. Una Cloud Function (trigger por evento) lo valida y carga a BigQuery. |
| **Almacenamiento** | BigQuery | Data warehouse serverless con soporte nativo para modelos estrella, particionado por fecha y clustering por `industria_id`. Reemplaza a DuckDB en producción. |
| **Transformación** | dbt Cloud + dbt-bigquery | Los mismos modelos dbt del proyecto se ejecutan sobre BigQuery. dbt Cloud orquesta las ejecuciones programadas y notifica fallos. |
| **Orquestación** | Cloud Composer (Airflow) | Un DAG semanal: ingesta GCS → dbt Cloud job → refresh de looker. Alternativa ligera: Cloud Scheduler + Cloud Run jobs. |
| **Visualización** | Looker Studio | Dashboard conectado directamente a las tablas de BigQuery (`marts.fact_originaciones` + dimensiones). KPIs con filtros por industria, mes y canal. |

**¿Por qué GCP?** BigQuery separa cómputo y almacenamiento, escala a cero cuando no hay queries, y su integración con dbt es nativa. Para un equipo pequeño, Cloud Run + dbt CLI es suficiente sin necesidad de Airflow.

---

## Cómo usar este proyecto

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Generar datos sintéticos
python scripts/generate_data.py

# 3. Ejecutar pipeline completo (validación + dbt)
python scripts/pipeline.py
```

**Salidas:**
- `data/raw/creditos_mes.csv` — Datos sintéticos generados
- `data/reports/registros_fallidos.csv` — Registros que no pasaron calidad
- `data/kapital_creditos.duckdb` — Base DuckDB con el modelo estrella

---

## Bonus — Docker Compose + Grafana

Levanta PostgreSQL con el modelo estrella y un dashboard de Grafana pre-configurado con todos los KPIs.

```bash
# 1. Generar datos sintéticos (si no existen)
python scripts/generate_data.py

# 2. Levantar los servicios
cd docker
docker compose up -d

# 3. Acceder a Grafana
#    URL:  http://localhost:3000
#    User: admin / Pass: admin
#    Dashboard: "Kapital — Dashboard de Originación y Cobranza"
```

**Servicios:**

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| PostgreSQL 16 | `5432` | Modelo estrella con datos cargados automáticamente |
| Grafana 11.5 | `3000` | Dashboard con 15 paneles de KPIs |

**Paneles del dashboard:**
- Stats: Total originado, total créditos, ticket promedio, mediana, P25, P75
- Donut: % primer pago, distribución por canal
- Barras: Top 5 industrias, índice de mora, ticket por segmento
- Tablas: Tickets por canal, plazo promedio por industria
- Time series: Monto originado por día, % pago a tiempo por día

**Arquitectura Docker:**
```
docker compose up
      │
      ├─ postgres:16 ─── initdb.d/
      │     └─ 01_create_tables.sql         (DDL + funciones try_cast_*)
      │
      ├─ etl (python:3.12-slim)
      │     ├─ Espera activa (hasta 60s) a que las tablas existan
      │     ├─ Crea funciones try_cast_date/double/integer (PL/pgSQL)
      │     ├─ Trunca tablas → carga CSV → staging → dims → fact
      │     └─ Verifica conteo de filas en cada tabla
      │
      └─ grafana:11 ─── provisioning/
            ├─ datasources/postgres.yml      (conexión automática)
            └─ dashboards/
                  ├─ dashboard.yml           (provider)
                  └─ kpis_dashboard.json     (15 paneles KPIs)
```

**Notas técnicas:**
- Los datos sintéticos incluyen ~50 fechas inválidas y ~78 montos negativos. El ETL usa funciones PL/pgSQL `try_cast_*` (equivalentes a `TRY_CAST` de DuckDB) para convertirlos a `NULL` sin romper la transformación. Los registros inválidos se filtran downstream.
- Las unidades del dashboard usan `currencyUSD` (nativo de Grafana) con formato automático: `$2.48 M`, `$11.2 B`.
- Para reconstruir desde cero: `docker compose down -v && docker compose up -d`.

**Dashboard — vista previa de paneles:**

| Sección | Paneles |
|---------|---------|
| Resumen General | `$11.2 B` Total originado · `4,514` Créditos · `$2.47 M` Ticket promedio · Donut % pago |
| Análisis por Industria | Top 5 industrias (barras horizontales) · Índice de mora >20% con thresholds verde/amarillo/rojo |
| Segmentación y Canales | Ticket por segmento (Micro→Grande) · Donut distribución por canal · Tabla tickets min/max |
| Estadísticas | Mediana `$2.46 M` · P25 `$1.21 M` · P75 `$3.72 M` · Tabla plazo promedio por industria |
| Tendencia | Time series: monto diario + % pago a tiempo diario (suavizado) |