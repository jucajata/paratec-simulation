# Plan: análisis de contingencias N-1

**Feature**: 003-contingencias-n1 | **Spec**: [spec.md](./spec.md) | **Fecha**: 2026-10-24
**Rama**: `feat/contingencias-n1` | **Release**: 0.6.0
**Constitución**: v1.2.0 → 1.3.0 (enmienda MINOR de IV por el comando público `sinsim n1`; ver
«Revisión de cumplimiento»).

## Resumen

Sobre una ejecución AC convergida, sinsim saca de servicio cada línea, cada transformador y cada
generador (planta por barra, incluidos los compensadores), uno a la vez, y corre un flujo AC por
cada uno: 1.261 contingencias en el caso del 2026-10-20. Compara cada resultado con la
ejecución base y arma cuatro grupos: listado de cargabilidad, listado de tensiones, «Aíslan
demanda» y «Sin solución». El cálculo se reparte entre procesos y tarda unos 76 s en el portátil
del usuario (research R2). Se lanza desde la interfaz, con avance, o con `sinsim n1`, que escribe
los CSV.

## Contexto técnico

- **Lenguajes y stack**: Python 3.12, pandapower 3.5.6, FastAPI, React + TypeScript, TanStack
  Query, como hoy. **Sin dependencias nuevas**: el paralelismo usa `concurrent.futures`
  (research R2).
- **Dominio puro** (`domain/contingency.py`): la regla FR-052 y el orden de los listados, sin
  pandapower ni E/S (data-model §8). Entidades nuevas en `domain/entities.py` (data-model §2–7).
- **Servicio** (`services/n1.py`):
  - `enumerate_outages(net)`: líneas, transformadores y generadores en servicio, con su
    `OutageKind`;
  - `require_base(run)`: exige flujo AC convergido (`N1_BASE_INVALID`); la usan el router y
    `analyze`;
  - `analyze(run, net_json, cfg, *, workers, outages, progress)`: lanza el `ProcessPoolExecutor` con
    `os.cpu_count() − 1` procesos; cada proceso carga la red una vez, corre el flujo base y
    atiende lotes de contingencias;
  - por contingencia: restaurar el estado base (research R1), sacar el activo, `detect_and_isolate`
    si es una rama (R5), mover la referencia si sale el generador de referencia (R6), `runpp`
    desde la solución base y reintento desde DC (R4), extraer cargabilidades y tensiones;
  - el proceso principal reúne los resultados, aplica el dominio contra la ejecución base guardada
    (R9) y arma el `N1Analysis`.
- **Refactor mínimo**:
  - `run_flow.bus_vm_nominal(net)`, extraída de `_result`, para que el flujo y el N-1 expresen la
    tensión igual (R7);
  - `build_case._angle_ref` pasa a ser pública como `choose_angle_ref` (R6).
  - `scrape.internal_problem` deja de ser privada para que el N-1 reutilice el mismo Problem
    Details de error no previsto.
  Ninguno de los tres cambia resultados existentes; las pruebas actuales lo cubren.
- **Tarea en segundo plano** (`services/n1.py: N1Runner`): un cupo en memoria, como
  `ScrapeRunner`. Hilo que lanza el análisis y actualiza `done`/`total`.
- **API** (`api/routers/n1.py`): `POST /api/runs/{run_id}/n1` y `GET /api/n1/{job_id}`
  ([contrato](./contracts/openapi-n1.yaml)).
- **Errores** (`domain/errors.py`):
  - `N1_BASE_INVALID` (422, salida 4): la ejecución es DC o no convergió;
  - `N1_IN_PROGRESS` (409, salida 1);
  - `N1_JOB_NOT_FOUND` (404, salida 1).
  Cada uno con su `user_message` en español.
- **Exportación** (`adapters/storage/export_n1.py`): los cuatro CSV y `metadatos.json`
  ([contrato](./contracts/export-n1.md)).
- **CLI**: `sinsim n1` ([contrato](./contracts/cli-n1.md)), con la misma construcción de caso que
  `sinsim run`.
- **Interfaz** (`frontend/src/features/contingencies/`):
  - `N1Panel.tsx`: botón, avance, resumen, los dos listados lado a lado y los bloques «Aíslan
    demanda» y «Sin solución», en una sección nueva después de las tablas de resultados;
  - `n1.ts`: módulo puro con etiquetas, formato y textos de la marca «aísla N barras, X MW»;
  - hooks `useStartN1` y `useN1Job`, que consulta cada segundo mientras corre, como
    `useScrapeJob`; tipos en `api/types.ts`; métodos en `api/client.ts`;
  - el panel se monta con `key={run.run_id}`, así que cambiar de ejecución descarta el análisis
    mostrado sin efectos adicionales.
- **Rendimiento**: 76 s medidos para 1.260 contingencias con 11 procesos (SC-014 pide < 3 min).
- **Pruebas**:
  - unitarias de `domain/contingency.py`;
  - integración del servicio sobre una red de referencia pequeña de pandapower y sobre el caso de
    ejemplo;
  - contrato de API y CLI;
  - Vitest de `n1.ts` y `N1Panel`;
  - un paso e2e.
  Las pruebas no llaman a XM (VI.7).

## Revisión de cumplimiento de la constitución

- **I. Naturaleza**: el N-1 está en «Capacidades en alcance». La generación de seguridad, que es
  optimización, queda fuera, como exige I. Esta feature levanta NG-01 de la spec 001 solo para N-1.
- **II. Stack**: sin dependencias nuevas (research R2). Numba se descarta.
- **III. Reglas de dominio**:
  - III.1 unidades: % y pu como en el resto del modelo;
  - III.2 base: no se toca;
  - III.5 sin parámetros inventados: el análisis no crea parámetros;
  - III.7 trazabilidad: FR-060;
  - III.8 no convergencia: FR-056, nunca se presenta como válida;
  - III.9 límites: los configurados, con su fuente en la interfaz y en `metadatos.json`. FR-052 no
    usa umbral (decisión del usuario), así que no hay un valor nuevo que citar.
- **IV. Estructura**:
  - código en `domain/`, `services/`, `adapters/storage/`, `api/routers/` y
    `frontend/src/features/`, según la estructura de IV;
  - `pandapowerNet` solo se crea y muta en `services/` (IV, «Paradigmas»);
  - `domain/contingency.py` no importa pandapower;
  - el comando público nuevo `sinsim n1` exige enmendar IV («Comandos públicos»), versión MINOR
    1.3.0, como hizo la spec 002 con `sinsim serve`.
- **V. Errores**: tres códigos nuevos en el catálogo único, con Problem Details y códigos de salida
  del CLI. Sin `except` desnudos: los errores del flujo de una contingencia se convierten en
  «Sin solución»; los demás, en `ProblemInfo` con `trace_id`.
- **VI. Agente**:
  - la spec, este plan y las tareas documentan todo lo que se construye: comando, rutas, códigos y
    columnas (VI.2);
  - no se tocan archivos de `data/paratec/` (VI.5);
  - no hay llamadas a PARATEC (VI.7).

## Decisiones del usuario (2026-10-24)

1. Solo N-1. N-2 y generación de seguridad quedan fuera.
2. Dos listados independientes, lado a lado (boceto B), ordenados por el peor valor absoluto.
3. Solo cuenta lo que la contingencia empeora frente al base, sin umbral mínimo.
4. Un generador es la planta por barra, como en el modelo actual.
5. Bloque propio «Aíslan demanda», con su CSV.
6. Se lanza desde la interfaz y desde la terminal; la terminal exporta CSV.

## Decisiones de diseño (del agente)

- **Un análisis a la vez en toda la API**, no solo por caso. El análisis ocupa todos los núcleos
  menos uno, así que dos simultáneos solo se estorbarían. Cumple FR-058, que pide uno por caso, y
  es más estricto. `N1_IN_PROGRESS` avisa del que corre.
- **Base de la comparación**: la ejecución guardada que el usuario tiene en pantalla (R9).
- **Carpeta por defecto de `sinsim n1`**: `./n1-<fecha>-p<NN>/`, para no exigir una opción que
  `sinsim run` sí exige (`--exportar`), porque aquí exportar es el propósito del comando.
- **Ubicación en la interfaz**: una sección «Contingencias N-1» después de las tablas de
  resultados, visible solo con un flujo en pantalla.
- **Sin persistencia** del análisis (S24): la API lo guarda en memoria y el CLI lo escribe a disco.

## Estructura

```text
backend/src/sinsim/
├── domain/contingency.py          # FR-052, orden y empates (puro)
├── domain/entities.py             # + Outage, Isolation, filas, N1Summary, N1Analysis, N1Job
├── domain/errors.py               # + N1_BASE_INVALID, N1_IN_PROGRESS, N1_JOB_NOT_FOUND
├── services/n1.py                 # enumerar, analizar en paralelo, N1Runner
├── services/run_flow.py           # + bus_vm_nominal (extraída)
├── services/build_case.py         # _angle_ref → choose_angle_ref
├── adapters/storage/export_n1.py  # CSV + metadatos.json
├── api/routers/n1.py              # POST /runs/{id}/n1, GET /n1/{job_id}
├── bootstrap.py                   # + n1_runner en AppContext
└── cli.py                         # + sinsim n1
backend/tests/
├── unit/test_contingency.py
├── integration/test_n1.py
└── contract/test_api_n1.py, test_cli_n1.py, test_export_n1.py
frontend/src/
├── features/contingencies/{N1Panel.tsx, n1.ts, *.test.ts(x)}
├── api/{types.ts, client.ts, hooks.ts}
└── features/workspace/Workspace.tsx
frontend/e2e/flujo.spec.ts          # + paso N-1
```

Documentación: README (sección N-1), `docs/supuestos.md` (S23 a S25), CHANGELOG 0.6.0,
constitución 1.3.0 y versión 0.6.0 en backend y frontend.

## Riesgos

- **Máquinas con pocos núcleos**: con 2 núcleos, el análisis tardaría unos 4 minutos y no cumpliría
  SC-014 en esa máquina. SC-014 se mide en el portátil del usuario; el avance visible deja claro que
  sigue trabajando.
- **Memoria**: cada proceso carga su copia de la red, unos 50–100 MB con pandapower; con 11
  procesos, cerca de 1 GB. Es aceptable en un portátil.
- **Arranque de procesos en macOS (spawn)**: cada proceso importa pandapower de nuevo, unos
  segundos. Ya está incluido en los 76 s medidos.
- **Listados largos sin umbral**: el revisor estimó que casi todas las contingencias entran al
  listado de cargabilidad. Es la decisión del usuario; si se vuelve ruido, el umbral se añade en
  otra spec.
- **e2e lento**: el paso e2e corre el análisis completo, entre 1 y 2 minutos en local. No hay CI de
  pruebas en el repositorio (solo la acción de release), así que no afecta tiempos de CI.

## Seguimiento de complejidad

Ninguna violación de la constitución que justificar. La enmienda de IV es el procedimiento
previsto para un comando público nuevo.
