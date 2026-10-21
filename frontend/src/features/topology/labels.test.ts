import type { TopologyEdge, TopologyNode } from "../../api/types";
import { DEFAULT_LABELS, branchCaption, busCaption, loadLabelSelection, saveLabelSelection } from "./labels";

const node: TopologyNode = {
  id: "GUAVIO|230", label: "GUAVIO|230", vn_kv: 230, vm_pu: 1.0234, violation: null, in_service: true, subarea: "Bogota",
  vm_kv: 235.4, va_degree: -12.34, p_gen_mw: 800, q_gen_mvar: 50.5, p_load_mw: 0, q_load_mvar: 0, slack_adjust_mw: -154,
};
const edge: TopologyEdge = {
  id: "L", source: "a", target: "b", kind: "line", loading_percent: 61.4, overload: false,
  p_from_mw: -500.2, q_from_mvar: 10.1, p_to_mw: 495, q_to_mvar: -5, i_ka: 1.234, pl_mw: 5.2, ql_mvar: 12,
};

describe("labels", () => {
  it("compone la etiqueta de barra con los datos elegidos y omite lo que no aplica", () => {
    expect(busCaption(node, DEFAULT_LABELS.bus)).toBe("GUAVIO|230\nG 800 MW");
    expect(busCaption(node, ["vm_pu", "vm_kv", "va", "q_gen", "p_load", "slack"])).toBe("1.023 pu\n235.4 kV\n-12.3°\nG 50.5 Mvar\nref -154 MW");
  });

  it("compone la etiqueta de rama en valor absoluto", () => {
    expect(branchCaption(edge, ["p"])).toBe("500 MW");
    expect(branchCaption(edge, ["p", "q", "i", "loading", "losses"])).toBe("500 MW · 10.1 Mvar · 1.234 kA · 61 % · Δ 5.2 MW");
  });

  it("guarda y recupera la selección, y vuelve a la de por defecto si el almacenamiento falla", () => {
    const store = new Map<string, string>();
    const storage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) };
    saveLabelSelection(storage, { bus: ["name", "vm_pu"], branch: ["loading"] });
    expect(loadLabelSelection(storage)).toEqual({ bus: ["name", "vm_pu"], branch: ["loading"] });
    store.set("sinsim.topology.labels", "{no es json");
    expect(loadLabelSelection(storage)).toEqual(DEFAULT_LABELS);
    expect(loadLabelSelection(null)).toEqual(DEFAULT_LABELS);
    const broken = { getItem: () => { throw new Error("bloqueado"); }, setItem: () => { throw new Error("bloqueado"); } };
    expect(loadLabelSelection(broken)).toEqual(DEFAULT_LABELS);
    expect(() => saveLabelSelection(broken, DEFAULT_LABELS)).not.toThrow();
  });
});
