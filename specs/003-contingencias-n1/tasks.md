# Tareas: análisis de contingencias N-1

**Entrada**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)
**Constitución**: v1.2.0 → 1.3.0. Las pruebas son condición de cierre (VI.6, SC-019).

## Formato: `[ID] [P?] [Historia] Descripción con ruta`

- **[P]**: se puede hacer en paralelo (otro archivo, sin dependencias pendientes).
- **[US7]**: HU-7, ver las contingencias críticas en la interfaz (P1).
- **[US8]**: HU-8, correr el análisis desde la terminal y exportar CSV (P2).

---

## Fase 1: Gobernanza

- [X] T300 Enmendar la constitución a v1.3.0 (MINOR): en IV «Comandos públicos» añadir
  `uv run sinsim n1 --fecha YYYY-MM-DD --periodo N [--fecha-despacho F] [--salida CARPETA] [--json]`; actualizar el Sync Impact
  Report, la versión y la fecha de última enmienda (`.specify/memory/constitution.md`).

---

## Fase 2: Fundamentos (bloquean HU-7 y HU-8)

**Propósito**: el dominio y el servicio de análisis que usan tanto la interfaz como el CLI.

### Dominio

- [X] T301 [P] Entidades en `backend/src/sinsim/domain/entities.py` (data-model §1–7), todas
  `Frozen`:
  - `OutageKind = Literal["line", "trafo2w", "gen", "compensador"]` y
    `N1Status = Literal["en_cola", "calculando", "listo", "error"]`;
  - `Outage` (`element_id`, `kind`, `subarea: str | None`, `angle_ref_moved_to: str | None`);
  - `Isolation` (`n_buses` «> 0», `p_demand_lost_mw` «≥ 0»);
  - `LoadingRow`, `VoltageRow`, `IsolationRow` y `UnsolvedRow`, con los campos de data-model §4;
  - `N1Summary`, `N1Analysis` y `N1Job`, con los campos de data-model §5–7.
- [X] T302 [P] Códigos en el catálogo único `backend/src/sinsim/domain/errors.py`, con título,
  HTTP, código de salida y `user_message` en español:
  - `N1_BASE_INVALID` (422, `ExitCode.VALIDATION`): «El análisis N-1 se hace sobre un flujo AC que
    convergió. Corre el flujo AC primero.»;
  - `N1_IN_PROGRESS` (409, `ExitCode.GENERAL`);
  - `N1_JOB_NOT_FOUND` (404, `ExitCode.GENERAL`): «…los análisis solo se recuerdan mientras la API
    sigue encendida.».
  Ampliar la prueba existente del catálogo si la hay.
- [X] T303 [P] Pruebas unitarias de la regla FR-052 y del orden, con valores conocidos, **antes**
  de implementarla (`backend/tests/unit/test_contingency.py`):
  - rama base 105 % que sigue en 105 % no cuenta;
  - de 105 % a 105,01 % sí cuenta (sin umbral, decisión del usuario);
  - de 90 % a 100 % no cuenta y de 90 % a 100,5 % sí cuenta, con límite 100;
  - barra dentro de banda que pasa a −0,02 pu sí cuenta;
  - barra base en −0,03 pu que pasa a −0,02 pu no cuenta, porque se acerca a la banda;
  - barra sin banda no cuenta;
  - barra que pasa de −0,03 pu (subtensión) a +0,02 pu (sobretensión) no cuenta; a +0,04 sí;
  - el elemento más cargado se elige solo entre los que cuentan;
  - orden descendente y empate por `outage.element_id` ascendente en los tres listados;
  - `IsolationRow` solo con `p_demand_lost_mw > 0`;
  - invariante del resumen de SC-017.
- [X] T304 Implementar `backend/src/sinsim/domain/contingency.py` sin pandapower ni E/S
  (data-model §8):
  - `branch_counts`, `bus_distance`, `bus_counts`;
  - `evaluate(base, after, bands, loading)`, que devuelve la peor rama y la peor barra que cuentan,
    y cuántas cuentan;
  - `rank_loading`, `rank_voltage`, `rank_isolation` y `summarize`.
  Reutiliza `band_for` de `domain/limits.py`. Hace pasar T303.

### Refactor sin cambio de resultados

- [X] T305 [P] Extraer `bus_vm_nominal(net) -> dict[int, tuple[float, float]]`, que da tensión en
  pu del nominal de PARATEC y nominal en kV por barra en servicio (research R7), de `_result` en
  `backend/src/sinsim/services/run_flow.py`; `_result` la usa. Las pruebas existentes de flujo
  deben seguir pasando sin cambios.
- [X] T306 [P] Renombrar `_angle_ref` a `choose_angle_ref` (pública) en
  `backend/src/sinsim/services/build_case.py` y actualizar su uso (research R6). Sin cambio de
  comportamiento.

### Servicio de análisis

- [X] T307 Pruebas de integración del servicio **antes** de implementarlo, sobre una red de
  referencia pequeña de pandapower construida en la prueba (como en
  `backend/tests/integration/test_reference_networks.py`) y sobre `cases/demo`
  (`backend/tests/integration/test_n1.py`):
  - SC-015: para una contingencia, la cargabilidad y la tensión del análisis coinciden con un flujo
    corrido a mano con ese activo fuera (tolerancia 1e-6 pu y 1e-4 %);
  - una contingencia que no converge termina en `unsolved` con `Diagnostics`;
  - una línea radial produce `Isolation` con la demanda de las barras aisladas;
  - sacar el generador con `slack=True` llena `angle_ref_moved_to` y converge;
  - un compensador (`svc:`/`statcom:`) se clasifica `compensador`;
  - el resultado es el mismo con 1 proceso y con varios, con mismas filas y mismo orden (R3);
  - el flujo base de cada proceso coincide con la ejecución guardada (R9).
- [X] T308 Implementar `backend/src/sinsim/services/n1.py`:
  - `enumerate_outages(net)`: líneas, transformadores y generadores con `in_service`, con su
    `OutageKind`, y compensador por prefijo `svc:`/`statcom:`;
  - inicializador de proceso: carga `net_json`, corre el flujo base con `solver_settings(cfg)` y
    guarda el estado base (columnas `in_service` de `bus`, `line`, `trafo`, `gen` y `load`, y
    `res_bus`);
  - `_run_outage`, por contingencia:
    - restaura el estado base;
    - saca el activo;
    - si es rama, `detect_and_isolate(net, ref)`;
    - si sale el generador de referencia, mueve `slack` con `choose_angle_ref`;
    - `pp.runpp(init="results")` y, si lanza `LoadflowNotConverged`, un reintento con
      `init="dc"`; si tampoco converge, `diagnose`;
    - devuelve cargabilidades por nombre de rama y `bus_vm_nominal`;
  - `analyze(case, run, net_json, cfg, progress)`:
    - `ProcessPoolExecutor(max(1, os.cpu_count() - 1))` con lotes;
    - llama a `progress(done, total)`;
    - compara contra `run.result` con `domain/contingency.py` y arma el `N1Analysis` con `trace`,
      `limits`, `analyzed_at`, `workers` y `duration_s`;
    - lanza `N1_BASE_INVALID` si `run.flow_type != "ac"` o `run.status != "convergio"`.
  Hace pasar T307.

**Punto de control**: el análisis corre de punta a punta desde Python sobre `cases/demo`.

---

## Fase 3: HU-7, ver las contingencias críticas en la interfaz (P1) 🎯 MVP

**Objetivo**: botón «Analizar N-1», avance y los listados lado a lado.

**Prueba independiente**: con `make dev`, correr 2026-10-20 periodo 19 AC, pulsar «Analizar N-1»
y ver el resumen, los dos listados y los bloques «Aíslan demanda» y «Sin solución» (quickstart §3).

### Backend

- [X] T309 [P] [US7] Pruebas de contrato de la API **antes** de implementarla, según
  `contracts/openapi-n1.yaml` (`backend/tests/contract/test_api_n1.py`):
  - `POST /api/runs/{run_id}/n1` responde 202 con `N1Job`;
  - 404 `RUN_NOT_FOUND` con un run que no existe;
  - 422 `N1_BASE_INVALID` con un run DC;
  - 409 `N1_IN_PROGRESS` con otro análisis corriendo;
  - `GET /api/n1/{job_id}` avanza hasta `listo` con `result`;
  - 404 `N1_JOB_NOT_FOUND`;
  - un POST con origen ajeno sigue bloqueado por FR-047.
  Para mantener la prueba corta, usa un caso de la red de referencia.
- [X] T310 [US7] `N1Runner` en `backend/src/sinsim/services/n1.py`:
  - un único cupo en memoria para toda la API (decisión del plan), con `threading.Lock` y un hilo
    por análisis, como `ScrapeRunner`;
  - estados `en_cola → calculando → listo | error`, con `done` y `total` actualizados por el
    callback de progreso;
  - `ProblemInfo` con `trace_id` ante un error no previsto, nunca un stack trace (V).
- [X] T311 [US7] Router `backend/src/sinsim/api/routers/n1.py` con `POST /runs/{run_id}/n1` (202) y
  `GET /n1/{job_id}`; añadir `n1_runner: N1Runner` a `AppContext` en
  `backend/src/sinsim/bootstrap.py` y registrar el router con prefijo `/api` en
  `backend/src/sinsim/api/app.py`. Hace pasar T309.

### Frontend

- [X] T312 [P] [US7] Tipos `N1Job`, `N1Analysis`, `Outage`, `LoadingRow`, `VoltageRow`,
  `IsolationRow`, `UnsolvedRow` y `N1Summary` en `frontend/src/api/types.ts`:
  - `kind: "line" | "trafo2w" | "gen" | "compensador"`;
  - `status: "en_cola" | "calculando" | "listo" | "error"`.
  Métodos `api.startN1(runId)` y `api.n1Job(jobId)` en `frontend/src/api/client.ts`.
- [X] T313 [US7] Hooks `useStartN1` y `useN1Job` en `frontend/src/api/hooks.ts`. `useN1Job` consulta
  cada 1 s mientras el estado no es `listo` ni `error`, como `useScrapeJob`.
- [X] T314 [P] [US7] Módulo puro `frontend/src/features/contingencies/n1.ts` y su prueba Vitest
  `n1.test.ts`:
  - etiqueta de tipo de activo (línea, transformador, generador, compensador);
  - texto de la marca «aísla N barras, X MW sin servicio»;
  - formato de cargabilidad (%, 1 decimal) y de distancia fuera de banda (pu con signo, 3
    decimales);
  - texto del avance «done / total contingencias».
- [X] T315 [US7] Componente `frontend/src/features/contingencies/N1Panel.tsx`, sección
  «Contingencias N-1», y su prueba Vitest `N1Panel.test.tsx` con la API simulada:
  - botón «Analizar N-1» (`n1-start`), deshabilitado con explicación si el flujo es DC o no
    convergió (FR-061);
  - avance (`n1-progress`);
  - resumen (`n1-summary`) con los conteos de FR-057, la duración y los límites con su fuente
    (FR-060);
  - listados lado a lado (`n1-loading`, `n1-voltage`) con las columnas de FR-053 y FR-054 y la
    marca de aislamiento;
  - debajo, los bloques compactos «Aíslan demanda» (`n1-isolation`) y «Sin solución»
    (`n1-unsolved`), este con su diagnóstico;
  - error con `user_message`;
  - solo visualización, sin acciones por fila;
  - en pantallas angostas, los listados se apilan.
- [X] T316 [US7] Montar `N1Panel` en `frontend/src/features/workspace/Workspace.tsx`, después de
  `ResultsTables`, solo cuando hay una ejecución en pantalla. Al cambiar de ejecución se descarta
  el análisis mostrado.
- [X] T317 [US7] Paso e2e en `frontend/e2e/flujo.spec.ts`:
  - tras el flujo AC, pulsar «Analizar N-1»;
  - ver el avance;
  - subir el límite de esa prueba con `test.setTimeout(420_000)` (el global es 180 s) y esperar
    hasta 4 minutos a que aparezcan `n1-summary`, `n1-loading` y `n1-voltage`;
  - comprobar que los dos listados tienen filas y que el resumen cuadra (SC-017).

**Punto de control**: HU-7 funciona sola, sin el CLI.

---

## Fase 4: HU-8, análisis N-1 desde la terminal (P2)

**Objetivo**: `sinsim n1` escribe los CSV y `metadatos.json`.

**Prueba independiente**:
`uv run --project backend sinsim n1 --fecha 2026-10-20 --periodo 19 --salida out/n1-demo`
(quickstart §2).

- [X] T318 [P] [US8] Pruebas de la exportación **antes** de implementarla, según
  `contracts/export-n1.md` (`backend/tests/contract/test_export_n1.py`):
  - encabezados exactos de los cuatro CSV;
  - mismo orden de filas que `N1Analysis`;
  - columnas vacías cuando no aplican;
  - `barras_problematicas` separadas por `;`;
  - `metadatos.json` con trazabilidad, límites, resumen y atribución de XM.
- [X] T319 [US8] `backend/src/sinsim/adapters/storage/export_n1.py`:
  - `export_n1_files(case, analysis, attribution) -> dict[str, bytes]`;
  - `write_export_n1(…, out_dir)`, que crea la carpeta y reemplaza los archivos existentes.
  Hace pasar T318.
- [X] T320 [P] [US8] Pruebas del comando **antes** de implementarlo, según `contracts/cli-n1.md`
  (`backend/tests/contract/test_cli_n1.py`):
  - código 0 y los cinco archivos en `--salida`;
  - carpeta por defecto `./n1-<fecha>-p<NN>/`;
  - código 2 con un periodo fuera de rango;
  - `--fecha-despacho` distinta de `--fecha` se respeta como en `sinsim run`;
  - código 4 y `N1_BASE_INVALID` sin archivos si el flujo base no converge (reutiliza el caso de
    `test_no_convergence.py`);
  - `--json` imprime un `N1Analysis` válido;
  - avance en stderr.
- [X] T321 [US8] Comando `sinsim n1` en `backend/src/sinsim/cli.py`:
  - opciones `--fecha`, `--periodo`, `--fecha-despacho`, `--salida` y `--json`;
  - construye el caso como `run`, corre el flujo AC base y lo guarda;
  - si no converge, imprime el diagnóstico y sale con 4;
  - corre `analyze` con avance en stderr y escribe la exportación;
  - imprime el resumen y las 10 primeras filas de cada listado.
  Hace pasar T320.

**Punto de control**: HU-8 funciona sola, sin la interfaz. Sus CSV coinciden con los listados de
HU-7 para el mismo caso (SC-018).

---

## Fase 5: Documentación, versión y cierre

- [X] T322 [P] `docs/supuestos.md`: S23 (reparto de la potencia del generador que sale), S24 (sin
  persistencia del análisis) y S25 (compensadores como contingencias), con referencia a FR-049 a
  FR-061.
- [X] T323 [P] `README.md`: sección «Análisis de contingencias N-1», con el botón, `sinsim n1`, la
  regla de empeoramiento sin umbral, los cuatro grupos y la duración esperada.
- [X] T324 [P] `CHANGELOG.md` 0.6.0 y versión 0.6.0 en `backend/pyproject.toml` y
  `frontend/package.json`.
- [X] T325 Validación completa:
  - `ruff`, `mypy`, `pnpm lint` y typecheck;
  - `make test` (pytest con cobertura ≥ 85 % en `domain/` y `adapters/`, Vitest y e2e);
  - quickstart §2 midiendo el tiempo (SC-014: < 3 min en el portátil del usuario);
  - quickstart §3, paso 4: los CSV coinciden con los listados de la interfaz (SC-018);
  - quickstart §4 (SC-015).
  Reportar los resultados.

---

## Dependencias

- **Fase 1** (T300): no bloquea el código, pero va antes del merge.
- **Fase 2**:
  - T301, T302, T305 y T306 en paralelo;
  - T303 → T304;
  - T307 → T308, que necesita T301, T302 y T304 a T306.
- **Fase 3 (HU-7)** necesita la Fase 2:
  - backend: T309 → T310 → T311;
  - frontend: T312 → T313; T314 en paralelo; T315 necesita T313 y T314; T316 → T317;
  - T317 necesita T311.
- **Fase 4 (HU-8)** necesita la Fase 2 y es independiente de la 3:
  - T318 → T319;
  - T320 → T321, que necesita T319.
- **Fase 5**: T322 a T324 en cualquier momento; T325 al final.

## Ejemplos en paralelo

```text
Fase 2:  T301 entidades | T302 errores | T303 pruebas de dominio | T305 bus_vm_nominal | T306 choose_angle_ref
Fase 3:  T309 pruebas de API | T312 tipos y cliente | T314 n1.ts
Fase 4:  T318 pruebas de exportación | T320 pruebas del CLI
Fases 3 y 4 entre sí: una persona en la interfaz y otra en el CLI, después de la Fase 2.
```

## Estrategia

1. **MVP**: Fases 1 a 3, HU-7 en la interfaz. Es lo que pidió el usuario: la tabla de las
   contingencias más críticas en pantalla.
2. **Incremento**: Fase 4, HU-8 en la terminal con CSV.
3. **Cierre**: Fase 5 y release 0.6.0 (PR, fusión y release, con el permiso del usuario antes de
   tocar GitHub).
