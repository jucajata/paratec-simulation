import { fireEvent, render, screen } from "@testing-library/react";

import type { QualityReport } from "../../api/types";
import { Collaborate } from "./Collaborate";
import { pendingText } from "./pending";

const quality: QualityReport = {
  unlocated_resources: [{ resource: "PLANTA_FANTASMA", p_mw: 123.4, reason: "sin equivalencia" }],
  unlocated_demand: [{ node: "NODO_X", vn_kv: 115, p_mw: 12.5, q_mvar: 3.1, reason: "sin equivalencia" }],
  transfers: [],
  excluded: [],
  imputed: [],
  not_modeled: [],
  islands: [],
  physical_issues: [],
  balance: {
    p_scheduled_total_mw: 0, p_located_mw: 0, p_unlocated_mw: 0, coverage_pct: 0, p_demand_mw: 0, p_demand_unlocated_mw: 0, difference_mw: 0,
  },
};

beforeAll(() => {
  // jsdom no implementa <dialog>.showModal.
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
});

describe("Collaborate", () => {
  it("resume lo pendiente y abre el paso a paso", () => {
    render(<Collaborate quality={quality} />);
    expect(screen.getByTestId("collab-pending")).toHaveTextContent("1");
    const dialog = screen.getByTestId("collab-dialog") as HTMLDialogElement;
    expect(dialog.open).toBe(false);
    fireEvent.click(screen.getByTestId("collab-open"));
    expect(dialog.open).toBe(true);
    expect(dialog).toHaveTextContent("recursos_despacho.csv");
    expect(dialog).toHaveTextContent("nodos_demanda.csv");
    expect(dialog).toHaveTextContent("make test");
    expect(screen.getByRole("link", { name: /github\.com\/jucajata\/sinsim/ })).toHaveAttribute("target", "_blank");
  });

  it("prepara la lista de pendientes para copiar", () => {
    const text = pendingText(quality);
    expect(text).toContain("PLANTA_FANTASMA\t123.4 MW");
    expect(text).toContain("NODO_X\t115 kV\t12.5 MW");
    expect(pendingText({ ...quality, unlocated_resources: [], unlocated_demand: [] })).toBe("");
  });
});
