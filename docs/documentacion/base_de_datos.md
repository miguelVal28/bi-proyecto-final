# D. Base de datos

> **Borrador.** Pendiente de revisión del equipo. Las consultas SQL aún no se han ejecutado contra la base; se probarán en DBeaver cuando exista el modelo.

## D1. DDL del modelo dimensional

**Motor: PostgreSQL**, administrado desde DBeaver. Por qué: soporta funciones de ventana y `FILTER` sin extensiones, Grafana y Power BI tienen conectores nativos y funciona en Docker con un volumen.

Contenido del script `sql/01_ddl.sql`:
- `CREATE SCHEMA dw;`
- Las seis dimensiones y cuatro tablas de hechos del diccionario de datos (B6), con los tipos y llaves de esa sección.
- Un esquema `staging` con `stg_base_datos` (copia cruda del Excel) y la tabla `etl_log`.
- Dos vistas de apoyo: `vw_oee_turno` (OEE por fecha, máquina y turno) y `vw_paros_detalle` (paros con todas las dimensiones ya unidas).

Convenciones: nombres en minúsculas y sin tildes, claves sustitutas `..._key`, claves foráneas con `ON DELETE RESTRICT`, y un registro con clave 0 en cada dimensión para el miembro «Sin dato».

Roles previstos (ver G4):
- `etl_writer`: escribe en `dw` y `staging`.
- `bi_reader`: solo lectura sobre `dw`. Lo usan Power BI y Grafana.

## D2. Restricciones e índices

### Restricciones

| Tabla | Restricción | Para qué |
|---|---|---|
| Todas | `PRIMARY KEY` en la llave sustituta | Identidad de la fila |
| Dimensiones | `UNIQUE` en el nombre o la combinación natural (p. ej. `(codigo, subcodigo)`) | Evita duplicar miembros |
| Hechos | `FOREIGN KEY` a cada dimensión | Integridad: ningún hecho sin contexto |
| `fact_produccion` | `CHECK (horas_trabajadas BETWEEN 0 AND 24)` y `CHECK (pacas_producidas >= 0)` | Rechaza valores imposibles |
| `fact_paro` | `CHECK (minutos_paro > 0)` | Solo se guardan paros reales |
| `fact_tiempo_no_programado` | `CHECK (horas_no_trabajadas BETWEEN 0 AND 24)` | Las 32 h de la fuente se limitan en R11 |
| `fact_lectura_hora` | `UNIQUE (maquina_key, ts_hora)` | Una lectura por máquina y hora |

### Índices

El volumen es pequeño (unas 16.500 filas en el hecho más grande), así que se busca cubrir las uniones y los filtros que usan los tableros, sin llenar las tablas de índices.

| Índice | Tabla | Consulta que lo justifica |
|---|---|---|
| `(fecha_key, maquina_key)` | `fact_produccion` | Producción por máquina y mes (I01, I02) |
| `(causa_key)` | `fact_paro` | Pareto y detalle por código y subcódigo (I05, I06) |
| `(maquina_key, fecha_key)` | `fact_paro` | Paros por máquina y periodo; relación con producción |
| `(fecha_key, maquina_key)` | `fact_tiempo_no_programado` | Utilización de capacidad (I07) |
| `(ts_hora DESC)` | `fact_lectura_hora` | Paneles de Grafana con rango de tiempo y lectura más reciente por máquina |

Las columnas de dimensiones pequeñas (4 máquinas, 7 turnos) no necesitan índice propio. El uso de cada índice se comprueba con `EXPLAIN` en DBeaver.

## D3. Consultas SQL analíticas

Cada consulta responde una pregunta del catálogo (A1) y usa al menos una técnica pedida: agregación, función de ventana o comparativo entre periodos.

### Q1. ¿Qué causas concentran más horas de paro? (Pareto con porcentaje acumulado)

```sql
WITH h AS (
  SELECT c.codigo, c.nombre_codigo, SUM(p.horas_paro) AS horas
  FROM dw.fact_paro p
  JOIN dw.dim_causa_paro c USING (causa_key)
  GROUP BY c.codigo, c.nombre_codigo
)
SELECT codigo, nombre_codigo,
       ROUND(horas, 1) AS horas,
       ROUND(100 * horas / SUM(horas) OVER (), 1) AS pct,
       ROUND(100 * SUM(horas) OVER (ORDER BY horas DESC, codigo) / SUM(horas) OVER (), 1) AS pct_acumulado
FROM h
ORDER BY horas DESC, codigo;
```

Técnica: función de ventana `SUM() OVER`.

### Q2. ¿Cómo varía la producción mes a mes?

```sql
WITH m AS (
  SELECT f.anio_mes, SUM(p.pacas_producidas) AS pacas
  FROM dw.fact_produccion p
  JOIN dw.dim_fecha f USING (fecha_key)
  GROUP BY f.anio_mes
)
SELECT anio_mes, pacas,
       LAG(pacas) OVER (ORDER BY anio_mes) AS pacas_mes_anterior,
       ROUND(100.0 * (pacas - LAG(pacas) OVER (ORDER BY anio_mes))
             / NULLIF(LAG(pacas) OVER (ORDER BY anio_mes), 0), 1) AS variacion_pct
FROM m
ORDER BY anio_mes;
```

Técnica: `LAG` para comparar con el periodo anterior.

### Q3. ¿Qué máquina rinde más cada mes? (pacas por hora trabajada)

```sql
SELECT f.anio_mes, m.nombre AS maquina,
       ROUND(SUM(p.pacas_producidas) / NULLIF(SUM(p.horas_trabajadas), 0), 2) AS pacas_por_hora,
       RANK() OVER (PARTITION BY f.anio_mes
                    ORDER BY SUM(p.pacas_producidas) / NULLIF(SUM(p.horas_trabajadas), 0) DESC) AS ranking
FROM dw.fact_produccion p
JOIN dw.dim_fecha f   USING (fecha_key)
JOIN dw.dim_maquina m USING (maquina_key)
GROUP BY f.anio_mes, m.nombre
ORDER BY f.anio_mes, ranking;
```

Técnica: `RANK() OVER (PARTITION BY …)`.

### Q4. ¿Cómo se compara el primer trimestre de 2025 con el de 2024? (comparativo entre periodos)

```sql
SELECT m.nombre AS maquina,
       SUM(p.pacas_producidas) FILTER (WHERE f.anio = 2024) AS pacas_2024,
       SUM(p.pacas_producidas) FILTER (WHERE f.anio = 2025) AS pacas_2025,
       ROUND(100.0 * (SUM(p.pacas_producidas) FILTER (WHERE f.anio = 2025)
                    - SUM(p.pacas_producidas) FILTER (WHERE f.anio = 2024))
             / NULLIF(SUM(p.pacas_producidas) FILTER (WHERE f.anio = 2024), 0), 1) AS variacion_pct
FROM dw.fact_produccion p
JOIN dw.dim_fecha f   USING (fecha_key)
JOIN dw.dim_maquina m USING (maquina_key)
WHERE f.anio IN (2024, 2025) AND f.mes BETWEEN 1 AND 3
GROUP BY m.nombre
ORDER BY m.nombre;
```

Nota: los datos de 2025 terminan el 28 de marzo, así que el trimestre de 2025 está casi completo pero no del todo.

### Q5. ¿Qué subcódigos concentran más tiempo de falla y ajuste por máquina?

```sql
SELECT *
FROM (
  SELECT m.nombre AS maquina, c.codigo, c.subcodigo, c.nombre_subcodigo,
         ROUND(SUM(p.horas_paro), 1) AS horas,
         ROW_NUMBER() OVER (PARTITION BY m.nombre ORDER BY SUM(p.horas_paro) DESC) AS posicion
  FROM dw.fact_paro p
  JOIN dw.dim_causa_paro c USING (causa_key)
  JOIN dw.dim_maquina m    USING (maquina_key)
  WHERE c.codigo IN (1, 3, 5) AND c.subcodigo <> 'Sin especificar'
  GROUP BY m.nombre, c.codigo, c.subcodigo, c.nombre_subcodigo
) t
WHERE posicion <= 3
ORDER BY maquina, posicion;
```

Técnica: `ROW_NUMBER` para un ranking dentro de cada máquina.
