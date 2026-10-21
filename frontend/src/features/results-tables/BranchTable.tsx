import type { BranchResult } from "../../api/types";
import { fmtMvar, fmtMw, fmtNum } from "../../lib/format";

/** "A" si los dos extremos están en la misma subárea; "A → B" si es una rama de frontera. */
function subareaLabel(from: string | null | undefined, to: string | null | undefined): string {
  const a = from ?? "sin subárea";
  const b = to ?? "sin subárea";
  return a === b ? a : `${a} → ${b}`;
}

/** Tabla de líneas o transformadores; las sobrecargas llevan la clase `overload` (FR-031). */
export function BranchTable({ rows }: { rows: BranchResult[] }): JSX.Element {
  return (
    <table data-testid="table-branches">
      <thead>
        <tr>
          <th>Elemento</th>
          <th>Desde</th>
          <th>Hacia</th>
          <th>Subárea</th>
          <th className="num">P desde</th>
          <th className="num">Q desde</th>
          <th className="num">I (kA)</th>
          <th className="num">Cargabilidad</th>
          <th className="num">Pérdidas</th>
          <th>Estado</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((b) => (
          <tr key={b.element_id} className={b.overload ? "violation overload" : ""}>
            <td>{b.element_id}</td>
            <td>{b.from_bus}</td>
            <td>{b.to_bus}</td>
            <td>{subareaLabel(b.subarea_from, b.subarea_to)}</td>
            <td className="num">{fmtMw(b.p_from_mw)}</td>
            <td className="num">{fmtMvar(b.q_from_mvar)}</td>
            <td className="num">{fmtNum(b.i_ka, 3)}</td>
            <td className="num">{b.overload ? <strong>{fmtNum(b.loading_percent, 1)} %</strong> : `${fmtNum(b.loading_percent, 1)} %`}</td>
            <td className="num">{fmtMw(b.pl_mw)}</td>
            <td>{b.overload && <span className="chip chip--error chip--outline">Sobrecarga</span>}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
