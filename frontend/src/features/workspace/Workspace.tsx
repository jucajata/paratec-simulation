import { useState } from "react";

import { ProblemError, api } from "../../api/client";
import { useCreateCase, useRunCase } from "../../api/hooks";
import type { Run, StudyCase } from "../../api/types";
import { CaseQuality } from "../case-quality/CaseQuality";
import { ResultsTables } from "../results-tables/ResultsTables";
import { RunPicker, type RunRequest } from "../run-picker/RunPicker";
import { TopologyView } from "../topology/TopologyView";
import { ViolationsReport } from "../violations/ViolationsReport";

const ATTRIBUTION = "Información proporcionada por XM S.A. E.S.P. – PARATEC y archivos públicos de despacho";

/** Flujo completo: picker → calidad del caso → ejecución → resultados, topología y exportación. */
export function Workspace(): JSX.Element {
  const createCase = useCreateCase();
  const runCase = useRunCase();
  const [studyCase, setStudyCase] = useState<StudyCase | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);

  const busy = createCase.isPending || runCase.isPending;

  async function execute(req: RunRequest): Promise<void> {
    setError(null);
    setRun(null);
    try {
      const built = await createCase.mutateAsync({ snapshot_date: req.snapshotDate, period: req.period });
      setStudyCase(built);
      const result = await runCase.mutateAsync({ caseId: built.case_id, flowType: req.flowType });
      setRun(result);
    } catch (e) {
      setError(e instanceof ProblemError ? e.problem.user_message : "Ocurrió un error no previsto.");
    }
  }

  return (
    <>
      <header>
        <h1>sinsim</h1>
        <p className="label" data-testid="label">
          {run ? run.label : "Flujo sobre despacho programado (no es el estado real del SIN)"}
        </p>
        {run && (
          <p className="trace">
            Snapshot {run.trace.snapshot_date} · despacho {run.trace.dispatch_date} periodo {run.trace.period} · flujo{" "}
            {run.trace.flow_type} · pandapower {run.trace.pandapower_version} · sinsim {run.trace.sinsim_version} · caso{" "}
            <code>{run.trace.case_id.slice(0, 12)}…</code>
          </p>
        )}
      </header>
      <main>
        <RunPicker busy={busy} onSubmit={(r) => void execute(r)} />
        {error && (
          <p className="error" role="alert" data-testid="error">
            {error}
          </p>
        )}
        {busy && <p className="muted">Construyendo el caso y corriendo el flujo…</p>}
        {studyCase && <CaseQuality studyCase={studyCase} />}
        {run && (
          <>
            <p className="actions">
              <a className="button" href={api.exportUrl(run.run_id)} download data-testid="export-link">
                Exportar .zip
              </a>
            </p>
            <ResultsTables run={run} />
            <ViolationsReport run={run} />
            {run.result && <TopologyView run={run} />}
          </>
        )}
      </main>
      <footer>{ATTRIBUTION}</footer>
    </>
  );
}
