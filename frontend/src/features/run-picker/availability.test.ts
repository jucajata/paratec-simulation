import type { SnapshotSummary } from "../../api/types";
import { availabilityOf, incompleteReason, isoDate, latestAllowed } from "./availability";

const ok: SnapshotSummary = { date: "2026-10-20", has_paratec: true, has_dispatch: true, has_demand: true, intact: true };
const broken: SnapshotSummary = { ...ok, date: "2026-10-19", intact: false };
const partial: SnapshotSummary = { ...ok, date: "2026-10-09", has_dispatch: false, has_demand: false };
const today = new Date(2026, 9, 21); // 2026-10-21

describe("availability", () => {
  it("admite hasta mañana (FR-039)", () => {
    expect(latestAllowed(today)).toBe("2026-10-22");
    expect(isoDate(new Date(2026, 11, 31), 1)).toBe("2027-01-01");
    expect(availabilityOf("2026-10-22", [], today)).toEqual({ kind: "missing" });
    expect(availabilityOf("2026-10-23", [], today)).toEqual({ kind: "too_late", latest: "2026-10-22" });
  });

  it("distingue disponible, incompleto, alterado y sin descargar", () => {
    const list = [ok, broken, partial];
    expect(availabilityOf("2026-10-20", list, today)).toEqual({ kind: "available", snapshot: ok });
    expect(availabilityOf("2026-10-19", list, today)).toMatchObject({ kind: "incomplete", reason: expect.stringContaining("alterado") });
    expect(availabilityOf("2026-10-09", list, today)).toMatchObject({
      kind: "incomplete",
      reason: "faltan: despacho programado, pronóstico de demanda",
    });
    expect(availabilityOf("2026-10-15", list, today)).toEqual({ kind: "missing" });
    expect(incompleteReason(ok)).toBeNull();
  });

  it("rechaza vacío y mal formado", () => {
    expect(availabilityOf("", [], today)).toEqual({ kind: "empty" });
    expect(availabilityOf("2026-13-01", [], today)).toEqual({ kind: "invalid" });
    expect(availabilityOf("hoy", [], today)).toEqual({ kind: "invalid" });
  });
});
