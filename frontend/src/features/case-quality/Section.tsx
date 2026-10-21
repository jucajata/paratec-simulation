import type { ReactNode } from "react";

interface Props {
  title: string;
  count: number;
  /** Con `alert` (por defecto) un conteo mayor que cero se resalta como problema. */
  alert?: boolean;
  children: ReactNode;
}

/** Bloque plegable del reporte de calidad con el conteo de elementos en el título. */
export function Section({ title, count, alert = true, children }: Props): JSX.Element {
  return (
    <details className="section">
      <summary>
        {title} <span className={alert && count > 0 ? "count count--alert" : "count"}>{count}</span>
      </summary>
      {count === 0 ? <p className="muted">Ninguno.</p> : children}
    </details>
  );
}
