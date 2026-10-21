# Tareas: Flujo de potencia del SIN con PARATEC, despacho programado y demanda por barra

**Entrada**: documentos de diseño en `specs/001-flujo-potencia-despacho/`
**Prerrequisitos**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)
**Constitución**: v1.1.0. Las pruebas son condición de cierre (VI.6); `domain/` y `adapters/`
necesitan ≥ 85 % de cobertura (IV); ninguna prueba llama a PARATEC ni a XM (R-03).

**Organización**: por historia de usuario. Cada fase es un incremento que se prueba solo.

## Formato: `[ID] [P?] [Historia] Descripción con ruta`

- **[P]**: puede ir en paralelo (archivos distintos, sin dependencias pendientes).
- **[US1..US4]**: historia de usuario de la spec (HU-1..HU-4).
- Rutas relativas a la raíz del repo. Identificadores en inglés, textos al usuario en español.

## Convenciones de rutas

- Backend: `backend/src/sinsim/` y `backend/tests/`.
- Frontend: `frontend/src/`.
- Datos: `data/paratec/<fecha>/`, `data/equivalencias/`, `config/`, `cases/`.

---

## Fase 1: Setup (infraestructura compartida)

**Propósito**: estructura del repo, dependencias fijadas y herramientas de calidad.

- [X] T001 Crear el árbol de carpetas del plan: `backend/src/sinsim/{api/routers,domain,services,adapters/sources_to_pandapower,adapters/storage,scraper}`, `backend/tests/{unit,integration,contract,fixtures/paratec,fixtures/xm,fixtures/equivalencias}`, `frontend/src/{api,features,components,lib}`, `data/paratec`, `data/equivalencias`, `config`, `cases`, `docs`, con `__init__.py` en cada paquete Python
- [X] T002 Crear `backend/pyproject.toml` (uv, `requires-python = ">=3.12,<3.13"`): dependencias fijadas `pandapower==3.5.6`, `httpx`, `typer`, `fastapi`, `pydantic>=2`, `uvicorn`, `pyarrow`, `duckdb`, `networkx`; dev `pytest`, `pytest-cov`, `ruff`, `mypy`; entry point `sinsim = "sinsim.cli:app"`; generar `backend/uv.lock` con `uv lock`
- [X] T003 [P] Configurar ruff (lint + format, reglas `D` con `convention = "google"`), mypy strict y `.pre-commit-config.yaml` en `backend/pyproject.toml` y `.pre-commit-config.yaml` (constitución IV)
- [X] T004 [P] Inicializar `frontend/` con Vite + React + TypeScript (`strict: true`) y pnpm; dependencias `@tanstack/react-query`, `cytoscape`; dev `vitest`, `@playwright/test`, ESLint; archivos `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`
- [X] T005 [P] Escribir `Makefile` con `dev` (uvicorn en 127.0.0.1:8000 + Vite en 127.0.0.1:5173), `demo` (`uv run sinsim run --fecha 2026-10-20 --periodo 19 --exportar out/demo`) y `test` (pytest con cobertura + vitest + playwright), según [contracts/cli.md](./contracts/cli.md)
- [X] T006 [P] Escribir `.gitignore`: `backend/.venv`, `frontend/node_modules`, `out/`, `cases/*` excepto `cases/demo/`, `.pytest_cache`, `coverage`
- [X] T007 [P] Escribir `README.md` en español: propósito, comandos públicos, leyenda "flujo sobre despacho programado" y la atribución "Información proporcionada por XM S.A. E.S.P. – PARATEC y archivos públicos de despacho" (constitución III.10)
- [X] T008 [P] Escribir `config/defaults.toml` con: límites de tensión por nivel (500 kV 0,90–1,05; 220/230 kV 0,90–1,10; STR 0,90–1,10) y cargabilidad 100 %, cada uno con su fuente (research R9); `generator.vm_pu_default = 1.0` con fuente "supuesto aprobado por el usuario 2026-10-20"; `trafo.i0_percent = 0`; `imputation.rule = "exclude"` y lista `imputation.params = []`; `scraper.min_interval_s`, `scraper.user_agent = "sinsim/<version> (+https://github.com/jucajata/paratec-simulation)"`; `solver = {algorithm="nr", tolerance_mva=1e-8, max_iteration=30, init="dc", enforce_q_lims=true}`; `angle_ref_bus` vacío con comentario del criterio (se fija en T064)

---

## Fase 2: Fundacional (prerrequisitos bloqueantes)

**Propósito**: dominio puro, lectura/escritura de snapshots, normalización raw → normalized y
fixtures. Ninguna historia puede empezar sin esto.

**⚠️ CRÍTICO**: las conversiones de unidades viven solo en `adapters/sources_to_pandapower/`
(III.1), cada una con la fórmula en el docstring y una prueba con valor conocido.

- [X] T009 Crear `backend/src/sinsim/domain/constants.py` con `F_HZ = 60` y `S_BASE_MVA = 100` (constitución III.2; ningún otro archivo los redefine)
- [X] T010 [P] Crear `backend/src/sinsim/domain/errors.py`: clase `DomainError(code, user_message, http_status, exit_code, detail)` y catálogo único: `SNAPSHOT_NOT_FOUND` (404/1), `SNAPSHOT_EXISTS` (409/1), `SNAPSHOT_CORRUPTED` (409/1), `OPERATING_POINT_MISSING` (404/1), `PERIOD_OUT_OF_RANGE` (422/2), `INVALID_DATE` (400/2), `PARAM_MISSING`, `PARATEC_SCHEMA_CHANGED` (502/4), `XM_FILE_SCHEMA_CHANGED` (502/4), `DISPATCH_TOTAL_MISMATCH` (4), `EQUIVALENCE_OVERLAP` (4), `NETWORK_ERROR` (503/3), `PHYSICAL_CHECK_FAILED` (400/4); `user_message` en español y accionable (constitución V)
- [X] T011 [P] Crear `backend/src/sinsim/domain/entities.py` con modelos Pydantic v2 inmutables de [data-model.md](./data-model.md): `SourceFile`, `Manifest` (`schema_version=1`, `extracted_at`, `scraper_version`, `attribution`, `sources[]` con `source_modified_at` obligatorio para XM y `standard_version`, `dispatch_version {used, available}`, `record_counts`, `files[] {path, sha256, bytes}`), `Snapshot` (`availability {paratec, despacho, demanda}`), `CaseInputs`, `StudyCase`, `QualityReport` (secciones §5 y `balance`), `Run` (`flow_type ∈ {ac, dc}`, `status ∈ {convergio, no_convergio}`, `trace` con los 8 campos obligatorios de FR-023, `diagnostics` obligatorio si `no_convergio`), `RunResult` (tablas §7)
- [X] T012 [P] Crear `backend/src/sinsim/domain/ports.py` con protocolos `SnapshotRepository`, `EquivalenceRepository`, `CaseRepository` (sin importar pandapower, httpx ni FastAPI)
- [X] T013 [P] Crear `backend/src/sinsim/observability.py`: logging estructurado JSON con `trace_id` por petición o invocación de CLI (constitución V). Es un módulo añadido al árbol del plan porque V lo exige
- [X] T014 Crear `backend/src/sinsim/adapters/sources_to_pandapower/field_mapping.py`: único diccionario nombre-de-campo-PARATEC → nombre interno para líneas, subestaciones, transformadores, unidades, reactores, condensadores y SVC/STATCOM (constitución IV)
- [X] T015 [P] Crear `backend/src/sinsim/adapters/sources_to_pandapower/buses.py`: función pura que construye la tabla `buses` desde `SubstationInfo.voltageLevel[]` con `bus_id = "<SUBESTACIÓN>|<kV>"`, `level` = STN (≥ 220), STR (≥ 57,5 y < 220) o SDL (< 57,5); helper `parse_connection_point("GUATAPE 220") -> (substation, vn_kv)` que devuelve `None` si no se puede parsear
- [X] T016 [P] Crear `backend/src/sinsim/adapters/sources_to_pandapower/lines.py`: extremos desde `subStation` "A - B" con respaldo `sub1/sub2` del mapa; agregación en serie de `typeLines[]`: `r_ohm_per_km = Σ(rᵢ·lᵢ)/Σlᵢ`, igual para X, `c_nf_per_km = (Σ(bᵢ·lᵢ)/Σlᵢ)·1e3/(2π·60)` con B en µS/km, `length_km = Σlᵢ`, `max_i_ka = ratedCurrent/1000` (D-4); valores "-" o "N/A" → `missing_params`; fórmulas en docstring (III.1)
- [X] T017 [P] Crear `backend/src/sinsim/adapters/sources_to_pandapower/trafos.py`: bidevanado → `trafos2w` (`vk_percent = impedanceHighLow`, `vkr_percent = P_cu_kW/(sn_mva·1000)·100`, `pfe_kw = ironLosses`, `i0_percent = 0`); tridevanado → `trafos3w` (`vk_hv = impedanceHighMedium`, `vk_mv = impedanceMediumLow`, `vk_lv = impedanceHighLow`, `vkr` con base `min(S_a, S_b)` del par); taps `tap_min = lowStep`, `tap_max = highStep`, `tap_neutral = tap_pos = normalStep`, `tap_step_percent = step` con orientación "paso mayor → tensión menor" (research R6); sin cambiador si `step` o `lowStep` es "-"; "-"/"N/A" → `missing_params`
- [X] T018 [P] Crear `backend/src/sinsim/adapters/sources_to_pandapower/generators.py`: unidades hidráulicas, térmicas, solares equivalentes y eólicas → tabla `generators` (`unit_id`, `plant`, `bus` vía `parse_connection_point`, `p_max_mw = ratedNetMaxP`, `min_q_mvar = -minQ`, `max_q_mvar = +maxQ`, `tech ∈ {hidráulica, térmica, solar, eólica}`); sin `connectionPoint` parseable → `missing_params`
- [X] T019 [P] Crear `backend/src/sinsim/adapters/sources_to_pandapower/shunts.py`: reactores (`q_mvar = -nominalCapacity`) y condensadores (`q_mvar = +ratedCapacity`) → tabla `shunts`; SVC/STATCOM → tabla `svc_statcom` (`cap_mvar = capacitiveRating`, `ind_mvar = inductiveRating`, `kind`)
- [X] T020 [P] Crear `backend/src/sinsim/adapters/sources_to_pandapower/xm_dispatch.py`: parser de `dDEC` (fila `"<RECURSO>",v1..v24`, separador "," o ";", fila `"Total"` como control); `mwh_per_period_to_mw` (identidad para periodos de 1 h, documentada); validación `|Σrecursos − Total| ≤ 0,01 MW` por periodo → `DISPATCH_TOTAL_MISMATCH`; `select_dispatch_version(files)` que elige `_V<n>` de mayor `n` y trata el archivo sin sufijo como V0 (D-3)
- [X] T021 [P] Crear `backend/src/sinsim/adapters/sources_to_pandapower/xm_demand.py`: parser de `PRON_BARRA` (columnas `UCP, NODO, kV, CONCEPTO, HORA01..24`; acepta `Ener.Act.`, `Ener.Reac`/`Ener.Reac.`, `Perd.PSTR`/`Perd.PSTR.`); exige los 3 conceptos por nodo; produce filas `demand` con `p_act_mw`, `p_pstr_mw`, `q_mvar` (MWh/h → MW y Mvar, research R3)
- [X] T022 Crear `backend/src/sinsim/scraper/validate.py`: reglas de [data-model.md §2](./data-model.md): columnas esperadas por entidad, exactamente 24 valores por fila, `period ∈ [1, 24]`, total de `dDEC`, 3 conceptos por nodo, valores numéricos; cada fallo → `PARATEC_SCHEMA_CHANGED` o `XM_FILE_SCHEMA_CHANGED` con la entidad en `detail`
- [X] T023 Crear `backend/src/sinsim/scraper/writer.py`: `write_snapshot(raw_files, out_dir, date)` que escribe en `<out>/.tmp-<fecha>/`, normaliza con T015–T021 a Parquet (`buses, lines, trafos2w, trafos3w, generators, shunts, svc_statcom, dispatch, demand`, todas con `source_id`, `imputed`, `imputation_method`, `missing_params`), valida con T022, calcula SHA-256 de cada archivo, escribe `manifest.json` según [contracts/snapshot-format.md](./contracts/snapshot-format.md) y solo al final renombra a `<out>/<fecha>/`; si falla, borra el temporal; si `<out>/<fecha>/` existe → `SNAPSHOT_EXISTS`
- [X] T024 Crear `backend/src/sinsim/adapters/storage/snapshots.py` (implementa `SnapshotRepository`): `list()` con `availability` e `intact`, `load(date)` que recalcula SHA-256 y lanza `SNAPSHOT_CORRUPTED` indicando el archivo, lectura de Parquet con DuckDB, `SNAPSHOT_NOT_FOUND`
- [X] T025 Crear `backend/src/sinsim/services/snapshots.py`: `list_snapshots()` y `load_verified(date)` que usan `SnapshotRepository` y devuelven entidades de dominio; es la única entrada a snapshots para CLI y API (constitución IV: `api → services → domain`)
- [X] T026 [P] Crear `backend/src/sinsim/adapters/storage/equivalences.py` (implementa `EquivalenceRepository`): lee `recursos_despacho.csv` y `nodos_demanda.csv` de [contracts/snapshot-format.md §3](./contracts/snapshot-format.md), valida vigencias solapadas → `EQUIVALENCE_OVERLAP`, `resolve_resource(name, date)` y `resolve_node(node, vn_kv, date)` devuelven `None` si no hay fila vigente
- [X] T027 Copiar los archivos crudos ya descargados al directorio de fixtures: PARATEC (22 JSON de `scratchpad/paratec/api/`, p. ej. `reportetransmision_api_Line_getAll.json`) a `backend/tests/fixtures/paratec/`, y de `scratchpad/dl/` `descarga-archivo.out` como `backend/tests/fixtures/xm/dDEC1020.txt`, `dDEC1014.txt`, `dDEC1014_V1.txt`, `PB1020.txt` como `PRON_BARRA1020.txt`; crear `backend/tests/fixtures/equivalencias/{recursos_despacho.csv,nodos_demanda.csv}` con unas 20 filas curadas a mano que cubran GUATAPE, SAN CARLOS, CHIVOR, GUAVIO, los nodos de Uantioquia de la muestra y un recurso inexistente ("PLANTA_FANTASMA"). Ruta origen: `/private/tmp/claude-502/-Users-jucajata-dev-paratec-simulation/f363aa72-b7ae-4819-a7e4-71e4811cc2cb/scratchpad/` (se pierde al cerrar la sesión)
- [X] T028 Crear `backend/tests/conftest.py` con fixture `fixture_snapshot(tmp_path)` que invoca `writer.write_snapshot` sobre `backend/tests/fixtures/` para la fecha `2026-10-20` y fixture `equivalences_repo` sobre `backend/tests/fixtures/equivalencias/`
- [X] T029 [P] Pruebas unitarias con valores conocidos en `backend/tests/unit/test_lines.py`, `test_trafos.py`, `test_generators.py`, `test_shunts.py`, `test_buses.py`: un registro real de cada fixture → parámetros esperados calculados a mano; orientación de taps; "-" → `missing_params`
- [X] T030 [P] Pruebas unitarias en `backend/tests/unit/test_xm_dispatch.py` y `test_xm_demand.py`: parseo de `dDEC1020` (626 recursos + Total), `DISPATCH_TOTAL_MISMATCH` con un total alterado, selección V0/V1 con `dDEC1014`, parseo de `PRON_BARRA1020` (552 nodos × 3 conceptos), etiquetas con y sin punto final
- [X] T031 Pruebas de integración en `backend/tests/integration/test_snapshot_storage.py`: `write_snapshot` crea manifiesto completo y checksums válidos; `SNAPSHOT_EXISTS` sin tocar nada; un byte alterado → `SNAPSHOT_CORRUPTED` con el archivo; fallo de validación → no queda `.tmp-*` ni destino (SC-006)

**Checkpoint**: snapshot de fixtures legible, normalizado y verificado. Las historias pueden empezar.

---

## Fase 3: Historia de usuario 1 - Correr un flujo de potencia con datos incluidos (Prioridad: P1) 🎯 MVP

**Objetivo**: construir el caso para una fecha y un periodo, correr el flujo AC (o DC) y
entregar resultados trazables, o `no_convergio` con diagnóstico. CLI `sinsim run` y API.

**Prueba independiente**: `backend/tests/integration/test_build_and_run.py` sobre el snapshot
de fixtures produce `convergio` con la trazabilidad completa; `make demo` sobre el snapshot
incluido se valida al cerrar la fase 5 (T065).

### Implementación de la historia 1

- [X] T032 [P] [US1] Crear `backend/src/sinsim/domain/case_hash.py`: `canonical_json(CaseInputs)` con claves ordenadas y floats con `repr`, y `case_id = sha256(...)`; determinista entre ejecuciones
- [X] T033 [P] [US1] Crear `backend/src/sinsim/domain/limits.py`: funciones puras que marcan `violation ∈ {null, low, high}` por barra según el límite de su nivel de tensión y `overload` por rama cuando `loading_percent > límite`, leyendo los valores y fuentes de `config/defaults.toml`
- [X] T034 [US1] Crear `backend/src/sinsim/adapters/sources_to_pandapower/net_builder.py`: `build_net(tables, case_inputs, config) -> pandapowerNet` solo con barras ≥ 57,5 kV; líneas, `trafo`/`trafo3w` (sin cambiador si falta), `shunt`; cada generador despachado como `gen` con `p_mw` programado, `vm_pu` de la consigna, límites de Q, `slack_weight = p_mw` (FR-015); SVC/STATCOM como `gen` con `p_mw = 0`, `slack_weight = 0`, `min_q = -ind`, `max_q = +cap` y la misma consigna que un PV ya presente en la barra (D-6); enlaces internacionales como `sgen` de P fija (NG-11); cargas con `p_mw = p_act + p_pstr`, `q_mvar = q` (FR-014); un `gen` con `slack=True` en `angle_ref_bus`
- [X] T035 [US1] Crear `backend/src/sinsim/services/build_case.py`: `build_case(snapshot_date, dispatch_date, period, config) -> StudyCase`: valida `period ∈ [1, 24]` (`PERIOD_OUT_OF_RANGE`), exige despacho y demanda (`OPERATING_POINT_MISSING`), concilia recursos y nodos con las equivalencias (FR-011); P = 0 → generador fuera de servicio; recurso con unidades en varias barras → reparto ∝ `p_max_mw` registrado como supuesto; traslado a la frontera STR/SDL: barra de la misma subestación con nivel ≥ 57,5 kV más bajo unida por un transformador al nivel original, si no existe → no ubicado (FR-019, FR-014a); supuestos visibles (consigna, barra de ángulo, factores de participación, repartos, traslados, taps neutros, `i0 = 0`, SVC como reactiva); advertencias `PROGRAM_NOT_REAL_STATE` siempre, `DATES_DIFFER` si las fechas difieren, `DISPATCH_REVISED` si `dispatch_version.used ≠ V0`; `CaseInputs` con los 3 hashes (manifiesto, equivalencias, configuración), las fechas, el periodo, la versión y `case_id`
- [X] T036 [US1] Crear `backend/src/sinsim/services/islands.py`: componentes conexas con `pandapower.topology.create_nxgraph` + `networkx.connected_components`; conserva la componente con `angle_ref_bus`, saca de servicio las demás y devuelve `islands[]` con `island_id`, `n_buses`, `buses[]`, `p_gen_lost_mw`, `p_demand_lost_mw`, `energized` (D-5); se ejecuta antes de cualquier flujo
- [X] T037 [US1] Crear `backend/src/sinsim/services/diagnostics.py`: a partir de `net._ppc["internal"]` (`V`, `Ybus`, `bus`, `gen`) calcula `mis = (V·conj(Ybus·V) − Sbus)·baseMVA`, `max_mismatch_mva`, `iterations = net._ppc["iterations"]` y las 10 peores barras mapeadas con `net._pd2ppc_lookups["bus"]` (research R5)
- [X] T038 [US1] Crear `backend/src/sinsim/domain/physical_checks.py`: función pura `check_case(tables) -> list[PhysicalIssue]` con comprobaciones estructurales, sin rangos numéricos inventados (R-13): r/x/longitud de líneas > 0, `vn_kv` > 0, `sn_mva` > 0, `vk_percent` > 0, `0 ≤ p_mw ≤ p_max_mw` por generador, `min_q ≤ max_q`, carga P ≥ 0, ninguna barra sin nivel de tensión; cada hallazgo bloquea la ejecución con `PHYSICAL_CHECK_FAILED` y aparece en el reporte de calidad (constitución V, "validación física antes de simular")
- [X] T039 [US1] Crear `backend/src/sinsim/services/run_flow.py`: `run(case, flow_type) -> Run`: invoca `physical_checks.check_case` antes de cualquier flujo; AC con `pp.runpp(net, algorithm="nr", distributed_slack=True, enforce_q_lims=True, init="dc", calculate_voltage_angles=True, tolerance_mva, max_iteration)` capturando `LoadflowNotConverged` → `status = no_convergio` + `diagnostics`, sin `result` (FR-022); DC con `pp.rundcpp` y `label = "Aproximación DC sobre despacho programado"` (FR-021); `trace` con los 8 campos (FR-023); `RunResult` con `vm_kv = vm_pu·vn_kv`, `slack_adjust_mw = p_mw − p_scheduled_mw`, violaciones vía T033 y `summary`
- [X] T040 [US1] Crear `backend/src/sinsim/adapters/storage/cases.py` (implementa `CaseRepository`): `cases/<case_id>/case.json`, `net.json` (`pp.to_json`), `runs/<run_id>.json`; `get_case` → `CASE_NOT_FOUND` (404) y `get_run` → `RUN_NOT_FOUND` (404), añadidos al catálogo de T010
- [X] T041 [US1] Crear `backend/src/sinsim/cli.py` con Typer: `sinsim snapshots list [--json]` (columnas `fecha | paratec | despacho | demanda | íntegro`, vía `services/snapshots.py`) y `sinsim run --fecha --periodo [--fecha-despacho] [--tipo ac|dc] [--json]` con la salida de texto de [contracts/cli.md](./contracts/cli.md) (trazabilidad, leyenda FR-026, balance, estado, 10 peores en tensión y cargabilidad o diagnóstico) y códigos de salida 0/1/2/3/4 derivados de `DomainError.exit_code`
- [X] T042 [US1] Crear `backend/src/sinsim/api/app.py`, `api/problems.py` y `api/schemas.py`: FastAPI en `127.0.0.1`, handler que convierte `DomainError` y errores de validación en Problem Details RFC 9457 extendido (`type` = `https://github.com/jucajata/paratec-simulation/errors/<code-en-kebab>`, `title`, `status`, `detail`, `code`, `user_message`, `trace_id`), 500 con `trace_id` y sin stack trace, logs JSON de T013
- [X] T043 [P] [US1] Crear `backend/src/sinsim/api/routers/snapshots.py`: `GET /api/snapshots` → `SnapshotSummary[]` de [contracts/openapi.yaml](./contracts/openapi.yaml), vía `services/snapshots.py`
- [X] T044 [P] [US1] Crear `backend/src/sinsim/api/routers/cases.py`: `POST /api/cases` (`CaseRequest`; 201 si es nuevo, 200 si el `case_id` ya existe; 400 fecha futura; 404; 422) y `GET /api/cases/{case_id}`
- [X] T045 [P] [US1] Crear `backend/src/sinsim/api/routers/runs.py`: `POST /api/cases/{case_id}/runs` (siempre 200, incluso `no_convergio`) y `GET /api/runs/{run_id}`
- [X] T046 [P] [US1] Pruebas unitarias en `backend/tests/unit/test_case_hash.py` (determinismo, cambio de un hash cambia el id) y `backend/tests/unit/test_net_builder.py` (gen con `slack_weight`, SVC como gen de reactiva, carga = act + pstr, un solo `slack=True`)
- [X] T047 [US1] Prueba de integración `backend/tests/integration/test_build_and_run.py` sobre `fixture_snapshot`: AC → `convergio`, `trace` completo, `summary` coherente (Σgen ≈ Σcarga + pérdidas); DC → etiqueta de aproximación; `--fecha-despacho` distinta → `DATES_DIFFER`; fixture sin `dDEC` → `OPERATING_POINT_MISSING`; periodo 25 → `PERIOD_OUT_OF_RANGE`
- [X] T048 [P] [US1] Prueba de integración `backend/tests/integration/test_no_convergence.py`: caso derivado del fixture con una carga multiplicada por 50 → `no_convergio`, `diagnostics.iterations`, `max_mismatch_mva`, 10 `worst_buses`, `result is None`
- [X] T049 [P] [US1] Prueba de integración `backend/tests/integration/test_reference_networks.py`: `pandapower.networks.case9/case14/case30` con los parámetros del solver de `config/defaults.toml` frente a PYPOWER `runpf` → error máximo 1e-6 pu en `vm_pu` (SC-005)
- [X] T050 [P] [US1] Prueba de contrato `backend/tests/contract/test_pandapower_internals.py`: la versión instalada es 3.5.6 y `net._ppc` expone `iterations` e `internal.{V,Ybus,bus,gen}` tras una no convergencia forzada
- [X] T051 [US1] Prueba de contrato `backend/tests/contract/test_api.py` con `TestClient`: cada ruta de [contracts/openapi.yaml](./contracts/openapi.yaml) existe en el OpenAPI generado; un error devuelve `application/problem+json` con los 7 campos; `POST /api/cases` repetido → 200; `POST .../runs` con no convergencia → 200 y `status = no_convergio`
- [X] T052 [US1] Prueba de contrato `backend/tests/contract/test_cli.py` con `typer.testing.CliRunner`: códigos de salida 0 (convergio), 0 (no_convergio), 1 (`SNAPSHOT_NOT_FOUND`), 2 (periodo 25, fecha mal formada); `--json` es JSON válido con `case`, `run`

**Checkpoint**: `sinsim run` y la API producen resultados o `no_convergio` con diagnóstico sobre el snapshot de fixtures.

---

## Fase 4: Historia de usuario 2 - Revisar la calidad del caso antes de interpretar (Prioridad: P1)

**Objetivo**: que el reporte de calidad liste todo lo que no quedó representado y el balance
muestre la cobertura del despacho.

**Prueba independiente**: con un despacho que incluye "PLANTA_FANTASMA", el reporte la lista
como no ubicada con sus MW y el balance lo refleja.

### Implementación de la historia 2

- [X] T053 [P] [US2] Crear `backend/src/sinsim/domain/balance.py`: función pura `compute_balance(...)` → `p_scheduled_total_mw`, `p_located_mw`, `p_unlocated_mw`, `coverage_pct = p_located/p_scheduled·100` solo con recursos de P > 0, `p_demand_mw`, `p_demand_unlocated_mw`, `difference_mw` ([data-model.md §5](./data-model.md))
- [X] T054 [US2] Completar `QualityReport` en `backend/src/sinsim/services/build_case.py`: `unlocated_resources[] {resource, p_mw}` (solo P > 0, SC-002), `unlocated_demand[] {node, vn_kv, p_mw, q_mvar}`, `transfers[] {element, kind ∈ {gen, demand}, from_bus, to_bus, p_mw, q_mvar}`, `excluded[] {element, kind, missing_params[]}`, `imputed[] {element, param, method, value}` con método "mediana de elementos del mismo tipo y nivel de tensión en el snapshot" solo para los parámetros de `imputation.params` (research R8), `not_modeled[] {element, kind, reason}`, `islands[]` de T036 y `balance` de T053
- [X] T055 [US2] Ampliar `sinsim run` en `backend/src/sinsim/cli.py`: imprime antes del flujo el resumen del reporte de calidad (conteos por sección, MW no ubicados, cobertura %, islas con MW perdidos) y lo incluye en `--json` como `case.quality`
- [X] T056 [P] [US2] Pruebas unitarias `backend/tests/unit/test_balance.py` y `backend/tests/unit/test_limits.py` con valores conocidos (cobertura con recursos de 0 MW excluidos del denominador; violación low/high en el límite exacto)
- [X] T057 [US2] Prueba de integración `backend/tests/integration/test_quality_report.py` sobre `fixture_snapshot`: "PLANTA_FANTASMA" aparece en `unlocated_resources` con sus MW y resta cobertura; un transformador del fixture con `impedanceHighLow = "-"` aparece en `excluded` con `missing_params`; un generador en barra de 44 kV aparece en `transfers` hacia la barra de 110 kV de su subestación; una línea eliminada artificialmente crea una isla que se reporta con sus MW; `balance` completo (HU-2.1–2.4)

**Checkpoint**: HU-1 y HU-2 funcionan juntas sobre fixtures; nada se descarta en silencio.

---

## Fase 5: Historia de usuario 3 - Actualizar datos para otra fecha (Prioridad: P2)

**Objetivo**: `sinsim scrape --fecha` descarga PARATEC, `dDEC` y `PRON_BARRA`, valida y
escribe un snapshot atómico. Al final de esta fase se genera y versiona el snapshot real que
exige FR-001, y con él se validan `make demo`, SC-003 y SC-004.

**Prueba independiente**: con `httpx.MockTransport` y los fixtures, el comando produce un
snapshot completo en un directorio temporal, y en cada fallo deja `data/` intacto.

### Implementación de la historia 3

- [X] T058 [US3] Crear `backend/src/sinsim/scraper/http.py`: cliente `httpx.Client` con User-Agent de `config/defaults.toml`, espera mínima `scraper.min_interval_s` entre peticiones, timeouts, sin paralelismo (III.10); errores de conexión o 5xx → `NETWORK_ERROR` (exit 3); acepta un `transport` inyectable para pruebas
- [X] T059 [P] [US3] Crear `backend/src/sinsim/scraper/paratec.py`: descarga los endpoints de research R1 (`Line/getAll`, `Substation/SubstationInfo`, `Reactor/getAll`, `StatcomSvc/getAll`, `PowerTransformer/PowerTransformerInfo`, `HydraulicUnit/HydraulicUnitInfo`, `ThermalUnit/ThermalUnitInfo`, `SolarEquivalentUnit/getAll`, `WindPlant/WindPlantInfo`, `Capacitor/getAll`, `TransmissionMap/getLines`), exige `{"header", "data"}` → `PARATEC_SCHEMA_CHANGED`, guarda cada respuesta tal cual en `raw/paratec/<servicio>__<recurso>.json`
- [X] T060 [P] [US3] Crear `backend/src/sinsim/scraper/xm_files.py`: listado `GET https://api-portalxm.xm.com.co/administracion-archivos/ficheros?ruta=/M:/InformacionAgentes/Usuarios/Publico/<DESPACHO|DEMANDAS/Pronostico Oficial>/<AAAA-MM>&contenedor=storageportalxm&...&nombre=<prefijo>` y descarga `.../descarga-archivo?ruta=M:/...&nombreBlobContainer=storageportalxm`; trae todas las versiones `dDEC<MMDD>*.txt` y `PRON_BARRA<MMDD>`; conserva `fechaModificacion` como `source_modified_at`; JSON inesperado → `XM_FILE_SCHEMA_CHANGED`; guarda en `raw/xm/`
- [X] T061 [US3] Añadir `sinsim scrape --fecha YYYY-MM-DD [--out data/paratec/]` a `backend/src/sinsim/cli.py`: rechaza fecha mal formada o futura (exit 2), comprueba `SNAPSHOT_EXISTS` antes de descargar (exit 1), orquesta T059 + T060 → T023 (`write_snapshot`), imprime ruta, conteos por entidad, `dispatch_version.used` y `standard_version = "XM-CND-2014-045 ed. 2025"`
- [X] T062 [US3] Prueba de integración `backend/tests/integration/test_scrape_fixtures.py` con `httpx.MockTransport` sobre `backend/tests/fixtures/`: éxito crea snapshot y `snapshots list` lo muestra; segundo intento → exit 1 y árbol sin cambios; respuesta de PARATEC sin `data` → exit 4 y sin `.tmp-*` ni destino; `dDEC` con total alterado → exit 4; transporte que lanza `httpx.ConnectError` → exit 3 y hash del árbol de `data/` idéntico al previo (SC-006, HU-3.1–3.4)
- [X] T063 [US3] Ejecutar la tarea explícita de scraping (constitución VI.7): `uv run sinsim scrape --fecha 2026-10-20` contra las fuentes reales, verificar `uv run sinsim snapshots list` (`íntegro = sí`, paratec/despacho/demanda = sí) y hacer commit `data: snapshot PARATEC 2026-10-20`
- [ ] T064 [US3] Curar `data/equivalencias/recursos_despacho.csv` y `data/equivalencias/nodos_demanda.csv` para el snapshot incluido: generar una propuesta por nombre normalizado con un script desechable fuera del repo (research R7), revisar a mano cada fila, documentar en `note` los casos dudosos, dejar sin fila lo que no se pudo confirmar; fijar `angle_ref_bus` en `config/defaults.toml` con el criterio "barra STN con mayor Σ`p_max_mw` de generadores conectados en el snapshot incluido" y el valor calculado; objetivo `coverage_pct ≥ 95` en el periodo 19 (SC-003)
- [X] T065 [US3] Prueba de integración `backend/tests/integration/test_all_periods.py` (marcada `@pytest.mark.included_snapshot`): los 24 periodos de `2026-10-20` del snapshot incluido terminan en `convergio`, `coverage_pct ≥ 95` y cada periodo tarda menos de 30 s en construir el caso y correr el flujo (SC-003, SC-004, meta de rendimiento del plan); ejecutar `make demo`, versionar `cases/demo/` y medir el tiempo desde un clon limpio (< 10 min, SC-001)

**Checkpoint**: el repositorio trae un snapshot real, íntegro y con equivalencias; `make demo` funciona sin red.

---

## Fase 6: Historia de usuario 4 - Visualizar y exportar resultados (Prioridad: P3)

**Objetivo**: interfaz local con tablas filtrables, violaciones resaltadas, topología
coloreable y exportación idéntica valor a valor.

**Prueba independiente**: con una ejecución existente, Playwright recorre la interfaz y el
`.zip` descargado coincide con `GET /api/runs/{id}`.

### Implementación de la historia 4

- [X] T066 [US4] Crear `backend/src/sinsim/adapters/storage/export.py`: `barras.csv`, `lineas.csv`, `transformadores.csv` (columna `tipo` 2w/3w), `generadores.csv` (UTF-8 sin BOM, separador ",", decimal ".", float64 sin redondear) y `metadatos.json` (`trace`, `solver`, `status`, `case_id`, `quality_summary`, `assumptions`, `limits` con fuentes, `warnings`, `attribution`, `label`); si `no_convergio` solo `metadatos.json` con `diagnostics`; variante `.zip` ([contracts/export-format.md](./contracts/export-format.md))
- [X] T067 [P] [US4] Añadir `--exportar DIR` a `sinsim run` en `backend/src/sinsim/cli.py` usando T066
- [X] T068 [P] [US4] Añadir a `backend/src/sinsim/api/routers/runs.py`: `GET /api/runs/{run_id}/topology` (nodos con `vm_pu`, `violation`; aristas con `kind`, `loading_percent`, `overload`) y `GET /api/runs/{run_id}/export` (`application/zip`)
- [X] T069 [US4] Prueba de contrato `backend/tests/contract/test_export.py`: los 5 archivos existen, columnas de [data-model.md §7](./data-model.md), cada valor del CSV es igual (`==` tras `float()`) al de `GET /api/runs/{id}`, `metadatos.json` con los 8 campos de `trace` y la atribución (SC-007); con `no_convergio` no hay CSV
- [X] T070 [US4] Crear `frontend/src/api/types.ts` (tipos escritos a mano que reflejan [contracts/openapi.yaml](./contracts/openapi.yaml)), `frontend/src/api/client.ts` (fetch a `/api`, lanza `Problem` tipado) y `frontend/src/api/hooks.ts` (TanStack Query: `useSnapshots`, `useCreateCase`, `useCase`, `useRunCase`, `useRun`, `useTopology`)
- [X] T071 [P] [US4] Crear `frontend/src/features/run-picker/RunPicker.tsx`: selector de fecha (solo fechas con despacho y demanda; las incompletas aparecen deshabilitadas con el motivo), periodo 1–24, tipo AC/DC, botón Ejecutar; muestra `user_message` de los Problem Details
- [X] T072 [P] [US4] Crear `frontend/src/features/case-quality/CaseQuality.tsx`: balance, cobertura %, listas plegables de no ubicados, traslados, excluidos/imputados, islas con MW perdidos, y los supuestos del caso
- [X] T073 [P] [US4] Crear `frontend/src/features/results-tables/ResultsTables.tsx` con pestañas barras/líneas/transformadores/generadores, filtro por texto y por "solo violaciones", filas fuera de límite resaltadas y contador en el resumen; en `no_convergio` muestra el diagnóstico y ninguna tabla de resultados
- [X] T074 [P] [US4] Crear `frontend/src/features/topology/TopologyView.tsx` con Cytoscape: nodos = barras, aristas = líneas y transformadores, selector de color por `vm_pu` o por `loading_percent`, leyenda de escala y tooltip con `bus_id`/`vn_kv`
- [X] T075 [US4] Crear `frontend/src/App.tsx`, `frontend/src/main.tsx` y `frontend/src/lib/queryClient.ts`: flujo picker → calidad → ejecutar → resultados/topología → botón "Exportar .zip"; cabecera con la leyenda "Flujo sobre despacho programado (no es el estado real del SIN)" o la de aproximación DC; pie con la atribución a XM; advertencias `DATES_DIFFER`/`DISPATCH_REVISED` visibles
- [X] T076 [P] [US4] Pruebas Vitest en `frontend/src/features/results-tables/ResultsTables.test.tsx` (filtro y conteo de violaciones) y `frontend/src/features/case-quality/CaseQuality.test.tsx` (balance y cobertura)
- [X] T077 [US4] Prueba e2e `frontend/e2e/flujo.spec.ts` con Playwright contra `make dev`: seleccionar fecha y periodo 19, ejecutar, ver tablas y topología, cambiar coloreado, descargar el zip y comparar con la API (quickstart escenario 6)

**Checkpoint**: las cuatro historias funcionan; la interfaz nunca muestra stack traces.

---

## Fase 7: Pulido y transversales

- [X] T078 Configurar en `backend/pyproject.toml` `[tool.pytest.ini_options]` y `[tool.coverage]` con `--cov=sinsim.domain --cov=sinsim.adapters --cov-fail-under=85`, y que `make test` falle si baja (constitución IV, VI.6)
- [X] T079 [P] Escribir `docs/fuentes-de-datos.md` (endpoints, formatos, versiones del estándar, atribución) y `docs/supuestos.md` (consigna 1,0 pu, taps neutros, `i0 = 0`, SVC como reactiva, referencia distribuida, traslados STR/SDL, pérdidas PSTR, alcance ≥ 57,5 kV, con la fecha y el origen de cada decisión)
- [X] T080 [P] Ejecutar `pre-commit run --all-files`, `mypy --strict backend/src` y `pnpm --dir frontend lint`; corregir lo que salga sin desactivar reglas
- [X] T081 Ejecutar los 6 escenarios de [quickstart.md](./quickstart.md) de principio a fin y registrar los resultados reales en `docs/validacion-001.md` (tiempos, cobertura obtenida, periodos convergidos)

---

## Dependencias y orden de ejecución

### Entre fases

- **Setup (1)**: sin dependencias.
- **Fundacional (2)**: depende de Setup. Bloquea todas las historias.
- **US1 (3)**: depende de Fundacional. Se prueba con el snapshot de fixtures.
- **US2 (4)**: depende de US1 (completa `build_case` y el CLI).
- **US3 (5)**: depende de Fundacional para el scraper (T058–T062); T063–T065 dependen además de US1 y US2, porque validan `make demo`, SC-003 y SC-004 sobre el snapshot real.
- **US4 (6)**: depende de US1 (API) y US2 (reporte); T077 depende de T063 (datos reales).
- **Pulido (7)**: depende de todo lo anterior.

### Dependencia de datos (honesta)

FR-001 exige un snapshot real en el repositorio, y la única forma legítima de producirlo es el
scraper (constitución VI.7). Por eso **el MVP demostrable con `make demo` requiere US1 + US2 +
US3**. US1 y US2 se desarrollan y prueban antes con el snapshot de fixtures.

### Dentro de cada historia

- Dominio puro → adaptadores → servicios → CLI/API → pruebas de integración y contrato.
- Una tarea no se cierra con pruebas fallando ni con cobertura por debajo del 85 % (VI.6).
- Al cerrar cada tarea: archivos tocados, decisiones y desviaciones del plan (VI.8).

### Oportunidades de paralelismo

- Setup: T003–T008 en paralelo tras T001–T002.
- Fundacional: T010–T013 en paralelo; T015–T021 en paralelo tras T014; T029–T030 en paralelo; T025 tras T024.
- US1: T032–T033 y T038 en paralelo; T043–T045 en paralelo tras T042; T046, T048–T050 en paralelo.
- US3: T059–T060 en paralelo tras T058.
- US4: T067–T068 en paralelo tras T066; T071–T074 en paralelo tras T070.

---

## Ejemplo de paralelismo: Fundacional

```bash
# Tras T014 (field_mapping), lanzar a la vez los cinco adaptadores de PARATEC y los dos de XM:
Tarea: "T015 buses.py"      Tarea: "T016 lines.py"       Tarea: "T017 trafos.py"
Tarea: "T018 generators.py" Tarea: "T019 shunts.py"
Tarea: "T020 xm_dispatch.py" Tarea: "T021 xm_demand.py"
```

## Ejemplo de paralelismo: Historia 1

```bash
# Tras T042 (app + Problem Details):
Tarea: "T043 routers/snapshots.py"  Tarea: "T044 routers/cases.py"  Tarea: "T045 routers/runs.py"
# Pruebas independientes entre sí:
Tarea: "T046 test_case_hash + test_net_builder"  Tarea: "T048 test_no_convergence"
Tarea: "T049 test_reference_networks"            Tarea: "T050 test_pandapower_internals"
```

---

## Estrategia de implementación

### MVP primero

1. Fase 1 y Fase 2 completas (fixtures incluidos).
2. Fase 3 (US1) → `test_build_and_run` en verde sobre fixtures.
3. Fase 4 (US2) → reporte de calidad completo.
4. Fase 5 (US3) → scraper, **T063 snapshot real**, T064 equivalencias, T065 `make demo`.
5. **PARAR Y VALIDAR**: quickstart escenarios 1–5.

### Entrega incremental

- Fase 6 (US4) añade la interfaz y la exportación sin tocar los resultados.
- Fase 7 cierra cobertura, documentación y validación completa.

### Riesgos que vigilar durante la ejecución

- **SC-004** (24 periodos convergidos) se decide en T065; si falla, el diagnóstico de T037 y
  los supuestos de T035 son el punto de partida, no un cambio silencioso de parámetros.
- **T027** depende de archivos que viven en el scratchpad de la sesión; si se pierden, los
  fixtures se obtienen con una ejecución explícita del scraper (VI.7) una vez exista T061.

---

## Notas

- `[P]` = archivos distintos y sin dependencias pendientes.
- Ningún valor eléctrico se inventa: los defaults salen de `config/defaults.toml` con su
  fuente (III.9, VI.4).
- No se añaden endpoints, flags, dependencias ni "mejoras" fuera de esta lista (VI.2).
- Commits con Conventional Commits; el snapshot con `data: snapshot PARATEC 2026-10-20`.

## Fase 8: Convergencia

Hallazgos de `/speckit-converge` (2026-10-20) tras ejecutar `/speckit-implement` sobre T001–T081.

- [X] T082 Conservar por separado los dos componentes de la demanda activa de cada barra (`Ener.Act.` y `Perd.PSTR`): en `backend/src/sinsim/services/build_case.py` (`_assign_demand`) agregar por barra `p_act_mw` y `p_pstr_mw` además de `p_mw`, llevarlos como columnas de `ModelTables.loads` en `adapters/sources_to_pandapower/net_builder.py` y exponerlos en el caso (por ejemplo en `quality` o `assumptions.repartos_entre_barras`), con prueba unitaria en `backend/tests/unit/test_net_builder.py` per FR-014 (partial)
- [X] T083 Mostrar en `assumptions` del caso, por generador conciliado, la consigna de tensión y los límites de reactiva asignados (`gen_id`, `vm_pu`, `q_min_mvar`, `q_max_mvar`) con la fuente de cada valor (PARATEC o el supuesto de `config/defaults.toml`), en `backend/src/sinsim/services/build_case.py`; reflejarlo en `frontend/src/features/case-quality/CaseQuality.tsx` y en `metadatos.json` de la exportación, con pruebas en `backend/tests/integration/test_build_and_run.py` per FR-018 (partial)
- [X] T084 Dejar un componente por archivo en el frontend (constitución IV, convenciones TypeScript): extraer `BusTable`, `BranchTable` y `GenTable` de `frontend/src/features/results-tables/ResultsTables.tsx`, `Section` de `frontend/src/features/case-quality/CaseQuality.tsx` y `Workspace` de `frontend/src/App.tsx` a archivos propios, sin cambiar comportamiento; `pnpm lint`, `pnpm test` y el e2e deben seguir en verde per Constitution IV (contradicts)
- [X] T085 Registrar y justificar en la tabla "Complejidad y desviaciones" de `specs/001-flujo-potencia-despacho/plan.md` (y en `data-model.md` donde aplique) lo que el código añadió sin estar en spec, plan ni tareas: módulos `backend/src/sinsim/config.py` y `bootstrap.py`; tabla `data/equivalencias/subestaciones_alias.csv` y el supuesto `alias_subestaciones`; base de tensión por clase (115/230/13,8 kV) conservando la nominal declarada; códigos `REQUEST_INVALID` y `XM_FILE_NOT_FOUND` en `domain/errors.py`; `imputation.rule = "median"` en lugar del `"exclude"` que pedía T008; tridevanados con dos devanados o terciario SDL modelados como 2 devanados. Lo que no se justifique se retira per Constitution VI.2 (unrequested)

## Fase 9: Clasificación por subárea (FR-034)

Ampliación de HU-4 aprobada por el usuario el 2026-10-20 (spec FR-034, escenario 4 de HU-4; plan D-7).

- [X] T086 [US4] Añadir `"subAreaName": "subarea"` a `SUBSTATION` en `backend/src/sinsim/adapters/sources_to_pandapower/field_mapping.py`; crear `parse_subareas()` en `adapters/sources_to_pandapower/buses.py` (subestación normalizada → `subAreaName` sin el prefijo "SubArea "; nulo si falta) y la columna `subarea` en `build_buses_table`; pasarla desde `backend/src/sinsim/scraper/writer.py`; pruebas en `backend/tests/unit/test_buses.py`
- [X] T087 [US4] En `backend/src/sinsim/adapters/storage/snapshots.py`, si `buses` no trae `subarea` (snapshots anteriores a FR-034), derivarla de `raw/paratec/*Substation_SubstationInfo.json` al cargar, sin escribir archivos (III.3, III.4); prueba en `backend/tests/integration/test_snapshot_storage.py` con el fixture
- [X] T088 [US4] Llevar `subarea` a `net.bus` en `adapters/sources_to_pandapower/net_builder.py`; añadir `BusResult.subarea`, `BranchResult.subarea_from`/`subarea_to` y `QualityReport.buses_without_subarea` (por defecto vacío) en `domain/entities.py`; llenarlos en `services/run_flow.py` y `services/build_case.py`; pruebas en `test_net_builder.py` y `test_build_and_run.py`
- [X] T089 [US4] Añadir `[unifilares]` a `config/defaults.toml` (URL base, `typeReport` del tema "Diagrama unifilar por subárea" y `category` por subárea, con la fuente: API pública `unifilares/api/Diagrama/getAll` de PARATEC, consultada el 2026-10-20) y su modelo en `backend/src/sinsim/config.py`
- [X] T090 [US4] En `GET /api/runs/{run_id}/topology` (`api/routers/runs.py`) devolver `subarea` por nodo y la lista `subareas` con `unifilar_url`; prueba de contrato en `backend/tests/contract/test_api.py`
- [X] T091 [P] [US4] Frontend: tipos en `frontend/src/api/types.ts`; en `features/topology/TopologyView.tsx` opción "subárea" en "Colorear por" con paleta categórica y leyenda, selector de subárea que deja solo sus barras y los enlaces de frontera, y enlace "Ver unifilar de XM"; columna y filtro de subárea en `features/results-tables/`; prueba Vitest del filtro
- [X] T092 [US4] Actualizar `docs/supuestos.md` y `docs/fuentes-de-datos.md` (origen de la subárea y de los unifilares); ejecutar la suite completa, `ruff`, `mypy`, `pnpm lint`, Vitest y el e2e; regenerar `cases/demo`

## Fase 10: Disposición geográfica con mapa base (FR-035)

Ampliación de HU-4 aprobada por el usuario el 2026-10-20 (retira NG-12; spec FR-035, escenario 5 de HU-4; plan D-8).

- [X] T093 [US4] Descargar Natural Earth 1:10m admin-1, filtrar Colombia, simplificar y guardar en `data/geo/colombia_departamentos.geojson` con `data/geo/README.md` (fuente, licencia de dominio público, fecha y procesamiento); script desechable fuera del repo
- [X] T094 [US4] Añadir `latitude`/`longitude` a `SUBSTATION` en `field_mapping.py`; `parse_substation_coords()` y columnas `lat`/`lon` en `build_buses_table` (`buses.py`); pasarlas desde `scraper/writer.py`; derivarlas de `raw/` al cargar snapshots anteriores (`adapters/storage/snapshots.py`); pruebas en `test_buses.py` y `test_snapshot_storage.py`
- [X] T095 [US4] Llevar `lat`/`lon` a `net.bus` (`net_builder.py`); `QualityReport.buses_without_coordinates` (`domain/entities.py`, `services/build_case.py`); `lat`/`lon` por nodo en `GET /api/runs/{run_id}/topology`; `GET /api/geo/basemap` (`api/routers/`); subir sinsim a 0.3.0 porque cambia el contenido del caso; pruebas de contrato
- [X] T096 [P] [US4] Frontend: tipos y `api.basemap()`; proyección pura en `features/topology/geo.ts` (equirectangular, separación de barras de una misma subestación, franja para barras sin coordenadas) con prueba Vitest; selector "Disposición: lógica / geográfica" en `TopologyView.tsx` con fondo SVG sincronizado con el zoom; sección "Barras sin coordenadas" en `CaseQuality.tsx`
- [X] T097 [US4] Actualizar `docs/supuestos.md` y `docs/fuentes-de-datos.md`; paso geográfico en `frontend/e2e/flujo.spec.ts`; ejecutar suite completa, `ruff`, `mypy`, `pnpm lint`, Vitest y e2e; regenerar `cases/demo`

## Fase 11: Flujos, generación y carga por barra en la topología (FR-036)

Ampliación de HU-4 pedida por el usuario el 2026-10-20 (spec FR-036, escenario 6 de HU-4; FR-035 pasa a disposición geográfica por defecto).

- [X] T098 [US4] En `GET /api/runs/{run_id}/topology` (`api/routers/runs.py`) añadir por nodo `p_gen_mw`, `q_gen_mvar` (de `RunResult.generators`), `p_load_mw`, `q_load_mvar`, `p_load_act_mw`, `p_load_pstr_mw` (de `net.load`) y por rama `p_from_mw`, `q_from_mvar`, `p_to_mw`, `q_to_mvar` (de `RunResult`); prueba de contrato con el balance Σgen ≈ Σcarga + pérdidas
- [X] T099 [P] [US4] Frontend: módulo puro `features/topology/busDetail.ts` (flujos orientados desde la barra, balance) con prueba Vitest; componente `features/topology/BusDetail.tsx` con tensión, generadores, carga, ramas y balance, con prueba Vitest
- [X] T100 [US4] `TopologyView.tsx`: disposición geográfica por defecto; tamaño de nodos y grosor de ramas ∝ zoom^−0,6; etiquetas de barra (nombre, G, C) y de rama (|P| MW) visibles solo al acercarse; flecha de sentido de P; clic en barra abre `BusDetail`; pasar `run` desde `Workspace.tsx`
- [X] T101 [US4] Actualizar `docs/supuestos.md`; ajustar `frontend/e2e/flujo.spec.ts`; suite completa, `ruff`, `mypy`, `pnpm lint`, Vitest y e2e

## Fase 12: Nivel de detalle y barras fijas en el mapa (FR-036, ampliación del 2026-10-20)

- [X] T102 [US4] Comprimir las respuestas de la API con `GZipMiddleware` de Starlette en `backend/src/sinsim/api/app.py` (sin dependencia nueva); prueba de contrato: `/topology` con `Accept-Encoding: gzip` responde `Content-Encoding: gzip`
- [X] T103 [US4] `TopologyView.tsx`: nivel de detalle por zoom (solo STN por debajo de un umbral; el STR aparece al acercarse), barras fijas en la disposición geográfica (`autoungrabify`) y arrastrables en la lógica, `hideEdgesOnViewport` al desplazar; leyenda que lo explique; prueba Vitest de la regla de detalle en `features/topology/lod.ts`
- [X] T104 [US4] Actualizar `docs/supuestos.md` (S18); e2e; suite completa, `ruff`, `mypy`, `pnpm lint`, Vitest

## Fase 13: Etiquetas seleccionables y reporte de violaciones (FR-036, FR-037; 2026-10-20)

- [X] T105 [US4] `GET /api/runs/{run_id}/topology`: añadir por nodo `vm_kv`, `va_degree`, `slack_adjust_mw` y por rama `i_ka`, `pl_mw`, `ql_mvar`; prueba de contrato
- [X] T106 [US4] Reporte de violaciones (FR-037): función pura `domain/violations.py` (tres grupos ordenados por desviación, con límite y fuente) usada por `adapters/storage/export.py` para `violaciones.csv` y expuesta en `RunResult.summary` o por `GET /api/runs/{run_id}` sin cambiar el hash; pruebas unitarias y de contrato; actualizar `contracts/export-format.md`
- [X] T107 [P] [US4] Frontend: selectores de etiquetas de barra y de rama en `TopologyView.tsx` (módulo puro `features/topology/labels.ts` con prueba Vitest; preferencia guardada en `localStorage` con `try/catch`), "Colorear por → ángulo", pérdidas por rama en `BusDetail.tsx`
- [X] T108 [P] [US4] Frontend: componente `features/violations/ViolationsReport.tsx` con las tres tablas (tensión baja, tensión alta, sobrecarga > 100 %) ordenadas por desviación, con subárea, límite y fuente; prueba Vitest; enlazado desde `Workspace.tsx`
- [X] T109 [US4] Docs (`docs/supuestos.md`, `docs/fuentes-de-datos.md` no cambia), e2e, suite completa, `ruff`, `mypy`, `pnpm lint`, Vitest; regenerar `cases/demo`
