import type { BusDetailData } from "./busModel";
import { fmtKv, fmtMvar, fmtMw, fmtNum, fmtPu } from "../../lib/format";

interface Props {
  detail: BusDetailData;
  onClose: () => void;
}

/** Panel con tensión, generación, carga, ramas y balance de la barra seleccionada (FR-036). */
export function BusDetail({ detail, onClose }: Props): JSX.Element {
  const { node, generators, branches, balance_mw } = detail;
  const pGen = node.p_gen_mw ?? 0;
  const pLoad = node.p_load_mw ?? 0;
  const parts = node.p_load_act_mw !== null && node.p_load_act_mw !== undefined;
  return (
    <aside className="bus-detail" data-testid="bus-detail">
      <div className="toolbar">
        <div className="stack" style={{ gap: 2 }}>
          <strong>{node.label}</strong>
          <span className="muted small">
            {fmtKv(node.vn_kv)}
            {node.vm_pu !== null && ` · ${fmtPu(node.vm_pu)}`}
            {` · ${node.subarea ?? "sin subárea"}`}
          </span>
        </div>
        <button type="button" onClick={onClose} data-testid="bus-detail-close">
          Cerrar
        </button>
      </div>
      {node.violation && (
        <span className="chip chip--error chip--outline" style={{ alignSelf: "flex-start" }}>
          {node.violation === "low" ? "Tensión baja" : "Tensión alta"}
        </span>
      )}
      <dl className="balance">
        <dt>Generación</dt>
        <dd data-testid="bus-gen">
          {fmtMw(pGen)} · {fmtMvar(node.q_gen_mvar ?? 0)}
        </dd>
        <dt>Carga</dt>
        <dd data-testid="bus-load">
          {fmtMw(pLoad)} · {fmtMvar(node.q_load_mvar ?? 0)}
          {parts && ` (Ener.Act. ${fmtMw(node.p_load_act_mw ?? 0)} + Perd.PSTR ${fmtMw(node.p_load_pstr_mw ?? 0)})`}
        </dd>
        <dt>Balance</dt>
        <dd data-testid="bus-balance">
          {balance_mw === null ? "sin flujos" : `${fmtMw(balance_mw)} (generación − carga − flujos salientes)`}
        </dd>
      </dl>
      {generators.length > 0 && (
        <div className="table-scroll">
          <table data-testid="bus-generators">
            <thead>
              <tr>
                <th>Generador</th>
                <th className="num">P programada</th>
                <th className="num">P</th>
                <th className="num">Q</th>
              </tr>
            </thead>
            <tbody>
              {generators.map((g) => (
                <tr key={g.gen_id}>
                  <td>{g.gen_id}</td>
                  <td className="num">{fmtMw(g.p_scheduled_mw)}</td>
                  <td className="num">{fmtMw(g.p_mw)}</td>
                  <td className="num">{fmtMvar(g.q_mvar)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="table-scroll">
        <table data-testid="bus-branches">
          <thead>
            <tr>
              <th>Rama</th>
              <th>Hacia</th>
              <th className="num">P sale</th>
              <th className="num">Q sale</th>
              <th className="num">Cargabilidad</th>
              <th className="num">Pérdidas</th>
            </tr>
          </thead>
          <tbody>
            {branches.map((b) => (
              <tr key={b.id} className={b.overload ? "violation overload" : ""}>
                <td>{b.id}</td>
                <td>{b.other}</td>
                <td className="num">{b.p_out_mw === null ? "—" : `${b.p_out_mw >= 0 ? "→" : "←"} ${fmtMw(Math.abs(b.p_out_mw))}`}</td>
                <td className="num">{b.q_out_mvar === null ? "—" : fmtMvar(b.q_out_mvar)}</td>
                <td className="num">
                  {b.loading_percent === null ? "—" : b.overload ? <strong>{fmtNum(b.loading_percent, 1)} %</strong> : `${fmtNum(b.loading_percent, 1)} %`}
                </td>
                <td className="num">{b.pl_mw === null ? "—" : `${fmtMw(b.pl_mw)} · ${fmtMvar(b.ql_mvar ?? 0)}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">Flecha hacia la derecha: la potencia sale de esta barra; hacia la izquierda: entra.</p>
    </aside>
  );
}
