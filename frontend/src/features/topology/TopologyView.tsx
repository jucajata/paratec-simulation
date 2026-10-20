import cytoscape, { type EdgeSingular, type NodeSingular } from "cytoscape";
import { useEffect, useRef, useState } from "react";

import { useTopology } from "../../api/hooks";
import type { TopologyEdge, TopologyNode } from "../../api/types";
import { loadingColor, voltageColor } from "./colors";

type ColorBy = "voltage" | "loading";

interface Props {
  runId: string;
}

export function TopologyView({ runId }: Props): JSX.Element {
  const topology = useTopology(runId);
  const container = useRef<HTMLDivElement>(null);
  const [colorBy, setColorBy] = useState<ColorBy>("voltage");
  const [hover, setHover] = useState<string>("");

  useEffect(() => {
    const data = topology.data;
    const el = container.current;
    if (!data || !el) return;
    const nodes = data.nodes.filter((n) => n.in_service);
    const nodeIds = new Set(nodes.map((n) => n.id));
    const edges = data.edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
    const cy = cytoscape({
      container: el,
      elements: [
        ...nodes.map((n: TopologyNode) => ({
          data: { id: n.id, label: n.label, vn_kv: n.vn_kv, vm_pu: n.vm_pu, violation: n.violation },
        })),
        ...edges.map((e: TopologyEdge) => ({
          data: { id: e.id, source: e.source, target: e.target, kind: e.kind, loading: e.loading_percent, overload: e.overload },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            width: (ele: NodeSingular) => 6 + Math.sqrt(Number(ele.data("vn_kv")) || 0) / 2,
            height: (ele: NodeSingular) => 6 + Math.sqrt(Number(ele.data("vn_kv")) || 0) / 2,
            "background-color": (ele: NodeSingular) =>
              colorBy === "voltage" ? voltageColor(ele.data("vm_pu") as number | null) : "#5f6368",
            "border-width": (ele: NodeSingular) => (ele.data("violation") ? 2 : 0),
            "border-color": "#000",
            label: "",
          },
        },
        {
          selector: "edge",
          style: {
            width: (ele: EdgeSingular) => (ele.data("kind") === "line" ? 1.5 : 2.5),
            "line-style": (ele: EdgeSingular) => (ele.data("kind") === "line" ? "solid" : "dashed"),
            "line-color": (ele: EdgeSingular) =>
              colorBy === "loading" ? loadingColor(ele.data("loading") as number | null) : "#b0b4b8",
            "curve-style": "haystack",
          },
        },
      ],
      layout: { name: "cose", animate: false, numIter: 400, nodeRepulsion: () => 8000, idealEdgeLength: () => 40 },
      wheelSensitivity: 0.2,
    });
    cy.on("mouseover", "node", (evt) => {
      const d = evt.target.data();
      setHover(`${d.label} · ${d.vn_kv} kV${d.vm_pu !== null ? ` · ${Number(d.vm_pu).toFixed(3)} pu` : ""}`);
    });
    cy.on("mouseover", "edge", (evt) => {
      const d = evt.target.data();
      setHover(`${d.id}${d.loading !== null ? ` · ${Number(d.loading).toFixed(1)} %` : ""}`);
    });
    cy.on("mouseout", () => setHover(""));
    return () => {
      cy.destroy();
    };
  }, [topology.data, colorBy]);

  return (
    <section className="topology" data-testid="topology">
      <h2>Topología lógica</h2>
      <div className="toolbar">
        <label>
          Colorear por{" "}
          <select value={colorBy} onChange={(e) => setColorBy(e.target.value as ColorBy)} data-testid="color-by">
            <option value="voltage">tensión (pu)</option>
            <option value="loading">cargabilidad (%)</option>
          </select>
        </label>
        <span className="legend">
          {colorBy === "voltage" ? (
            <>
              <i style={{ background: voltageColor(0.9) }} /> 0,90 pu <i style={{ background: voltageColor(1.0) }} /> 1,00 pu{" "}
              <i style={{ background: voltageColor(1.1) }} /> 1,10 pu
            </>
          ) : (
            <>
              <i style={{ background: loadingColor(0) }} /> 0 % <i style={{ background: loadingColor(50) }} /> 50 %{" "}
              <i style={{ background: loadingColor(100) }} /> ≥ 100 %
            </>
          )}
          {" · "}líneas continuas, transformadores discontinuos
        </span>
        <span className="hover" data-testid="hover">
          {hover}
        </span>
      </div>
      {topology.isLoading && <p>Cargando topología…</p>}
      {topology.isError && <p className="error">No se pudo cargar la topología.</p>}
      <div ref={container} className="graph" />
    </section>
  );
}
