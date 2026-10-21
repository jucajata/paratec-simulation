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

/** Separa cifra y unidad de un valor ya formateado («9.631,9 MW») para la franja de indicadores. */
function Kpi({ label, value, alert = false, testId }: { label: string; value: string; alert?: boolean; testId?: string }): JSX.Element {
  const i = value.indexOf(" ");
  const num = i < 0 ? value : value.slice(0, i);
  const unit = i < 0 ? "" : value.slice(i + 1);
  return (
    <div className="kpi">
      <span className="kpi__label">{label}</span>
      <span className={alert ? "kpi__value kpi__value--alert" : "kpi__value"} data-testid={testId}>
        {num}
        {unit && <small>{` ${unit}`}</small>}
      </span>
    </div>
  );
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

  const converged = run.status === "convergio";
  const statusChip = (
    <span className={converged ? "chip chip--ok" : "chip chip--error"}>Estado: {run.status}</span>
  );

  if (r === null) {
    const d = run.diagnostics;
    return (
      <section className="results stack" data-testid="results">
        <div className="section-head">
          <h2>Resultado del flujo</h2>
          {statusChip}
          {d && <span className="muted small">{d.iterations} iteraciones</span>}
        </div>
        <div className="card card--padded stack" style={{ borderColor: "var(--error)" }}>
          <p className="error" role="alert" style={{ fontWeight: 600 }}>
            El flujo no convergió. No se muestran tensiones ni flujos como si fueran válidos.
          </p>
          {d && (
            <p>
              {d.iterations} iteraciones; desbalance máximo {fmtNum(d.max_mismatch_mva, 2)} MVA ({d.basis}). Revisa las barras
              con mayor desbalance y los recursos no ubicados del reporte de calidad.
            </p>
          )}
        </div>
        {d && (
          <div className="card">
            <div className="results__bar">
              <h3>Barras con mayor desbalance</h3>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Barra</th>
                    <th className="num">Desbalance (MVA)</th>
                  </tr>
                </thead>
                <tbody>
                  {d.worst_buses.map((w) => (
                    <tr key={w.bus}>
                      <td>{w.bus}</td>
                      <td className="num">{fmtNum(w.mismatch_mva, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    );
  }

  const s = r.summary;
  const rowsShown = tab === "buses" ? buses.length : tab === "lines" ? lines.length : tab === "trafos" ? trafos.length : gens.length;
  const rowsTotal =
    tab === "buses" ? r.buses.length : tab === "lines" ? r.lines.length : tab === "trafos" ? r.trafos.length : r.generators.length;

  return (
    <section className="results stack" data-testid="results">
      <div className="section-head">
        <h2>Resultado del flujo</h2>
        {statusChip}
        <span className="muted small">
          Snapshot {run.trace.snapshot_date} · periodo {run.trace.period} · flujo {run.trace.flow_type}
        </span>
      </div>
      <div className="card kpis">
        <Kpi label="Generación" value={fmtMw(s.p_gen_mw)} />
        <Kpi label="Carga" value={fmtMw(s.p_load_mw)} />
        <Kpi label="Pérdidas" value={fmtMw(s.p_losses_mw)} />
        <Kpi label="Ajuste de la referencia" value={fmtMw(s.slack_adjust_total_mw)} />
        <Kpi
          label="Fuera de límite"
          value={`${s.n_voltage_violations} violaciones de tensión`}
          alert={s.n_voltage_violations > 0}
          testId="n-voltage-violations"
        />
        <Kpi label="Cargabilidad" value={`${s.n_overloads} sobrecargas`} alert={s.n_overloads > 0} testId="n-overloads" />
      </div>
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
      <div className="card">
        <div className="results__bar toolbar">
          <h2>Resultados</h2>
          <div className="tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                aria-pressed={tab === t.id}
                className={tab === t.id ? "active" : ""}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <span className="spacer" />
          <input
            type="search"
            placeholder="Filtrar por nombre"
            aria-label="Filtrar por nombre"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            data-testid="filter"
          />
          <select value={subarea} aria-label="Subárea" onChange={(e) => setSubarea(e.target.value)} data-testid="table-subarea">
            <option value="">Todas las subáreas</option>
            {subareaOptions.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <label className="inline-check">
            <input type="checkbox" checked={onlyViolations} onChange={(e) => setOnlyViolations(e.target.checked)} data-testid="only-violations" />
            Solo fuera de límite
          </label>
        </div>
        <div className="table-scroll">
          {tab === "buses" && <BusTable rows={buses} />}
          {tab === "lines" && <BranchTable rows={lines} />}
          {tab === "trafos" && <BranchTable rows={trafos} />}
          {tab === "generators" && <GenTable rows={gens} subareaOfBus={subareaOfBus} />}
        </div>
        <p className="results__foot muted">
          {rowsShown} de {rowsTotal} {TABS.find((t) => t.id === tab)?.label.toLowerCase()}
          {(filter || subarea || onlyViolations) && " · con filtros aplicados"}
        </p>
      </div>
    </section>
  );
}
