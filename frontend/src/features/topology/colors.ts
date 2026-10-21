/** Escalas de color de la vista de topología (separadas del componente por fast refresh). */

/** Color por tensión: azul (bajo) → verde (1 pu) → rojo (alto). Sin dato: gris. */
export function voltageColor(vm: number | null): string {
  if (vm === null) return "#9aa0a6";
  const x = Math.max(-1, Math.min(1, (vm - 1.0) / 0.1));
  if (x < 0) {
    const t = -x;
    return `rgb(${Math.round(46 - 46 * t)}, ${Math.round(160 - 60 * t)}, ${Math.round(67 + 160 * t)})`;
  }
  return `rgb(${Math.round(46 + 180 * x)}, ${Math.round(160 - 110 * x)}, ${Math.round(67 - 30 * x)})`;
}

/** Color por cargabilidad: verde (0 %) → amarillo (50 %) → rojo (≥ 100 %). Sin dato: gris. */
export function loadingColor(loading: number | null): string {
  if (loading === null) return "#9aa0a6";
  const x = Math.max(0, Math.min(1, loading / 100));
  const r = Math.round(x < 0.5 ? 60 + 380 * x : 250);
  const g = Math.round(x < 0.5 ? 170 : 170 - 300 * (x - 0.5));
  return `rgb(${r}, ${g}, 60)`;
}

/** Color por ángulo: azul (muy negativo) → gris (0°) → naranja (positivo); ±30° saturan. */
export function angleColor(va: number | null | undefined): string {
  if (typeof va !== "number") return "#9aa0a6";
  const x = Math.max(-1, Math.min(1, va / 30));
  if (x < 0) {
    const t = -x;
    return `rgb(${Math.round(120 - 90 * t)}, ${Math.round(130 - 60 * t)}, ${Math.round(140 + 100 * t)})`;
  }
  return `rgb(${Math.round(120 + 130 * x)}, ${Math.round(130 - 20 * x)}, ${Math.round(140 - 120 * x)})`;
}
