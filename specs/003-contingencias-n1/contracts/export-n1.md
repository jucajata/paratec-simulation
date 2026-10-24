# Formato de exportación del análisis N-1 (FR-059, FR-060)

CSV en UTF-8 con encabezado, separador coma y punto decimal, como la exportación de un flujo
([specs/001/contracts/export-format.md](../../001-flujo-potencia-despacho/contracts/export-format.md)).
Las filas van en el mismo orden que la interfaz (SC-018).

## `n1_cargabilidad.csv` (FR-053)

`posicion, activo_fuera, tipo_activo, subarea_activo, elemento, cargabilidad_base_pct,
cargabilidad_pct, elementos_que_cuentan, barras_aisladas, demanda_sin_servicio_mw,
referencia_movida_a`

## `n1_tensiones.csv` (FR-054)

`posicion, activo_fuera, tipo_activo, subarea_activo, barra, v_base_pu, v_pu,
distancia_fuera_de_banda_pu, barras_que_cuentan, barras_aisladas, demanda_sin_servicio_mw,
referencia_movida_a`

## `n1_aislan_demanda.csv` (FR-055)

`posicion, activo_fuera, tipo_activo, subarea_activo, barras_aisladas, demanda_sin_servicio_mw`

## `n1_sin_solucion.csv` (FR-056)

`activo_fuera, tipo_activo, subarea_activo, iteraciones, desbalance_maximo_mva,
barras_problematicas`

`barras_problematicas` lista las barras del diagnóstico separadas por `;`.

Las columnas `barras_aisladas`, `demanda_sin_servicio_mw` y `referencia_movida_a` van vacías
cuando no aplican.

## `metadatos.json` (FR-060)

```json
{
  "tipo": "analisis_n1",
  "snapshot": "2026-10-20",
  "despacho": "2026-10-20",
  "periodo": 19,
  "case_id": "…",
  "run_id": "…",
  "pandapower": "3.5.6",
  "sinsim": "0.6.0",
  "solver": {"algorithm": "nr", "tolerance_mva": 1e-6, "…": "…"},
  "limites": [{"name": "…", "value": "…", "source": "…"}],
  "analizado_en": "2026-10-24T15:00:00Z",
  "procesos": 11,
  "resumen": {"n_total": 1261, "n_loading": 0, "…": "…"},
  "atribucion": "Información proporcionada por XM S.A. E.S.P. …"
}
```
