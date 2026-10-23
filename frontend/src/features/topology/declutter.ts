/**
 * Control de densidad de la topología: tamaños en pantalla acotados y etiquetas sin solapes.
 * Funciones puras; la vista solo les pasa posiciones en pantalla y aplica el resultado.
 */

/** Exponente con que barras y ramas crecen en pantalla al acercarse (más despacio que el zoom). */
export const GROWTH_EXPONENT = 0.4;
/** Tope de ese crecimiento: con más zoom las barras se separan, pero ya no crecen. */
export const MAX_GROWTH = 1.5;
/** Lado de la flecha de sentido del flujo, en píxeles de pantalla. */
export const ARROW_PX = 9;
/** Separación en pantalla entre ramas paralelas (doble circuito) que unen las mismas barras. */
export const PARALLEL_GAP_PX = 10;
/** Tamaño de letra en pantalla de las etiquetas de barra y de rama. */
export const BUS_FONT_PX = 11;
export const BRANCH_FONT_PX = 10;
/** Holgura entre etiquetas, en píxeles de pantalla. */
const LABEL_GAP_PX = 3;
/** Ancho medio de un carácter respecto al tamaño de letra (fuente sans del sistema). */
const CHAR_WIDTH = 0.6;
const LINE_HEIGHT = 1.25;

/** Factor de crecimiento en pantalla para un zoom dado. */
export function screenGrowth(zoom: number): number {
  return Math.min(Math.pow(zoom, GROWTH_EXPONENT), MAX_GROWTH);
}

/** Diámetro en pantalla de una barra: crece con la tensión y, acotado, con el zoom. */
export function busDiameterPx(vn_kv: number, zoom: number): number {
  return (6 + Math.sqrt(Math.max(vn_kv, 0)) / 2) * screenGrowth(zoom);
}

/** Ancho en pantalla de una rama: los transformadores un poco más gruesos que las líneas. */
export function branchWidthPx(kind: string, zoom: number): number {
  return (kind === "line" ? 1.5 : 2.5) * screenGrowth(zoom);
}

/**
 * Escala de flecha que Cytoscape necesita para dibujarla de `ARROW_PX` en pantalla.
 * Cytoscape mide la flecha como `max((ancho · 13,37)^0,9, 29) · escala` en unidades de modelo:
 * con zoom alto ese mínimo de 29 la volvía gigante. Aquí se compensa exactamente.
 */
export function arrowScale(edgeModelWidth: number, zoom: number, px = ARROW_PX): number {
  const base = Math.max(Math.pow(edgeModelWidth * 13.37, 0.9), 29);
  return px / (zoom * base);
}

/**
 * Radio de modelo del círculo en que se reparten las barras de una misma subestación, para que
 * no se tapen en pantalla: la cuerda entre dos vecinas debe superar su diámetro. Acotado arriba
 * para no alejar las barras de su ubicación real cuando el zoom es bajo.
 */
export function ringRadius(count: number, diameterPx: number, zoom: number, minModel: number, maxModel: number): number {
  if (count < 2) return 0;
  const chord = diameterPx + 4;
  const screen = chord / (2 * Math.sin(Math.PI / count));
  return Math.min(Math.max(screen / zoom, minModel), maxModel);
}

export interface Box {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export function overlaps(a: Box, b: Box): boolean {
  return a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2;
}

/** Ancho y alto en pantalla de un texto de varias líneas. */
export function textSize(text: string, fontPx: number): { w: number; h: number } {
  const lines = text.split("\n");
  const longest = Math.max(0, ...lines.map((l) => l.length));
  return { w: longest * fontPx * CHAR_WIDTH + 4, h: lines.length * fontPx * LINE_HEIGHT + 2 };
}

/** Posiciones posibles de la etiqueta de una barra, en orden de preferencia. */
export const LABEL_POSITIONS = ["bottom", "top", "right", "left"] as const;
export type LabelPosition = (typeof LABEL_POSITIONS)[number];

/** Separación entre el disco y su etiqueta, en píxeles de pantalla. */
export const LABEL_OFFSET_PX = 3;

/** Caja de la etiqueta de una barra en una posición: debajo, encima, a la derecha o a la izquierda. */
export function busLabelBox(
  x: number,
  y: number,
  diameterPx: number,
  text: string,
  position: LabelPosition = "bottom",
  fontPx = BUS_FONT_PX,
): Box {
  const { w, h } = textSize(text, fontPx);
  const r = diameterPx / 2 + LABEL_OFFSET_PX;
  if (position === "bottom") return { x1: x - w / 2, y1: y + r, x2: x + w / 2, y2: y + r + h };
  if (position === "top") return { x1: x - w / 2, y1: y - r - h, x2: x + w / 2, y2: y - r };
  if (position === "right") return { x1: x + r, y1: y - h / 2, x2: x + r + w, y2: y + h / 2 };
  return { x1: x - r - w, y1: y - h / 2, x2: x - r, y2: y + h / 2 };
}

/** Las cuatro cajas candidatas de una barra, en el orden de `LABEL_POSITIONS`. */
export function busLabelBoxes(x: number, y: number, diameterPx: number, text: string, fontPx = BUS_FONT_PX): Box[] {
  return LABEL_POSITIONS.map((pos) => busLabelBox(x, y, diameterPx, text, pos, fontPx));
}

/**
 * Caja de la etiqueta de una rama, girada sobre la rama: se usa la caja alineada a los ejes que
 * la contiene. Devuelve `null` si la rama es demasiado corta en pantalla para que quepa.
 */
export function branchLabelBox(
  a: { x: number; y: number; d: number },
  b: { x: number; y: number; d: number },
  mid: { x: number; y: number },
  text: string,
  fontPx = BRANCH_FONT_PX,
): Box | null {
  const { w, h } = textSize(text, fontPx);
  const length = Math.hypot(b.x - a.x, b.y - a.y);
  if (length < w + (a.d + b.d) / 2 + 8) return null;
  const angle = Math.atan2(b.y - a.y, b.x - a.x);
  const c = Math.abs(Math.cos(angle));
  const s = Math.abs(Math.sin(angle));
  const bw = w * c + h * s;
  const bh = w * s + h * c;
  return { x1: mid.x - bw / 2, y1: mid.y - bh / 2, x2: mid.x + bw / 2, y2: mid.y + bh / 2 };
}

export interface LabelCandidate {
  id: string;
  /** Cajas posibles en orden de preferencia; se usa la primera que quepa. */
  boxes: Box[];
  /** Mayor primero: barras seleccionadas, fuera de límite, de mayor tensión o con más potencia. */
  priority: number;
  /** Se muestra siempre (la barra seleccionada), aunque se solape. */
  force?: boolean;
}

export interface Obstacle {
  /** Elemento dueño: una etiqueta no choca con el disco de su propia barra. */
  owner: string;
  box: Box;
}

/** Índice espacial por celdas para no comparar cada caja con todas las demás. */
class Grid<T extends { box: Box }> {
  private readonly cells = new Map<string, T[]>();
  constructor(private readonly size = 64) {}
  private keys(b: Box): string[] {
    const out: string[] = [];
    for (let i = Math.floor(b.x1 / this.size); i <= Math.floor(b.x2 / this.size); i++)
      for (let j = Math.floor(b.y1 / this.size); j <= Math.floor(b.y2 / this.size); j++) out.push(`${i},${j}`);
    return out;
  }
  add(item: T): void {
    for (const k of this.keys(item.box)) {
      const cell = this.cells.get(k);
      if (cell) cell.push(item);
      else this.cells.set(k, [item]);
    }
  }
  /** ¿Alguna caja guardada que cumpla `keep` se solapa con `b`? */
  hits(b: Box, keep: (item: T) => boolean = () => true): boolean {
    return this.keys(b).some((k) => (this.cells.get(k) ?? []).some((o) => keep(o) && overlaps(o.box, b)));
  }
}

function pad(b: Box, p: number): Box {
  return { x1: b.x1 - p, y1: b.y1 - p, x2: b.x2 + p, y2: b.y2 + p };
}

/**
 * Elige qué etiquetas mostrar sin que se solapen entre sí ni tapen discos de otras barras:
 * de mayor a menor prioridad, cada etiqueta toma la primera de sus posiciones que quepa, o se
 * oculta. Las ocultas aparecen al acercar el zoom, al pasar el cursor o al seleccionar la barra.
 * Devuelve, por elemento mostrado, el índice de la posición elegida.
 */
export function placeLabels(candidates: readonly LabelCandidate[], obstacles: readonly Obstacle[], placed: Box[] = []): Map<string, number> {
  const accepted = new Grid<{ box: Box }>();
  for (const box of placed) accepted.add({ box });
  const discs = new Grid<Obstacle>();
  for (const o of obstacles) discs.add(o);
  const shown = new Map<string, number>();
  const order = [...candidates].sort((a, b) => Number(!!b.force) - Number(!!a.force) || b.priority - a.priority);
  for (const c of order) {
    const boxes = c.boxes.map((b) => pad(b, LABEL_GAP_PX / 2));
    let index = boxes.findIndex((box) => !accepted.hits(box) && !discs.hits(box, (o) => o.owner !== c.id));
    if (index < 0 && c.force) index = 0;
    const box = boxes[index];
    if (box) {
      shown.set(c.id, index);
      accepted.add({ box });
      placed.push(box);
    }
  }
  return shown;
}
