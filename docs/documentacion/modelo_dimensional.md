# B. Modelo dimensional

> **Borrador.** Pendiente de revisión del equipo. «Pregunta» marca una decisión abierta y «por verificar», un dato por confirmar contra el Excel. Los conteos vienen del perfilado de la hoja `Base De Datos`.

## B1. Elección del tipo de modelo

**Modelo elegido: constelación de hechos** (fact constellation: varias tablas de hechos que comparten dimensiones, cada una en forma de estrella).

Por qué:
- La fuente mezcla procesos de negocio con granos distintos: producción por registro, paros por causa y días sin producción por motivo. Una sola tabla de hechos obligaría a repetir medidas o a dejar celdas vacías.
- Las dimensiones se comparten (fecha, máquina, turno, referencia, operario, causa de paro), de modo que se puede comparar paros contra producción sin duplicar datos (*drill-across*).
- Cada estrella queda con pocas uniones, lo que simplifica las consultas SQL y el modelo semántico de Power BI.

Por qué no copo de nieve: normalizar las dimensiones en subtablas añadiría uniones sin ganancia real. El volumen es pequeño (unos 16.500 paros) y el espacio ahorrado es irrelevante.

## B2. Grano de cada tabla de hechos

El grano declara qué representa exactamente una fila.

| Tabla de hechos | Grano | Filas esperadas (aprox.) | Medidas |
|---|---|---|---|
| `fact_produccion` | Un registro de producción por máquina, fecha, turno, operario y referencia | 4.700 (4.758 menos duplicados) | `pacas_producidas`, `horas_trabajadas` |
| `fact_paro` | Un paro de una causa (código y subcódigo) dentro de un registro, tras desagregar las 18 columnas de código | 16.500 (16.532 celdas con paro mayor que cero, antes de depurar) | `minutos_paro`, `horas_paro` |
| `fact_tiempo_no_programado` | Un día sin producción de una máquina, con su motivo | 1.850 (1.863 filas antes de depurar) | `horas_no_trabajadas` |
| `fact_lectura_hora` | Una lectura horaria de una máquina (la llena el simulador, no el Excel) | Crece en la demo | `pacas`, `minutos_paro_programado`, `minutos_paro_no_programado` |

Nota sobre los paros. Las 1.354 filas de subcódigo cargan sus propias claves de fecha, máquina, turno, operario y referencia, así que `fact_paro` no necesita unirse a `fact_produccion`. Ambas se relacionan a través de las dimensiones compartidas.

## B3. Dimensiones, atributos y jerarquías

| Dimensión | Atributos | Jerarquía | ¿Construida por nosotros? |
|---|---|---|---|
| `dim_fecha` | fecha, año, trimestre, mes, nombre del mes, año-mes, semana ISO, día de la semana, es fin de semana | Año → trimestre → mes → día | Sí: se genera de 2022-01-01 a 2026-12-31 |
| `dim_maquina` | nombre (Vinilos_1 a Vinilos_4) | Ninguna | No: sale de `Maquina` |
| `dim_turno` | nombre normalizado, grupo de turno, hora de inicio, hora de fin, duración | Grupo → turno | Sí: normaliza 7 formatos de texto y agrega «Sin dato» |
| `dim_referencia` | nombre normalizado, marca, volumen en cc, número de colores | Marca → volumen → referencia | Sí: marca, volumen y colores se extraen del nombre con una expresión regular |
| `dim_operario` | identificador seudónimo, marcador de sin dato | Ninguna | Parcial: sin nombres (ver G4) |
| `dim_causa_paro` | área de impacto, código, nombre del código, subcódigo, nombre del subcódigo, tipo de paro (programado o no), si está en el P-MTO-22 | Área de impacto → código → subcódigo | Sí: combina `TABLA CODIGOS` con un mapeo de catálogos antiguos |

Valores previstos de `dim_turno`: Turno 1 (6am-2pm), Turno 2 (2pm-10pm), Turno 3 (10pm-6am), Jornada 6am-4:30pm, Jornada 6am-6pm, Jornada 6pm-6am y «Sin dato / No aplica». Las jornadas de 12 h y la de 10,5 h existen en la fuente pero con pocos registros (35, 20 y 359).

La jerarquía de referencias (marca → volumen) se apoya en el patrón del nombre, por ejemplo «Parchesitos 22cc (6 col)». Hay excepciones (`Parchesitos 125 cc`, `Vinilos x 30 Blanco`) que quedan con colores vacíos. **Por verificar:** si se tratan a mano.

Tabla de apoyo `objetivo_rendimiento` (no es dimensión ni hecho): contiene `maquina_key`, `referencia_key` y `pacas_h_objetivo`, calculada por el ETL como el percentil 90 histórico de pacas por hora de operación (ver A5). Solo sirve para I09.

## B4. Jerarquía de los paros

El Excel tiene tres niveles: área de impacto (Mantenimiento, Producción, Calidad, Almacén, Paro programado), código (01 a 17) y subcódigo (solo para los códigos 1, 3 y 5, p. ej. «1.2.B Ajuste de sensor»).

**Decisión: una dimensión aplanada `dim_causa_paro` a nivel de subcódigo**, con las tres columnas de la jerarquía en la misma fila. Cada código sin subcódigos tiene una fila con subcódigo «Sin especificar».

Justificación:
- Power BI hace drill-down sobre una jerarquía que está en una sola tabla, sin relaciones extra.
- Una sola clave foránea (`causa_key`) en `fact_paro` basta para cualquier nivel.
- Es consistente con la decisión de B1 (estrella, no copo de nieve).
- «Sin especificar» evita claves nulas: el Excel lo usa en 5.020 filas.

Dos puntos abiertos:
- Los códigos 18 («Paro de máquina por ventas») y 19 («No aplica») aparecen en los datos pero no en el P-MTO-22. Se incluyen con la marca `en_catalogo_pmto22 = falso`. **Pregunta:** ¿qué área de impacto lleva el 18? Se plantea «Planeación y ventas».
- Los 10 valores antiguos de `Tipo de paro` (p. ej. «17. PARO DE MAQUINA», «16. PARO POR PROCESO ANTERIOR») no tienen equivalente evidente. Mapeo previsto en C2, regla R07. **Por verificar** con quien conozca la planta.

## B5. Matriz de bus

| Proceso de negocio | `dim_fecha` | `dim_maquina` | `dim_turno` | `dim_referencia` | `dim_operario` | `dim_causa_paro` |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Producción (`fact_produccion`) | X | X | X | X | X | |
| Paros (`fact_paro`) | X | X | X | X | X | X |
| Tiempo no programado (`fact_tiempo_no_programado`) | X | X | | | | X |
| Lectura horaria (`fact_lectura_hora`) | X | X | X | X | | X |

En `fact_lectura_hora`, `dim_causa_paro` guarda la causa principal de la hora si hubo paro.

## B6. Diccionario de datos

Convención: `PK` llave primaria, `FK` llave foránea, claves sustitutas enteras generadas por la base de datos. «Origen» es la columna de la hoja `Base De Datos` (o la fuente indicada). Los tipos son de PostgreSQL. El esquema se llama `dw`.

### dim_fecha
Una fila por día. Calendario generado.

| Columna | Tipo | Llave | Regla de transformación | Origen |
|---|---|---|---|---|
| fecha_key | INTEGER | PK | AAAAMMDD | Generado |
| fecha | DATE | UNIQUE | | Generado (reemplaza `Fecha`, `Mes`, `Año`) |
| anio | SMALLINT | | | Derivado de fecha |
| trimestre | SMALLINT | | 1 a 4 | Derivado |
| mes | SMALLINT | | 1 a 12 | Derivado |
| nombre_mes | VARCHAR(12) | | En español | Derivado |
| anio_mes | CHAR(7) | | Formato AAAA-MM | Derivado |
| semana_iso | SMALLINT | | | Derivado |
| dia_semana | SMALLINT | | 1 lunes a 7 domingo | Derivado |
| es_fin_de_semana | BOOLEAN | | | Derivado |

### dim_maquina

| Columna | Tipo | Llave | Regla | Origen |
|---|---|---|---|---|
| maquina_key | SMALLINT | PK | Identidad | Generado |
| nombre | VARCHAR(20) | UNIQUE | Sin espacios sobrantes | `Maquina` |

### dim_turno

| Columna | Tipo | Llave | Regla | Origen |
|---|---|---|---|---|
| turno_key | SMALLINT | PK | 0 reservado para «Sin dato / No aplica» | Generado |
| turno_nombre | VARCHAR(30) | UNIQUE | Normalizar los 7 formatos de texto | `Turno` |
| grupo_turno | VARCHAR(30) | | Turnos de 8 h, Jornada administrativa, Turnos de 12 h, Sin dato | Derivado |
| hora_inicio | TIME | | Del texto del turno | `Turno` |
| hora_fin | TIME | | Del texto del turno | `Turno` |
| duracion_horas | NUMERIC(4,1) | | Fin − inicio | Derivado |

### dim_referencia

| Columna | Tipo | Llave | Regla | Origen |
|---|---|---|---|---|
| referencia_key | INTEGER | PK | 0 reservado para «Sin referencia» | Generado |
| referencia_nombre | VARCHAR(60) | UNIQUE | Corregir espacios y erratas; nulos y «No aplica» → «Sin referencia» | `Referencia` |
| marca | VARCHAR(40) | | Texto antes del volumen | Derivado |
| volumen_cc | SMALLINT | | Número antes de «cc» | Derivado |
| num_colores | SMALLINT | NULL | Número dentro de «( col)» | Derivado |

### dim_operario

| Columna | Tipo | Llave | Regla | Origen |
|---|---|---|---|---|
| operario_key | INTEGER | PK | 0 reservado para «Sin operario» | Generado |
| operario_id | VARCHAR(12) | UNIQUE | Seudónimo estable tipo `OP-001`, derivado del nombre normalizado con sal | `Operario` |
| es_sin_dato | BOOLEAN | | Verdadero para nulos, «No» y «No aplica» (545 filas) | `Operario` |

El nombre real nunca se carga a la base.

### dim_causa_paro

| Columna | Tipo | Llave | Regla | Origen |
|---|---|---|---|---|
| causa_key | INTEGER | PK | Identidad | Generado |
| area_impacto | VARCHAR(40) | | Del catálogo; códigos 18 y 19 con valor propio | `TABLA CODIGOS`, columna ÁREA DE IMPACTO |
| codigo | SMALLINT | | 1 a 19 | `TABLA CODIGOS` y nombre de la columna `Codigo de paro N` |
| nombre_codigo | VARCHAR(100) | | Texto del catálogo | `TABLA CODIGOS` |
| subcodigo | VARCHAR(10) | | Ej. `1.2.B`; «Sin especificar» si no aplica | `Sub Codigo de paro 1`, `Subcodigo 3`, `Subcodigo 5` |
| nombre_subcodigo | VARCHAR(100) | | Unificar `4.x` con `5.x` por nombre | Idem |
| tipo_paro | VARCHAR(15) | | «Programado» para 15, 16 y 17; «No programado» para el resto | Derivado |
| en_catalogo_pmto22 | BOOLEAN | | Falso para 18 y 19 | Derivado |
| UNIQUE | | (codigo, subcodigo) | | |

### fact_produccion

| Columna | Tipo | Llave | Regla | Origen |
|---|---|---|---|---|
| produccion_key | BIGINT | PK | Identidad | Generado |
| fecha_key | INTEGER | FK → dim_fecha | | `Fecha` |
| maquina_key | SMALLINT | FK → dim_maquina | | `Maquina` |
| turno_key | SMALLINT | FK → dim_turno | Normalizado | `Turno` |
| referencia_key | INTEGER | FK → dim_referencia | Normalizado | `Referencia` |
| operario_key | INTEGER | FK → dim_operario | Seudonimizado | `Operario` |
| pacas_producidas | INTEGER | NULL | Sin dato → NULL, no 0 | `Pacas producidas` |
| horas_trabajadas | NUMERIC(5,2) | | Entre 0 y 24 | `Horas trabajadas` |
| flag_calidad | VARCHAR(20) | | `ok`, `pacas_cero`, `sin_pacas`, `paro_mayor_horas` | Derivado (P10, P11) |
| fila_fuente | INTEGER | | Número de fila del Excel, para trazabilidad | Posición en la hoja |

### fact_paro

| Columna | Tipo | Llave | Regla | Origen |
|---|---|---|---|---|
| paro_key | BIGINT | PK | Identidad | Generado |
| fecha_key, maquina_key, turno_key, referencia_key, operario_key | | FK | Como en `fact_produccion`, tomados de la propia fila | Idem |
| causa_key | INTEGER | FK → dim_causa_paro | Código de la columna más subcódigo de la fila | `Codigo de paro N`, subcódigos |
| minutos_paro | NUMERIC(7,2) | | Solo si > 0 | `Codigo de paro N` |
| horas_paro | NUMERIC(8,4) | | Minutos / 60 | `Codigo N en horas` |
| area_involucrada | VARCHAR(30) | NULL | «Operarios» o «Personal_de_mantenimiento» | `Área involucrada en subcodigo 5` |
| personal_id | VARCHAR(12) | NULL | Seudónimo del personal involucrado | `Personal involucrado` |
| tipo_fila_origen | VARCHAR(10) | | `registro` o `subcodigo` | Derivado (A2.2) |
| fila_fuente | INTEGER | | | Posición en la hoja |

### fact_tiempo_no_programado

| Columna | Tipo | Llave | Regla | Origen |
|---|---|---|---|---|
| tnp_key | BIGINT | PK | Identidad | Generado |
| fecha_key | INTEGER | FK | | `Fecha` |
| maquina_key | SMALLINT | FK | | `Maquina` |
| causa_key | INTEGER | FK | Motivo mapeado desde `Tipo de paro` | `Tipo de paro` |
| horas_no_trabajadas | NUMERIC(5,2) | | Entre 0 y 24 (el valor 32 se marca) | `Horas no trabajadas` |
| observacion | TEXT | NULL | Texto libre | `Observaciones de paro` |
| fila_fuente | INTEGER | | | Posición en la hoja |

### fact_lectura_hora (simulador)

| Columna | Tipo | Llave | Regla | Origen |
|---|---|---|---|---|
| lectura_key | BIGINT | PK | Identidad | Generado |
| ts_hora | TIMESTAMPTZ | | Hora de la lectura | Simulador |
| fecha_key, maquina_key, turno_key, referencia_key | | FK | | Simulador |
| pacas | INTEGER | | ≥ 0 | Simulador |
| minutos_paro_programado | NUMERIC(5,2) | | Entre 0 y 60 | Simulador |
| minutos_paro_no_programado | NUMERIC(5,2) | | Entre 0 y 60 | Simulador |
| causa_key_principal | INTEGER | FK, NULL | Causa con más minutos | Simulador |
| UNIQUE | | (maquina_key, ts_hora) | | |

## B7. SCD (bonificación)

**Decisión: `dim_causa_paro` con SCD tipo 1** (se sobrescribe el valor, sin guardar historia).

Qué cambió con el tiempo: el catálogo de causas. Los subcódigos de ajuste operativo pasaron de la numeración `4.x` a `5.x` (945 y 2.149 filas respectivamente) y se agregaron los códigos 18 y 19. La dirección quiere comparar 2022 a 2025 bajo una sola taxonomía.

Por qué tipo 1 y no tipo 2: el tipo 2 crearía una fila por versión y partiría la historia de un mismo subcódigo en dos, que es exactamente el problema que se quiere evitar. Se conserva la numeración antigua en una columna de auditoría (`codigo_origen_antiguo`) para poder rastrearla.

Cuándo sí convendría tipo 2: en `dim_referencia`, si una referencia cambiara de presentación o de meta, o en `dim_maquina` si cambiara su configuración. La fuente actual no registra esos cambios, así que no se aplica. **Pregunta:** ¿se prefiere justificar otra dimensión?
