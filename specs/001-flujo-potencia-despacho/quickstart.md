# Quickstart: validar la feature de principio a fin

Guía de validación, no de implementación. Los detalles están en [contracts/](./contracts/) y
[data-model.md](./data-model.md). `<FECHA>` es la fecha del snapshot incluido en el
repositorio.

## Prerrequisitos

- Python 3.12, `uv`, Node 20 o superior, `pnpm`.
- Un clon del repositorio. Para los escenarios 1 a 4 **no hace falta red** después de instalar
  las dependencias.

```bash
uv sync --project backend
pnpm --dir frontend install
```

## Escenario 1: primer resultado sin red (HU-1, SC-001, R-01)

```bash
make demo
```

**Esperado**:
- La salida incluye la leyenda "Flujo sobre despacho programado".
- Muestra la trazabilidad completa: fecha del snapshot, fecha del despacho, periodo 19, `ac`,
  versión de pandapower 3.5.6, solver e id del caso.
- Muestra el balance con la cobertura (%) y `estado: convergio`.
- Se crea `out/demo/` con 4 CSV y `metadatos.json`.
- Tiempo total, contado desde un clon con las dependencias ya instaladas: menos de 10 minutos.

## Escenario 2: calidad del caso (HU-2)

```bash
uv run sinsim run --fecha <FECHA> --periodo 19 --json | jq '.case.quality.balance, (.case.quality.unlocated_resources|length), (.case.quality.transfers|length), .case.quality.islands'
```

**Esperado**:
- Todo recurso con P > 0 aparece en `generators` o en `unlocated_resources` (SC-002).
- `coverage_pct` es al menos el umbral de SC-003.
- Con el snapshot incluido se espera una sola componente energizada. Cualquier isla extra
  aparece como hallazgo de calidad de datos, con los MW que quedaron fuera (D-5).
- Los supuestos incluyen la consigna de 1,0 pu, los taps en posición neutra, `i0 = 0` y los
  SVC/STATCOM modelados como fuentes de reactiva.

## Escenario 3: no convergencia y validaciones (HU-1.3, HU-1.4, casos borde)

- `uv run sinsim run --fecha <FECHA> --periodo 25` → código 2 y un mensaje que pide un periodo
  entre 1 y 24.
- `uv run sinsim run --fecha 2000-01-01 --periodo 1` → código 1 y `SNAPSHOT_NOT_FOUND`, con la
  sugerencia de ejecutar `sinsim scrape`.
- Prueba automatizada con un caso preparado para no converger
  (`backend/tests/integration/test_no_convergence.py`) → `status = no_convergio`,
  `diagnostics` completo y `result = null`.
- Un snapshot de prueba con un byte alterado → `SNAPSHOT_CORRUPTED`, indicando el archivo
  afectado (FR-006).

## Escenario 4: convergencia en los 24 periodos y red de referencia (SC-004, SC-005)

```bash
uv run pytest backend/tests/integration/test_all_periods.py backend/tests/integration/test_reference_networks.py
```

**Esperado**:
- Los 24 periodos de `<FECHA>` terminan en `convergio`.
- `case9`, `case14` y `case30` coinciden con la solución de referencia con un error máximo
  de 1e-6 pu.

## Escenario 5: actualización de datos con fixtures (HU-3, SC-006)

```bash
uv run pytest backend/tests/integration/test_scrape_fixtures.py
```

Usa respuestas grabadas con `httpx.MockTransport`; no hace llamadas reales (R-03).

**Esperado**:
- Se crea un snapshot completo con su manifiesto.
- Un segundo intento sobre la misma fecha da `SNAPSHOT_EXISTS` sin cambios.
- Con una entidad corrupta: código 4 y ningún directorio residual.
- Con un error de red simulado: código 3 y el árbol de `data/` idéntico al de antes, comparado
  por hash.

## Escenario 6: interfaz y exportación (HU-4)

```bash
make dev   # en otra terminal
pnpm --dir frontend exec playwright test
```

**Esperado**:
- La interfaz permite escribir cualquier fecha hasta mañana; si no tiene snapshot, ofrece
  descargarla y muestra el paso en curso (FR-038); al terminar queda disponible y seleccionada.
- La interfaz permite elegir la fecha y el periodo, y ejecutar.
- Muestra las tablas filtrables de barras, líneas, transformadores y generadores.
- Las violaciones aparecen resaltadas y contadas.
- La topología se puede colorear por tensión o por cargabilidad.
- El `.zip` descargado coincide valor a valor con `GET /api/runs/{id}`.
