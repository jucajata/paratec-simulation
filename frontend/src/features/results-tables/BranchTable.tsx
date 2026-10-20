import type { BranchResult } from "../../api/types";
import { fmtMvar, fmtMw, fmtNum } from "../../lib/format";

/** Tabla de líneas o transformadores; las sobrecargas llevan la clase `overload` (FR-031). */
export function BranchTable({ rows }: { rows: BranchResult[] }): JSX.Element {
  return (
    <table data-testid="table-branches">
      <thead>
        <tr>
          <th>Elemento</th>
          <th>Desde</th>
          <th>Hacia</th>
          <th>P desde</th>
          <th>Q desde</th>
          <th>I (kA)</th>
          <th>Cargabilidad</th>
          <th>Pérdidas</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((b) => (
          <tr key={b.element_id} className={b.overload ? "violation overload" : ""}>
            <td>{b.element_id}</td>
            <td>{b.from_bus}</td>
            <td>{b.to_bus}</td>
            <td>{fmtMw(b.p_from_mw)}</td>
            <td>{fmtMvar(b.q_from_mvar)}</td>
            <td>{fmtNum(b.i_ka, 3)}</td>
            <td>{fmtNum(b.loading_percent, 1)} %</td>
            <td>{fmtMw(b.pl_mw)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
