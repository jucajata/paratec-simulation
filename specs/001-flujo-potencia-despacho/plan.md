# Plan de implementación: Flujo de potencia del SIN con PARATEC, despacho programado y demanda por barra

**Rama**: `001-flujo-potencia-despacho` | **Fecha**: 2026-10-19 | **Spec**: [spec.md](./spec.md)

**Entrada**: especificación de la feature en `specs/001-flujo-potencia-despacho/spec.md`
(clarificada el 2026-10-19).

## Resumen

Se construye un modelo pandapower del STN + STR (≥ 57,5 kV) a partir de un snapshot inmutable
que reúne tres fuentes de XM, todas con trazabilidad y reporte de calidad. El flujo AC (o DC)
se corre para una fecha y un periodo:

| Fuente | Qué aporta | Acceso |
|---|---|---|
| PARATEC | Parámetros técnicos de los equipos | API JSON pública |
| `dDEC<MMDD>` | Despacho programado | API HTTPS del portal de XM |
| `PRON_BARRA<MMDD>` | Demanda P/Q por barra | API HTTPS del portal de XM |

Enfoque técnico:
- **Conciliación de nombres**: tablas de equivalencias versionadas; nunca coincidencia
  aproximada en tiempo de ejecución.
- **Referencia (slack)**: distribuida, con `runpp(distributed_slack=True)`.
- **Islas**: se detectan y se sacan de servicio antes de correr el flujo.
- **No convergencia**: diagnóstico calculado a partir del estado interno de Newton-Raphson.
- **Interfaces**: CLI `sinsim` (scrape, snapshots list, run), API FastAPI local e interfaz
  React con tablas y topología.

Detalle en [research.md](./research.md).

## Contexto técnico

| Aspecto | Valor |
|---|---|
| **Lenguaje/versión** | Python 3.12 (backend) · TypeScript strict (frontend) |
| **Dependencias principales** | pandapower==3.5.6, httpx, typer, fastapi, pydantic v2, uvicorn, pyarrow, duckdb · React, Vite, @tanstack/react-query, cytoscape (justificadas en research R12) |
| **Almacenamiento** | Archivos: snapshots (JSON/TXT crudos + Parquet normalizado + `manifest.json`) en `data/paratec/<fecha>/`; equivalencias CSV en `data/equivalencias/`; casos y ejecuciones en `cases/<case_id>/` (JSON). Sin servidor de base de datos |
| **Pruebas** | pytest + pytest-cov (≥ 85 % en `domain/` y `adapters/`), `httpx.MockTransport` con fixtures grabados, Vitest y Playwright (e2e de HU-4) |
| **Plataforma** | Local: macOS, Linux y Windows (WSL), monousuario, `127.0.0.1` |
| **Tipo de proyecto** | Aplicación web local (backend + frontend) con CLI |
| **Metas de rendimiento** | Construir el caso y correr el flujo AC de un periodo en menos de 30 s en un portátil (red de unas 1500 barras), para que SC-001 (< 10 min) tenga margen. `make demo` sin red |
| **Restricciones** | Sin red en el MVP (R-01); snapshots inmutables (III.4); sin llamadas reales a XM en las pruebas (R-03); versión de pandapower fija, porque el diagnóstico usa estado privado (`net._ppc`) |
| **Escala** | Snapshot real: 929 líneas, 1075 transformadores, unas 790 unidades de generación, 509 subestaciones, unos 625 recursos en `dDEC` y 552 nodos de demanda. Una ejecución corresponde a un periodo (NG-03) |

No quedan marcadores NEEDS CLARIFICATION: todos se resolvieron en research.md. Lo que no se
pudo verificar quedó como **decisión pendiente** (D-1 a D-6) o como **riesgo**.

## Revisión de cumplimiento de la constitución

*Gate previo a la Fase 0 y repetido después de la Fase 1. La Gobernanza exige verificar III,
IV y VI; se revisan todos los principios.*

### I. Naturaleza del proyecto

| Regla | Estado | Evidencia |
|---|---|---|
| Alcance (flujo AC/DC; sin N-1 ni cortocircuito en esta feature) | ✅ | NG-01 y NG-02 de la spec. Las capacidades de alcance que no entran aquí quedan para features futuras |
| Reproducibilidad sin red (`uv sync`, `pnpm install`, `make demo`) | ✅ | [quickstart.md](./quickstart.md), escenario 1. El snapshot real se versiona en el repo (D-1) |

### II. Stack

| Regla | Estado | Evidencia |
|---|---|---|
| Solo tecnologías de la tabla de stack; cada dependencia justificada | ✅ | research R12. No se agregan Playwright en el scraper, Plotly, librería de tablas, respx ni p3s |
| Sin servidor de base de datos | ✅ | |
| Backend y frontend solo vía OpenAPI | ✅ | [contracts/openapi.yaml](./contracts/openapi.yaml) |

### III. Reglas de dominio

| Regla | Estado | Evidencia |
|---|---|---|
| III.1 Conversiones solo en `adapters/sources_to_pandapower/`, con fórmula en el docstring y prueba con valor conocido | ✅ | Fórmulas en research R2, R3 y R6; ahí viven también las de los archivos de XM (MWh/h → MW) |
| III.2 f = 60 Hz y S_base = 100 MVA en un solo módulo | ✅ | `domain/constants.py` |
| III.3 raw → normalized → modelo; `raw/` inmutable | ✅ | [contracts/snapshot-format.md](./contracts/snapshot-format.md) |
| III.4 Snapshot inmutable con manifiesto | ✅ | Manifiesto con los campos exigidos, más `source_modified_at` y `standard_version`. Sin `--force` |
| III.5 Cero parámetros inventados; imputación explícita | ✅ | research R8: excluir por defecto; imputar solo con método declarado, columna `imputed` y reporte |
| III.6 Punto de operación de una fuente documentada | ✅ | `dDEC` (generación) y `PRON_BARRA` (demanda), documentados en la spec |
| III.7 Trazabilidad | ✅ | `Run.trace` ([data-model.md §6](./data-model.md)) |
| III.8 No convergencia como `no_convergio` con diagnóstico | ✅ | research R5. Además, las islas sin referencia se excluyen antes del cálculo para evitar los NaN con `converged=True` |
| III.9 Límites configurables con fuente | ✅ | research R9 (CREG 025/1995, CREG 153/2019) |
| III.10 Scraping responsable | ✅ | Tasa limitada, User-Agent descriptivo, sin paralelismo |
| III.10 Respetar los términos de uso de XM y redistribuir citando a XM | ✅ por decisión del usuario | D-1 (2026-10-20): los datos son públicos y se redistribuyen con la atribución "Información proporcionada por XM S.A. E.S.P. – PARATEC…" en el manifiesto, las exportaciones, la UI y el README. El riesgo frente al art. 6 de los términos de XM (research R4) lo asume el usuario. Recogido en la constitución 1.1.0 (III.10) |

### IV. Estructura y estilo

| Regla | Estado | Evidencia |
|---|---|---|
| Árbol de carpetas de la constitución | ✅ | Incluye `data/equivalencias/` y `config/` (constitución 1.1.0) |
| Dependencias `api → services → domain`; `domain` sin pandapower, httpx ni FastAPI | ✅ | Ver estructura abajo; las islas (networkx/pandapower) viven en `services/`; CLI y API acceden a snapshots solo vía `services/snapshots.py` (tasks T025) |
| `pandapowerNet` solo en `services/` y `adapters/` | ✅ | |
| Un único archivo de mapeo de campos PARATEC | ✅ | `adapters/sources_to_pandapower/field_mapping.py` |
| Fixtures grabados; cobertura ≥ 85 % | ✅ | |
| Comandos públicos: `scrape`, `snapshots list`, `run`, `make dev/demo/test` | ✅ | [contracts/cli.md](./contracts/cli.md) |

### V. Errores

| Regla | Estado | Evidencia |
|---|---|---|
| Problem Details + `user_message` + `trace_id` | ✅ | |
| Códigos HTTP | ✅ | `SNAPSHOT_NOT_FOUND`/`OPERATING_POINT_MISSING` → 404; `PERIOD_OUT_OF_RANGE` → 422 (esquema); fecha futura → 400; `SNAPSHOT_CORRUPTED` → 409 (constitución 1.1.0) |
| Códigos de salida del CLI 0–4 | ✅ | [contracts/cli.md](./contracts/cli.md) |
| Scraper atómico | ✅ | Directorio temporal + rename |
| Validación en tres puntos | ✅ | Pydantic (API), scraper ([data-model.md §2](./data-model.md)) y `domain/physical_checks.py` antes de simular (tasks T038): comprobaciones estructurales sin rangos numéricos inventados |

### VI. Agente

| Regla | Estado | Evidencia |
|---|---|---|
| Sin valores eléctricos inventados | ✅ | La consigna de 1,0 pu, `i0 = 0`, los taps en posición neutra y el límite = corriente nominal son decisiones del usuario (D-2, D-4) y se muestran como supuestos con esa fuente. Las impedancias de los transformadores entran sin convertir, en la convención de pandapower (usuario, 2026-10-20; research R6) |
| Contradicciones detectadas y escaladas | ✅ | D-1 a D-6, todas resueltas por el usuario el 2026-10-20 |

**Resultado del gate**:
- **PASA**, sin `TODO(fuente)` abiertos.
- **Después de la Fase 1**: pasa. Las decisiones D-1 a D-6 ya están aplicadas en
  research.md, data-model.md, contracts/ y en el caso borde de islas y versiones de despacho
  de la spec.

## Decisiones del usuario (2026-10-20)

| ID | Tema | Decisión | Dónde se aplica |
|---|---|---|---|
| **D-1** | Redistribución de datos de XM | Se publican en el repo: son públicos y de uso difundido. Atribución obligatoria: "Información proporcionada por XM S.A. E.S.P. – PARATEC y archivos públicos de despacho" | research R4; manifiesto, export, UI, README |
| **D-2** | Valores sin fuente regulatoria | Consigna de 1,0 pu en generadores y compensadores; `i0_percent = 0`; taps en `normalStep` (posición neutra según PARATEC, verificada en research R6). PARATEC trae el rango, el paso y el neutro; no hace falta otra fuente | research R6, R8, R10; supuestos del caso |
| **D-3** | Varias versiones de `dDEC` en el mismo día | Prevalece la `_V<n>` de mayor `n`; el archivo sin sufijo es V0. Se guardan todas en `raw/` y se advierte `DISPATCH_REVISED` | research R2; snapshot-format; cli |
| **D-4** | Límite de corriente de las líneas | La corriente nominal (`ratedCurrent`) es el 100 % | research R6 |
| **D-5** | Islas | El SIN es totalmente interconectado: una isla en el modelo es un artefacto de los datos. Solo se energiza la componente con la barra de ángulo; el resto se reporta como hallazgo con los MW perdidos. Se elimina la referencia de ángulo por isla | research R5; data-model §5; caso borde de la spec |
| **D-6** | SVC/STATCOM | Se modelan como fuentes de reactiva: `gen` con P = 0, Q ∈ [−inductivo, +capacitivo], consigna D-2 y `enforce_q_lims`. Probado en pandapower 3.5.6; `create_svc` y `create_ssc` se descartaron (research R6) | research R6; data-model §2 |

**Pendiente fuera de este plan**: la opción `--force` de FR-004 sigue en "Decisiones
pendientes" de la spec. Este plan la excluye, de acuerdo con la constitución III.4.

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| SC-004 (convergencia en los 24 periodos) con STN + STR y una brecha de demanda de unos 218 MW sin explicar (research R3) | Alto | Referencia distribuida; `init="dc"`; `enforce_q_lims` (compatibilidad con la referencia distribuida verificada en case14); SVC/STATCOM como soporte de reactiva (D-6); la prueba `test_all_periods` es la que da el veredicto |
| Taps en posición neutra y consigna uniforme de 1,0 pu (D-2) pueden dar perfiles de tensión lejanos a la operación real, o violaciones que no ocurren | Medio | Se declaran como supuestos visibles en cada caso y exportación. Una mejora futura (feature aparte, fuera de esta) sería que los cambiadores bajo carga (`ltcFlag`) regulen tensión automáticamente con los datos de PARATEC |
| APIs no documentadas (PARATEC backend, portal de XM) pueden cambiar | Medio | Validación de esquema y código 4; fixtures grabados; nunca hay respaldo silencioso |
| Esfuerzo de curación de equivalencias (unos 625 recursos y 552 nodos) | Medio | El heurístico propone y una persona revisa (R7); SC-003 mide la cobertura lograda |
| Diagnóstico basado en `net._ppc` (privado) | Bajo | Versión de pandapower fija y prueba de contrato |
| Textos libres de PARATEC (`connectionPoint`, `subStation`) | Medio | Parser con pruebas sobre los registros reales del snapshot; lo que no se puede parsear se excluye y se reporta |

## Estructura del proyecto

### Documentación (esta feature)

```text
specs/001-flujo-potencia-despacho/
├── plan.md              # este archivo
├── research.md          # Fase 0
├── data-model.md        # Fase 1
├── quickstart.md        # Fase 1
├── contracts/
│   ├── openapi.yaml     # API REST local
│   ├── cli.md           # comandos sinsim y make
│   ├── snapshot-format.md
│   └── export-format.md
└── tasks.md             # Fase 2 (/speckit-tasks)
```

### Código fuente (raíz del repositorio)

```text
backend/
├── pyproject.toml
├── src/sinsim/
│   ├── cli.py                          # Typer: scrape, snapshots list, run
│   ├── domain/
│   │   ├── constants.py                # F_HZ, S_BASE_MVA (III.2)
│   │   ├── errors.py                   # catálogo único de códigos (V)
│   │   ├── entities.py                 # Snapshot, StudyCase, QualityReport, Run, RunResult
│   │   ├── case_hash.py                # JSON canónico + SHA-256 (puro)
│   │   ├── balance.py                  # balance y cobertura (puro)
│   │   ├── limits.py                   # violaciones de tensión y cargabilidad (puro)
│   │   ├── physical_checks.py          # validación física antes de simular (puro, V)
│   │   └── ports.py                    # interfaces que implementan los adapters
│   ├── observability.py                # logs JSON con trace_id (V)
│   ├── adapters/
│   │   ├── sources_to_pandapower/
│   │   │   ├── field_mapping.py        # único mapeo de campos PARATEC → internos
│   │   │   ├── buses.py · lines.py · trafos.py · generators.py · shunts.py
│   │   │   ├── xm_dispatch.py          # dDEC: MWh/h → MW
│   │   │   ├── xm_demand.py            # PRON_BARRA: P = Act + PSTR, Q
│   │   │   └── net_builder.py          # arma el pandapowerNet
│   │   └── storage/
│   │       ├── snapshots.py            # manifiesto, checksums, Parquet, DuckDB
│   │       ├── equivalences.py         # CSV con vigencias
│   │       ├── cases.py                # cases/<case_id>/ (net.json, caso, ejecuciones)
│   │       └── export.py               # CSV + metadatos.json + zip
│   ├── scraper/
│   │   ├── http.py                     # httpx: User-Agent, límite de tasa, timeouts
│   │   ├── paratec.py                  # endpoints de R1
│   │   ├── xm_files.py                 # listado y descarga del portal de XM (R2, R3)
│   │   ├── validate.py                 # validaciones de esquema (FR-005)
│   │   └── writer.py                   # escritura atómica + manifiesto
│   ├── services/
│   │   ├── snapshots.py                # listar y verificar
│   │   ├── build_case.py               # conciliación, traslados, imputación, islas, supuestos
│   │   ├── islands.py                  # networkx/pandapower.topology
│   │   ├── run_flow.py                 # runpp/rundcpp, referencia distribuida
│   │   └── diagnostics.py              # desbalance y peores barras
│   └── api/
│       ├── app.py · problems.py · schemas.py
│       └── routers/ snapshots.py · cases.py · runs.py
└── tests/
    ├── fixtures/{paratec,xm}/          # respuestas grabadas (sin red)
    ├── unit/                           # conversiones con valor conocido, parsers, dominio
    ├── integration/                    # build+run, 24 periodos, redes de referencia, scraper
    └── contract/                       # OpenAPI, CLI, export, diagnóstico de pandapower

frontend/
└── src/
    ├── api/                            # cliente tipado de openapi.yaml + hooks TanStack Query
    ├── features/
    │   ├── run-picker/                 # fecha, periodo, tipo de flujo
    │   ├── case-quality/               # reporte de calidad y balance (HU-2)
    │   ├── results-tables/             # tablas filtrables y violaciones (HU-4)
    │   └── topology/                   # Cytoscape coloreable (FR-033)
    ├── components/
    └── lib/

data/
├── paratec/<YYYY-MM-DD>/               # snapshot (contracts/snapshot-format.md)
└── equivalencias/                      # recursos_despacho.csv, nodos_demanda.csv
config/
└── defaults.toml                       # límites (con fuente), reglas de imputación,
                                        # consignas, barra de ángulo, tasa del scraper
cases/                                  # caso de demo versionado; los demás en .gitignore
Makefile
```

**Decisión de estructura**: se sigue exactamente el árbol de la constitución IV v1.1.0
(backend + frontend + `data/paratec/` + `data/equivalencias/` + `config/` + `cases/`).

## Complejidad y desviaciones

No hay desviaciones. Las cinco que tenía la versión anterior de este plan (`data/equivalencias/`,
`config/`, el paquete `sources_to_pandapower`, `SNAPSHOT_CORRUPTED` → 409 y el comando
`sinsim run`) quedaron incorporadas en la enmienda 1.1.0 de la constitución (2026-10-20).
