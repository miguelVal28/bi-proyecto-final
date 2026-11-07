# F. Grafana

> **Borrador.** Pendiente de revisión del equipo. Las consultas aún no se han probado en Grafana.

## F1. Fuente de datos

- Tipo: PostgreSQL, base `dw`, con el rol de solo lectura `bi_reader`.
- Dentro de Docker el servidor es el nombre del servicio (por ejemplo `postgres:5432`), no `localhost`.
- La fuente se aprovisiona por archivo (carpeta `grafana/provisioning/datasources`) para que exista al iniciar el contenedor (K3). La contraseña llega por variable de entorno.

## F2. Paneles de series de tiempo y de estado actual

Los paneles leen `dw.fact_lectura_hora` (la llena el simulador de F5) y comparten el rango de tiempo del tablero.

| Panel | Tipo | Qué muestra | Indicador |
|---|---|---|---|
| Pacas por hora | Serie de tiempo | Una línea por máquina | I17 |
| Minutos de paro no programado | Serie de tiempo | Una línea por máquina, con línea del umbral | I15 |
| Estado actual por máquina | Cuadros de estado (State timeline o Stat) | Corriendo o parada, con la última lectura | I16 |
| Causa principal del último paro | Tabla | Última causa por máquina | I15 |

Consulta de la serie de pacas:

```sql
SELECT l.ts_hora AS "time", m.nombre AS metric, l.pacas AS value
FROM dw.fact_lectura_hora l
JOIN dw.dim_maquina m USING (maquina_key)
WHERE $__timeFilter(l.ts_hora)
  AND m.nombre IN ($maquina)
  AND l.turno_key IN ($turno)
ORDER BY 1;
```

Consulta del estado actual (la última lectura de cada máquina):

```sql
SELECT DISTINCT ON (l.maquina_key)
       m.nombre AS maquina, l.ts_hora, l.pacas,
       l.minutos_paro_no_programado,
       CASE WHEN l.minutos_paro_programado + l.minutos_paro_no_programado >= 60
            THEN 'Parada' ELSE 'Corriendo' END AS estado
FROM dw.fact_lectura_hora l
JOIN dw.dim_maquina m USING (maquina_key)
WHERE m.nombre IN ($maquina)
ORDER BY l.maquina_key, l.ts_hora DESC;
```

## F3. Variables de tablero

| Variable | Consulta | Selección |
|---|---|---|
| `$maquina` | `SELECT nombre FROM dw.dim_maquina ORDER BY 1` | Múltiple, con «Todas» |
| `$turno` | `SELECT turno_key AS __value, turno_nombre AS __text FROM dw.dim_turno ORDER BY 1` | Múltiple, con «Todos» |

## F4. Alerta sobre un KPI operativo

**KPI: minutos de paro no programado en la última lectura horaria (I15).**

**Umbral: 15 minutos de 60 (25 % de la hora).**

Justificación con los datos históricos del Excel:
- Paro total: 8.449,7 h; paro programado (códigos 15, 16 y 17): 2.886,8 h; paro no programado: 5.562,9 h.
- Horas trabajadas: 38.063,4 h.
- El paro no programado medio es 5.562,9 / 38.063,4 = 14,6 % del tiempo, o **8,8 minutos por hora**.
- 15 minutos es unas 1,7 veces ese promedio: señala una hora claramente peor de lo normal, sin disparar la alerta con la variación diaria.

**Pregunta:** después de cargar el modelo, ¿se ajusta el umbral al percentil 90 histórico de minutos de paro no programado por hora de operación? Esa cifra se calcula con el ETL y sustituiría al 15 si es distinta.

Regla de alerta de Grafana:
- Consulta: última lectura de `minutos_paro_no_programado` por máquina.
- Condición: mayor o igual a 15.
- Evaluación: cada minuto, con estado «Pending» durante 1 minuto antes de disparar.
- Destino: el panel del tablero con una anotación; si se quiere, un contact point de correo o Telegram (opcional).

## F5. Simulación hora a hora

Un script `simulador/simulador.py` inserta una lectura por máquina cada pocos segundos en `dw.fact_lectura_hora`. Cada lectura representa una hora de operación en tiempo acelerado (por ejemplo, 10 segundos reales equivalen a 1 hora simulada), con `ts_hora` igual a la hora real del insert, de modo que el tablero se mueve con la demo.

Comportamiento:
- **Modo normal:** pacas por hora y minutos de paro salen de la distribución histórica de cada máquina (mediana de pacas por hora de operación; paro no programado en torno a 8,8 minutos por hora).
- **Modo incidente:** una opción por línea de comandos (por ejemplo, `--incidente Vinilos_3`) fuerza paros largos en esa máquina durante unas lecturas, para disparar la alerta en vivo.
- **Demostración:** abrir Grafana, correr el simulador en modo normal, luego activar el incidente y mostrar que el panel de estado cambia a «Parada» y que la alerta pasa de «Pending» a «Firing».

## F6. Tablero exportado

El tablero se exporta como JSON y se guarda en `grafana/dashboards/`. Con el aprovisionamiento (K3) se carga solo al iniciar. Cada vez que se cambie el tablero se vuelve a exportar y se hace commit del JSON.
