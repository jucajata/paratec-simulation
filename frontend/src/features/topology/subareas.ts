/** Clasificación de la topología por subárea de PARATEC (FR-034). Funciones puras. */

import type { TopologyEdge, TopologyNode } from "../../api/types";

/** Gris para barras sin subárea: nunca se les asigna una por inferencia. */
export const NO_SUBAREA_COLOR = "#9aa0a6";

/** Paleta categórica de 20 colores distinguibles (las subáreas del SIN son 18). */
const PALETTE = [
  "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
  "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#393b79",
  "#637939", "#8c6d31", "#843c39", "#7b4173", "#3182bd",
  "#e6550d", "#31a354", "#756bb1", "#636363", "#b5cf6b",
];

/**
 * Color estable de una subárea: depende de su posición en la lista ordenada de todas las
 * subáreas de la red, así que no cambia al filtrar.
 */
export function subareaColor(subarea: string | null | undefined, all: readonly string[]): string {
  if (!subarea) return NO_SUBAREA_COLOR;
  const i = [...all].sort((a, b) => a.localeCompare(b, "es")).indexOf(subarea);
  return i < 0 ? NO_SUBAREA_COLOR : (PALETTE[i % PALETTE.length] ?? NO_SUBAREA_COLOR);
}

export interface SubareaView {
  nodes: (TopologyNode & { frontier: boolean })[];
  edges: (TopologyEdge & { frontier: boolean })[];
}

/**
 * Deja las barras de una subárea, sus ramas internas y las ramas de frontera con la barra
 * vecina de la otra subárea, marcada como `frontier`. Con `subarea = null` no filtra.
 */
export function filterBySubarea(
  nodes: readonly TopologyNode[],
  edges: readonly TopologyEdge[],
  subarea: string | null,
): SubareaView {
  if (subarea === null) {
    return {
      nodes: nodes.map((n) => ({ ...n, frontier: false })),
      edges: edges.map((e) => ({ ...e, frontier: false })),
    };
  }
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const inside = new Set(nodes.filter((n) => n.subarea === subarea).map((n) => n.id));
  const keptEdges = edges.filter((e) => inside.has(e.source) || inside.has(e.target));
  const neighbors = new Set<string>();
  for (const e of keptEdges) {
    if (!inside.has(e.source)) neighbors.add(e.source);
    if (!inside.has(e.target)) neighbors.add(e.target);
  }
  const keptNodes = [...inside, ...neighbors]
    .map((id) => byId.get(id))
    .filter((n): n is TopologyNode => n !== undefined)
    .map((n) => ({ ...n, frontier: !inside.has(n.id) }));
  return {
    nodes: keptNodes,
    edges: keptEdges.map((e) => ({ ...e, frontier: !(inside.has(e.source) && inside.has(e.target)) })),
  };
}
