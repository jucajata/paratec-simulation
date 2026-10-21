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
          <th className="num">Vn</th>
          <th className="num">V (pu)</th>
          <th className="num">V (kV)</th>
          <th className="num">Ángulo (°)</th>
          <th>Estado</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((b) => (
          <tr key={b.bus_id} className={b.violation ? `violation ${b.violation}` : ""}>
            <td>{b.bus_id}</td>
            <td>{b.subarea ?? "sin subárea"}</td>
            <td className="num">{fmtKv(b.vn_kv)}</td>
            <td className="num">{b.violation ? <strong>{fmtPu(b.vm_pu)}</strong> : fmtPu(b.vm_pu)}</td>
            <td className="num">{fmtKv(b.vm_kv)}</td>
            <td className="num">{fmtNum(b.va_degree, 2)}</td>
            <td>
              {b.violation && (
                <span className="chip chip--error chip--outline">{b.violation === "low" ? "Tensión baja" : "Tensión alta"}</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
