const mw = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const pu = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 3, minimumFractionDigits: 3 });
const pct = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 1, minimumFractionDigits: 1 });

export const fmtMw = (v: number): string => `${mw.format(v)} MW`;
export const fmtMvar = (v: number): string => `${mw.format(v)} Mvar`;
export const fmtKv = (v: number): string => `${mw.format(v)} kV`;
export const fmtPu = (v: number): string => `${pu.format(v)} pu`;
export const fmtPct = (v: number): string => `${pct.format(v)} %`;
export const fmtNum = (v: number, digits = 1): string =>
  new Intl.NumberFormat("es-CO", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(v);
