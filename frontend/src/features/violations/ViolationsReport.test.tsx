import { render, screen, within } from "@testing-library/react";

import type { Run } from "../../api/types";
import { ViolationsReport } from "./ViolationsReport";

const solver = { algorithm: "nr", tolerance_mva: 1e-8, max_iteration: 30, init: "dc", enforce_q_lims: true, distributed_slack: true };
const run: Run = {
  run_id: "r", case_id: "c".repeat(64), flow_type: "ac", status: "convergio", label: "Flujo sobre despacho programado", solver,
  trace: { snapshot_date: "2026-10-20", dispatch_date: "2026-10-20", period: 19, flow_type: "ac", pandapower_version: "3.5.6", sinsim_version: "0.3.0", solver, case_id: "c".repeat(64) },
  diagnostics: null,
  created_at: "2026-10-20T00:00:00Z",
  result: {
    buses: [], lines: [], trafos: [], generators: [],
    summary: {
      p_gen_mw: 1, p_load_mw: 1, p_losses_mw: 0, slack_adjust_total_mw: 0, n_voltage_violations: 2, n_overloads: 1, limits: [], warnings: [],
      violations: [
        { kind: "tension_baja", element: "MOMPOX|115", subarea: "Bolivar", value: 0.853, limit: 0.9, deviation: 0.047, unit: "pu", source: "CREG 153/2019" },
        { kind: "tension_alta", element: "EL BANCO|115", subarea: "GCM", value: 1.187, limit: 1.1, deviation: 0.087, unit: "pu", source: "CREG 153/2019" },
        { kind: "sobrecarga", element: "line:GAMBOTE - TERNERA 1 66 kV", subarea: null, value: 104.9, limit: 100, deviation: 4.9, unit: "%", source: "CREG 025/1995" },
      ],
    },
  },
};

describe("ViolationsReport", () => {
  it("muestra los tres grupos con valor, límite, desviación y fuente", () => {
    render(<ViolationsReport run={run} />);
    const low = within(screen.getByTestId("violations-low")).getAllByRole("row");
    expect(low).toHaveLength(2);
    expect(low[1]).toHaveTextContent("MOMPOX|115");
    expect(low[1]).toHaveTextContent("0,853 pu");
    expect(low[1]).toHaveTextContent("0,90 pu");
    expect(low[1]).toHaveTextContent("CREG 153/2019");
    expect(within(screen.getByTestId("violations-high")).getByText("EL BANCO|115")).toBeInTheDocument();
    const over = within(screen.getByTestId("violations-overload")).getAllByRole("row");
    expect(over[1]).toHaveTextContent("104,9 %");
    expect(over[1]).toHaveTextContent("entre subáreas");
  });

  it("explica cuando la ejecución es anterior al reporte", () => {
    const result = run.result;
    if (!result) throw new Error("fixture sin resultado");
    const { violations: _omitted, ...summary } = result.summary;
    void _omitted;
    const old: Run = { ...run, result: { ...result, summary } };
    render(<ViolationsReport run={old} />);
    expect(screen.getByText(/anterior al reporte/)).toBeInTheDocument();
  });
});
