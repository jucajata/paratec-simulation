# Modelo de datos: Flujo de potencia del SIN con PARATEC, despacho y demanda por barra

**Feature**: [spec.md](./spec.md) · **Investigación**: [research.md](./research.md)

Unidades internas: las convenciones de pandapower (constitución III.1). Base del sistema:
`F_HZ = 60` y `S_BASE_MVA = 100`, definidas en `backend/src/sinsim/domain/constants.py`
(III.2). Los identificadores de código van en inglés; esta tabla usa los nombres de dominio
en español y el nombre interno entre paréntesis cuando difiere.

---

## 1. Snapshot (`Snapshot`)

Es un directorio inmutable `data/paratec/<YYYY-MM-DD>/`; su formato está en
[contracts/snapshot-format.md](./contracts/snapshot-format.md).

| Campo | Tipo | Regla |
|---|---|---|
| fecha (`date`) | date | Clave del snapshot. Es la fecha de operación del despacho y de la demanda |
| fuentes (`sources`) | lista de `SourceFile` | Exactamente una por entidad PARATEC + `dDEC` + `PRON_BARRA` |
| manifiesto (`manifest`) | `Manifest` | Obligatorio; ver §1.1 |
| disponibilidad (`availability`) | {paratec, despacho, demanda}: bool | Se calcula al listar (FR-002) |

**Validación**:
- Al cargar, se recalcula el SHA-256 de cada archivo y se compara con el manifiesto. Si alguno
  no coincide, el snapshot es `SNAPSHOT_CORRUPTED` (FR-006).
- Un snapshot sin `dDEC` o sin `PRON_BARRA` puede listarse, pero no ejecutarse:
  `OPERATING_POINT_MISSING` (HU-1.4).

### 1.1 Manifiesto (`Manifest`)

| Campo | Tipo | Regla |
|---|---|---|
| fecha_extraccion (`extracted_at`) | datetime ISO-8601 con zona | Obligatorio (III.4) |
| version_scraper (`scraper_version`) | str (SemVer de `sinsim`) | Obligatorio |
| fuentes (`sources[]`) | `{entity, url, source_modified_at, standard_version?}` | `source_modified_at` es obligatorio para los archivos de XM (FR-003). `standard_version` = "XM-CND-2014-045 ed. 2025" para `dDEC` y `PRON_BARRA` (R-04) |
| version_despacho (`dispatch_version`) | `{used: "V0" \| "V<n>", available: [..]}` | Prevalece la `_V<n>` más alta; V0 es el archivo sin sufijo (D-3) |
| registros (`record_counts`) | {entidad: int} | Obligatorio (III.4) |
| archivos (`files[]`) | `{path, sha256, bytes}` | Uno por cada archivo de `raw/` y `normalized/` |
| atribucion (`attribution`) | str | "Información proporcionada por XM S.A. E.S.P. – PARATEC y archivos públicos de despacho" (III.10, R-12, D-1) |

## 2. Tablas normalizadas (Parquet en `normalized/`)

Todas tienen `source_id` (el identificador del registro en `raw/`) para la trazabilidad, y
las columnas de calidad `imputed: bool`, `imputation_method: str | null` y
`missing_params: list[str]` (III.5).

| Tabla | Columnas principales (unidad) | Origen |
|---|---|---|
| `buses` | `bus_id` = "<SUBESTACIÓN>\|<kV>", `substation`, `vn_kv`, `level` ∈ {STN, STR, SDL} | `SubstationInfo.voltageLevel[]` |
| `lines` | `line_id`, `name`, `from_bus`, `to_bus`, `length_km`, `r_ohm_per_km`, `x_ohm_per_km`, `c_nf_per_km`, `max_i_ka`, `parallel` | `Line/getAll` (+ `getLines` para extremos) |
| `trafos2w` | `trafo_id`, `hv_bus`, `lv_bus`, `sn_mva`, `vn_hv_kv`, `vn_lv_kv`, `vk_percent`, `vkr_percent`, `pfe_kw`, `i0_percent`, datos de tap | `PowerTransformerInfo` (Bidevanado) |
| `trafos3w` | análogo, con hv/mv/lv | `PowerTransformerInfo` (Tridevanado) |
| `generators` | `unit_id`, `plant`, `bus`, `p_max_mw`, `min_q_mvar`, `max_q_mvar`, `tech` ∈ {hidráulica, térmica, solar, eólica} | Unidades de generación |
| `shunts` | `shunt_id`, `bus`, `q_mvar` (+ capacitivo / − inductivo según pandapower), `kind` | Reactores y condensadores |
| `svc_statcom` | `id`, `bus`, `cap_mvar`, `ind_mvar`, `kind` ∈ {SVC, STATCOM} | Se modelan como `gen` con P = 0 y Q ∈ [−ind, +cap] (D-6) |
| `dispatch` | `resource`, `period` (1..24), `p_mw` | `dDEC` (MWh/h → MW) |
| `demand` | `ucp`, `node`, `vn_kv`, `period`, `p_act_mw`, `p_pstr_mw`, `q_mvar` | `PRON_BARRA` |

**Reglas de validación del scraper** (FR-005, código de salida 4 si fallan):
- Cada entidad tiene las columnas esperadas.
- `period` está entre 1 y 24 y hay exactamente 24 valores por fila.
- La suma de recursos de `dDEC` coincide con su fila `"Total"` (tolerancia 0,01 MW por
  periodo).
- Cada nodo de `PRON_BARRA` tiene los 3 conceptos.
- Los valores son numéricos; los valores negativos solo se aceptan donde el estándar los
  permite.

## 3. Tablas de equivalencias (CSV versionado en `data/equivalencias/`)

Esquema en [contracts/snapshot-format.md §3](./contracts/snapshot-format.md).

| Tabla | Clave | Columnas | Regla |
|---|---|---|---|
| `recursos_despacho.csv` | (`resource`, `valid_from`) | `resource`, `kind` ∈ {plant, unit, intl_link}, `paratec_ids` (separados por `;`), `connection_bus` (solo para `intl_link`), `valid_from`, `valid_to`, `note` | Una sola fila vigente por recurso y fecha |
| `nodos_demanda.csv` | (`node`, `vn_kv`, `valid_from`) | `node`, `ucp`, `vn_kv`, `substation`, `paratec_vn_kv`, `valid_from`, `valid_to`, `note` | Igual |

Una vigencia que se solapa es un error de validación. Un recurso o nodo sin fila vigente
queda **no ubicado** (FR-012, FR-014a).

## 4. Caso de estudio (`StudyCase`)

| Campo | Tipo | Regla |
|---|---|---|
| id (`case_id`) | str = SHA-256 de `CaseInputs` canónico | Identificador y hash del caso (FR-023) |
| entradas (`inputs: CaseInputs`) | ver abajo | Inmutable |
| red (`net`) | JSON de pandapower (`pp.to_json`) en `cases/<case_id>/net.json` | Solo se crea en `services/` y `adapters/` (IV) |
| reporte (`quality: QualityReport`) | ver §5 | Se genera al construir el caso |
| creado_en (`created_at`) | datetime | No forma parte del hash |

**`CaseInputs`** (lo único que entra al hash, serializado como JSON canónico con claves
ordenadas y floats con `repr`):

| Campo | Contenido |
|---|---|
| Identificación | `snapshot_date`, `dispatch_date`, `period` (1..24) |
| Integridad | `snapshot_manifest_sha256` |
| Equivalencias | `equivalences_sha256`, de ambos CSV |
| Configuración | `config_sha256`, de la configuración efectiva: límites, reglas de imputación, consignas y barra de ángulo |
| Versión | `sinsim_version` |

**Supuestos visibles** (FR-018, R-11, A-04), que forman parte del reporte:
- consigna de tensión por generador y su fuente;
- barra de referencia de ángulo y su criterio;
- factores de participación de la referencia distribuida;
- repartos de P entre barras de un mismo recurso;
- traslados a la frontera STR/SDL;
- regla de imputación aplicada;
- taps de transformadores en `normalStep`, la posición neutra de PARATEC (D-2; PARATEC no
  publica la posición operativa);
- `i0_percent = 0` en todos los transformadores (D-2);
- SVC y STATCOM modelados como fuentes de reactiva con consigna de tensión (D-6).

**Advertencias**:
- `DATES_DIFFER`, si `snapshot_date ≠ dispatch_date` (FR-025).
- `PROGRAM_NOT_REAL_STATE`, siempre: "flujo sobre despacho programado" (FR-026).

## 5. Reporte de calidad (`QualityReport`)

| Sección | Contenido |
|---|---|
| `unlocated_resources[]` | `{resource, p_mw}` para recursos con P > 0 sin equivalencia o sin barra (FR-012, SC-002) |
| `unlocated_demand[]` | `{node, vn_kv, p_mw, q_mvar}` (FR-014a) |
| `transfers[]` | `{element, kind ∈ {gen, demand}, from_bus, to_bus, p_mw, q_mvar}` (FR-019, FR-014) |
| `excluded[]` | `{element, kind, missing_params[]}` (FR-013) |
| `imputed[]` | `{element, param, method, value}` (FR-013, III.5) |
| `not_modeled[]` | `{element, kind, reason}`: enlaces internacionales o compensadores sin barra resoluble |
| `islands[]` | `{island_id, n_buses, buses[], p_gen_lost_mw, p_demand_lost_mw, energized}` (FR-016). Solo la componente con la barra de ángulo tiene `energized = true`; cualquier otra isla es un hallazgo de calidad de datos, porque el SIN real no tiene islas (D-5) |
| `balance` | `{p_scheduled_total_mw, p_located_mw, p_unlocated_mw, coverage_pct, p_demand_mw, p_demand_unlocated_mw, difference_mw}` (FR-024, HU-2.4) |

`coverage_pct = p_located_mw / p_scheduled_total_mw · 100`, contando solo los recursos con
P > 0 en el periodo (SC-002, SC-003). Los enlaces internacionales cuentan como generación
programada.

## 6. Ejecución (`Run`)

| Campo | Tipo | Regla |
|---|---|---|
| id (`run_id`) | UUID v4 | |
| caso (`case_id`) | ref `StudyCase` | |
| tipo (`flow_type`) | `ac` \| `dc` | `dc` se etiqueta "aproximación DC" (FR-021) |
| estado (`status`) | `convergio` \| `no_convergio` | Solo en AC puede ser `no_convergio` |
| solver (`solver`) | `{algorithm: "nr", tolerance_mva, max_iteration, distributed_slack: true, enforce_q_lims, init}` | Se registra completo (FR-023) |
| trazabilidad (`trace`) | `{snapshot_date, dispatch_date, period, flow_type, pandapower_version, sinsim_version, solver, case_id}` | Obligatorio y completo (FR-023, SC-007, III.7) |
| diagnóstico (`diagnostics`) | `{iterations, max_mismatch_mva, worst_buses: [{bus, mismatch_mva}] (top 10)}` | Obligatorio si `status = no_convergio` (FR-022, III.8) |
| creada_en (`created_at`) | datetime | |

**Transición de estados**: la ejecución es síncrona. Termina en `convergio` o en
`no_convergio`, y una ejecución terminada no cambia. Un error de entrada no crea una
ejecución: es un error de la API o del CLI (V).

## 7. Resultado (`RunResult`)

Solo existe si `status = convergio` (FR-022).

| Tabla | Columnas |
|---|---|
| `buses` | `bus_id`, `vm_pu`, `vm_kv`, `va_degree`, `violation` ∈ {null, low, high} |
| `lines` | `line_id`, `p_from_mw`, `q_from_mvar`, `p_to_mw`, `q_to_mvar`, `i_ka`, `loading_percent`, `pl_mw`, `ql_mvar`, `overload: bool` |
| `trafos` | análogo a `lines` (2w y 3w) |
| `generators` | `gen_id`, `resource`, `p_scheduled_mw`, `p_mw`, `q_mvar`, `slack_adjust_mw` |
| `summary` | `{p_gen_mw, p_load_mw, p_losses_mw, slack_adjust_total_mw, n_voltage_violations, n_overloads, warnings[]}` |

Los límites que se usan para marcar violaciones vienen de la configuración (R9) y su fuente se
incluye en `summary` (FR-031, III.9).
