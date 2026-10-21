import type { TopologyNode } from "../../api/types";
import { PX_PER_DEGREE, SAME_SUBSTATION_RADIUS, UNPLACED_MARGIN, geoLayout, geometryPath, project } from "./geo";

function node(id: string, vn_kv: number, lat: number | null, lon: number | null): TopologyNode {
  return { id, label: id, vn_kv, vm_pu: 1, violation: null, in_service: true, subarea: null, lat, lon };
}

describe("geo", () => {
  it("proyecta el norte hacia arriba y el este hacia la derecha", () => {
    const bogota = project(4.6, -74.08);
    const barranquilla = project(10.96, -74.8);
    const cucuta = project(7.89, -72.5);
    expect(barranquilla.y).toBeLessThan(bogota.y);
    expect(cucuta.x).toBeGreaterThan(bogota.x);
    expect(project(5.5, -74).y - project(4.5, -74).y).toBeCloseTo(-PX_PER_DEGREE, 6);
  });

  it("separa las barras de una misma subestación y deja una sola en su punto exacto", () => {
    const { positions, unplaced } = geoLayout([
      node("GUATAPE|230", 230, 6.23, -75.16),
      node("GUATAPE|115", 115, 6.23, -75.16),
      node("ANCON SUR|230", 230, 6.13, -75.62),
    ]);
    expect(unplaced).toEqual([]);
    const a = positions.get("GUATAPE|230");
    const b = positions.get("GUATAPE|115");
    const center = project(6.23, -75.16);
    expect(a && b).toBeTruthy();
    expect(Math.hypot((a?.x ?? 0) - center.x, (a?.y ?? 0) - center.y)).toBeCloseTo(SAME_SUBSTATION_RADIUS, 6);
    expect(a).not.toEqual(b);
    expect(positions.get("ANCON SUR|230")).toEqual(project(6.13, -75.62));
  });

  it("nunca ubica por inferencia las barras sin coordenadas: van a una franja al oeste", () => {
    const { positions, unplaced } = geoLayout([node("A|115", 115, 6, -75), node("SIN|115", 115, null, null)]);
    expect(unplaced).toEqual(["SIN|115"]);
    expect(positions.get("SIN|115")?.x).toBeCloseTo(project(6, -75).x - UNPLACED_MARGIN, 6);
  });

  it("convierte polígonos GeoJSON en trazos SVG", () => {
    const d = geometryPath({ type: "Polygon", coordinates: [[[-75, 6], [-74, 6], [-74, 5], [-75, 6]]] });
    expect(d.startsWith("M")).toBe(true);
    expect(d.endsWith("Z")).toBe(true);
    expect(d.split("L")).toHaveLength(4);
    const multi = geometryPath({
      type: "MultiPolygon",
      coordinates: [[[[-75, 6], [-74, 6], [-75, 5]]], [[[-70, 2], [-69, 2], [-70, 1]]]],
    });
    expect(multi.match(/M/g)).toHaveLength(2);
  });
});
