# E. Power BI

> **Borrador.** Pendiente de revisión del equipo. Las medidas DAX aún no se han probado en Power BI y deben validarse con datos reales.

## E1. Conexión a la base de datos

- Origen: PostgreSQL, esquema `dw`, con el rol de solo lectura `bi_reader` (D1). No se usa el Excel.
- Modo: **Import** (Power BI copia los datos al modelo). Con unas 16.500 filas es rápido, y el análisis histórico no necesita datos en vivo. DirectQuery se descarta porque no aporta aquí y limita funciones de DAX.
- Servidor `localhost` y puerto publicado del contenedor. La contraseña no se guarda en el repositorio: Power BI la pide al abrir.
- Tablas que se importan: las seis dimensiones, `fact_produccion`, `fact_paro`, `fact_tiempo_no_programado` y la vista `vw_oee_turno`. `fact_lectura_hora` no se importa; es para Grafana.

## E2. Modelo semántico y DAX

### Relaciones

Todas de uno a muchos, de la dimensión al hecho, con filtro en un solo sentido:

| Dimensión (uno) | Hechos (muchos) |
|---|---|
| `dim_fecha[fecha_key]` | `fact_produccion`, `fact_paro`, `fact_tiempo_no_programado` |
| `dim_maquina[maquina_key]` | Los tres |
| `dim_turno[turno_key]` | `fact_produccion`, `fact_paro` |
| `dim_referencia[referencia_key]` | `fact_produccion`, `fact_paro` |
| `dim_operario[operario_key]` | `fact_produccion`, `fact_paro` |
| `dim_causa_paro[causa_key]` | `fact_paro`, `fact_tiempo_no_programado` |

Se marca `dim_fecha` como tabla de fechas por la columna `fecha`. La jerarquía de causas se crea en `dim_causa_paro` (área de impacto → código → subcódigo) y la de fechas en `dim_fecha`.

### Medidas

```dax
Pacas = SUM ( fact_produccion[pacas_producidas] )

Horas trabajadas = SUM ( fact_produccion[horas_trabajadas] )

Horas paro = SUM ( fact_paro[horas_paro] )

Horas paro programado =
    CALCULATE ( [Horas paro], dim_causa_paro[tipo_paro] = "Programado" )

Disponibilidad =
    DIVIDE ( [Horas trabajadas] - [Horas paro],
             [Horas trabajadas] - [Horas paro programado] )

-- Inteligencia de tiempo (requisito del enunciado)
Pacas año anterior =
    CALCULATE ( [Pacas], SAMEPERIODLASTYEAR ( dim_fecha[fecha] ) )

Variación vs año anterior % =
    DIVIDE ( [Pacas] - [Pacas año anterior], [Pacas año anterior] )

Pacas acumuladas año = TOTALYTD ( [Pacas], dim_fecha[fecha] )

-- Pareto: porcentaje acumulado de horas de paro por código
Pareto % acumulado =
VAR horasActual = [Horas paro]
VAR codigos     = ALLSELECTED ( dim_causa_paro[nombre_codigo] )
VAR acumulado   =
    SUMX ( FILTER ( ADDCOLUMNS ( codigos, "@h", [Horas paro] ), [@h] >= horasActual ), [@h] )
RETURN
    DIVIDE ( acumulado, CALCULATE ( [Horas paro], ALLSELECTED ( dim_causa_paro ) ) )
```

**Rendimiento y OEE.** Se leen de `vw_oee_turno` (nivel fecha × máquina × turno), donde el SQL ya calculó las horas de operación y las pacas objetivo. En Power BI queda:

```dax
Rendimiento = DIVIDE ( SUM ( vw_oee_turno[pacas] ), SUM ( vw_oee_turno[pacas_objetivo] ) )
Calidad     = 1   -- supuesto declarado (A5, I10)
OEE         = [Disponibilidad] * [Rendimiento] * [Calidad]
```

**Pregunta:** este es el punto más delicado del proyecto porque exige repartir los paros entre registros (la vista debe asignar a cada fecha, máquina y turno sus paros). Si el tiempo aprieta, la alternativa es calcular el rendimiento como pacas por hora trabajada contra el objetivo y explicarlo como aproximación.

## E3. Informe: páginas, segmentaciones y drill

| Página | Contenido | Segmentaciones | Drill |
|---|---|---|---|
| Resumen | Tarjetas: pacas, horas trabajadas, horas de paro, utilización, OEE. Línea de pacas por mes | Año, máquina | De año a mes a día |
| Producción | Barras de pacas por máquina con el año anterior al lado (I01, I02). Ranking de turnos y referencias | Año, mes, máquina, turno, referencia | Máquina → referencia |
| Paros | Pareto de causas (E4). Matriz de horas por máquina y código | Año, máquina, tipo de paro | Área de impacto → código → subcódigo |
| OEE | Disponibilidad, rendimiento, OEE por máquina y mes | Año, máquina | Mes → turno |

Navegación: botones de página en la parte superior de cada una. Drill-down: se activa en los visuales de la página «Paros» sobre la jerarquía de `dim_causa_paro`.

## E4. Pareto de causas de paro

Gráfico combinado de columnas y línea:
- Eje X: `dim_causa_paro[nombre_codigo]`, ordenado por horas de paro de mayor a menor.
- Columnas: `[Horas paro]`.
- Línea (eje secundario): `[Pareto % acumulado]`.

## E5. Diseño y narrativa

La narrativa que sugieren los datos, a validar tras cargar el modelo (cifras del perfilado del Excel):

1. **Buena parte de la capacidad no se usa.** Hay 41.519,8 h sin trabajar frente a 38.063,4 h trabajadas (utilización de 47,8 %). Hay que revisar los motivos de los 1.863 días sin producción antes de concluir si es demanda, falta de materia prima u otra causa.
2. **El tiempo perdido se concentra en pocas causas.** Alimentación y aseo (código 16), ajuste operativo (05) y limpieza por derrame (06) suman el 63,5 % de las horas de paro; con la pausa activa (17) llegan al 72 %.
3. **Una parte importante del paro es programada.** Los códigos 15, 16 y 17 suman 2.886,8 h, el 34,2 % del paro total. Mejorar la disponibilidad real exige mirar el resto: ajuste operativo, limpieza y fallas.
4. **Las fallas electromecánicas (código 01) pesan poco en horas**: 323,9 h en 467 casos, el 3,8 % del paro. **Por verificar:** si, aun así, su costo (repuestos, urgencia) justifica un plan de mantenimiento; con I13 e I14 se puede ver su frecuencia y duración.

Recomendaciones posibles para gerencia: revisar la programación de las líneas, estandarizar los ajustes y la limpieza entre referencias, y registrar la meta por hora y los defectos para que el OEE sea completo.

## E6. Formato versionable

**PBIP** (Power BI Project): guarda el modelo y los informes como archivos de texto (carpeta `.SemanticModel` en formato TMDL y carpeta `.Report`). Git puede mostrar las diferencias línea por línea, a diferencia del `.pbix`, que es un binario comprimido. Se guarda en `powerbi/`. Requiere activar la vista previa «Power BI Project (.pbip)» en Opciones. **Por verificar:** que la versión de Power BI Desktop la tenga.
