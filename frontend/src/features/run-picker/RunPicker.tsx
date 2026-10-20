import { useState } from "react";

import { useSnapshots } from "../../api/hooks";
import type { FlowType, SnapshotSummary } from "../../api/types";

export interface RunRequest {
  snapshotDate: string;
  period: number;
  flowType: FlowType;
}

interface Props {
  busy: boolean;
  onSubmit: (request: RunRequest) => void;
}

function disabledReason(s: SnapshotSummary): string | null {
  if (!s.intact) return "snapshot alterado: no coincide con su manifiesto";
  const missing: string[] = [];
  if (!s.has_paratec) missing.push("parámetros PARATEC");
  if (!s.has_dispatch) missing.push("despacho programado");
  if (!s.has_demand) missing.push("pronóstico de demanda");
  return missing.length ? `faltan: ${missing.join(", ")}` : null;
}

export function RunPicker({ busy, onSubmit }: Props): JSX.Element {
  const snapshots = useSnapshots();
  const [date, setDate] = useState<string>("");
  const [period, setPeriod] = useState<number>(19);
  const [flowType, setFlowType] = useState<FlowType>("ac");

  const rows = snapshots.data ?? [];
  const selectable = rows.filter((s) => disabledReason(s) === null);
  const effectiveDate = date || selectable[0]?.date || "";
  const periodValid = Number.isInteger(period) && period >= 1 && period <= 24;

  return (
    <form
      className="picker"
      onSubmit={(e) => {
        e.preventDefault();
        if (effectiveDate && periodValid) onSubmit({ snapshotDate: effectiveDate, period, flowType });
      }}
    >
      <label>
        Fecha del snapshot
        <select
          value={effectiveDate}
          onChange={(e) => setDate(e.target.value)}
          disabled={snapshots.isLoading || rows.length === 0}
          data-testid="snapshot-date"
        >
          {rows.map((s) => {
            const reason = disabledReason(s);
            return (
              <option key={s.date} value={s.date} disabled={reason !== null}>
                {s.date}
                {reason ? ` — ${reason}` : ""}
              </option>
            );
          })}
        </select>
      </label>
      <label>
        Periodo (1–24)
        <input
          type="number"
          min={1}
          max={24}
          value={period}
          onChange={(e) => setPeriod(Number(e.target.value))}
          data-testid="period"
        />
      </label>
      <label>
        Tipo de flujo
        <select value={flowType} onChange={(e) => setFlowType(e.target.value as FlowType)} data-testid="flow-type">
          <option value="ac">AC</option>
          <option value="dc">DC (aproximación)</option>
        </select>
      </label>
      <button type="submit" disabled={busy || !effectiveDate || !periodValid} data-testid="run-button">
        {busy ? "Calculando…" : "Ejecutar"}
      </button>
      {snapshots.isError && <p className="error">No se pudo leer la lista de snapshots.</p>}
      {!snapshots.isLoading && rows.length === 0 && (
        <p className="error">No hay snapshots en data/paratec/. Ejecuta `sinsim scrape --fecha YYYY-MM-DD`.</p>
      )}
      {!periodValid && <p className="error">El periodo debe estar entre 1 y 24.</p>}
    </form>
  );
}
