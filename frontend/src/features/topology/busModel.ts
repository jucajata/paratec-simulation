/** Detalle de una barra en la topología (FR-036). Funciones puras. */

import type { GeneratorResult, TopologyEdge, TopologyNode } from "../../api/types";

/** Rama vista desde una barra: P y Q positivos salen de la barra hacia `other`. */
export interface BranchFromBus {
  id: string;
  kind: TopologyEdge["kind"];
  other: string;
  p_out_mw: number | null;
  q_out_mvar: number | null;
  loading_percent: number | null;
  overload: boolean;
  pl_mw: number | null;
  ql_mvar: number | null;
}

export interface BusDetailData {
  node: TopologyNode;
  generators: GeneratorResult[];
  branches: BranchFromBus[];
  /** Σ generación − Σ carga − Σ flujos salientes: cero salvo redondeo si el flujo convergió. */
  balance_mw: number | null;
}

/** Orienta cada rama conectada desde la barra `busId`. */
export function branchesFromBus(busId: string, edges: readonly TopologyEdge[]): BranchFromBus[] {
  const out: BranchFromBus[] = [];
  for (const e of edges) {
    if (e.source !== busId && e.target !== busId) continue;
    const atSource = e.source === busId;
    out.push({
      id: e.id,
      kind: e.kind,
      other: atSource ? e.target : e.source,
      p_out_mw: atSource ? (e.p_from_mw ?? null) : (e.p_to_mw ?? null),
      q_out_mvar: atSource ? (e.q_from_mvar ?? null) : (e.q_to_mvar ?? null),
      loading_percent: e.loading_percent,
      overload: e.overload,
      pl_mw: e.pl_mw ?? null,
      ql_mvar: e.ql_mvar ?? null,
    });
  }
  return out.sort((a, b) => Math.abs(b.p_out_mw ?? 0) - Math.abs(a.p_out_mw ?? 0) || a.id.localeCompare(b.id));
}

/** Reúne todo lo que se muestra de una barra: generadores, carga, ramas y balance. */
export function busDetail(
  node: TopologyNode,
  edges: readonly TopologyEdge[],
  generators: readonly GeneratorResult[],
): BusDetailData {
  const branches = branchesFromBus(node.id, edges);
  const gens = generators.filter((g) => g.bus === node.id);
  const flows = branches.map((b) => b.p_out_mw);
  const balance_mw = flows.every((p): p is number => p !== null)
    ? (node.p_gen_mw ?? 0) - (node.p_load_mw ?? 0) - flows.reduce((acc, p) => acc + p, 0)
    : null;
  return { node, generators: gens, branches, balance_mw };
}
