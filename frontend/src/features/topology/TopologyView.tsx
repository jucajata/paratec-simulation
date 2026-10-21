import cytoscape, { type EdgeSingular, type NodeSingular } from "cytoscape";
import { useEffect, useMemo, useRef, useState } from "react";

import { useBasemap, useTopology } from "../../api/hooks";
import type { Run, TopologyNode } from "../../api/types";
import { BusDetail } from "./BusDetail";
import { busDetail, type BusDetailData } from "./busModel";
import { angleColor, loadingColor, voltageColor } from "./colors";
import { type BasemapGeometry, geoLayout, geometryPath } from "./geo";
import {
  BRANCH_LABELS,
  BRANCH_LABEL_TEXT,
  BUS_LABELS,
  BUS_LABEL_TEXT,
  type BranchLabel,
  type BusLabel,
  type LabelSelection,
  branchCaption,
  busCaption,
  loadLabelSelection,
  saveLabelSelection,
} from "./labels";
import { STR_ZOOM, busVisible } from "./lod";
import { NO_SUBAREA_COLOR, filterBySubarea, subareaColor } from "./subareas";

type ColorBy = "voltage" | "loading" | "subarea" | "angle";


function storage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}
type Layout = "logical" | "geo";

interface Props {
  run: Run;
}

/** Zoom a partir del cual se leen las etiquetas de barras y de flujos (FR-036). */
const LABEL_ZOOM = 2.5;
/** Tamaños ∝ zoom^−0,6: crecen con el acercamiento, pero más despacio, y las barras se separan. */
const SIZE_EXPONENT = -0.6;


export function TopologyView({ run }: Props): JSX.Element {
  const runId = run.run_id;
  const topology = useTopology(runId);
  const [selectedBus, setSelectedBus] = useState<string | null>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const busIds = useMemo(
    () => (topology.data?.nodes ?? []).filter((n) => n.in_service).map((n) => n.id).sort(),
    [topology.data],
  );

  /** Selecciona una barra por nombre y centra la vista en ella (FR-036). */
  function focusBus(id: string): void {
    if (!busIds.includes(id)) return;
    setSelectedBus(id);
    const cy = cyRef.current;
    const node = cy?.getElementById(id);
    if (cy && node && node.nonempty()) {
      cy.animate({ center: { eles: node }, zoom: Math.max(cy.zoom(), LABEL_ZOOM * 1.5) }, { duration: 300 });
      cy.nodes().unselect();
      node.select();
    }
  }
  const container = useRef<HTMLDivElement>(null);
  const [colorBy, setColorBy] = useState<ColorBy>("voltage");
  const [subarea, setSubarea] = useState<string | null>(null);
  const [layout, setLayout] = useState<Layout>("geo");
  const [hover, setHover] = useState<string>("");
  const [unplaced, setUnplaced] = useState<string[]>([]);
  const [strVisible, setStrVisible] = useState(false);
  const [labels, setLabels] = useState<LabelSelection>(() => loadLabelSelection(storage()));
  function toggleBusLabel(l: BusLabel): void {
    const bus = labels.bus.includes(l) ? labels.bus.filter((x) => x !== l) : [...labels.bus, l];
    const next = { ...labels, bus };
    setLabels(next);
    saveLabelSelection(storage(), next);
  }
  function toggleBranchLabel(l: BranchLabel): void {
    const branch = labels.branch.includes(l) ? labels.branch.filter((x) => x !== l) : [...labels.branch, l];
    const next = { ...labels, branch };
    setLabels(next);
    saveLabelSelection(storage(), next);
  }
  const basemap = useBasemap(layout === "geo");
  const basemapLayer = useRef<SVGGElement>(null);
  const basemapPaths = useMemo(
    () =>
      (basemap.data?.features ?? []).map((f) => ({
        key: `${f.properties.kind}:${f.properties.name}`,
        kind: f.properties.kind,
        d: geometryPath(f.geometry as BasemapGeometry),
      })),
    [basemap.data],
  );

  const subareas = useMemo(() => topology.data?.subareas ?? [], [topology.data]);
  const allNames = useMemo(() => subareas.map((s) => s.name), [subareas]);
  const selected = subareas.find((s) => s.name === subarea) ?? null;
  const detail: BusDetailData | null = useMemo(() => {
    const data = topology.data;
    if (!data || !selectedBus) return null;
    const node = data.nodes.find((n: TopologyNode) => n.id === selectedBus);
    return node ? busDetail(node, data.edges, run.result?.generators ?? []) : null;
  }, [topology.data, selectedBus, run.result]);

  useEffect(() => {
    const data = topology.data;
    const el = container.current;
    if (!data || !el) return;
    const inService = data.nodes.filter((n) => n.in_service);
    const ids = new Set(inService.map((n) => n.id));
    const view = filterBySubarea(
      inService,
      data.edges.filter((e) => ids.has(e.source) && ids.has(e.target)),
      subarea,
    );
    const geo = layout === "geo" ? geoLayout(view.nodes) : null;
    setUnplaced(geo ? geo.unplaced : []);
    const unplacedIds = new Set(geo ? geo.unplaced : []);
    let zoom = 1;
    const sizeFactor = () => Math.pow(zoom, SIZE_EXPONENT);
    const labelsVisible = () => zoom >= LABEL_ZOOM;
    const cy = cytoscape({
      container: el,
      elements: [
        ...view.nodes.map((n) => ({
          data: {
            id: n.id,
            label: n.label,
            vn_kv: n.vn_kv,
            vm_pu: n.vm_pu,
            violation: n.violation,
            subarea: n.subarea,
            frontier: n.frontier,
            p_gen: n.p_gen_mw ?? 0,
            p_load: n.p_load_mw ?? 0,
            va: n.va_degree ?? null,
            caption: busCaption(n, labels.bus),
          },
        })),
        ...view.edges.map((e) => ({
          data: {
            id: e.id,
            source: e.source,
            target: e.target,
            kind: e.kind,
            loading: e.loading_percent,
            overload: e.overload,
            frontier: e.frontier,
            // Ramas hacia barras sin coordenadas: se atenúan para no cruzar el mapa con trazos falsos.
            unplaced: unplacedIds.has(e.source) || unplacedIds.has(e.target),
            // Flujo con el signo de pandapower: positivo sale de source (FR-036).
            p_from: e.p_from_mw ?? null,
            flow_label: branchCaption(e, labels.branch),
          },
        })),
      ],
      // Factor de tamaño según el zoom actual; se recalcula en cada cambio de zoom.
      // Barras fijas en el mapa (sus coordenadas son datos); arrastrables en la disposición lógica.
      autoungrabify: layout === "geo",
      boxSelectionEnabled: false,
      // Mientras se desplaza o hace zoom no se dibujan las ramas: se repintan al soltar.
      hideEdgesOnViewport: true,
      style: [
        {
          selector: "node",
          style: {
            // Nivel de detalle: con poco zoom solo el STN; Cytoscape oculta también sus ramas.
            display: (ele: NodeSingular) => (busVisible(Number(ele.data("vn_kv")) || 0, zoom) ? "element" : "none"),
            width: (ele: NodeSingular) => sizeFactor() * (6 + Math.sqrt(Number(ele.data("vn_kv")) || 0) / 2),
            height: (ele: NodeSingular) => sizeFactor() * (6 + Math.sqrt(Number(ele.data("vn_kv")) || 0) / 2),
            "background-color": (ele: NodeSingular) => {
              if (colorBy === "voltage") return voltageColor(ele.data("vm_pu") as number | null);
              if (colorBy === "subarea") return subareaColor(ele.data("subarea") as string | null, allNames);
              if (colorBy === "angle") return angleColor(ele.data("va") as number | null);
              return "#5f6368";
            },
            "background-opacity": (ele: NodeSingular) => (ele.data("frontier") ? 0.35 : 1),
            "border-width": (ele: NodeSingular) => sizeFactor() * (ele.data("violation") ? 2 : 0),
            "border-color": "#000",
            label: (ele: NodeSingular) => (labelsVisible() ? String(ele.data("caption")) : ""),
            "text-wrap": "wrap",
            "font-size": () => 10 / zoom,
            "text-valign": "bottom",
            "text-margin-y": () => 3 / zoom,
            "text-background-color": "#fff",
            "text-background-opacity": 0.75,
            "text-background-padding": "1px",
          },
        },
        {
          selector: "node:selected",
          style: { "border-width": () => sizeFactor() * 3, "border-color": "#0b5fff" },
        },
        {
          selector: "edge",
          style: {
            width: (ele: EdgeSingular) => sizeFactor() * (ele.data("kind") === "line" ? 1.5 : 2.5),
            "line-style": (ele: EdgeSingular) => (ele.data("kind") === "line" ? "solid" : "dashed"),
            "line-color": (ele: EdgeSingular) =>
              colorBy === "loading" ? loadingColor(ele.data("loading") as number | null) : "#b0b4b8",
            "line-opacity": (ele: EdgeSingular) => (ele.data("unplaced") ? 0.12 : ele.data("frontier") ? 0.45 : 1),
            "curve-style": "straight",
            // Flecha en el sentido del flujo de P: hacia target si p_from > 0, hacia source si < 0.
            "target-arrow-shape": (ele: EdgeSingular) =>
              labelsVisible() && typeof ele.data("p_from") === "number" && ele.data("p_from") > 0 ? "triangle" : "none",
            "source-arrow-shape": (ele: EdgeSingular) =>
              labelsVisible() && typeof ele.data("p_from") === "number" && ele.data("p_from") < 0 ? "triangle" : "none",
            "target-arrow-color": "#5f6368",
            "source-arrow-color": "#5f6368",
            // En pantalla la flecha mide ∝ zoom · ancho · escala; con escala ∝ zoom^−0,7 y ancho
            // ∝ zoom^−0,6, la flecha se hace proporcionalmente más pequeña al acercarse.
            "arrow-scale": () => Math.max(0.15, 1.2 * Math.pow(zoom, -0.7)),
            label: (ele: EdgeSingular) => (labelsVisible() ? String(ele.data("flow_label")) : ""),
            "font-size": () => 9 / zoom,
            "text-rotation": "autorotate",
            "text-background-color": "#fff",
            "text-background-opacity": 0.75,
          },
        },
      ],
      layout: geo
        ? {
            name: "preset",
            positions: Object.fromEntries(geo.positions),
            fit: true,
            padding: 20,
          }
        : { name: "cose", animate: false, numIter: 400, nodeRepulsion: () => 8000, idealEdgeLength: () => 40 },
      wheelSensitivity: 0.2,
    });
    // El mapa base vive en coordenadas de modelo: se mueve con el pan y el zoom del grafo.
    const syncBasemap = () => {
      const g = basemapLayer.current;
      if (!g) return;
      const { x, y } = cy.pan();
      g.setAttribute("transform", `translate(${x},${y}) scale(${cy.zoom()})`);
    };
    cyRef.current = cy;
    cy.on("viewport", syncBasemap);
    syncBasemap();
    zoom = cy.zoom();
    cy.style().update();
    let frame = 0;
    let strShown = zoom >= STR_ZOOM;
    setStrVisible(strShown);
    cy.on("zoom", () => {
      zoom = cy.zoom();
      // Un recálculo por cuadro basta: los estilos leen `zoom` al evaluarse.
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => cy.style().update());
      if ((zoom >= STR_ZOOM) !== strShown) {
        strShown = zoom >= STR_ZOOM;
        setStrVisible(strShown);
      }
    });
    cy.on("tap", "node", (evt) => setSelectedBus(String(evt.target.id())));
    cy.on("tap", (evt) => {
      if (evt.target === cy) setSelectedBus(null);
    });
    cy.on("mouseover", "node", (evt) => {
      const d = evt.target.data();
      const vm = d.vm_pu !== null ? ` · ${Number(d.vm_pu).toFixed(3)} pu` : "";
      const sa = d.subarea ? ` · ${d.subarea}${d.frontier ? " (vecina)" : ""}` : " · sin subárea";
      setHover(`${d.label} · ${d.vn_kv} kV${vm}${sa}`);
    });
    cy.on("mouseover", "edge", (evt) => {
      const d = evt.target.data();
      const ld = d.loading !== null ? ` · ${Number(d.loading).toFixed(1)} %` : "";
      setHover(`${d.id}${ld}${d.frontier ? " · frontera entre subáreas" : ""}`);
    });
    cy.on("mouseout", () => setHover(""));
    return () => {
      cancelAnimationFrame(frame);
      cyRef.current = null;
      cy.destroy();
    };
  }, [topology.data, colorBy, subarea, allNames, layout, labels]);

  return (
    <section className="topology" data-testid="topology">
      <h2>Topología {layout === "geo" ? "geográfica" : "lógica"}</h2>
      <div className="toolbar">
        <label>
          Colorear por{" "}
          <select value={colorBy} onChange={(e) => setColorBy(e.target.value as ColorBy)} data-testid="color-by">
            <option value="voltage">tensión (pu)</option>
            <option value="loading">cargabilidad (%)</option>
            <option value="subarea">subárea</option>
            <option value="angle">ángulo (°)</option>
          </select>
        </label>
        <label>
          Disposición{" "}
          <select value={layout} onChange={(e) => setLayout(e.target.value as Layout)} data-testid="layout">
            <option value="logical">lógica</option>
            <option value="geo">geográfica</option>
          </select>
        </label>
        <label>
          Subárea{" "}
          <select
            value={subarea ?? ""}
            onChange={(e) => setSubarea(e.target.value === "" ? null : e.target.value)}
            data-testid="subarea-filter"
          >
            <option value="">todas</option>
            {subareas.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Barra{" "}
          <input
            list="bus-ids"
            placeholder="buscar y centrar"
            data-testid="bus-search"
            onChange={(e) => focusBus(e.target.value)}
          />
          <datalist id="bus-ids">
            {busIds.map((id) => (
              <option key={id} value={id} />
            ))}
          </datalist>
        </label>
        {selected &&
          (selected.unifilar_url ? (
            <a href={selected.unifilar_url} target="_blank" rel="noreferrer" data-testid="unifilar-link">
              Ver unifilar de XM ({selected.name})
            </a>
          ) : (
            <span className="muted">XM no publica unifilar de esta subárea.</span>
          ))}
        <span className="legend">
          {colorBy === "voltage" && (
            <>
              <i style={{ background: voltageColor(0.9) }} /> 0,90 pu <i style={{ background: voltageColor(1.0) }} /> 1,00 pu{" "}
              <i style={{ background: voltageColor(1.1) }} /> 1,10 pu
            </>
          )}
          {colorBy === "loading" && (
            <>
              <i style={{ background: loadingColor(0) }} /> 0 % <i style={{ background: loadingColor(50) }} /> 50 %{" "}
              <i style={{ background: loadingColor(100) }} /> ≥ 100 %
            </>
          )}
          {colorBy === "angle" && (
            <>
              <i style={{ background: angleColor(-30) }} /> −30° <i style={{ background: angleColor(0) }} /> 0°{" "}
              <i style={{ background: angleColor(30) }} /> +30°
            </>
          )}
          {colorBy === "subarea" && (
            <span data-testid="subarea-legend">
              {subareas.map((s) => (
                <span key={s.name}>
                  <i style={{ background: subareaColor(s.name, allNames) }} /> {s.name}{" "}
                </span>
              ))}
              <i style={{ background: NO_SUBAREA_COLOR }} /> sin subárea
            </span>
          )}
          {" · "}líneas continuas, transformadores discontinuos
          {strVisible ? " · STN y STR visibles" : " · solo STN: acerca para ver el STR"}
          {" · acerca más para ver G, C y flujos; clic en una barra para su detalle"}
          {layout === "geo" ? " · barras fijas en su ubicación" : " · barras arrastrables"}
          {subarea && ", barras y ramas de frontera atenuadas"}
          {layout === "geo" && unplaced.length > 0 && (
            <span data-testid="unplaced">
              {" · "}
              {unplaced.length} barras sin coordenadas en PARATEC, en la columna izquierda
            </span>
          )}
        </span>
        <span className="hover" data-testid="hover">
          {hover}
        </span>
      </div>
      <div className="toolbar labels" data-testid="label-selectors">
        <span className="muted">Etiquetas de barra:</span>
        {BUS_LABELS.map((l) => (
          <label key={l}>
            <input type="checkbox" checked={labels.bus.includes(l)} onChange={() => toggleBusLabel(l)} data-testid={`bus-label-${l}`} />{" "}
            {BUS_LABEL_TEXT[l]}
          </label>
        ))}
        <span className="muted">· de rama:</span>
        {BRANCH_LABELS.map((l) => (
          <label key={l}>
            <input type="checkbox" checked={labels.branch.includes(l)} onChange={() => toggleBranchLabel(l)} data-testid={`branch-label-${l}`} />{" "}
            {BRANCH_LABEL_TEXT[l]}
          </label>
        ))}
      </div>
      {topology.isLoading && <p>Cargando topología…</p>}
      {topology.isError && <p className="error">No se pudo cargar la topología.</p>}
      {layout === "geo" && basemap.isError && (
        <p className="error">No se pudo cargar el mapa base; las barras siguen en su ubicación.</p>
      )}
      <div className="graph-wrap">
        <svg className="basemap" aria-hidden="true" style={{ display: layout === "geo" ? "block" : "none" }} data-testid="basemap">
          <g ref={basemapLayer}>
            {basemapPaths.map((p) => (
              <path key={p.key} d={p.d} className={p.kind === "departamento" ? "department" : "neighbor"} />
            ))}
          </g>
        </svg>
        <div ref={container} className="graph" />
      </div>
      {detail && <BusDetail detail={detail} onClose={() => setSelectedBus(null)} />}
      {layout === "geo" && basemap.data && <p className="muted attribution">{basemap.data.attribution}</p>}
    </section>
  );
}
