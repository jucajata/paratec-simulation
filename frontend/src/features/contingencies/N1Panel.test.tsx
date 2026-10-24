import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ProblemError } from "../../api/client";
import type { N1Analysis, N1Job, Outage, Problem, Run } from "../../api/types";
import { N1Panel } from "./N1Panel";

const mocks = vi.hoisted(() => ({
  startN1: vi.fn<(runId: string) => Promise<N1Job>>(),
  n1Job: vi.fn<(id: string) => Promise<N1Job>>(),
}));

vi.mock("../../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../api/client")>();
  return { ...original, api: { ...original.api, ...mocks } };
});

function run(partial: Partial<Run>): Run {
  return { run_id: "r1", case_id: "c1", flow_type: "ac", status: "convergio", result: {}, diagnostics: null, ...partial } as unknown as Run;
}

const outage = (element_id: string, kind: Outage["kind"] = "line", extra: Partial<Outage> = {}): Outage => ({
  element_id,
  kind,
  subarea: "Bogotá",
  angle_ref_moved_to: null,
  ...extra,
});

const analysis: N1Analysis = {
  run_id: "r1",
  trace: {
    snapshot_date: "2026-10-20",
    dispatch_date: "2026-10-20",
    period: 19,
    flow_type: "ac",
    pandapower_version: "3.5.6",
    sinsim_version: "0.6.0",
    solver: { algorithm: "nr", tolerance_mva: 1e-8, max_iteration: 30, init: "dc", enforce_q_lims: true, distributed_slack: true },
    case_id: "abcdef0123456789",
  },
  limits: [{ name: "Cargabilidad", value: "100 %", source: "CREG 025/1995" }],
  analyzed_at: "2026-10-24T15:00:00Z",
  workers: 11,
  summary: { n_total: 1261, n_loading: 1, n_voltage: 1, n_isolation: 1, n_unsolved: 1, n_no_impact: 1257, duration_s: 76.2 },
  loading: [
    {
      rank: 1,
      outage: outage("line:GUAVIO - MAMBITA 1 115 kV"),
      element_id: "trafo:GUAVIO 6 230/115 kV",
      loading_base_percent: 97.3,
      loading_percent: 201.4,
      n_elements: 3,
      isolation: { n_buses: 1, p_demand_lost_mw: 12.5 },
    },
  ],
  voltage: [
    {
      rank: 1,
      outage: outage("SAN CARLOS@SAN CARLOS|230", "gen", { angle_ref_moved_to: "GUAVIO|230" }),
      bus_id: "JAMONDINO|230",
      vm_base_pu: 0.95,
      vm_pu: 0.842,
      deviation_pu: -0.058,
      n_buses: 4,
      isolation: null,
    },
  ],
  isolation: [{ rank: 1, outage: outage("line:MAGANGUE - MOMPOX 1 110 kV"), n_buses: 1, p_demand_lost_mw: 33.3 }],
  unsolved: [
    {
      outage: outage("line:OCOA - SANTA HELENA 1 115 KV"),
      diagnostics: { iterations: 30, max_mismatch_mva: 12.3, worst_buses: [{ bus: "OCOA|115", mismatch_mva: 12.3 }], basis: "última iteración" },
    },
  ],
};

function job(partial: Partial<N1Job>): N1Job {
  return { job_id: "j1", run_id: "r1", status: "en_cola", done: 0, total: 0, started_at: "2026-10-24T15:00:00Z", finished_at: null, result: null, error: null, ...partial };
}

function problem(code: string, user_message: string): Problem {
  return { type: "x", title: code, status: 409, detail: "", code, user_message, trace_id: "t" };
}

function renderPanel(r: Run) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <N1Panel run={r} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mocks.startN1.mockReset();
  mocks.n1Job.mockReset();
});

describe("N1Panel", () => {
  it("no ofrece el análisis sobre un flujo DC ni sobre uno que no convergió (FR-061)", () => {
    renderPanel(run({ flow_type: "dc" }));
    expect(screen.getByTestId("n1-start")).toBeDisabled();
    expect(screen.getByTestId("n1-unavailable")).toHaveTextContent("aproximación DC");
  });

  it("lanza el análisis, muestra el avance y después los listados (FR-053 a FR-058)", async () => {
    mocks.startN1.mockResolvedValue(job({ status: "en_cola" }));
    mocks.n1Job.mockResolvedValueOnce(job({ status: "calculando", done: 640, total: 1261 })).mockResolvedValue(job({ status: "listo", done: 1261, total: 1261, finished_at: "2026-10-24T15:01:16Z", result: analysis }));
    renderPanel(run({}));
    fireEvent.click(screen.getByTestId("n1-start"));
    await waitFor(() => expect(mocks.startN1).toHaveBeenCalledWith("r1"));
    await waitFor(() => expect(screen.getByTestId("n1-progress")).toHaveTextContent("640 / 1261 contingencias"));
    await waitFor(() => expect(screen.getByTestId("n1-summary")).toBeVisible());
    expect(screen.getByTestId("n1-total")).toHaveTextContent("1261");
    expect(screen.getByTestId("n1-summary")).toHaveTextContent("1 min 16 s");
    const loading = screen.getByTestId("n1-loading");
    expect(loading).toHaveTextContent("GUAVIO - MAMBITA 1 115 kV");
    expect(loading).toHaveTextContent("201,4 %");
    expect(loading).toHaveTextContent("aísla 1 barra, 12,5 MW sin servicio");
    expect(loading).toHaveTextContent("Línea");
    const voltage = screen.getByTestId("n1-voltage");
    expect(voltage).toHaveTextContent("JAMONDINO|230");
    expect(voltage).toHaveTextContent("0,842 pu");
    expect(voltage).toHaveTextContent("−0,058 pu");
    expect(voltage).toHaveTextContent("referencia de ángulo → GUAVIO|230");
    expect(screen.getByTestId("n1-isolation")).toHaveTextContent("33,3 MW");
    expect(screen.getByTestId("n1-unsolved")).toHaveTextContent("OCOA - SANTA HELENA 1 115 KV");
    expect(screen.getByTestId("n1-unsolved")).toHaveTextContent("30");
    expect(screen.getByTestId("n1-trace")).toHaveTextContent("pandapower 3.5.6");
    expect(screen.getByText(/CREG 025\/1995/)).toBeInTheDocument();
    expect(screen.getByTestId("n1-start")).toBeEnabled();
  });

  it("muestra el mensaje del 409 cuando ya hay un análisis en curso", async () => {
    mocks.startN1.mockRejectedValue(new ProblemError(problem("N1_IN_PROGRESS", "Ya hay un análisis N-1 en curso. Espera a que termine.")));
    renderPanel(run({}));
    fireEvent.click(screen.getByTestId("n1-start"));
    await waitFor(() => expect(screen.getByTestId("n1-error")).toHaveTextContent("Ya hay un análisis N-1 en curso"));
    expect(screen.getByTestId("n1-start")).toBeEnabled();
  });
});
