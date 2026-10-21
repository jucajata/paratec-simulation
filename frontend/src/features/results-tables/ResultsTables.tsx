import { useMemo, useState } from "react";

import type { Run } from "../../api/types";
import { fmtMw, fmtNum } from "../../lib/format";
import { BranchTable } from "./BranchTable";
import { BusTable } from "./BusTable";
import { GenTable } from "./GenTable";

type Tab = "buses" | "lines" | "trafos" | "generators";

const TABS: { id: Tab; label: string }[] = [
  { id: "buses", label: "Barras" },
  { id: "lines", label: "Líneas" },
  { id: "trafos", label: "Transformadores" },
  { id: "generators", label: "Generadores" },
];

interface Props {
  run: Run;
}

function matches(text: string, filter: string): boolean {
  return filter === "" || text.toLowerCase().includes(filter.toLowerCase());
}

/** Filtro por subárea (FR-034): "" = todas; una rama pasa si alguno de sus extremos está. */
function inSubarea(subarea: string, ...values: (string | null | undefined)[]): boolean {
  return subarea === "" || values.some((v) => v === subarea);
}

export function ResultsTables({ run }: Props): JSX.Element {
  const [tab, setTab] = useState<Tab>("buses");
  const [filter, setFilter] = useState("");
  const [onlyViolations, setOnlyViolations] = useState(false);
  const [subarea, setSubarea] = useState("");
  // Los hooks van antes de cualquier retorno temprano (reglas de hooks). Con `result` nulo
  // las listas quedan vacías y no se usan.
  const r = run.result;
  const subareaOfBus = useMemo(() => new Map((r?.buses ?? []).map((b) => [b.bus_id, b.subarea ?? null])), [r]);
  const subareaOptions = useMemo(
    () => [...new Set((r?.buses ?? []).map((b) => b.subarea).filter((s): s is string => !!s))].sort((a, b) => a.localeCompare(b, "es")),
    [r],
  );
  const buses = useMemo(
    () =>
      (r?.buses ?? []).filter(
        (b) => matches(b.bus_id, filter) && inSubarea(subarea, b.subarea) && (!onlyViolations || b.violation !== null),
      ),
    [r, filter, subarea, onlyViolations],
  );
  const lines = useMemo(
    () =>
      (r?.lines ?? []).filter(
        (b) => matches(b.element_id, filter) && inSubarea(subarea, b.subarea_from, b.subarea_to) && (!onlyViolations || b.overload),
      ),
    [r, filter, subarea, onlyViolations],
  );
  const trafos = useMemo(
    () =>
      (r?.trafos ?? []).filter(
        (b) => matches(b.element_id, filter) && inSubarea(subarea, b.subarea_from, b.subarea_to) && (!onlyViolations || b.overload),
      ),
    [r, filter, subarea, onlyViolations],
  );
  const gens = useMemo(
    () => (r?.generators ?? []).filter((g) => matches(g.gen_id, filter) && inSubarea(subarea, subareaOfBus.get(g.bus))),
    [r, filter, subarea, subareaOfBus],
  );

  if (r === null) {
    const d = run.diagnostics;
    return (
      <section className="results" data-testid="results">
        <h2>Estado: {run.status}</h2>
        <p className="error">El flujo no convergió. No se muestran tensiones ni flujos como si fueran válidos.</p>
        {d && (
          <>
            <p>
              {d.iterations} iteraciones; desbalance máximo {fmtNum(d.max_mismatch_mva, 2)} MVA ({d.basis}).
            </p>
            <table>
              <thead>
                <tr>
                  <th>Barra</th>
                  <th>Desbalance (MVA)</th>
                </tr>
              </thead>
              <tbody>
                {d.worst_buses.map((w) => (
                  <tr key={w.bus}>
                    <td>{w.bus}</td>
                    <td>{fmtNum(w.mismatch_mva, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>
    );
  }

  const s = r.summary;

  return (
    <section className="results" data-testid="results">
      <h2>Estado: {run.status}</h2>
      <p className="summary">
        Generación {fmtMw(s.p_gen_mw)} · carga {fmtMw(s.p_load_mw)} · pérdidas {fmtMw(s.p_losses_mw)} · ajuste de la
        referencia {fmtMw(s.slack_adjust_total_mw)} ·{" "}
        <strong data-testid="n-voltage-violations">{s.n_voltage_violations} violaciones de tensión</strong> ·{" "}
        <strong data-testid="n-overloads">{s.n_overloads} sobrecargas</strong>
      </p>
      <details className="section">
        <summary>Límites aplicados (con fuente)</summary>
        <ul>
          {s.limits.map((l) => (
            <li key={l.name}>
              {l.name}: {l.value} — {l.source}
            </li>
          ))}
        </ul>
      </details>
      <div className="toolbar">
        {TABS.map((t) => (
          <button key={t.id} type="button" className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
        <input placeholder="Filtrar por nombre" value={filter} onChange={(e) => setFilter(e.target.value)} data-testid="filter" />
        <select value={subarea} onChange={(e) => setSubarea(e.target.value)} data-testid="table-subarea">
          <option value="">Todas las subáreas</option>
          {subareaOptions.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <label>
          <input type="checkbox" checked={onlyViolations} onChange={(e) => setOnlyViolations(e.target.checked)} data-testid="only-violations" /> Solo
          fuera de límite
        </label>
      </div>
      {tab === "buses" && <BusTable rows={buses} />}
      {tab === "lines" && <BranchTable rows={lines} />}
      {tab === "trafos" && <BranchTable rows={trafos} />}
      {tab === "generators" && <GenTable rows={gens} subareaOfBus={subareaOfBus} />}
    </section>
  );
}
