import type { GeneratorAssumption, StudyCase } from "../../api/types";
import { fmtMvar, fmtMw, fmtPct, fmtPu } from "../../lib/format";
import { Section } from "./Section";

interface Props {
  studyCase: StudyCase;
}

export function CaseQuality({ studyCase }: Props): JSX.Element {
  const q = studyCase.quality;
  const b = q.balance;
  const islandsOut = q.islands.slice(1);
  const lostGen = islandsOut.reduce((acc, i) => acc + i.p_gen_lost_mw, 0);
  const generators = Array.isArray(studyCase.assumptions.generadores)
    ? (studyCase.assumptions.generadores as GeneratorAssumption[])
    : [];
  return (
    <section className="quality" data-testid="case-quality">
      <h2>Reporte de calidad del caso</h2>
      <dl className="balance">
        <dt>Generación programada</dt>
        <dd>{fmtMw(b.p_scheduled_total_mw)}</dd>
        <dt>Generación ubicada</dt>
        <dd>
          {fmtMw(b.p_located_mw)} (<strong data-testid="coverage">{fmtPct(b.coverage_pct)}</strong> de cobertura)
        </dd>
        <dt>Generación no ubicada</dt>
        <dd>{fmtMw(b.p_unlocated_mw)}</dd>
        <dt>Demanda asignada</dt>
        <dd>{fmtMw(b.p_demand_mw)}</dd>
        <dt>Demanda no ubicada</dt>
        <dd>{fmtMw(b.p_demand_unlocated_mw)}</dd>
        <dt>Diferencia generación − demanda</dt>
        <dd>{fmtMw(b.difference_mw)}</dd>
      </dl>
      {studyCase.warnings.map((w) => (
        <p className="warning" key={w}>
          ⚠ {w}
        </p>
      ))}
      <Section title="Recursos del despacho no ubicados" count={q.unlocated_resources.length}>
        <table>
          <thead>
            <tr>
              <th>Recurso</th>
              <th>P programada</th>
              <th>Motivo</th>
            </tr>
          </thead>
          <tbody>
            {q.unlocated_resources.map((u) => (
              <tr key={u.resource}>
                <td>{u.resource}</td>
                <td>{fmtMw(u.p_mw)}</td>
                <td>{u.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
      <Section title="Nodos de demanda no ubicados" count={q.unlocated_demand.length}>
        <table>
          <thead>
            <tr>
              <th>Nodo</th>
              <th>kV</th>
              <th>P</th>
              <th>Motivo</th>
            </tr>
          </thead>
          <tbody>
            {q.unlocated_demand.map((u) => (
              <tr key={`${u.node}-${u.vn_kv}`}>
                <td>{u.node}</td>
                <td>{u.vn_kv}</td>
                <td>{fmtMw(u.p_mw)}</td>
                <td>{u.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
      <Section title="Traslados a la frontera STR/SDL" count={q.transfers.length}>
        <table>
          <thead>
            <tr>
              <th>Elemento</th>
              <th>Tipo</th>
              <th>Desde</th>
              <th>Hacia</th>
              <th>P</th>
            </tr>
          </thead>
          <tbody>
            {q.transfers.map((t) => (
              <tr key={`${t.kind}-${t.element}`}>
                <td>{t.element}</td>
                <td>{t.kind === "gen" ? "generación" : "demanda"}</td>
                <td>{t.from_bus}</td>
                <td>{t.to_bus}</td>
                <td>{fmtMw(t.p_mw)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
      <Section title="Elementos excluidos por parámetros faltantes" count={q.excluded.length}>
        <ul>
          {q.excluded.map((e) => (
            <li key={e.element}>
              {e.kind} {e.element}: faltan {e.missing_params.join(", ")}
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Parámetros imputados" count={q.imputed.length}>
        <ul>
          {q.imputed.map((i) => (
            <li key={`${i.element}-${i.param}`}>
              {i.kind} {i.element}: {i.param} = {i.value.toFixed(4)} ({i.method})
            </li>
          ))}
        </ul>
      </Section>
      <Section title="No modelados" count={q.not_modeled.length}>
        <ul>
          {q.not_modeled.map((n) => (
            <li key={n.element}>
              {n.kind} {n.element}: {n.reason}
            </li>
          ))}
        </ul>
      </Section>
      <Section title={`Islas (${lostGen.toFixed(1)} MW de generación fuera)`} count={q.islands.length}>
        <ul>
          {q.islands.map((i) => (
            <li key={i.island_id}>
              {i.energized ? "Energizada" : "Fuera de servicio"}: {i.n_buses} barras
              {!i.energized && ` — ${fmtMw(i.p_gen_lost_mw)} de generación y ${fmtMw(i.p_demand_lost_mw)} de demanda fuera`}
              {!i.energized && i.buses.length <= 6 && ` (${i.buses.join(", ")})`}
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Avisos de validación física" count={q.physical_issues.length}>
        <ul>
          {q.physical_issues.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      </Section>
      <Section title="Supuestos por generador (consigna y reactiva)" count={generators.length}>
        <table data-testid="generator-assumptions">
          <thead>
            <tr>
              <th>Generador</th>
              <th>Barra</th>
              <th>Consigna</th>
              <th>Q mín</th>
              <th>Q máx</th>
              <th>Fuente de Q</th>
            </tr>
          </thead>
          <tbody>
            {generators.map((g) => (
              <tr key={g.gen_id}>
                <td>{g.gen_id}</td>
                <td>{g.barra}</td>
                <td title={g.fuente_vm}>{fmtPu(g.vm_pu)}</td>
                <td>{g.q_min_mvar === null ? "—" : fmtMvar(g.q_min_mvar)}</td>
                <td>{g.q_max_mvar === null ? "—" : fmtMvar(g.q_max_mvar)}</td>
                <td>{g.fuente_q}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
      <details className="section">
        <summary>Supuestos del caso</summary>
        <pre>{JSON.stringify(studyCase.assumptions, null, 2)}</pre>
      </details>
    </section>
  );
}
