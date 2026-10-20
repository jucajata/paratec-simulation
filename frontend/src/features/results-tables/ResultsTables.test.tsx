import { fireEvent, render, screen, within } from "@testing-library/react";

import type { Run } from "../../api/types";
import { ResultsTables } from "./ResultsTables";

function makeRun(): Run {
  const base = {
    run_id: "r1",
    case_id: "c".repeat(64),
    flow_type: "ac" as const,
    label: "Flujo sobre despacho programado",
    solver: { algorithm: "nr", tolerance_mva: 1e-8, max_iteration: 30, init: "dc", enforce_q_lims: true, distributed_slack: true },
    trace: {
      snapshot_date: "2026-10-20",
      dispatch_date: "2026-10-20",
      period: 19,
      flow_type: "ac" as const,
      pandapower_version: "3.5.6",
      sinsim_version: "0.1.0",
      solver: { algorithm: "nr", tolerance_mva: 1e-8, max_iteration: 30, init: "dc", enforce_q_lims: true, distributed_slack: true },
      case_id: "c".repeat(64),
    },
    created_at: "2026-10-20T00:00:00Z",
  };
  return {
    ...base,
    status: "convergio",
    diagnostics: null,
    result: {
      buses: [
        { bus_id: "GUAVIO|230", vn_kv: 230, vm_pu: 1.01, vm_kv: 232.3, va_degree: 0, violation: null },
        { bus_id: "MOMPOX|115", vn_kv: 110, vm_pu: 0.85, vm_kv: 93.5, va_degree: -20, violation: "low" },
        { bus_id: "EL BANCO|115", vn_kv: 110, vm_pu: 1.18, vm_kv: 129.8, va_degree: -5, violation: "high" },
      ],
      lines: [
        {
          element_id: "line:A - B 1 230 kV",
          kind: "line",
          from_bus: "A|230",
          to_bus: "B|230",
          p_from_mw: 100,
          q_from_mvar: 10,
          p_to_mw: -99,
          q_to_mvar: -8,
          i_ka: 0.3,
          loading_percent: 106,
          pl_mw: 1,
          ql_mvar: 2,
          overload: true,
        },
        {
          element_id: "line:C - D 1 115 kV",
          kind: "line",
          from_bus: "C|115",
          to_bus: "D|115",
          p_from_mw: 10,
          q_from_mvar: 1,
          p_to_mw: -10,
          q_to_mvar: -1,
          i_ka: 0.05,
          loading_percent: 20,
          pl_mw: 0.1,
          ql_mvar: 0.2,
          overload: false,
        },
      ],
      trafos: [],
      generators: [
        { gen_id: "GUAVIO@GUAVIO|230", resource: "GUAVIO", bus: "GUAVIO|230", p_scheduled_mw: 954, p_mw: 800, q_mvar: 50, slack_adjust_mw: -154 },
      ],
      summary: {
        p_gen_mw: 800,
        p_load_mw: 790,
        p_losses_mw: 10,
        slack_adjust_total_mw: -154,
        n_voltage_violations: 2,
        n_overloads: 1,
        limits: [{ name: "Tensión STN", value: "0.90–1.10 pu", source: "CREG 025/1995" }],
        warnings: ["PROGRAM_NOT_REAL_STATE"],
      },
    },
  };
}

describe("ResultsTables", () => {
  it("cuenta y resalta las violaciones y filtra por texto", () => {
    render(<ResultsTables run={makeRun()} />);
    expect(screen.getByTestId("n-voltage-violations")).toHaveTextContent("2 violaciones de tensión");
    expect(screen.getByTestId("n-overloads")).toHaveTextContent("1 sobrecargas");
    const table = screen.getByTestId("table-buses");
    expect(within(table).getAllByRole("row")).toHaveLength(4); // encabezado + 3
    expect(within(table).getByText("MOMPOX|115").closest("tr")).toHaveClass("violation", "low");
    expect(within(table).getByText("GUAVIO|230").closest("tr")).not.toHaveClass("violation");

    fireEvent.click(screen.getByTestId("only-violations"));
    expect(within(screen.getByTestId("table-buses")).getAllByRole("row")).toHaveLength(3);

    fireEvent.change(screen.getByTestId("filter"), { target: { value: "banco" } });
    expect(within(screen.getByTestId("table-buses")).getAllByRole("row")).toHaveLength(2);
    expect(screen.getByText("EL BANCO|115")).toBeInTheDocument();
  });

  it("muestra las líneas sobrecargadas resaltadas", () => {
    render(<ResultsTables run={makeRun()} />);
    fireEvent.click(screen.getByRole("button", { name: "Líneas" }));
    const table = screen.getByTestId("table-branches");
    expect(within(table).getByText("line:A - B 1 230 kV").closest("tr")).toHaveClass("overload");
    fireEvent.click(screen.getByTestId("only-violations"));
    expect(within(screen.getByTestId("table-branches")).getAllByRole("row")).toHaveLength(2);
  });

  it("no muestra tablas cuando no converge", () => {
    const run = makeRun();
    const failed: Run = {
      ...run,
      status: "no_convergio",
      result: null,
      diagnostics: { iterations: 30, max_mismatch_mva: 1234.5, basis: "última iteración", worst_buses: [{ bus: "X|115", mismatch_mva: 1234.5 }] },
    };
    render(<ResultsTables run={failed} />);
    expect(screen.getByText(/no convergió/)).toBeInTheDocument();
    expect(screen.queryByTestId("table-buses")).not.toBeInTheDocument();
    expect(screen.getByText("X|115")).toBeInTheDocument();
  });
});
