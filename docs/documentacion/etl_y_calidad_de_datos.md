# C. ETL y calidad de datos

> **Borrador.** Los conteos «antes» vienen del perfilado de la hoja `Base De Datos`; los conteos «después» se completan al correr el ETL. «Pregunta» marca una decisión abierta y «por verificar», un dato por confirmar contra el Excel.

## C1. Proceso ETL y herramienta

**Herramienta: Python con pandas y SQLAlchemy** (pandas es una librería para manipular tablas; SQLAlchemy conecta con PostgreSQL).

Por qué Python:
- El Excel exige lógica que SQL y Power Query manejan mal: desagregar 18 pares de columnas, normalizar texto con expresiones regulares, calcular el seudónimo de operarios y percentiles.
- El código queda en el repositorio, se versiona y se puede repetir desde cero.
- El equipo ya tiene el proyecto configurado con Python (`pyproject.toml`).

Etapas:

| Etapa | Qué hace | Salida |
|---|---|---|
| Extract | Lee `Base De Datos` (encabezado en la fila 9) y `TABLA CODIGOS` | DataFrames en memoria; copia cruda en `stg_base_datos` |
| Transform | Aplica las reglas R01 a R12 (C2) | DataFrames de dimensiones y hechos |
| Load | Carga dimensiones y luego hechos en una transacción | Tablas del esquema `dw` |
| Validate | Ejecuta las verificaciones de calidad y la conciliación (C3) | Informe en consola y tabla `etl_log` |

Estructura prevista en el repositorio: `etl/extract.py`, `etl/transform.py`, `etl/load.py`, `etl/validate.py` y `etl/run.py`; el DDL va en `sql/`.

## C2. Reglas de limpieza y su efecto

Cada regla se mide con conteos antes y después. Donde la columna «Después» dice *medir*, el ETL imprimirá el valor y se copia aquí.

| Regla | Qué hace | Antes | Después |
|---|---|---|---|
| R01 | Clasificar cada fila en registro de producción, día sin producción o fila de subcódigo (A2.2) | 8.208 filas | 4.758 producción; 1.863 días sin producción; 1.587 sin horas (1.354 con paros, 233 sin paros) |
| R02 | Eliminar duplicados exactos en producción y días sin producción. En filas de subcódigo, conservar salvo evidencia de duplicado. **Pregunta:** ¿es correcto conservarlos? | 42 duplicados exactos (17 producción, 8 días sin producción, 17 subcódigo) | *medir* |
| R03 | Descartar filas sin horas y sin paros | 233 | 0 |
| R04 | Descartar columnas inservibles: `Unidades producidas cada minuto`, `Display por paca` (100 % vacías) y `Unidad por display` (solo textos de turno) | 3 columnas | 0 |
| R05 | Normalizar `Turno` a la dimensión de turnos; vacíos y «No aplica» → «Sin dato» | 7 formatos, 3.912 vacíos | 6 turnos más «Sin dato» |
| R06 | Normalizar `Referencia` (espacios, erratas «Alocdor», «Stilo Kids»); vacíos y «No aplica» → «Sin referencia» | 52 valores | *medir* |
| R07 | Mapear `Tipo de paro` del catálogo antiguo al vigente (tabla abajo) | 1.463 filas con formato antiguo | 0 |
| R08 | Unificar subcódigos `4.x` con `5.x` por nombre; conservar «Sin especificar» | 945 con `4.x` | 0 con `4.x` |
| R09 | Desagregar las 18 columnas de código: una fila de `fact_paro` por cada celda con minutos mayores que cero | 16.532 celdas con paro | *medir* (menor tras R02) |
| R10 | Unificar operarios (variantes de nombre), sustituir marcadores «No» y «No aplica» por «Sin operario» y reemplazar el nombre por un seudónimo | 34 valores, 545 marcadores | *medir*; 0 nombres reales en la base |
| R11 | Marcar valores sospechosos sin borrarlos: 1 fila con 32 `Horas no trabajadas` (se limita a 24), 9 filas con suma mayor a 24, 3 registros con paro mayor que las horas, 27 con pacas en cero y 2 sin pacas | 1 + 9 + 3 + 27 + 2 casos (algunos pueden coincidir en una misma fila) | *medir* filas con `flag_calidad` distinto de `ok` |
| R12 | Reemplazar `Fecha`, `Mes` y `Año` por la dimensión de fecha | 3 columnas | 1 llave |

Mapeo previsto de R07 (catálogo antiguo → vigente). Las filas marcadas «por verificar» no tienen equivalente evidente:

| `Tipo de paro` antiguo | Filas | Código vigente |
|---|---|---|
| 17. PARO DE MAQUINA | 952 | por verificar |
| 9. FALTA DE PROGRAMACIÓN (PLANEACIÓN) | 251 | 18 (paro por ventas o falta de programación) (por verificar) |
| 16. PARO POR PROCESO ANTERIOR | 94 | por verificar |
| 10. PARO POR MATERIA PRIMA O MATERIAL DE EMPAQUE NO CONFORME | 66 | 12 |
| 6. FALTA DE MATERIALES O MATERIAS PRIMAS | 61 | 14 |
| 15. APROBACION DE LABORATORIO (MICROBIOLOGIA) | 24 | 13 |
| 3. AJUSTE ELECTRICO O DE SERVICIOS (AIRE, CALDERA, GAS) | 5 | 3 |
| 5. AISLAMIENTO/CAMBIO DE PRODUCTO | 5 | 7 |
| 11. LIMPIEZA NO PROGRAMADA | 3 | 6 |
| 4. AJUSTE DE OPERACIÓN | 2 | 5 |

## C3. Conciliación de totales

Objetivo: demostrar que lo cargado coincide con la fuente, o explicar cada diferencia.

Totales de la fuente (hoja `Base De Datos`, todas las filas):

| Medida | Fuente |
|---|---|
| Pacas producidas | 378.778 |
| Horas trabajadas | 38.063,4 |
| Horas no trabajadas | 41.519,8 |
| Horas de paro (`Tiempo de Paro`) | 8.449,7 |

La suma de las 18 columnas de horas por código es igual al total de `Tiempo de Paro` (diferencia 0), así que el total de `fact_paro` debe cuadrar con esa cifra.

Comparación a presentar tras cargar (una fila por medida, desagregada por año y por máquina):

| Medida | Fuente | Destino | Diferencia | Explicación |
|---|---|---|---|---|
| Pacas | 378.778 | *medir* | | Se espera una diferencia igual a las pacas de los duplicados eliminados |
| Horas trabajadas | 38.063,4 | *medir* | | Idem |
| Horas no trabajadas | 41.519,8 | *medir* | | Duplicados y el ajuste de la fila de 32 h a 24 h (−8 h) |
| Horas de paro | 8.449,7 | *medir* | | Duplicados eliminados |

Criterio: diferencia menor a 0,01 en cada medida o diferencia explicada fila por fila. Cada eliminación de R02 se registra en `etl_log` con su `fila_fuente` para poder sumarla.

## C4. Ejecución reproducible desde cero

Pasos para reproducir:
1. Crear una base vacía (con Docker Compose, ver K).
2. Ejecutar el DDL de `sql/` (esquema `dw`).
3. Ejecutar `python -m etl.run`.

Cómo se garantiza que dos corridas den el mismo resultado:
- El ETL abre una transacción, vacía las tablas del esquema `dw` con `TRUNCATE … RESTART IDENTITY CASCADE` y carga todo. Si algo falla, la transacción se revierte y la base queda como estaba.
- Las claves sustitutas se generan en orden determinista (por orden de aparición en el Excel), de modo que las mismas entradas producen las mismas claves.
- El seudónimo de operarios usa una sal definida en `.env`, de modo que es estable entre corridas y no depende de nombres reales.
- Prueba de aceptación: borrar el esquema, correr el ETL dos veces y comprobar que los conteos y totales de C3 no cambian.
