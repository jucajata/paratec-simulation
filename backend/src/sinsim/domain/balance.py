"""Balance del caso y cobertura del despacho (FR-024, SC-002, SC-003). Funciones puras."""

from __future__ import annotations

from sinsim.domain.entities import Balance


def compute_balance(
    *,
    p_scheduled_total_mw: float,
    p_located_mw: float,
    p_demand_mw: float,
    p_demand_unlocated_mw: float,
) -> Balance:
    """Calcula el balance del caso.

    Args:
        p_scheduled_total_mw: Suma de la potencia programada de los recursos con P > 0.
        p_located_mw: Parte de esa potencia que quedó asignada a generadores del modelo.
        p_demand_mw: Demanda asignada a barras del modelo (activa, con pérdidas PSTR).
        p_demand_unlocated_mw: Demanda de nodos sin barra asociable.

    Returns:
        `Balance` con cobertura en % y diferencia generación − demanda.
    """
    coverage = (p_located_mw / p_scheduled_total_mw * 100.0) if p_scheduled_total_mw > 0 else 0.0
    return Balance(
        p_scheduled_total_mw=p_scheduled_total_mw,
        p_located_mw=p_located_mw,
        p_unlocated_mw=p_scheduled_total_mw - p_located_mw,
        coverage_pct=coverage,
        p_demand_mw=p_demand_mw,
        p_demand_unlocated_mw=p_demand_unlocated_mw,
        difference_mw=p_located_mw - p_demand_mw,
    )
