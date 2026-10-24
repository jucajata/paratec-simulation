# Modelo de datos: análisis de contingencias N-1

**Feature**: 003-contingencias-n1 | **Spec**: [spec.md](./spec.md)

Entidades nuevas en `backend/src/sinsim/domain/entities.py` (Pydantic, inmutables como el resto:
`Frozen`). Se reutilizan `Trace`, `LimitInfo`, `Diagnostics` y `ProblemInfo`.

## 1. Tipos

| Tipo | Valores |
|---|---|
| `OutageKind` | `line`, `trafo2w`, `gen`, `compensador` |
| `N1Status` | `en_cola`, `calculando`, `listo`, `error` |

## 2. `Outage`: el activo que sale

| Campo | Tipo | Regla |
|---|---|---|
| `element_id` | str | Nombre del elemento en la red (`line:…`, `trafo:…`, `RECURSO@BARRA`, `svc:…`). Único. |
| `kind` | `OutageKind` | `compensador` si el nombre empieza por `svc:` o `statcom:` (research R8). |
| `subarea` | str \| null | Subárea de la barra de origen (línea, transformador) o de conexión (generador). |
| `angle_ref_moved_to` | str \| null | Barra que toma la referencia de ángulo si sale el generador de referencia (FR-051). |

## 3. `Isolation`: barras aisladas por una contingencia (FR-055)

| Campo | Tipo | Regla |
|---|---|---|
| `n_buses` | int | > 0. Barras que quedan sin la componente de referencia. |
| `p_demand_lost_mw` | float | ≥ 0. Demanda asignada a esas barras. |

## 4. Filas de los listados

### `LoadingRow` (FR-053)

| Campo | Tipo | Regla |
|---|---|---|
| `rank` | int | 1…n en el orden del listado. |
| `outage` | `Outage` | |
| `element_id` | str | El elemento con mayor cargabilidad entre los que cuentan (FR-052). |
| `loading_base_percent` | float | Cargabilidad de ese elemento en el caso base. |
| `loading_percent` | float | Con la contingencia. > límite y > base. |
| `n_elements` | int | ≥ 1. Elementos que cuentan según FR-052. |
| `isolation` | `Isolation` \| null | Marca «aísla N barras, X MW». |

Orden: `loading_percent` descendente; en empate, `outage.element_id` ascendente.

### `VoltageRow` (FR-054)

| Campo | Tipo | Regla |
|---|---|---|
| `rank` | int | |
| `outage` | `Outage` | |
| `bus_id` | str | La barra con mayor distancia fuera de banda entre las que cuentan. |
| `vm_base_pu` | float | Tensión base de esa barra, en pu del nominal de PARATEC (research R7). |
| `vm_pu` | float | Con la contingencia. |
| `deviation_pu` | float | Distancia a la banda con signo: `vm_pu − vm_min` (< 0) o `vm_pu − vm_max` (> 0). |
| `n_buses` | int | ≥ 1. Barras que cuentan según FR-052. |
| `isolation` | `Isolation` \| null | |

Orden: `abs(deviation_pu)` descendente; en empate, `outage.element_id` ascendente.

### `IsolationRow` (FR-055, bloque «Aíslan demanda»)

| Campo | Tipo | Regla |
|---|---|---|
| `rank` | int | |
| `outage` | `Outage` | |
| `n_buses` | int | |
| `p_demand_lost_mw` | float | |

Orden: `p_demand_lost_mw` descendente; en empate, `outage.element_id` ascendente. Incluye toda
contingencia que converge y deja demanda sin servicio (`p_demand_lost_mw > 0`), esté o no en los
listados.

### `UnsolvedRow` (FR-056)

| Campo | Tipo | Regla |
|---|---|---|
| `outage` | `Outage` | |
| `diagnostics` | `Diagnostics` | El mismo diagnóstico que un flujo `no_convergio` (FR-022). |

Orden: `outage.element_id` ascendente.

## 5. `N1Summary` (FR-057)

| Campo | Tipo | Regla |
|---|---|---|
| `n_total` | int | Contingencias analizadas. |
| `n_loading` | int | Filas del listado de cargabilidad. |
| `n_voltage` | int | Filas del listado de tensiones. |
| `n_isolation` | int | Filas de «Aíslan demanda». |
| `n_unsolved` | int | Filas de «Sin solución». |
| `n_no_impact` | int | Convergen y no están en ninguno de los tres anteriores. |
| `duration_s` | float | Desde que empieza el cálculo hasta que termina. |

Invariante (SC-017): `n_unsolved + n_converged = n_total`, donde `n_converged` cuenta las
contingencias que convergen; `n_no_impact = n_converged − |cargabilidad ∪ tensiones ∪ aislamiento|`.

## 6. `N1Analysis`: el resultado

| Campo | Tipo | Regla |
|---|---|---|
| `run_id` | str | Ejecución base (AC, `convergio`). |
| `trace` | `Trace` | La de la ejecución base: snapshot, periodo, pandapower, solver, `case_id` (FR-060). |
| `limits` | list[`LimitInfo`] | Límites aplicados con su fuente (III.9). |
| `analyzed_at` | datetime | UTC. |
| `workers` | int | Procesos usados. |
| `summary` | `N1Summary` | |
| `loading` | list[`LoadingRow`] | |
| `voltage` | list[`VoltageRow`] | |
| `isolation` | list[`IsolationRow`] | |
| `unsolved` | list[`UnsolvedRow`] | |

## 7. `N1Job`: análisis en segundo plano (FR-058)

| Campo | Tipo | Regla |
|---|---|---|
| `job_id` | str (uuid) | |
| `run_id` | str | |
| `status` | `N1Status` | `en_cola → calculando → listo` o `→ error`. |
| `done` | int | Contingencias terminadas. |
| `total` | int | Contingencias a analizar; se conoce al arrancar. |
| `started_at` | datetime | |
| `finished_at` | datetime \| null | |
| `result` | `N1Analysis` \| null | Solo con `status = listo`. |
| `error` | `ProblemInfo` \| null | Solo con `status = error`. |

Vive en memoria mientras la API está encendida (S24), como `ScrapeJob`.

## 8. Regla FR-052 como función pura

En `backend/src/sinsim/domain/contingency.py`, sin E/S ni pandapower:

- `branch_counts(base, after, limit)`: `after > limit.max_percent and after > base`.
- `bus_distance(vm_pu, band)`: 0 dentro de la banda; `vm_pu − vm_min` debajo y `vm_pu − vm_max`
  encima.
- `bus_counts(base_vm, after_vm, band)`: `bus_distance(after) ≠ 0` y
  `abs(bus_distance(after)) > abs(bus_distance(base))`.
- `rank_loading`, `rank_voltage`, `rank_isolation`: orden y empates de la sección 4.

Las barras sin banda configurada (fuera de todos los rangos de `limits.voltage`) no cuentan, como
en el reporte de violaciones (FR-037). Las barras aisladas y el activo que sale no cuentan.
