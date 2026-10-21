import type { Run, Violation } from "../../api/types";
import { fmtNum } from "../../lib/format";

interface Props {
  run: Run;
}

const GROUPS: { kind: Violation["kind"]; title: string; testId: string }[] = [
  { kind: "tension_baja", title: "Barras con tensión por debajo del límite", testId: "violations-low" },
  { kind: "tension_alta", title: "Barras con tensión por encima del límite", testId: "violations-high" },
  { kind: "sobrecarga", title: "Líneas y transformadores con cargabilidad mayor al 100 %", testId: "violations-overload" },
];

function fmtValue(v: Violation): string {
  return v.unit === "pu" ? `${fmtNum(v.value, 3)} pu` : `${fmtNum(v.value, 1)} %`;
}
function fmtLimit(v: Violation): string {
  return v.unit === "pu" ? `${fmtNum(v.limit, 2)} pu` : `${fmtNum(v.limit, 0)} %`;
}
function fmtDeviation(v: Violation): string {
  return v.unit === "pu" ? `${fmtNum(v.deviation, 3)} pu` : `${fmtNum(v.deviation, 1)} puntos`;
}

/** Reporte de violaciones del resultado (FR-037): tres grupos ordenados por desviación. */
export function ViolationsReport({ run }: Props): JSX.Element | null {
  const violations = run.result?.summary.violations;
  if (!run.result) return null;
  if (violations === undefined) {
    return (
      <section className="violations card card--padded stack" data-testid="violations">
        <h2>Reporte de violaciones</h2>
        <p className="muted">Esta ejecución es anterior al reporte; vuelve a ejecutar el caso para obtenerlo.</p>
      </section>
    );
  }
  return (
    <section className="violations card card--padded stack" data-testid="violations">
      <h2>Reporte de violaciones</h2>
      <p className="muted small">Ordenadas de mayor a menor desviación respecto al límite aplicado; cada límite cita su fuente.</p>
      <div>
        {GROUPS.map((g) => {
          const rows = violations.filter((v) => v.kind === g.kind);
          return (
            <details className="section" key={g.kind} open={rows.length > 0}>
              <summary>
                {g.title} <span className={rows.length > 0 ? "count count--alert" : "count"}>{rows.length}</span>
              </summary>
              {rows.length === 0 ? (
                <p className="muted">Ninguna.</p>
              ) : (
                <div className="table-scroll">
                  <table data-testid={g.testId}>
                    <thead>
                      <tr>
                        <th>Elemento</th>
                        <th>Subárea</th>
                        <th className="num">Valor</th>
                        <th className="num">Límite</th>
                        <th className="num">Desviación</th>
                        <th>Fuente</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((v) => (
                        <tr key={v.element} className="violation">
                          <td>{v.element}</td>
                          <td>{v.subarea ?? (g.kind === "sobrecarga" ? "entre subáreas" : "sin subárea")}</td>
                          <td className="num">
                            <strong>{fmtValue(v)}</strong>
                          </td>
                          <td className="num">{fmtLimit(v)}</td>
                          <td className="num">{fmtDeviation(v)}</td>
                          <td>{v.source}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </details>
          );
        })}
      </div>
    </section>
  );
}
