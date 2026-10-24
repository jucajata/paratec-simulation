"""Criterio de empeoramiento y orden de los listados N-1 (FR-052 a FR-057, spec 003).

Funciones puras sobre valores ya extraídos de los flujos: no importan pandapower ni hacen E/S
(constitución IV). Una contingencia solo cuenta por lo que empeora frente al caso base; las
violaciones que ya existían no suman criticidad. No hay umbral mínimo (decisión del usuario del
2026-10-24).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from sinsim.domain.entities import (
    Diagnostics,
    Isolation,
    IsolationRow,
    LoadingRow,
    N1Summary,
    Outage,
    UnsolvedRow,
    VoltageRow,
)
from sinsim.domain.limits import LoadingLimit, VoltageBand, band_for


@dataclass(frozen=True)
class FlowState:
    """Valores de un flujo convergido, por nombre de elemento y de barra.

    Los elementos fuera de servicio y las barras aisladas no aparecen: no tienen resultado.
    """

    loading: Mapping[str, float]
    """`element_id` → cargabilidad (%) de líneas y transformadores."""
    vm_pu: Mapping[str, float]
    """`bus_id` → tensión en pu del nominal de PARATEC."""
    vn_kv: Mapping[str, float]
    """`bus_id` → tensión nominal (kV), para elegir la banda."""


@dataclass(frozen=True)
class WorstBus:
    """La barra más alejada de su banda entre las que cuentan."""

    bus_id: str
    vm_base_pu: float
    vm_pu: float
    deviation_pu: float


@dataclass(frozen=True)
class Evaluation:
    """Resultado de comparar una contingencia con el caso base (FR-052)."""

    worst_branch: tuple[str, float, float] | None
    """`(element_id, cargabilidad base, cargabilidad con la contingencia)`."""
    n_branches: int
    worst_bus: WorstBus | None
    n_buses: int


@dataclass(frozen=True)
class ContingencyResult:
    """Lo que el servicio sabe de una contingencia antes de armar los listados."""

    outage: Outage
    evaluation: Evaluation | None
    """`None` si el flujo no convergió."""
    isolation: Isolation | None = None
    diagnostics: Diagnostics | None = None

    @property
    def converged(self) -> bool:
        """Convergió si hay evaluación."""
        return self.evaluation is not None


# --- FR-052 ---------------------------------------------------------------------------


def branch_counts(base: float, after: float, limit: LoadingLimit) -> bool:
    """Cuenta si con la contingencia supera el límite y está más cargada que en el caso base."""
    return after > limit.max_percent and after > base


def bus_distance(vm_pu: float, band: VoltageBand) -> float:
    """Distancia a la banda con signo: 0 dentro, negativa por debajo, positiva por encima."""
    if vm_pu < band.vm_min_pu:
        return vm_pu - band.vm_min_pu
    if vm_pu > band.vm_max_pu:
        return vm_pu - band.vm_max_pu
    return 0.0


def bus_counts(base_vm: float, after_vm: float, band: VoltageBand | None) -> bool:
    """Cuenta si queda fuera de banda y más lejos de ella (en valor absoluto) que en el base.

    Una barra sin banda configurada nunca cuenta, como en el reporte de violaciones (FR-037).
    """
    if band is None:
        return False
    after = bus_distance(after_vm, band)
    return after != 0.0 and abs(after) > abs(bus_distance(base_vm, band))


def evaluate(
    base: FlowState,
    after: FlowState,
    bands: Sequence[VoltageBand],
    loading: LoadingLimit,
) -> Evaluation:
    """Compara una contingencia convergida con el caso base.

    Solo se miran los elementos y barras presentes en `after`: el activo que sale y las barras
    aisladas no tienen resultado y por eso no cuentan (FR-052). El peor valor se elige entre los
    que cuentan; en empate, por nombre.
    """
    worst_branch: tuple[str, float, float] | None = None
    n_branches = 0
    for element_id in sorted(after.loading):
        if element_id not in base.loading:
            continue
        b, a = base.loading[element_id], after.loading[element_id]
        if not branch_counts(b, a, loading):
            continue
        n_branches += 1
        if worst_branch is None or a > worst_branch[2]:
            worst_branch = (element_id, b, a)

    worst_bus: WorstBus | None = None
    n_buses = 0
    for bus_id in sorted(after.vm_pu):
        if bus_id not in base.vm_pu or bus_id not in base.vn_kv:
            continue
        band = band_for(base.vn_kv[bus_id], bands)
        b, a = base.vm_pu[bus_id], after.vm_pu[bus_id]
        if not bus_counts(b, a, band):
            continue
        assert band is not None  # bus_counts ya lo garantiza
        n_buses += 1
        deviation = bus_distance(a, band)
        if worst_bus is None or abs(deviation) > abs(worst_bus.deviation_pu):
            worst_bus = WorstBus(bus_id=bus_id, vm_base_pu=b, vm_pu=a, deviation_pu=deviation)
    return Evaluation(
        worst_branch=worst_branch, n_branches=n_branches, worst_bus=worst_bus, n_buses=n_buses
    )


# --- Listados (FR-053 a FR-056) --------------------------------------------------------------


def rank_loading(results: Iterable[ContingencyResult]) -> list[LoadingRow]:
    """Listado de cargabilidad: mayor cargabilidad primero; empate por nombre del activo."""
    hits = [r for r in results if r.evaluation is not None and r.evaluation.worst_branch]
    hits.sort(key=lambda r: (-_branch(r)[2], r.outage.element_id))
    return [
        LoadingRow(
            rank=i,
            outage=r.outage,
            element_id=_branch(r)[0],
            loading_base_percent=_branch(r)[1],
            loading_percent=_branch(r)[2],
            n_elements=_eval(r).n_branches,
            isolation=r.isolation,
        )
        for i, r in enumerate(hits, start=1)
    ]


def rank_voltage(results: Iterable[ContingencyResult]) -> list[VoltageRow]:
    """Listado de tensiones: mayor distancia fuera de banda (valor absoluto) primero."""
    hits = [r for r in results if r.evaluation is not None and r.evaluation.worst_bus]
    hits.sort(key=lambda r: (-abs(_bus(r).deviation_pu), r.outage.element_id))
    return [
        VoltageRow(
            rank=i,
            outage=r.outage,
            bus_id=_bus(r).bus_id,
            vm_base_pu=_bus(r).vm_base_pu,
            vm_pu=_bus(r).vm_pu,
            deviation_pu=_bus(r).deviation_pu,
            n_buses=_eval(r).n_buses,
            isolation=r.isolation,
        )
        for i, r in enumerate(hits, start=1)
    ]


def rank_isolation(results: Iterable[ContingencyResult]) -> list[IsolationRow]:
    """Bloque «Aíslan demanda»: convergidas con demanda sin servicio, por MW descendente."""
    hits = [
        r
        for r in results
        if r.converged and r.isolation is not None and r.isolation.p_demand_lost_mw > 0
    ]
    hits.sort(key=lambda r: (-_iso(r).p_demand_lost_mw, r.outage.element_id))
    return [
        IsolationRow(
            rank=i,
            outage=r.outage,
            n_buses=_iso(r).n_buses,
            p_demand_lost_mw=_iso(r).p_demand_lost_mw,
        )
        for i, r in enumerate(hits, start=1)
    ]


def unsolved_rows(results: Iterable[ContingencyResult]) -> list[UnsolvedRow]:
    """Bloque «Sin solución»: no convergidas con su diagnóstico, por nombre del activo."""
    hits = [r for r in results if not r.converged and r.diagnostics is not None]
    hits.sort(key=lambda r: r.outage.element_id)
    return [UnsolvedRow(outage=r.outage, diagnostics=_diag(r)) for r in hits]


def summarize(results: Sequence[ContingencyResult], *, duration_s: float) -> N1Summary:
    """Resumen (FR-057). Invariante SC-017: convergidas = en algún grupo + sin impacto."""
    loading = rank_loading(results)
    voltage = rank_voltage(results)
    isolation = rank_isolation(results)
    unsolved = unsolved_rows(results)
    with_impact = (
        {r.outage.element_id for r in loading}
        | {r.outage.element_id for r in voltage}
        | {r.outage.element_id for r in isolation}
    )
    n_converged = sum(1 for r in results if r.converged)
    return N1Summary(
        n_total=len(results),
        n_loading=len(loading),
        n_voltage=len(voltage),
        n_isolation=len(isolation),
        n_unsolved=len(unsolved),
        n_no_impact=n_converged - len(with_impact),
        duration_s=duration_s,
    )


def _eval(r: ContingencyResult) -> Evaluation:
    assert r.evaluation is not None
    return r.evaluation


def _branch(r: ContingencyResult) -> tuple[str, float, float]:
    wb = _eval(r).worst_branch
    assert wb is not None
    return wb


def _bus(r: ContingencyResult) -> WorstBus:
    wb = _eval(r).worst_bus
    assert wb is not None
    return wb


def _iso(r: ContingencyResult) -> Isolation:
    assert r.isolation is not None
    return r.isolation


def _diag(r: ContingencyResult) -> Diagnostics:
    assert r.diagnostics is not None
    return r.diagnostics
