"""Reporte de violaciones de un resultado convergido (FR-037). Funciones puras."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sinsim.domain.entities import BranchResult, BusResult, Violation
from sinsim.domain.limits import LoadingLimit, VoltageBand, band_for


def violations_report(
    buses: Iterable[BusResult],
    branches: Iterable[BranchResult],
    bands: Sequence[VoltageBand],
    loading: LoadingLimit,
) -> list[Violation]:
    """Barras bajo y sobre tensión y ramas sobrecargadas, por grupo y desviación descendente.

    La desviación es la distancia al límite violado (pu para tensión, puntos de % para
    cargabilidad). Cada violación lleva el límite aplicado y su fuente (constitución III.9).
    """
    low: list[Violation] = []
    high: list[Violation] = []
    over: list[Violation] = []
    for b in buses:
        if b.violation is None:
            continue
        band = band_for(b.vn_kv, bands)
        if band is None:
            continue
        if b.violation == "low":
            low.append(
                Violation(
                    kind="tension_baja",
                    element=b.bus_id,
                    subarea=b.subarea,
                    value=b.vm_pu,
                    limit=band.vm_min_pu,
                    deviation=band.vm_min_pu - b.vm_pu,
                    unit="pu",
                    source=band.source,
                )
            )
        else:
            high.append(
                Violation(
                    kind="tension_alta",
                    element=b.bus_id,
                    subarea=b.subarea,
                    value=b.vm_pu,
                    limit=band.vm_max_pu,
                    deviation=b.vm_pu - band.vm_max_pu,
                    unit="pu",
                    source=band.source,
                )
            )
    for br in branches:
        if not br.overload:
            continue
        over.append(
            Violation(
                kind="sobrecarga",
                element=br.element_id,
                subarea=br.subarea_from if br.subarea_from == br.subarea_to else None,
                value=br.loading_percent,
                limit=loading.max_percent,
                deviation=br.loading_percent - loading.max_percent,
                unit="%",
                source=loading.source,
            )
        )
    by_deviation = lambda v: (-v.deviation, v.element)  # noqa: E731 - clave de orden local
    return (
        sorted(low, key=by_deviation)
        + sorted(high, key=by_deviation)
        + sorted(over, key=by_deviation)
    )
