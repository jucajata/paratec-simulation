import type { TopologyEdge, TopologyNode } from "../../api/types";
import { NO_SUBAREA_COLOR, filterBySubarea, subareaColor } from "./subareas";

function node(id: string, subarea: string | null): TopologyNode {
  return { id, label: id, vn_kv: 115, vm_pu: 1, violation: null, in_service: true, subarea };
}
function edge(id: string, source: string, target: string): TopologyEdge {
  return { id, source, target, kind: "line", loading_percent: 10, overload: false };
}

const nodes = [node("A|115", "Antioquia"), node("B|115", "Antioquia"), node("C|115", "Valle"), node("D|115", null)];
const edges = [edge("A-B", "A|115", "B|115"), edge("B-C", "B|115", "C|115"), edge("C-D", "C|115", "D|115")];

describe("subareas", () => {
  it("da un color estable por subárea y gris a las barras sin subárea", () => {
    const all = ["Valle", "Antioquia"];
    expect(subareaColor("Antioquia", all)).toBe(subareaColor("Antioquia", ["Antioquia", "Valle"]));
    expect(subareaColor("Antioquia", all)).not.toBe(subareaColor("Valle", all));
    expect(subareaColor(null, all)).toBe(NO_SUBAREA_COLOR);
    expect(subareaColor("Desconocida", all)).toBe(NO_SUBAREA_COLOR);
  });

  it("filtra una subárea con sus ramas internas y la frontera con la vecina", () => {
    const view = filterBySubarea(nodes, edges, "Antioquia");
    expect(view.nodes.map((n) => [n.id, n.frontier])).toEqual([
      ["A|115", false],
      ["B|115", false],
      ["C|115", true],
    ]);
    expect(view.edges.map((e) => [e.id, e.frontier])).toEqual([
      ["A-B", false],
      ["B-C", true],
    ]);
  });

  it("sin subárea elegida no filtra nada", () => {
    const view = filterBySubarea(nodes, edges, null);
    expect(view.nodes).toHaveLength(4);
    expect(view.edges).toHaveLength(3);
    expect(view.edges.every((e) => !e.frontier)).toBe(true);
  });
});
