# Contrato de exportación de resultados (FR-032, SC-007)

Para una ejecución, la exportación produce un directorio (desde el CLI) o un `.zip` (desde la
API) con estos archivos:

| Archivo | Contenido | Columnas |
|---|---|---|
| `barras.csv` | Una fila por barra | Las de `RunResult.buses` ([data-model.md §7](../data-model.md)) |
| `lineas.csv` | Una fila por línea | `RunResult.lines` |
| `transformadores.csv` | Una fila por transformador; incluye la columna `tipo` (`2w` o `3w`) | `RunResult.trafos` |
| `generadores.csv` | Una fila por generador | `RunResult.generators` |
| `metadatos.json` | Trazabilidad y contexto | Ver abajo |

## Formato de los CSV

- UTF-8 sin BOM.
- Separador `,` y decimal `.`.
- Encabezado con los nombres de columna internos y la unidad en el nombre (`vm_pu`, `p_mw`,
  ...).
- Los valores se escriben con la precisión completa de float64, sin redondear, para que la
  comparación "valor a valor" de HU-4 sea exacta.

## `metadatos.json`

Contiene:
- `trace`: completo, igual a `Run.trace` (FR-023).
- `solver`.
- `status`.
- `case_id`.
- `quality_summary`: el balance y los conteos de cada sección del reporte.
- `assumptions`: los supuestos visibles del caso.
- `limits`: valores y fuente de cada uno (III.9).
- `warnings`.
- `attribution`: "Información proporcionada por XM S.A. E.S.P. – PARATEC y archivos públicos
  de despacho" (R-12, D-1).
- `label`: "Flujo sobre despacho programado" o "Aproximación DC sobre despacho programado".

Si `status = no_convergio`, no se generan los CSV de resultados. Solo se escribe
`metadatos.json` con `diagnostics` (FR-022).
