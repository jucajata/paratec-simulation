/** Disposición geográfica de la topología (FR-035). Funciones puras, sin dependencias. */

import type { TopologyNode } from "../../api/types";

export interface Point {
  x: number;
  y: number;
}

/** Píxeles de modelo por grado de latitud. Colombia ocupa unos 1 900 px de alto. */
export const PX_PER_DEGREE = 100;
/** Centro aproximado de Colombia: la proyección es equirectangular alrededor de él. */
const LAT0 = 4.5;
const LON0 = -74.0;
const COS_LAT0 = Math.cos((LAT0 * Math.PI) / 180);

/** Radio de la separación entre barras de una misma subestación, en píxeles de modelo. */
export const SAME_SUBSTATION_RADIUS = 3;
/** Radio máximo al repartirlas según el zoom: unos 13 km, para no alejarlas de su ubicación. */
export const MAX_SUBSTATION_RADIUS = 12;
/** Distancia de la franja de barras sin coordenadas al borde oeste del mapa. */
export const UNPLACED_MARGIN = 60;
const UNPLACED_STEP = 14;

/** Proyecta (lat, lon) WGS84 a coordenadas de modelo: x hacia el este, y hacia el sur. */
export function project(lat: number, lon: number): Point {
  return { x: (lon - LON0) * PX_PER_DEGREE * COS_LAT0, y: -(lat - LAT0) * PX_PER_DEGREE };
}

function substationOf(busId: string): string {
  const i = busId.lastIndexOf("|");
  return i < 0 ? busId : busId.slice(0, i);
}

export interface SubstationGroup {
  center: Point;
  /** Barras de la subestación, la de mayor tensión primero. */
  members: string[];
}

export interface GeoLayout {
  positions: Map<string, Point>;
  /** Subestaciones con más de una barra: la vista las reparte según el zoom. */
  groups: SubstationGroup[];
  /** Barras sin coordenadas, dibujadas en una franja al oeste: nunca se ubican por inferencia. */
  unplaced: string[];
}

/**
 * Ubica cada barra en las coordenadas de su subestación. Las barras de una misma subestación
 * se reparten en un círculo pequeño, la de mayor tensión primero, para que no se tapen.
 */
export function geoLayout(nodes: readonly TopologyNode[]): GeoLayout {
  const positions = new Map<string, Point>();
  const groups = new Map<string, TopologyNode[]>();
  const unplaced: string[] = [];
  const multi: SubstationGroup[] = [];
  for (const n of nodes) {
    if (n.lat === null || n.lon === null || n.lat === undefined || n.lon === undefined) {
      unplaced.push(n.id);
      continue;
    }
    const key = substationOf(n.id);
    groups.set(key, [...(groups.get(key) ?? []), n]);
  }
  for (const members of groups.values()) {
    const sorted = [...members].sort((a, b) => b.vn_kv - a.vn_kv || a.id.localeCompare(b.id));
    const head = sorted[0];
    if (head && sorted.length > 1) {
      multi.push({ center: project(head.lat as number, head.lon as number), members: sorted.map((n) => n.id) });
    }
    sorted.forEach((n, i) => {
      const center = project(n.lat as number, n.lon as number);
      if (sorted.length === 1) {
        positions.set(n.id, center);
        return;
      }
      const angle = (2 * Math.PI * i) / sorted.length - Math.PI / 2;
      positions.set(n.id, {
        x: center.x + SAME_SUBSTATION_RADIUS * Math.cos(angle),
        y: center.y + SAME_SUBSTATION_RADIUS * Math.sin(angle),
      });
    });
  }
  if (unplaced.length > 0) {
    const placed = [...positions.values()];
    const minX = placed.length ? Math.min(...placed.map((p) => p.x)) : 0;
    const minY = placed.length ? Math.min(...placed.map((p) => p.y)) : 0;
    [...unplaced].sort().forEach((id, i) => {
      positions.set(id, { x: minX - UNPLACED_MARGIN, y: minY + i * UNPLACED_STEP });
    });
  }
  return { positions, groups: multi, unplaced: [...unplaced].sort() };
}

type Ring = readonly (readonly number[])[];
type Polygon = readonly Ring[];

/** Geometría GeoJSON mínima que usa el mapa base. */
export interface BasemapGeometry {
  type: "Polygon" | "MultiPolygon";
  coordinates: Polygon | readonly Polygon[];
}

/** Trazo SVG (`d`) de un Polygon o MultiPolygon GeoJSON en coordenadas de modelo. */
export function geometryPath(geometry: BasemapGeometry): string {
  const polygons = (geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates) as readonly Polygon[];
  const parts: string[] = [];
  for (const polygon of polygons) {
    for (const ring of polygon) {
      const pts = ring
        .filter((c) => c.length >= 2)
        .map((c) => project(c[1] as number, c[0] as number))
        .map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`);
      if (pts.length > 1) parts.push(`M${pts.join("L")}Z`);
    }
  }
  return parts.join("");
}
