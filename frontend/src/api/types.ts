// Tipos escritos a mano que reflejan specs/001-flujo-potencia-despacho/contracts/openapi.yaml.

export interface Problem {
  type: string;
  title: string;
  status: number;
  detail: string;
  code: string;
  user_message: string;
  trace_id: string;
}

export interface SnapshotSummary {
  date: string;
  has_paratec: boolean;
  has_dispatch: boolean;
  has_demand: boolean;
  intact: boolean;
}

export type FlowType = "ac" | "dc";
export type RunStatus = "convergio" | "no_convergio";

export interface CaseRequest {
  snapshot_date: string;
  dispatch_date?: string;
  period: number;
}

export interface Balance {
  p_scheduled_total_mw: number;
  p_located_mw: number;
  p_unlocated_mw: number;
  coverage_pct: number;
  p_demand_mw: number;
  p_demand_unlocated_mw: number;
  difference_mw: number;
}

export interface UnlocatedResource {
  resource: string;
  p_mw: number;
  reason: string;
}

export interface UnlocatedDemand {
  node: string;
  vn_kv: number;
  p_mw: number;
  q_mvar: number;
  reason: string;
}

export interface Transfer {
  element: string;
  kind: "gen" | "demand";
  from_bus: string;
  to_bus: string;
  p_mw: number;
  q_mvar: number;
}

export interface ExcludedElement {
  element: string;
  kind: string;
  missing_params: string[];
}

export interface ImputedValue {
  element: string;
  kind: string;
  param: string;
  method: string;
  value: number;
}

export interface NotModeled {
  element: string;
  kind: string;
  reason: string;
}

export interface Island {
  island_id: number;
  n_buses: number;
  buses: string[];
  p_gen_lost_mw: number;
  p_demand_lost_mw: number;
  energized: boolean;
}

export interface QualityReport {
  unlocated_resources: UnlocatedResource[];
  unlocated_demand: UnlocatedDemand[];
  transfers: Transfer[];
  excluded: ExcludedElement[];
  imputed: ImputedValue[];
  not_modeled: NotModeled[];
  islands: Island[];
  physical_issues: string[];
  balance: Balance;
}

export interface CaseInputs {
  snapshot_date: string;
  dispatch_date: string;
  period: number;
  snapshot_manifest_sha256: string;
  equivalences_sha256: string;
  config_sha256: string;
  sinsim_version: string;
}

export interface StudyCase {
  case_id: string;
  inputs: CaseInputs;
  quality: QualityReport;
  assumptions: Record<string, unknown>;
  warnings: string[];
  created_at: string;
}

export interface SolverSettings {
  algorithm: string;
  tolerance_mva: number;
  max_iteration: number;
  init: string;
  enforce_q_lims: boolean;
  distributed_slack: boolean;
}

export interface Trace {
  snapshot_date: string;
  dispatch_date: string;
  period: number;
  flow_type: FlowType;
  pandapower_version: string;
  sinsim_version: string;
  solver: SolverSettings;
  case_id: string;
}

export interface BusMismatch {
  bus: string;
  mismatch_mva: number;
}

export interface Diagnostics {
  iterations: number;
  max_mismatch_mva: number;
  worst_buses: BusMismatch[];
  basis: string;
}

export interface BusResult {
  bus_id: string;
  vn_kv: number;
  vm_pu: number;
  vm_kv: number;
  va_degree: number;
  violation: "low" | "high" | null;
}

export interface BranchResult {
  element_id: string;
  kind: "line" | "trafo2w" | "trafo3w";
  from_bus: string;
  to_bus: string;
  p_from_mw: number;
  q_from_mvar: number;
  p_to_mw: number;
  q_to_mvar: number;
  i_ka: number;
  loading_percent: number;
  pl_mw: number;
  ql_mvar: number;
  overload: boolean;
}

export interface GeneratorResult {
  gen_id: string;
  resource: string;
  bus: string;
  p_scheduled_mw: number;
  p_mw: number;
  q_mvar: number;
  slack_adjust_mw: number;
}

export interface LimitInfo {
  name: string;
  value: string;
  source: string;
}

export interface ResultSummary {
  p_gen_mw: number;
  p_load_mw: number;
  p_losses_mw: number;
  slack_adjust_total_mw: number;
  n_voltage_violations: number;
  n_overloads: number;
  limits: LimitInfo[];
  warnings: string[];
}

export interface RunResult {
  buses: BusResult[];
  lines: BranchResult[];
  trafos: BranchResult[];
  generators: GeneratorResult[];
  summary: ResultSummary;
}

export interface Run {
  run_id: string;
  case_id: string;
  flow_type: FlowType;
  status: RunStatus;
  label: string;
  solver: SolverSettings;
  trace: Trace;
  diagnostics: Diagnostics | null;
  result: RunResult | null;
  created_at: string;
}

export interface TopologyNode {
  id: string;
  label: string;
  vn_kv: number;
  vm_pu: number | null;
  violation: "low" | "high" | null;
  in_service: boolean;
}

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  kind: "line" | "trafo2w" | "trafo3w";
  loading_percent: number | null;
  overload: boolean;
}

export interface Topology {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

/** Supuesto por generador (FR-018): consigna y límites de reactiva asignados, con su fuente. */
export interface GeneratorAssumption {
  gen_id: string;
  barra: string;
  vm_pu: number;
  fuente_vm: string;
  q_min_mvar: number | null;
  q_max_mvar: number | null;
  fuente_q: string;
}

/** Demanda activa de una barra con sus dos componentes conservados (FR-014). */
export interface DemandByBus {
  barra: string;
  p_act_mw: number;
  p_pstr_mw: number;
  q_mvar: number;
}
