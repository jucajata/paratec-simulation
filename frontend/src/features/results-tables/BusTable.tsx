import type { BusResult } from "../../api/types";
import { fmtKv, fmtNum, fmtPu } from "../../lib/format";

/** Tabla de barras; las filas fuera de límite llevan la clase `violation` (FR-031). */
export function BusTable({ rows }: { rows: BusResult[] }): JSX.Element {
  return (
    <table data-testid="table-buses">
      <thead>
        <tr>
          <th>Barra</th>
          <th>Subárea</th>
          <th>Vn</th>
          <th>V (pu)</th>
          <th>V (kV)</th>
          <th>Ángulo (°)</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((b) => (
          <tr key={b.bus_id} className={b.violation ? `violation ${b.violation}` : ""}>
            <td>{b.bus_id}</td>
            <td>{b.subarea ?? "sin subárea"}</td>
            <td>{fmtKv(b.vn_kv)}</td>
            <td>{fmtPu(b.vm_pu)}</td>
            <td>{fmtKv(b.vm_kv)}</td>
            <td>{fmtNum(b.va_degree, 2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
