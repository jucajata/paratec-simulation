import type { GeneratorResult } from "../../api/types";
import { fmtMvar, fmtMw } from "../../lib/format";

/** Tabla de generadores con su P programada, P y Q resultantes y el ajuste de la referencia. */
export function GenTable({
  rows,
  subareaOfBus,
}: {
  rows: GeneratorResult[];
  subareaOfBus: ReadonlyMap<string, string | null>;
}): JSX.Element {
  return (
    <table data-testid="table-generators">
      <thead>
        <tr>
          <th>Generador</th>
          <th>Barra</th>
          <th>Subárea</th>
          <th className="num">P programada</th>
          <th className="num">P</th>
          <th className="num">Q</th>
          <th className="num">Ajuste referencia</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((g) => (
          <tr key={g.gen_id}>
            <td>{g.gen_id}</td>
            <td>{g.bus}</td>
            <td>{subareaOfBus.get(g.bus) ?? "sin subárea"}</td>
            <td className="num">{fmtMw(g.p_scheduled_mw)}</td>
            <td className="num">{fmtMw(g.p_mw)}</td>
            <td className="num">{fmtMvar(g.q_mvar)}</td>
            <td className="num">{fmtMw(g.slack_adjust_mw)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
