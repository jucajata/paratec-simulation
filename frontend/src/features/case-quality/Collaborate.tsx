import { useRef, useState } from "react";

import type { QualityReport } from "../../api/types";
import { PARATEC_URL, REPO_URL, pendingText } from "./pending";

interface Props {
  quality: QualityReport;
}

/**
 * Aviso de colaboración (FR-040): invita a afinar las tablas de equivalencias del repositorio y
 * explica el paso a paso en una ventana emergente.
 */
export function Collaborate({ quality }: Props): JSX.Element {
  const dialog = useRef<HTMLDialogElement>(null);
  const [copied, setCopied] = useState<"ok" | "error" | null>(null);
  const nResources = quality.unlocated_resources.length;
  const nNodes = quality.unlocated_demand.length;
  const pending = nResources + nNodes;

  async function copyPending(): Promise<void> {
    try {
      await navigator.clipboard.writeText(pendingText(quality));
      setCopied("ok");
    } catch {
      setCopied("error");
    }
  }

  return (
    <div className="collab" data-testid="collab">
      <p className="notice notice--info collab__banner">
        <span>
          {pending > 0 ? (
            <>
              Este caso tiene <strong data-testid="collab-pending">{nResources}</strong> recursos del despacho y{" "}
              <strong>{nNodes}</strong> nodos de demanda sin ubicar.{" "}
            </>
          ) : null}
          Puedes ayudar a afinar el modelo: las equivalencias entre el despacho, el pronóstico de demanda y PARATEC
          viven en el repositorio y cualquiera puede corregirlas.
        </span>
        <button type="button" onClick={() => dialog.current?.showModal()} data-testid="collab-open">
          Cómo colaborar
        </button>
      </p>
      <dialog ref={dialog} className="collab__dialog" data-testid="collab-dialog" aria-labelledby="collab-title">
        <form method="dialog" className="stack">
          <h3 id="collab-title">Cómo colaborar desde el repositorio</h3>
          <p className="muted">
            El flujo usa tres tablas CSV con vigencia en <code>data/equivalencias/</code>. Lo que no tiene fila queda
            "sin ubicar" y aparece en este reporte; nunca se completa en silencio. Cambiar una fila produce un caso
            distinto, así que cada aporte queda trazado.
          </p>
          <ol className="collab__steps">
            <li>
              <strong>Identifica qué falta.</strong> Revisa las secciones "Recursos del despacho no ubicados" y "Nodos
              de demanda no ubicados" de este reporte. Copia el nombre tal como aparece: es la clave del archivo de XM.
            </li>
            <li>
              <strong>Busca el elemento real en PARATEC.</strong> En{" "}
              <a href={PARATEC_URL} target="_blank" rel="noreferrer">
                paratec.xm.com.co
              </a>{" "}
              localiza la planta o unidad (para un recurso del despacho) o la subestación y su nivel de tensión (para
              un nodo de demanda). Los unifilares por subárea ayudan a confirmar la barra.
            </li>
            <li>
              <strong>Haz un fork y clona el repositorio.</strong>{" "}
              <a href={REPO_URL} target="_blank" rel="noreferrer">
                {REPO_URL.replace("https://", "")}
              </a>
              . Sigue el README para instalar <code>uv</code> y <code>pnpm</code>.
            </li>
            <li>
              <strong>Edita la tabla que corresponda</strong> en <code>data/equivalencias/</code>:
              <ul>
                <li>
                  <code>recursos_despacho.csv</code>: <code>resource</code>, <code>kind</code> (plant, unit o intl_link),{" "}
                  <code>paratec_ids</code> (varios separados por <code>;</code>), <code>connection_bus</code> (solo
                  intl_link), <code>valid_from</code>, <code>valid_to</code>, <code>note</code>.
                </li>
                <li>
                  <code>nodos_demanda.csv</code>: <code>node</code>, <code>ucp</code>, <code>vn_kv</code>,{" "}
                  <code>substation</code>, <code>paratec_vn_kv</code>, <code>valid_from</code>, <code>valid_to</code>,{" "}
                  <code>note</code>.
                </li>
                <li>
                  <code>subestaciones_alias.csv</code>: <code>alias</code>, <code>substation</code>,{" "}
                  <code>valid_from</code>, <code>valid_to</code>, <code>note</code>, cuando PARATEC nombra distinto una
                  misma subestación.
                </li>
              </ul>
              Reglas: fechas <code>AAAA-MM-DD</code>; una sola fila vigente por clave y fecha; en <code>note</code> cita
              la fuente (PARATEC, unifilar) y quita la marca "NO CURADA"; deja sin fila lo que no puedas confirmar. Nunca
              se inventan parámetros eléctricos.
            </li>
            <li>
              <strong>Comprueba.</strong> Ejecuta <code>make test</code> (valida las tablas: vigencias solapadas o
              campos inválidos fallan) y <code>make demo</code>; la cobertura de generación debe subir y no debe
              aparecer nada nuevo sin ubicar.
            </li>
            <li>
              <strong>Abre un pull request</strong> con el motivo y la fuente de cada fila cambiada. Si no puedes
              confirmar una equivalencia, abre un issue con lo que encontraste.
            </li>
          </ol>
          <div className="toolbar">
            {pending > 0 && (
              <button type="button" onClick={() => void copyPending()} data-testid="collab-copy">
                Copiar la lista de pendientes
              </button>
            )}
            {copied === "ok" && <span className="muted">Copiada al portapapeles.</span>}
            {copied === "error" && <span className="error">No se pudo copiar; selecciona las tablas del reporte.</span>}
            <button type="submit" data-testid="collab-close">
              Cerrar
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
