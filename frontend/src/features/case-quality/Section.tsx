import type { ReactNode } from "react";

interface Props {
  title: string;
  count: number;
  children: ReactNode;
}

/** Bloque plegable del reporte de calidad con el conteo de elementos en el título. */
export function Section({ title, count, children }: Props): JSX.Element {
  return (
    <details className="section">
      <summary>
        {title} <span className="count">{count}</span>
      </summary>
      {count === 0 ? <p className="muted">Ninguno.</p> : children}
    </details>
  );
}
