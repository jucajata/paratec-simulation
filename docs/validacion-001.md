# Validación de la feature 001 (flujo de potencia sobre despacho programado)

Ejecución real de los seis escenarios de
[quickstart.md](../specs/001-flujo-potencia-despacho/quickstart.md) sobre el snapshot incluido
(2026-10-20). Fecha de ejecución: 2026-10-20. Máquina: macOS (Darwin 25.6), Python 3.12,
pandapower 3.5.6 sin numba, Node 20+, Playwright 1.64.1.

> Información proporcionada por XM S.A. E.S.P. – PARATEC y archivos públicos de despacho.
> Todo resultado es un flujo sobre despacho programado, no el estado real del SIN.

## Resumen

| Escenario | Qué prueba | Resultado |
|---|---|---|
| 1 | `make demo` sin red | Convergió en 11,4 s; 5 archivos en `out/demo/` |
| 2 | Calidad del caso (periodo 19) | Cobertura 99,93 %; 4 recursos no ubicados (8,1 MW); 12 islas, 1 energizada |
| 3 | Validaciones y no convergencia | Códigos 2 y 1 correctos; pruebas de no convergencia y snapshot corrupto pasan |
| 4 | 24 periodos y redes de referencia | 28 pruebas pasan en 236 s; cada periodo < 30 s y cobertura ≥ 95 % |
| 5 | Actualización con fixtures | 7 pruebas pasan en 3,4 s, sin llamadas reales |
| 6 | Interfaz y exportación | 2 pruebas e2e pasan en 25 s; el zip coincide valor a valor con la API |

Criterios de éxito:

| Criterio | Objetivo | Obtenido |
|---|---|---|
| SC-001 primer resultado | < 10 min desde un clon con dependencias | 11,4 s (`make demo`) |
| SC-002 recursos con P > 0 | 100 % ubicados o reportados | Cumplido: 4 no ubicados reportados con sus MW |
| SC-003 cobertura del despacho | ≥ 95 % | 99,93 % en el periodo 19; ≥ 95 % en los 24 |
| SC-004 convergencia 24 periodos | Todos `convergio` | 24 de 24 |
| SC-005 red de referencia | Error máximo 1e-6 pu | Cumplido (Gauss-Seidel y MATPOWER case9) |
| SC-006 scrape interrumpido | Árbol de `data/` intacto | Cumplido (comparación por hash en el escenario 5) |
| SC-007 metadatos de exportación | Trazabilidad FR-023 completa | Cumplido (verificado en el e2e) |
| Cobertura de pruebas (constitución VI.6) | ≥ 85 % en `domain/` y `adapters/` | 96,48 % |

## Escenario 1: primer resultado sin red

```
make demo
```

Salida relevante:

```
── Reporte de calidad del caso ──
Generación programada: 12,331.0 MW | ubicada: 12,322.9 MW (99.9 %) | no ubicada: 8.1 MW
Demanda asignada: 8,929.8 MW | no ubicada: 3,220.2 MW | diferencia generación − demanda: 3,393.1 MW
Recursos no ubicados: 4 | nodos de demanda no ubicados: 154 | traslados a frontera: 157 | excluidos: 52 | imputados: 699 | no modelados: 30
Islas: 12 (energizada: 591 barras; 131.8 MW de generación fuera)
  ⚠ PROGRAM_NOT_REAL_STATE: el resultado describe el despacho programado por XM, no el estado real del SIN.
── Flujo sobre despacho programado ──
Snapshot PARATEC: 2026-10-20 | despacho: 2026-10-20 periodo 19 | flujo: ac | pandapower 3.5.6 | sinsim 0.1.0
Estado: convergio
Generación 8,999.7 MW | carga 8,816.4 MW | pérdidas 183.4 MW | ajuste de la referencia -3,323.2 MW
Violaciones de tensión: 50 | sobrecargas: 3
```

| Medida | Valor |
|---|---|
| Tiempo total (`time -p`) | 11,44 s |
| Archivos exportados | `barras.csv`, `lineas.csv`, `transformadores.csv`, `generadores.csv`, `metadatos.json` |
| Identificador del caso | `704c54fb…b65d00` |

Todo lo esperado aparece: leyenda, trazabilidad completa, balance con cobertura y estado.

## Escenario 2: calidad del caso

`sinsim run --fecha 2026-10-20 --periodo 19 --json`:

| Campo del balance | MW |
|---|---|
| Generación programada | 12 331,0 |
| Generación ubicada | 12 322,9 (99,93 %) |
| Generación no ubicada | 8,1 (4 recursos) |
| Demanda asignada | 8 929,8 |
| Demanda no ubicada | 3 220,2 (154 nodos) |
| Diferencia generación − demanda | 3 393,1 |

Hallazgos de calidad: 157 traslados a frontera, 52 elementos excluidos, 699 imputaciones
(solo pérdidas de transformadores), 30 no modelados, 2 avisos de validación física
(generadores con P programada por encima de `p_max_mw` de PARATEC).

Islas: 12. La componente 0 (591 barras) es la energizada. Las otras 11 son artefactos de datos
con 1 o 2 barras cada una; en total 131,8 MW de generación y 113,4 MW de demanda quedan fuera.

Los supuestos del caso incluyen consigna 1,0 pu, barra de referencia de ángulo, referencia
distribuida, taps neutros, `i0 = 0`, SVC/STATCOM como reactiva, imputación, alcance 57,5 kV,
alias de subestaciones y versión del despacho.

**Lectura**: la cobertura del despacho supera el objetivo, pero la demanda no ubicada
(3 220 MW) explica el ajuste de −3 323 MW de la referencia y gran parte de las 50 violaciones
de tensión. Es el efecto de las tablas de equivalencias sin curar (T064).

## Escenario 3: validaciones y no convergencia

| Prueba | Resultado |
|---|---|
| `run --periodo 25` | `PERIOD_OUT_OF_RANGE`, "El periodo debe estar entre 1 y 24.", código 2 |
| `run --fecha 2000-01-01` | `SNAPSHOT_NOT_FOUND` con sugerencia de `sinsim scrape`, código 1 |
| `tests/integration/test_no_convergence.py` | 1 prueba pasa: `no_convergio`, `diagnostics` completo, `result = null` |
| Snapshot con un byte alterado (`-k corrupt`) | 1 prueba pasa: `SNAPSHOT_CORRUPTED` con el archivo afectado |

## Escenario 4: 24 periodos y redes de referencia

```
uv run pytest tests/integration/test_all_periods.py tests/integration/test_reference_networks.py
```

| Medida | Valor |
|---|---|
| Pruebas | 28 pasan (24 periodos + redes de referencia) |
| Tiempo total | 236 s |
| Por periodo | < 30 s cada uno (aserción de la prueba) |
| Cobertura por periodo | ≥ 95 % (aserción de la prueba) |

Nota: el plan preveía `case9`, `case14` y `case30` de MATPOWER. pandapower 3.5.6 ya no expone
`runpf`/`to_ppc` ni esos casos como solución de referencia, así que la validación usa una
solución Gauss-Seidel independiente y el `case9` de MATPOWER con error máximo 1e-6 pu
(SC-005).

## Escenario 5: actualización con fixtures

```
uv run pytest tests/integration/test_scrape_fixtures.py
```

7 pruebas pasan en 3,4 s con `httpx.MockTransport`: snapshot completo con manifiesto,
`SNAPSHOT_EXISTS` sin cambios en el segundo intento, código 4 sin directorio residual con una
entidad corrupta, y código 3 con el árbol de `data/` idéntico por hash ante un error de red.

## Escenario 6: interfaz y exportación

```
pnpm --dir frontend exec playwright test
```

Playwright levanta la API y Vite por sí mismo (`webServer`), así que no hace falta `make dev`
en otra terminal.

| Prueba | Resultado |
|---|---|
| Flujo completo (fecha, periodo 19, ejecutar, tablas, topología, coloreado, zip) | Pasa en 16,7 s |
| Periodo inválido rechazado con mensaje claro | Pasa en 0,4 s |

La prueba abre el zip descargado y lo compara con `GET /api/runs/{id}`: mismos archivos,
mismo `case_id` y traza, y cada barra, línea y generador coincide valor a valor (tolerancia
1e-9).

## Verificaciones de calidad del código (T080)

| Herramienta | Resultado |
|---|---|
| `pytest` (backend) | 128 pruebas pasan |
| `pytest --cov` (domain + adapters) | 96,48 %, umbral 85 % superado |
| `mypy --strict` | sin hallazgos en 51 archivos |
| `ruff check` y `ruff format --check` | limpio, 80 archivos formateados |
| `tsc -b`, `eslint .`, `vitest run` | limpio, 4 pruebas pasan |

`pre-commit run --all-files` no revisa nada mientras los archivos no estén en git (omite los
no rastreados); por eso se ejecutaron las herramientas directamente.

## Pendiente

- **T064**: curar a mano `data/equivalencias/recursos_despacho.csv` y `nodos_demanda.csv`.
  Las filas actuales son propuestas heurísticas marcadas "NO CURADA". Hasta entonces, 154
  nodos de demanda (3 220 MW) quedan sin ubicar y los resultados de tensión no son
  interpretables como estado del sistema.
