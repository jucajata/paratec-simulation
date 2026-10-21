import { fireEvent, render, screen, within } from "@testing-library/react";

import type { GeneratorResult, TopologyEdge, TopologyNode } from "../../api/types";
import { BusDetail } from "./BusDetail";
import { busDetail } from "./busModel";

const node: TopologyNode = {
  id: "GUAVIO|230",
  label: "GUAVIO|230",
  vn_kv: 230,
  vm_pu: 1.02,
  violation: null,
  in_service: true,
  subarea: "Bogota",
  p_gen_mw: 800,
  q_gen_mvar: 50,
  p_load_mw: 12.5,
  q_load_mvar: 3,
  p_load_act_mw: 12,
  p_load_pstr_mw: 0.5,
};
const edges: TopologyEdge[] = [
  { id: "line:GUAVIO - TUNAL 1 230 kV", source: "GUAVIO|230", target: "TUNAL|230", kind: "line", loading_percent: 61, overload: false, p_from_mw: 500, q_from_mvar: 10, p_to_mw: -495, q_to_mvar: -5 },
  { id: "line:CIRCO - GUAVIO 1 230 kV", source: "CIRCO|230", target: "GUAVIO|230", kind: "line", loading_percent: 104, overload: true, p_from_mw: -290, q_from_mvar: 2, p_to_mw: 287.5, q_to_mvar: -1 },
];
const gens: GeneratorResult[] = [
  { gen_id: "GUAVIO@GUAVIO|230", resource: "GUAVIO", bus: "GUAVIO|230", p_scheduled_mw: 954, p_mw: 800, q_mvar: 50, slack_adjust_mw: -154 },
];

describe("BusDetail", () => {
  it("muestra generación, carga con sus componentes, ramas con sentido y balance", () => {
    const onClose = vi.fn();
    render(<BusDetail detail={busDetail(node, edges, gens)} onClose={onClose} />);
    expect(screen.getByTestId("bus-gen")).toHaveTextContent("800,0 MW");
    expect(screen.getByTestId("bus-load")).toHaveTextContent("Ener.Act. 12,0 MW + Perd.PSTR 0,5 MW");
    expect(screen.getByTestId("bus-balance")).toHaveTextContent("0,0 MW");
    const rows = within(screen.getByTestId("bus-branches")).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent("→ 500,0 MW");
    expect(rows[2]).toHaveTextContent("→ 287,5 MW");
    expect(rows[2]).toHaveClass("overload");
    expect(within(screen.getByTestId("bus-generators")).getByText("GUAVIO@GUAVIO|230")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("bus-detail-close"));
    expect(onClose).toHaveBeenCalled();
  });
});
