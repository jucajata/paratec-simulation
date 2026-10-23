import {
  ARROW_PX,
  MAX_GROWTH,
  arrowScale,
  branchLabelBox,
  busDiameterPx,
  busLabelBox,
  busLabelBoxes,
  placeLabels,
  ringRadius,
  screenGrowth,
  textSize,
} from "./declutter";

describe("declutter", () => {
  it("las barras crecen con el zoom, pero se detienen en un tope", () => {
    expect(screenGrowth(1)).toBeCloseTo(1, 6);
    expect(screenGrowth(4)).toBeGreaterThan(screenGrowth(2));
    expect(screenGrowth(50)).toBe(MAX_GROWTH);
    expect(busDiameterPx(500, 200)).toBeCloseTo(busDiameterPx(500, 50), 6);
    expect(busDiameterPx(500, 1)).toBeGreaterThan(busDiameterPx(115, 1));
  });

  it("la flecha mide lo mismo en pantalla con cualquier zoom", () => {
    for (const zoom of [0.5, 3, 20, 80]) {
      const width = 1.5 / zoom; // ancho de modelo de una línea fina
      const base = Math.max(Math.pow(width * 13.37, 0.9), 29);
      expect(base * arrowScale(width, zoom) * zoom).toBeCloseTo(ARROW_PX, 6);
    }
  });

  it("reparte las barras de una subestación sin que se toquen, con topes", () => {
    const zoom = 5;
    const d = 30;
    const r = ringRadius(3, d, zoom, 3, 50);
    const chord = 2 * r * zoom * Math.sin(Math.PI / 3);
    expect(chord).toBeGreaterThanOrEqual(d);
    expect(ringRadius(1, d, zoom, 3, 50)).toBe(0);
    expect(ringRadius(2, d, 0.1, 3, 12)).toBe(12);
    expect(ringRadius(2, d, 1000, 3, 12)).toBe(3);
  });

  it("mide el texto por su línea más larga y su número de líneas", () => {
    const one = textSize("SABANALARGA|500", 10);
    const two = textSize("SABANALARGA|500\nC 6.4 MW", 10);
    expect(two.w).toBeCloseTo(one.w, 6);
    expect(two.h).toBeGreaterThan(one.h);
  });

  it("muestra primero la etiqueta más importante y oculta la que no cabe en ninguna posición", () => {
    const a = busLabelBox(100, 100, 20, "SABANALARGA|500");
    const b = busLabelBox(104, 102, 12, "SABANALARGA|230");
    const far = busLabelBox(400, 100, 12, "TERNERA|230");
    const shown = placeLabels(
      [
        { id: "B", boxes: [b], priority: 230 },
        { id: "A", boxes: [a], priority: 500 },
        { id: "F", boxes: [far], priority: 230 },
      ],
      [],
    );
    expect([...shown.keys()].sort()).toEqual(["A", "F"]);
  });

  it("si la posición de abajo está ocupada, prueba encima, a la derecha y a la izquierda", () => {
    const top = placeLabels([{ id: "A", boxes: busLabelBoxes(100, 100, 20, "BARANOA|115"), priority: 1 }], [
      { owner: "X", box: { x1: 60, y1: 112, x2: 140, y2: 140 } },
    ]);
    expect(top.get("A")).toBe(1);
    const left = placeLabels([{ id: "A", boxes: busLabelBoxes(100, 100, 20, "BARANOA|115"), priority: 1 }], [
      { owner: "X", box: { x1: 60, y1: 60, x2: 160, y2: 88 } },
      { owner: "Y", box: { x1: 60, y1: 112, x2: 160, y2: 140 } },
      { owner: "Z", box: { x1: 112, y1: 90, x2: 200, y2: 110 } },
    ]);
    expect(left.get("A")).toBe(3);
  });

  it("una etiqueta no tapa el disco de otra barra, pero sí puede rozar el suyo", () => {
    const label = busLabelBox(100, 100, 20, "BARANOA|115");
    const ownDisc = { x1: 90, y1: 90, x2: 110, y2: 110 };
    const otherDisc = { x1: label.x1 + 2, y1: label.y1 + 2, x2: label.x1 + 12, y2: label.y1 + 12 };
    expect(placeLabels([{ id: "A", boxes: [label], priority: 1 }], [{ owner: "A", box: ownDisc }]).has("A")).toBe(true);
    expect(placeLabels([{ id: "A", boxes: [label], priority: 1 }], [{ owner: "B", box: otherDisc }]).has("A")).toBe(false);
  });

  it("la barra seleccionada siempre muestra su etiqueta", () => {
    const a = busLabelBox(100, 100, 20, "A|500");
    const shown = placeLabels(
      [
        { id: "A", boxes: [a], priority: 500 },
        { id: "SEL", boxes: [a], priority: 0, force: true },
      ],
      [],
    );
    expect(shown.has("SEL")).toBe(true);
  });

  it("no rotula una rama demasiado corta en pantalla", () => {
    const text = "41.4 MW · 31.2 Mvar · 54 %";
    const near = branchLabelBox({ x: 0, y: 0, d: 20 }, { x: 60, y: 0, d: 20 }, { x: 30, y: 0 }, text);
    const long = branchLabelBox({ x: 0, y: 0, d: 20 }, { x: 400, y: 0, d: 20 }, { x: 200, y: 0 }, text);
    expect(near).toBeNull();
    expect(long).not.toBeNull();
  });
});
