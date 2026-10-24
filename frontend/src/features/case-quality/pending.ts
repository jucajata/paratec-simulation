import type { QualityReport } from "../../api/types";

export const REPO_URL = "https://github.com/jucajata/sinsim";
export const PARATEC_URL = "https://paratec.xm.com.co";

/** Texto listo para pegar en una nota o issue con lo que falta por ubicar en este caso (FR-040). */
export function pendingText(q: QualityReport): string {
  const lines: string[] = [];
  if (q.unlocated_resources.length) {
    lines.push("# Recursos del despacho sin ubicar (recursos_despacho.csv)");
    for (const u of q.unlocated_resources) lines.push(`${u.resource}\t${u.p_mw.toFixed(1)} MW\t${u.reason}`);
  }
  if (q.unlocated_demand.length) {
    lines.push("# Nodos de demanda sin ubicar (nodos_demanda.csv)");
    for (const u of q.unlocated_demand) lines.push(`${u.node}\t${u.vn_kv} kV\t${u.p_mw.toFixed(1)} MW\t${u.reason}`);
  }
  return lines.join("\n");
}
