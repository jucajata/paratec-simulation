import type { GeneratorResult, TopologyEdge, TopologyNode } from "../../api/types";
import { branchesFromBus, busDetail } from "./busModel";

const node: TopologyNode = {
  id: "B|230",
  label: "B|230",
  vn_kv: 230,
  vm_pu: 1.01,
  violation: null,
  in_service: true,
  subarea: "Antioquia",
  p_gen_mw: 100,
  q_gen_mvar: 20,
  p_load_mw: 30,
  q_load_mvar: 10,
  p_load_act_mw: 28,
  p_load_pstr_mw: 2,
};
const edges: TopologyEdge[] = [
  { id: "A-B", source: "A|230", target: "B|230", kind: "line", loading_percent: 40, overload: false, p_from_mw: -49, q_from_mvar: 1, p_to_mw: 50, q_to_mvar: -2 },
  { id: "B-C", source: "B|230", target: "C|230", kind: "line", loading_percent: 20, overload: false, p_from_mw: 20, q_from_mvar: 3, p_to_mw: -19.8, q_to_mvar: -3 },
  { id: "C-D", source: "C|230", target: "D|230", kind: "line", loading_percent: 5, overload: false, p_from_mw: 1, q_from_mvar: 0, p_to_mw: -1, q_to_mvar: 0 },
];
const gens: GeneratorResult[] = [
  { gen_id: "G@B|230", resource: "G", bus: "B|230", p_scheduled_mw: 100, p_mw: 100, q_mvar: 20, slack_adjust_mw: 0 },
  { gen_id: "H@C|230", resource: "H", bus: "C|230", p_scheduled_mw: 5, p_mw: 5, q_mvar: 0, slack_adjust_mw: 0 },
];

describe("busDetail", () => {
  it("orienta los flujos desde la barra: positivo sale de ella", () => {
    const b = branchesFromBus("B|230", edges);
    expect(b.map((x) => [x.id, x.other, x.p_out_mw])).toEqual([
      ["A-B", "A|230", 50],
      ["B-C", "C|230", 20],
    ]);
  });

  it("reúne generadores propios, carga y balance de la barra", () => {
    const d = busDetail(node, edges, gens);
    expect(d.generators.map((g) => g.gen_id)).toEqual(["G@B|230"]);
    expect(d.branches).toHaveLength(2);
    expect(d.balance_mw).toBeCloseTo(100 - 30 - (50 + 20), 9);
  });

  it("deja el balance en nulo si falta algún flujo", () => {
    const noFlow = edges.map((e) => (e.id === "B-C" ? { ...e, p_from_mw: null } : e));
    expect(busDetail(node, noFlow, gens).balance_mw).toBeNull();
  });
});
