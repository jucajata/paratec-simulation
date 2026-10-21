import type { SnapshotSummary } from "../../api/types";

/** Estado de una fecha frente a la lista de snapshots y la regla D+1 (FR-038, FR-039). */
export type Availability =
  | { kind: "empty" }
  | { kind: "invalid" }
  | { kind: "too_late"; latest: string }
  | { kind: "available"; snapshot: SnapshotSummary }
  | { kind: "incomplete"; snapshot: SnapshotSummary; reason: string }
  | { kind: "missing" };

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Fecha ISO local (sin zona), `offsetDays` después de `base`. */
export function isoDate(base: Date, offsetDays = 0): string {
  const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() + offsetDays);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

/** Última fecha admitida: mañana, porque XM publica el despacho la víspera (FR-039). */
export function latestAllowed(today: Date): string {
  return isoDate(today, 1);
}

/** Por qué un snapshot no se puede usar, o null si está completo e íntegro. */
export function incompleteReason(s: SnapshotSummary): string | null {
  if (!s.intact) return "snapshot alterado: no coincide con su manifiesto";
  const missing: string[] = [];
  if (!s.has_paratec) missing.push("parámetros PARATEC");
  if (!s.has_dispatch) missing.push("despacho programado");
  if (!s.has_demand) missing.push("pronóstico de demanda");
  return missing.length ? `faltan: ${missing.join(", ")}` : null;
}

export function availabilityOf(date: string, snapshots: SnapshotSummary[], today: Date): Availability {
  if (date === "") return { kind: "empty" };
  if (!ISO_DATE.test(date) || Number.isNaN(Date.parse(date))) return { kind: "invalid" };
  const latest = latestAllowed(today);
  if (date > latest) return { kind: "too_late", latest };
  const snapshot = snapshots.find((s) => s.date === date);
  if (snapshot === undefined) return { kind: "missing" };
  const reason = incompleteReason(snapshot);
  return reason === null ? { kind: "available", snapshot } : { kind: "incomplete", snapshot, reason };
}

/** Texto del paso en curso de una descarga (FR-038). */
export const STEP_LABELS: Record<string, string> = {
  en_cola: "En cola…",
  paratec: "Descargando parámetros de PARATEC…",
  despacho_y_demanda: "Descargando despacho programado y pronóstico de demanda…",
  normalizacion: "Normalizando y escribiendo el snapshot…",
  listo: "Descarga terminada.",
  error: "La descarga falló.",
};
