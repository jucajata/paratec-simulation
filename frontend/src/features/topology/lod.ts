/** Nivel de detalle de la topología según el zoom (FR-036). Funciones puras. */

/** Por debajo de este zoom solo se dibuja el STN; el STR aparece al acercarse. */
export const STR_ZOOM = 1.6;
/** Tensión mínima del STN (kV); coincide con `level = STN` de PARATEC. */
export const STN_MIN_KV = 220;

/** Una barra se dibuja si es del STN o si el zoom ya permite ver el STR. */
export function busVisible(vn_kv: number, zoom: number): boolean {
  return vn_kv >= STN_MIN_KV || zoom >= STR_ZOOM;
}
