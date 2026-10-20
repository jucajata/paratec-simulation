import { render, screen, within } from "@testing-library/react";

import type { StudyCase } from "../../api/types";
import { CaseQuality } from "./CaseQuality";

const studyCase: StudyCase = {
  case_id: "c".repeat(64),
  inputs: {
    snapshot_date: "2026-10-20",
    dispatch_date: "2026-10-20",
    period: 19,
    snapshot_manifest_sha256: "a".repeat(64),
    equivalences_sha256: "b".repeat(64),
    config_sha256: "c".repeat(64),
    sinsim_version: "0.1.0",
  },
  quality: {
    unlocated_resources: [{ resource: "PLANTA_FANTASMA", p_mw: 123.4, reason: "sin equivalencia" }],
    unlocated_demand: [],
    transfers: [{ element: "PORCE III MENOR / U1", kind: "gen", from_bus: "GUADALUPE IV|13.8", to_bus: "GUADALUPE IV|115", p_mw: 1.5, q_mvar: 0 }],
    excluded: [{ element: "line:X", kind: "línea", missing_params: ["from_bus", "to_bus"] }],
    imputed: [{ element: "trafo:Y", kind: "transformador", param: "vkr_percent", method: "mediana", value: 0.25 }],
    not_modeled: [],
    islands: [
      { island_id: 0, n_buses: 590, buses: [], p_gen_lost_mw: 0, p_demand_lost_mw: 0, energized: true },
      { island_id: 1, n_buses: 2, buses: ["TEBSA II|115", "TEBSA II|230"], p_gen_lost_mw: 120, p_demand_lost_mw: 0, energized: false },
    ],
    physical_issues: [],
    balance: {
      p_scheduled_total_mw: 12331,
      p_located_mw: 12208,
      p_unlocated_mw: 123,
      coverage_pct: 99.0,
      p_demand_mw: 8930,
      p_demand_unlocated_mw: 3220,
      difference_mw: 3278,
    },
  },
  assumptions: {
    consigna_tension_pu: { valor: 1.0 },
    generadores: [
      {
        gen_id: "GUAVIO@GUAVIO|230",
        barra: "GUAVIO|230",
        vm_pu: 1.0,
        fuente_vm: "Supuesto del proyecto aprobado por el usuario el 2026-10-20",
        q_min_mvar: -300,
        q_max_mvar: 450,
        fuente_q: "PARATEC (q_absorb_mvar, q_gen_mvar de las unidades)",
      },
      {
        gen_id: "PEQUENA@X|115",
        barra: "X|115",
        vm_pu: 1.0,
        fuente_vm: "Supuesto del proyecto aprobado por el usuario el 2026-10-20",
        q_min_mvar: null,
        q_max_mvar: null,
        fuente_q: "PARATEC no publica los límites de todas las unidades: sin límite de Q",
      },
    ],
  },
  warnings: ["PROGRAM_NOT_REAL_STATE: el resultado describe el despacho programado por XM, no el estado real del SIN."],
  created_at: "2026-10-20T00:00:00Z",
};

describe("CaseQuality", () => {
  it("muestra el balance, la cobertura, los no ubicados y las islas", () => {
    render(<CaseQuality studyCase={studyCase} />);
    expect(screen.getByTestId("coverage")).toHaveTextContent("99,0 %");
    expect(screen.getByText("PLANTA_FANTASMA")).toBeInTheDocument();
    expect(screen.getByText(/PROGRAM_NOT_REAL_STATE/)).toBeInTheDocument();
    expect(screen.getByText(/120,0 MW de generación/)).toBeInTheDocument();
    expect(screen.getByText(/Islas \(120.0 MW/)).toBeInTheDocument();
    expect(screen.getByText(/faltan from_bus, to_bus/)).toBeInTheDocument();
    expect(screen.getByText(/vkr_percent = 0.2500/)).toBeInTheDocument();
  });

  it("muestra por generador la consigna y los límites de reactiva con su fuente (FR-018)", () => {
    render(<CaseQuality studyCase={studyCase} />);
    const table = screen.getByTestId("generator-assumptions");
    expect(within(table).getAllByRole("row")).toHaveLength(3); // encabezado + 2
    const guavio = within(table).getByText("GUAVIO@GUAVIO|230").closest("tr");
    expect(guavio).toHaveTextContent("PARATEC (q_absorb_mvar, q_gen_mvar de las unidades)");
    const small = within(table).getByText("PEQUENA@X|115").closest("tr");
    expect(small).toHaveTextContent("sin límite de Q");
    expect(within(small as HTMLElement).getAllByText("—")).toHaveLength(2);
  });
});
