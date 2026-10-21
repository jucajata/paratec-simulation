# Contrato del CLI `sinsim`

Punto de entrada único (constitución II). Se invoca como `uv run sinsim <comando>`. Todos los
mensajes al usuario están en español. Con `--json`, la salida estándar es un objeto JSON y los
mensajes de progreso van a stderr.

## Códigos de salida (constitución V)

| Código | Significado | Ejemplos de `code` de dominio |
|---|---|---|
| 0 | Éxito; incluye un flujo `no_convergio`, que es un resultado y no un error | — |
| 1 | Error general | `SNAPSHOT_EXISTS`, `SNAPSHOT_CORRUPTED`, `OPERATING_POINT_MISSING` |
| 2 | Uso incorrecto | Fecha mal formada o posterior a mañana (FR-039), `--periodo` fuera de 1–24 |
| 3 | Error de red | PARATEC o el portal de XM no responden |
| 4 | Validación fallida o cambio de estructura en la fuente | `PARATEC_SCHEMA_CHANGED`, `XM_FILE_SCHEMA_CHANGED`, `DISPATCH_TOTAL_MISMATCH` |

---

## `sinsim scrape --fecha YYYY-MM-DD [--out data/paratec/]` (HU-3; FR-003 a FR-007)

- Descarga las entidades de PARATEC, todas las versiones de `dDEC<MMDD>` (`.txt` = V0 y
  `_V<n>.txt`; prevalece la `n` más alta, D-3) y `PRON_BARRA<MMDD>` de la fecha.
- Respeta la tasa configurada `scraper.min_interval_s` y envía el User-Agent
  `sinsim/<versión> (+https://github.com/jucajata/paratec-simulation)` (III.10).
- Escribe en un directorio temporal dentro de `--out`, valida, calcula los checksums y solo
  al final renombra a `<out>/<fecha>/`. Si algo falla, borra el temporal (FR-005, SC-006).
- Si `<out>/<fecha>/` ya existe, sale con código 1 y `SNAPSHOT_EXISTS` sin tocar nada (FR-004).
  No hay opción `--force`, por la constitución III.4 (ver "Decisiones pendientes" en la spec).
- Al terminar imprime la ruta, los conteos por entidad y la versión del estándar de XM.
- Admite hasta mañana (D+1), porque XM publica el despacho la víspera (FR-039). Advierte que
  PARATEC no tiene histórico: los parámetros son los vigentes al descargar (FR-038).
- La interfaz usa la misma lógica a través de `POST /api/snapshots/{fecha}/descarga` (FR-038).

## `sinsim snapshots list [--json]` (FR-002)

Muestra una fila por fecha con estas columnas: `fecha | paratec | despacho | demanda |
íntegro`. La columna `íntegro` es `sí` o `no`, según la verificación de checksums (FR-006).

## `sinsim run --fecha YYYY-MM-DD --periodo N [opciones]` (HU-1, HU-2, HU-4.3)

Construye el caso, imprime el reporte de calidad, ejecuta el flujo e imprime el resumen.

| Opción | Valor por defecto | Descripción |
|---|---|---|
| `--fecha` | (obligatoria) | Snapshot de PARATEC |
| `--fecha-despacho` | igual a `--fecha` | Snapshot del que se toman el despacho y la demanda. Si difiere de `--fecha`, se emite la advertencia `DATES_DIFFER` (FR-025) |
| `--periodo` | (obligatoria) | 1–24 |
| `--tipo` | `ac` | `ac` o `dc` (FR-021) |
| `--exportar DIR` | — | Escribe la exportación de [export-format.md](./export-format.md) (FR-032) |
| `--json` | — | Salida en JSON (`StudyCase` + `Run` + resumen de `RunResult`) |

**Salida en texto**: un encabezado con la trazabilidad (FR-023), la leyenda "Flujo sobre
despacho programado (no es el estado real del SIN)" (FR-026), el balance y la cobertura, los
conteos del reporte de calidad, el estado y, si convergió, los 10 peores en tensión y en
cargabilidad. Si no convergió, imprime el diagnóstico (FR-022).

## `make` (contrato con quien clona el repo; constitución IV)

| Comando | Qué hace |
|---|---|
| `make demo` | `uv run sinsim run --fecha <fecha incluida> --periodo 19 --exportar out/demo`. Funciona sin red (R-01, SC-001) |
| `make dev` | Levanta uvicorn (API en `127.0.0.1:8000`) y Vite (UI en `127.0.0.1:5173`) |
| `make test` | `pytest` (con cobertura) + `vitest` + `playwright test` |
