/** Etiquetas seleccionables de barras y ramas en la topología (FR-036). Funciones puras. */

import type { TopologyEdge, TopologyNode } from "../../api/types";

export const BUS_LABELS = ["name", "vm_pu", "vm_kv", "va", "p_gen", "q_gen", "p_load", "q_load", "slack"] as const;
export const BRANCH_LABELS = ["p", "q", "i", "loading", "losses"] as const;
export type BusLabel = (typeof BUS_LABELS)[number];
export type BranchLabel = (typeof BRANCH_LABELS)[number];

export const BUS_LABEL_TEXT: Record<BusLabel, string> = {
  name: "nombre",
  vm_pu: "V (pu)",
  vm_kv: "V (kV)",
  va: "ángulo",
  p_gen: "generación P",
  q_gen: "generación Q",
  p_load: "carga P",
  q_load: "carga Q",
  slack: "ajuste de referencia",
};
export const BRANCH_LABEL_TEXT: Record<BranchLabel, string> = {
  p: "P",
  q: "Q",
  i: "corriente",
  loading: "cargabilidad",
  losses: "pérdidas",
};

export interface LabelSelection {
  bus: BusLabel[];
  branch: BranchLabel[];
}

/** Por defecto: nombre, generación y carga en barras; P en ramas. */
export const DEFAULT_LABELS: LabelSelection = { bus: ["name", "p_gen", "p_load"], branch: ["p"] };

const STORAGE_KEY = "sinsim.topology.labels";

/** Lee la selección guardada; cualquier fallo del almacenamiento devuelve la de por defecto. */
export function loadLabelSelection(storage: Pick<Storage, "getItem"> | null): LabelSelection {
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_LABELS;
    const parsed = JSON.parse(raw) as Partial<LabelSelection>;
    const bus = (parsed.bus ?? []).filter((l): l is BusLabel => (BUS_LABELS as readonly string[]).includes(l));
    const branch = (parsed.branch ?? []).filter((l): l is BranchLabel => (BRANCH_LABELS as readonly string[]).includes(l));
    return { bus, branch };
  } catch {
    return DEFAULT_LABELS;
  }
}

export function saveLabelSelection(storage: Pick<Storage, "setItem"> | null, selection: LabelSelection): void {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(selection));
  } catch {
    // Almacenamiento no disponible (modo privado, cuota): la selección vale solo en memoria.
  }
}

function mw(v: number | null | undefined): string {
  return typeof v === "number" ? `${Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1)} MW` : "";
}
function mvar(v: number | null | undefined): string {
  return typeof v === "number" ? `${Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1)} Mvar` : "";
}

/** Texto de la etiqueta de una barra, una línea por dato seleccionado. */
export function busCaption(n: TopologyNode, selected: readonly BusLabel[]): string {
  const lines: string[] = [];
  for (const l of selected) {
    if (l === "name") lines.push(n.label);
    else if (l === "vm_pu" && typeof n.vm_pu === "number") lines.push(`${n.vm_pu.toFixed(3)} pu`);
    else if (l === "vm_kv" && typeof n.vm_kv === "number") lines.push(`${n.vm_kv.toFixed(1)} kV`);
    else if (l === "va" && typeof n.va_degree === "number") lines.push(`${n.va_degree.toFixed(1)}°`);
    else if (l === "p_gen" && (n.p_gen_mw ?? 0) > 0) lines.push(`G ${mw(n.p_gen_mw)}`);
    else if (l === "q_gen" && (n.p_gen_mw ?? 0) > 0) lines.push(`G ${mvar(n.q_gen_mvar)}`);
    else if (l === "p_load" && (n.p_load_mw ?? 0) > 0) lines.push(`C ${mw(n.p_load_mw)}`);
    else if (l === "q_load" && (n.p_load_mw ?? 0) > 0) lines.push(`C ${mvar(n.q_load_mvar)}`);
    else if (l === "slack" && (n.slack_adjust_mw ?? 0) !== 0) lines.push(`ref ${mw(n.slack_adjust_mw)}`);
  }
  return lines.join("\n");
}

/** Texto de la etiqueta de una rama; P y Q se muestran en valor absoluto, la flecha da el sentido. */
export function branchCaption(e: TopologyEdge, selected: readonly BranchLabel[]): string {
  const parts: string[] = [];
  for (const l of selected) {
    if (l === "p" && typeof e.p_from_mw === "number") parts.push(mw(Math.abs(e.p_from_mw)));
    else if (l === "q" && typeof e.q_from_mvar === "number") parts.push(mvar(Math.abs(e.q_from_mvar)));
    else if (l === "i" && typeof e.i_ka === "number") parts.push(`${e.i_ka.toFixed(3)} kA`);
    else if (l === "loading" && typeof e.loading_percent === "number") parts.push(`${e.loading_percent.toFixed(0)} %`);
    else if (l === "losses" && typeof e.pl_mw === "number") parts.push(`Δ ${mw(e.pl_mw)}`);
  }
  return parts.join(" · ");
}
