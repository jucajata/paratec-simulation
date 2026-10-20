"""Validación física antes de simular (constitución V, tercer punto de validación).

Comprobaciones estructurales sobre las tablas que entran al modelo. No se inventa ningún rango
numérico (R-13): solo se detectan valores físicamente imposibles o inconsistentes.

- Bloqueantes (impiden la ejecución, `PHYSICAL_CHECK_FAILED`): tensiones nominales,
  capacidades, longitudes o reactancias no positivas; resistencias negativas; impedancias de
  cortocircuito no positivas; límites de reactiva invertidos; cargas con P negativa; barras sin
  nivel de tensión.
- No bloqueantes (se reportan como hallazgos): generación programada por encima de la
  capacidad declarada en PARATEC, que puede deberse a unidades no publicadas y no es un error
  del modelo.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class PhysicalIssue:
    """Hallazgo de la validación física."""

    element: str
    kind: str
    check: str
    value: float | None
    blocking: bool

    def describe(self) -> str:
        """Texto para el reporte de calidad."""
        level = "bloqueante" if self.blocking else "aviso"
        return f"[{level}] {self.kind} {self.element}: {self.check} (valor: {self.value})"


def _issues(
    df: pd.DataFrame, id_col: str, kind: str, column: str, predicate_bad: str, blocking: bool
) -> list[PhysicalIssue]:
    """Genera hallazgos para las filas donde `column` cumple la condición mala."""
    if df.empty or column not in df.columns:
        return []
    series = pd.to_numeric(df[column], errors="coerce")
    if predicate_bad == "<=0":
        mask = series <= 0
    elif predicate_bad == "<0":
        mask = series < 0
    else:
        mask = series.isna()
    return [
        PhysicalIssue(
            str(row[id_col]), kind, f"{column} {predicate_bad}", _num(row[column]), blocking
        )
        for _, row in df[mask.fillna(False)].iterrows()
    ]


def _num(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def check_model(
    buses: pd.DataFrame,
    lines: pd.DataFrame,
    trafos2w: pd.DataFrame,
    trafos3w: pd.DataFrame,
    generators: pd.DataFrame,
    loads: pd.DataFrame,
) -> list[PhysicalIssue]:
    """Ejecuta todas las comprobaciones sobre las tablas que entran al modelo.

    Args:
        buses: columnas `bus_id`, `vn_kv`.
        lines: `line_id`, `length_km`, `r_ohm_per_km`, `x_ohm_per_km`, `max_i_ka`.
        trafos2w: `trafo_id`, `sn_mva`, `vn_hv_kv`, `vn_lv_kv`, `vk_percent`.
        trafos3w: `trafo_id`, `sn_*_mva`, `vn_*_kv`, `vk_*_percent`.
        generators: `gen_id`, `p_mw`, `p_max_mw`, `min_q_mvar`, `max_q_mvar`.
        loads: `load_id`, `p_mw`.

    Returns:
        Lista de hallazgos; vacía si el modelo es físicamente consistente.
    """
    issues: list[PhysicalIssue] = []
    issues += _issues(buses, "bus_id", "barra", "vn_kv", "<=0", True)
    for col, bad in (
        ("length_km", "<=0"),
        ("x_ohm_per_km", "<=0"),
        ("r_ohm_per_km", "<0"),
        ("max_i_ka", "<=0"),
    ):
        issues += _issues(lines, "line_id", "línea", col, bad, True)
    for col in ("sn_mva", "vn_hv_kv", "vn_lv_kv", "vk_percent"):
        issues += _issues(trafos2w, "trafo_id", "transformador", col, "<=0", True)
    for col in (
        "sn_hv_mva",
        "sn_mv_mva",
        "sn_lv_mva",
        "vn_hv_kv",
        "vn_mv_kv",
        "vn_lv_kv",
        "vk_hv_percent",
        "vk_mv_percent",
        "vk_lv_percent",
    ):
        issues += _issues(trafos3w, "trafo_id", "transformador 3w", col, "<=0", True)
    issues += _issues(generators, "gen_id", "generador", "p_mw", "<0", True)
    issues += _issues(loads, "load_id", "carga", "p_mw", "<0", True)
    if not generators.empty and {"min_q_mvar", "max_q_mvar"} <= set(generators.columns):
        q = generators[["min_q_mvar", "max_q_mvar"]].apply(pd.to_numeric, errors="coerce")
        bad = (q.min_q_mvar > q.max_q_mvar).fillna(False)
        issues += [
            PhysicalIssue(
                str(r.gen_id), "generador", "min_q_mvar > max_q_mvar", _num(r.min_q_mvar), True
            )
            for _, r in generators[bad].iterrows()
        ]
    if not generators.empty and {"p_mw", "p_max_mw"} <= set(generators.columns):
        p = generators[["p_mw", "p_max_mw"]].apply(pd.to_numeric, errors="coerce")
        over = (p.p_mw > p.p_max_mw).fillna(False)
        issues += [
            PhysicalIssue(
                str(r.gen_id), "generador", "p_mw > p_max_mw (PARATEC)", _num(r.p_mw), False
            )
            for _, r in generators[over].iterrows()
        ]
    return issues


def blocking_issues(issues: list[PhysicalIssue]) -> list[PhysicalIssue]:
    """Solo los hallazgos que impiden simular."""
    return [i for i in issues if i.blocking]
