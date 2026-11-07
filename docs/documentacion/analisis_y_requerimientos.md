# A. Análisis y requerimientos

> Sección A del PDF final. Cada apartado lleva el código del punto de entregable (A1, A2…). Documento en borrador.

## A1. Usuarios y preguntas de negocio

*Qué pide el enunciado: Lista de usuarios de la solución (gerencia, supervisores, mantenimiento) y las preguntas que
cada uno necesita responder.*

Se cuenta con los siguientes usuarios. Cada uno cuenta con sus preguntas correspondientes

> Nota: Las operarias son consideradas partes del proceso y las mejoras que se implementen a partir de este proyecto 
> estarán enfocadas en mejorar el proceso de captación de datos (por parte de estas y directamente desde las máquinas) 

- **Directivos**: Son aquellos usuarios dueños de la empresa, los cuales están enfocados en conocer el 
  comportamiento y rendimiento comercial de la misma. Su enfoque principal consiste en el seguimiento de los 
  objetivos de producción, la rentabilidad de la operación y la toma de decisiones para optimizar estos procesos.
  - 
    - Analizar tendencias, turnos, referencias y datos consecuentes a estos de la data suministrada
    - Identificar las causas principales de paros para decidir inversiones y planes de mantenimiento
- **Supervisores**: Constituyen los líderes de la operación y juegan un rol intermedio entre esta y los directivos. 
  Se encargan de verificar que la operación en sí cumpla las metas dadas por la dirección de la empresa.
  - Ver comportamiento de las líneas de producción en la escala más cercana a tiempo real posible (Granularidad muy 
    fina)
  - Recibir alertas cuando haya problemas con los indicadores, sin tener que esperar a un informe mensual
- **Mantenimiento**: Son los operarios a cargo de atender novedades relacionadas con las líneas de producción. Se 
  encargan de hacer cambios en las materias primas, solucionar problemas y hacer tareas de limpieza y reparación de 
  las máquinas.
  - Ver comportamiento de las líneas de producción en la escala más cercana a tiempo real posible (Granularidad muy 
    fina)

> **Borrador.** Las preguntas siguientes son un punto de partida y se pueden ajustar con los usuarios reales.

**Preguntas de negocio por usuario**

| # | Usuario | Pregunta que necesita responder | Herramienta |
|---|---|---|---|
| Q1 | Directivos | ¿Qué causas de paro suman más horas por año y cómo cambió cada una entre 2022 y 2024? | Power BI |
| Q2 | Directivos | ¿Cómo se compara la producción de cada máquina en el primer trimestre de 2025 con el mismo periodo de 2024? | Power BI |
| Q3 | Directivos | ¿Qué turnos y referencias rinden más y pierden menos tiempo por paros no programados? | Power BI |
| Q4 | Directivos | ¿Qué parte de la capacidad se usa de verdad (horas trabajadas frente a horas sin programación) y por qué motivos no se programa? | Power BI |
| Q5 | Directivos | ¿Qué máquina justifica una inversión o un plan de mantenimiento por su historial de fallas (código 01) y de ajuste operativo (código 05)? | Power BI |
| Q6 | Supervisores | ¿Qué máquina está parada ahora y desde cuándo? | Grafana |
| Q7 | Supervisores | ¿Cuánto paro no programado lleva cada línea en la última hora y con qué causa? | Grafana |
| Q8 | Supervisores | ¿La producción por hora del turno va por encima o por debajo de lo habitual para esa máquina? | Grafana |
| Q9 | Mantenimiento | ¿Qué subcódigos (dosificación de pintura, transfer y pisador de tapa, video jet…) concentran más tiempo de falla y de ajuste? | Power BI y Grafana |
| Q10 | Mantenimiento | ¿Con qué frecuencia ocurren las fallas (código 01) por máquina y cuánto dura cada una en promedio? | Power BI |

Usuarios descartados como usuarios de los tableros: las operarias son parte del proceso (registran los datos), como se indica en la nota anterior. Su tratamiento como datos personales se desarrolla en G4. El coordinador de mantenimiento, que presenta el informe mensual según el P-MTO-22, usa los mismos tableros que Mantenimiento y Directivos. **Pregunta:** ¿se lista como usuario aparte?

## A2. Diagnóstico de la fuente

> **Borrador.** Todos los conteos salen de perfilar la hoja `Base De Datos` del archivo `SEGUIMIENTO TEMPERAS Y VINILOS Actividad.xlsm` (5 nov 2026) y se pueden repetir con el ETL. «Por verificar» marca lo que falta confirmar en el Excel.

### A2.1 Estructura del libro

El libro tiene la macro de registro y varias hojas de análisis:

| Hoja | Para qué sirve | Observación |
|---|---|---|
| `Registro` | Formulario «hora a hora» con los botones Ingreso total, Ingreso subcódigo y Limpiar (P-MTO-22 4.1.5) | Es la entrada manual de datos |
| `Base De Datos` | Tabla histórica de registros | 8.208 filas y 58 columnas; el encabezado está en la fila 9 |
| `Base de datos de Sub codigos` | Registro de subcódigos | 1.253 filas; no se perfiló; **por verificar:** si duplica lo que ya está en `Base De Datos` |
| `TABLA CODIGOS` | Catálogo de áreas de impacto, códigos 01 a 17 y subcódigos de los códigos 1, 3 y 5 | Es la base de la dimensión de causas de paro |
| `Tiempos`, `Calculadora de tiempos` | Cálculo de horas, meta por hora, producción ideal y eficiencia | Sus valores están en cero; no alimentan la base |
| `TD_*`, `prodMaquina`, `prodAño`, `prodCodigo`, `fallaMecanica`, `novPotencia`, `ajusteOperativo` | Tablas dinámicas y gráficos del informe mensual | Son los indicadores que hay que reproducir (A4) |

`Base De Datos` cubre del 1 de enero de 2022 al 28 de marzo de 2025: 1.654 filas en 2022, 2.891 en 2023, 3.129 en 2024 y 534 en 2025 (año incompleto). Las filas por máquina son Vinilos_4 con 2.585, Vinilos_3 con 2.491, Vinilos_1 con 1.877 y Vinilos_2 con 1.255.

### A2.2 Qué representa una fila

No todas las filas son el mismo tipo de evento:

| Tipo de fila | Cómo se reconoce | Filas | Qué contiene |
|---|---|---|---|
| Registro de producción | `Horas trabajadas` > 0 | 4.758 | Pacas, horas trabajadas, turno, operario, referencia y los paros del registro |
| Día sin producción | `Horas no trabajadas` > 0 y sin horas trabajadas | 1.863 | Horas sin programación (en general 24, 16 u 8) y el motivo en `Tipo de paro` |
| Fila sin horas | Sin horas trabajadas ni no trabajadas | 1.587 | 1.354 traen paros (799,2 h de las 8.449,7 h totales); 233 no traen paros |

Las 1.354 filas sin horas con paros corresponden al botón «Ingreso subcódigo»: agregan paros a un registro que ya existe. 1.334 de ellas coinciden en fecha, máquina y turno con un registro de producción. Por eso el paro de un turno puede estar repartido en varias filas.

Los paros están en formato ancho. Cada fila tiene 18 pares de columnas, `Codigo de paro N` (minutos) y `Codigo N en horas` (minutos divididos por 60). Hay 16.532 celdas con paro mayor que cero. Las columnas `Tiempo de Paro` y las 18 de horas son internamente consistentes: en ninguna fila difieren (0 discrepancias de 8.208).

### A2.3 Problemas de calidad de datos

| # | Hallazgo | Conteo | Impacto | Tratamiento previsto (se detalla en C2) |
|---|---|---|---|---|
| P1 | `Unidades producidas cada minuto` y `Display por paca` están 100 % vacías | 8.208 de 8.208 | No hay meta de producción en los datos; el rendimiento del OEE no se puede calcular contra una meta | Calcular un objetivo histórico (ver A3, I09) |
| P2 | `Unidad por display` contiene textos de turno y ningún número | 687 filas con turno desplazado; 0 numéricas | Columna inservible | Descartarla |
| P3 | Producción sin turno, operario ni referencia | 2022: 958 de 958; 2023: 1.261 de 1.591 sin turno | No se puede analizar por turno ni referencia antes de 2024 | Usar el miembro «Sin dato» y declararlo como limitación |
| P4 | `Turno` con formatos distintos | 7 formatos más 3.912 vacíos | Turnos de 8 h, jornadas de 10,5 h y de 12 h mezclados | Normalizar en una dimensión de turnos |
| P5 | `Tipo de paro` mezcla dos catálogos | 2.963 con formato `[NN]`, 1.463 con formato `N.` antiguo, 3.782 vacíos | Los motivos no son comparables entre años | Mapear el catálogo antiguo al vigente |
| P6 | `Subcodigo 5` con dos numeraciones y valor por defecto | 945 con prefijo `4.x` (antiguo), 2.149 con `5.x`, 5.020 «Sin especificar» | El detalle del código 05 se parte en dos | Unificar por nombre y conservar «Sin especificar» |
| P7 | Referencias con variantes de escritura | 52 valores; 51 al ignorar espacios y mayúsculas; erratas como «Alocdor» y «Stilo Kids» | Una referencia aparece como dos | Normalizar contra una lista corregida |
| P8 | `Operario` con marcadores y variantes | 34 valores; «No» y «No aplica» en 545 filas; pares como «Marcela» y «Marcela C.» | Posibles personas duplicadas | Unificar y seudonimizar (**por verificar:** las variantes) |
| P9 | Duplicados exactos | 42 filas (17 de producción, 8 de días sin producción, 17 sin horas) | Sobreconteo de pacas y horas | Eliminar en producción y días sin producción; revisar los de subcódigos |
| P10 | Valores fuera de rango | 1 fila con 32 `Horas no trabajadas`; 9 filas con horas trabajadas más no trabajadas mayores a 24; 3 registros con paro mayor que las horas trabajadas | Distorsiona disponibilidad | Conservar y marcar con una bandera de calidad |
| P11 | Pacas en cero o ausentes con horas trabajadas | 27 en cero, 2 sin dato | Rendimiento sesgado | Conservar y marcar |
| P12 | Códigos fuera del catálogo del P-MTO-22 | Los datos usan `[18] Paro de máquina por ventas` (605 filas) y `[19] No aplica` (2.282); el procedimiento lista 17 códigos pero habla de «1 al 18» | Hay códigos sin definición oficial | Agregarlos a la dimensión como «fuera del P-MTO-22» |
| P13 | Datos personales en texto libre | `Operario` (34 nombres) y `Personal involucrado` (incluye nombres completos de personal de mantenimiento) | Riesgo de privacidad en un repositorio | Seudonimizar (G4) |

### A2.4 Limitaciones del esquema de reporte actual

- **No hay OEE ni sus componentes.** El libro no calcula disponibilidad, rendimiento ni calidad. La hoja de tiempos tiene meta por hora y producción ideal en cero.
- **No existe una meta registrada.** Las columnas de unidades por minuto y display por paca están vacías, así que nada se compara contra un objetivo.
- **El reporte es mensual y manual.** Las operarias llenan el formato en papel, mantenimiento lo transcribe y de ahí salen las tablas dinámicas. Un paro tarda semanas en volverse visible.
- **La estructura ancha limita el análisis.** Cada paro vive en una de 18 columnas, lo que hace difícil el drill-down por subcódigo, turno o referencia, y mezcla registros con subcódigos adicionales.
- **La jerarquía de causas está incompleta.** Solo los códigos 1, 3 y 5 tienen subcódigos, con dos numeraciones históricas.
- **No hay control de calidad en la captura.** Turnos, referencias y operarios se escriben a mano, de ahí las variantes y los duplicados.
- **Una sola vista para todos.** No hay una vista casi en tiempo real ni alertas para supervisión.

## A3. Catálogo de indicadores

> **Borrador.** Las metas y umbrales son provisionales hasta calcular los percentiles históricos con el ETL. **Pregunta:** ¿se aceptan o se prefieren otros? Las fórmulas usan los nombres del modelo de B.

Definiciones previas:
- **Horas de operación** = horas trabajadas − horas de paro total.
- **Horas planificadas** = horas trabajadas − horas de paro programado. Paro programado son los códigos 15, 16 y 17 (área «Paro programado» de `TABLA CODIGOS`). **Pregunta:** ¿el 04 Mantenimiento preventivo también cuenta como programado?
- Los paros ocurren dentro de las horas trabajadas: 8.449,7 h de paro frente a 38.063,4 h trabajadas, y solo 3 registros tienen más paro que horas trabajadas.

| Cód. | Indicador | Fórmula | Unidad | Granularidad | Meta o umbral | Fuente | Usuario |
|---|---|---|---|---|---|---|---|
| I01 | Producción | Suma de `pacas_producidas` | pacas | Máquina, mes (drill a día, turno, referencia) | Sin meta; se compara con el año anterior | `fact_produccion` | Directivos |
| I02 | Variación de producción frente al año anterior | (Producción − Producción mismo periodo año anterior) / Producción año anterior | % | Máquina, mes | ≥ 0 % | `fact_produccion` | Directivos |
| I03 | Horas trabajadas | Suma de `horas_trabajadas` | h | Máquina, mes | Sin meta | `fact_produccion` | Directivos |
| I04 | Horas de paro | Suma de `horas_paro` | h | Máquina, mes, causa | Sin meta | `fact_paro` | Directivos, Mantenimiento |
| I05 | % de horas de paro por código | Horas del código / horas de paro totales | % | Máquina, mes, código | Sin meta; sirve de Pareto | `fact_paro` | Directivos, Mantenimiento |
| I06 | Detalle de códigos 01, 03 y 05 | Horas de paro de esos códigos por subcódigo | h | Máquina, mes, subcódigo | Sin meta | `fact_paro` | Mantenimiento |
| I07 | Utilización de capacidad | Horas trabajadas / (horas trabajadas + horas no trabajadas) | % | Máquina, mes | Referencia histórica global: 47,8 % | `fact_produccion`, `fact_tiempo_no_programado` | Directivos |
| I08 | Disponibilidad | Horas de operación / horas planificadas | % | Máquina, mes, turno | Provisional: percentil 75 histórico | `fact_produccion`, `fact_paro` | Directivos, Supervisores |
| I09 | Rendimiento | Pacas / (horas de operación × pacas por hora objetivo), con tope de 100 % | % | Máquina, mes, turno | Provisional: 100 % del objetivo | `fact_produccion`, `fact_paro`, objetivo histórico | Directivos, Supervisores |
| I10 | Calidad | Supuesto de 100 % (sin datos de unidades rechazadas) | % | Máquina, mes | Supuesto declarado | No aplica | Directivos |
| I11 | Horas perdidas por calidad | Horas de paro de los códigos 11, 12 y 13 | h | Máquina, mes | Sin meta | `fact_paro` | Directivos |
| I12 | OEE | I08 × I09 × I10 | % | Máquina, mes, turno | Provisional: 85 % es referencia habitual del sector; se ajustará al histórico | Derivado | Directivos, Supervisores |
| I13 | Frecuencia de paros no programados | Número de paros no programados / horas trabajadas × 100 | paros por 100 h | Máquina, mes | Provisional: percentil 75 histórico | `fact_paro` | Mantenimiento |
| I14 | Duración media del paro | Horas de paro / número de paros × 60 | min | Máquina, código | Sin meta | `fact_paro` | Mantenimiento |
| I15 | Minutos de paro no programado en la última lectura | `minutos_paro_no_programado` de la última lectura horaria | min de 60 | Máquina, hora | Alerta si ≥ 15 min | `fact_lectura_hora` | Supervisores |
| I16 | Estado de la máquina | Parada si las lecturas de paro suman 60 min; corriendo en otro caso | estado | Máquina, hora | No aplica | `fact_lectura_hora` | Supervisores |
| I17 | Pacas por hora | Pacas de la lectura | pacas/h | Máquina, hora | Referencia: mediana histórica de la máquina | `fact_lectura_hora` | Supervisores |

El umbral de 15 min de I15 se explica en F4.

## A4. Indicadores que ya reporta el P-MTO-22

El procedimiento (4.1.7) alimenta cuatro gráficos. Cada uno se reproduce con un indicador del catálogo:

| Gráfico del P-MTO-22 | Indicador del catálogo | Hoja del Excel que lo calcula hoy | Dónde se reproduce |
|---|---|---|---|
| Producción general | I01, I03 | `prodAño` / `TD_prodAño` | Power BI, página «Resumen» |
| Producción por máquina, comparativo 2024 contra 2025 | I01, I02 | `prodMaquina` / `TD_prodMaq` | Power BI, página «Producción» |
| Porcentaje de códigos de paro por máquina | I05 | `prodCodigo` / `TD_prodCodigo` | Power BI, página «Paros» (Pareto) |
| Análisis detallado de los códigos 01, 03 y 05 | I06 | `fallaMecanica`, `novPotencia`, `ajusteOperativo` y sus `TD_` | Power BI, página «Paros» (drill a subcódigo) |

Dos precauciones:
- Los datos de 2025 llegan hasta el 28 de marzo. El comparativo 2024 contra 2025 solo es justo con enero a marzo de ambos años.
- Las tablas dinámicas del Excel muestran «% Productividad». **Por verificar:** cómo se calcula esa cifra en el libro antes de afirmar que se reproduce igual. Si no coincide con I01 o I09, se explicará la diferencia.

## A5. Indicadores nuevos que el Excel no calcula

| Indicador | Por qué se propone |
|---|---|
| I08 Disponibilidad | Separa el tiempo perdido por paros no programados del tiempo planificado. Hoy los paros se suman sin distinguir si eran esperables, como la pausa activa o el aseo. |
| I09 Rendimiento | Compara el ritmo real de la máquina con un ritmo de referencia. Sin meta registrada se usa un objetivo histórico (percentil 90 de pacas por hora de operación por máquina y referencia, con un mínimo de registros), lo que mide la distancia frente al mejor desempeño propio. |
| I10 Calidad | La fuente no tiene unidades rechazadas. Se declara el supuesto de 100 % en lugar de inventar un dato, y se complementa con I11. |
| I11 Horas perdidas por calidad | Muestra el costo en tiempo de reproceso, materia prima defectuosa y espera del laboratorio. |
| I12 OEE | Resume en un número lo que la gerencia hoy lee en cuatro gráficos. Con calidad en 100 % es un OEE de disponibilidad y rendimiento, y así se debe presentar. |
| I07 Utilización de capacidad | Responde si el problema es de paros o de falta de programación: en el histórico hay 41.519,8 h sin trabajar frente a 38.063,4 h trabajadas. |
| I13 y I14 Frecuencia y duración del paro | Distinguen muchos paros cortos de pocos paros largos, que requieren acciones distintas de mantenimiento. |
| I15 a I17 Indicadores horarios | Habilitan el monitoreo casi en tiempo real y la alerta que el Excel no puede ofrecer. |
