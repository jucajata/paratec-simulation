"""FR-052 a FR-057: criterio de empeoramiento, orden de los listados y resumen (spec 003)."""

from __future__ import annotations

import pytest

from sinsim.domain.contingency import (
    ContingencyResult,
    FlowState,
    branch_counts,
    bus_counts,
    bus_distance,
    evaluate,
    rank_isolation,
    rank_loading,
    rank_voltage,
    summarize,
    unsolved_rows,
)
from sinsim.domain.entities import BusMismatch, Diagnostics, Isolation, Outage
from sinsim.domain.limits import LoadingLimit, VoltageBand

BANDS = [
    VoltageBand("STN", 220.0, 400.0, 0.90, 1.10, "CREG 025/1995"),
    VoltageBand("STR", 57.5, 220.0, 0.90, 1.10, "CREG 153/2019"),
]
STN = BANDS[0]
LOADING = LoadingLimit(100.0, "CREG 025/1995")


# --- FR-052: cargabilidad ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("base", "after", "counts"),
    [
        (105.0, 105.0, False),  # sigue igual: no empeora
        (105.0, 105.01, True),  # sin umbral: cualquier aumento cuenta
        (90.0, 100.0, False),  # no supera el límite (estricto, como branch_overload)
        (90.0, 100.5, True),
        (120.0, 110.0, False),  # mejora
    ],
)
def test_branch_counts_only_when_over_limit_and_worse_than_base(base, after, counts):
    assert branch_counts(base, after, LOADING) is counts


# --- FR-052: tensión -------------------------------------------------------------------


def test_bus_distance_is_zero_inside_band_and_signed_outside():
    assert bus_distance(1.0, STN) == 0.0
    assert bus_distance(0.90, STN) == 0.0
    assert bus_distance(0.88, STN) == pytest.approx(-0.02)
    assert bus_distance(1.13, STN) == pytest.approx(0.03)


@pytest.mark.parametrize(
    ("base", "after", "counts"),
    [
        (1.0, 0.88, True),  # entra en subtensión
        (0.87, 0.88, False),  # se acerca a la banda: mejora
        (0.87, 0.86, True),
        (0.87, 1.12, False),  # cambia de lado, pero |0,02| < |0,03|
        (0.87, 1.14, True),  # cambia de lado y se aleja más
        (1.0, 1.0, False),
    ],
)
def test_bus_counts_by_absolute_distance(base, after, counts):
    assert bus_counts(base, after, STN) is counts


def test_bus_without_band_never_counts():
    assert bus_counts(1.0, 0.5, None) is False


# --- evaluate -----------------------------------------------------------------------------


def state(loading: dict[str, float], vm: dict[str, float], vn: dict[str, float]) -> FlowState:
    return FlowState(loading=loading, vm_pu=vm, vn_kv=vn)


def test_evaluate_picks_worst_among_those_that_count_only():
    vn = {"A|230": 230.0, "B|230": 230.0, "C|115": 115.0}
    base = state(
        {"l1": 105.0, "l2": 90.0, "l3": 50.0}, {"A|230": 0.87, "B|230": 1.0, "C|115": 1.0}, vn
    )
    after = state(
        {"l1": 105.0, "l2": 103.0, "l3": 101.0}, {"A|230": 0.87, "B|230": 0.89, "C|115": 1.12}, vn
    )
    ev = evaluate(base, after, BANDS, LOADING)
    # l1 está más cargada (105) pero no cuenta porque no empeora; gana l2 entre las que cuentan.
    assert ev.worst_branch == ("l2", 90.0, 103.0)
    assert ev.n_branches == 2
    # A no cuenta (igual que en base); entre B (−0,01) y C (+0,02) gana C por valor absoluto.
    assert ev.worst_bus is not None
    assert ev.worst_bus.bus_id == "C|115"
    assert ev.worst_bus.vm_base_pu == 1.0
    assert ev.worst_bus.vm_pu == pytest.approx(1.12)
    assert ev.worst_bus.deviation_pu == pytest.approx(0.02)
    assert ev.n_buses == 2


def test_evaluate_ignores_elements_absent_after_the_outage():
    vn = {"A|230": 230.0, "B|230": 230.0}
    base = state({"l1": 50.0, "l2": 50.0}, {"A|230": 1.0, "B|230": 1.0}, vn)
    # l1 es el activo que sale (sin resultado) y B queda aislada (sin tensión).
    after = state({"l2": 120.0}, {"A|230": 0.85}, vn)
    ev = evaluate(base, after, BANDS, LOADING)
    assert ev.worst_branch == ("l2", 50.0, 120.0) and ev.n_branches == 1
    assert ev.worst_bus is not None and ev.worst_bus.bus_id == "A|230" and ev.n_buses == 1


def test_evaluate_without_impact_has_no_worst_values():
    vn = {"A|230": 230.0}
    base = state({"l1": 50.0}, {"A|230": 1.0}, vn)
    ev = evaluate(base, state({"l1": 60.0}, {"A|230": 1.02}, vn), BANDS, LOADING)
    assert ev.worst_branch is None and ev.worst_bus is None
    assert ev.n_branches == 0 and ev.n_buses == 0


# --- orden de los listados (FR-053, FR-054, FR-055) -----------------------------------------


def outage(name: str, kind: str = "line") -> Outage:
    return Outage(element_id=name, kind=kind)  # type: ignore[arg-type]


def result(
    name: str,
    *,
    branch: tuple[str, float, float] | None = None,
    bus: tuple[str, float, float, float] | None = None,
    isolation: Isolation | None = None,
    converged: bool = True,
) -> ContingencyResult:
    vn = {"X|230": 230.0}
    base = state({"e": 0.0}, {"X|230": 1.0}, vn)
    after_loading = {"e": 0.0}
    after_vm = {"X|230": 1.0}
    if branch:
        base = state({branch[0]: branch[1]}, base.vm_pu, vn)
        after_loading = {branch[0]: branch[2]}
    if bus:
        vn = {bus[0]: 230.0}
        base = state(base.loading, {bus[0]: bus[1]}, vn)
        after_vm = {bus[0]: bus[2]}
    ev = evaluate(base, state(after_loading, after_vm, vn), BANDS, LOADING) if converged else None
    diag = (
        None
        if converged
        else Diagnostics(
            iterations=30,
            max_mismatch_mva=9.9,
            worst_buses=[BusMismatch(bus="X|230", mismatch_mva=9.9)],
        )
    )
    return ContingencyResult(
        outage=outage(name), evaluation=ev, isolation=isolation, diagnostics=diag
    )


def test_rank_loading_descending_with_ties_by_outage_name():
    rows = rank_loading(
        [
            result("b", branch=("l", 90.0, 150.0)),
            result("c", branch=("l", 90.0, 200.0)),
            result("a", branch=("l", 90.0, 150.0)),
            result("d", branch=("l", 90.0, 95.0)),  # no cuenta
            result("e", converged=False),
        ]
    )
    assert [(r.rank, r.outage.element_id, r.loading_percent) for r in rows] == [
        (1, "c", 200.0),
        (2, "a", 150.0),
        (3, "b", 150.0),
    ]
    assert (
        rows[0].element_id == "l"
        and rows[0].loading_base_percent == 90.0
        and rows[0].n_elements == 1
    )


def test_rank_voltage_by_absolute_deviation_with_sign_kept():
    rows = rank_voltage(
        [
            result("low", bus=("X|230", 1.0, 0.85, 0.0)),
            result("high", bus=("X|230", 1.0, 1.13, 0.0)),
            result("same", bus=("X|230", 1.0, 1.0, 0.0)),
        ]
    )
    assert [(r.rank, r.outage.element_id) for r in rows] == [(1, "low"), (2, "high")]
    assert rows[0].deviation_pu == pytest.approx(-0.05) and rows[1].deviation_pu == pytest.approx(
        0.03
    )
    assert rows[0].vm_base_pu == 1.0 and rows[0].vm_pu == 0.85 and rows[0].n_buses == 1


def test_rank_isolation_only_with_demand_lost_and_by_mw():
    rows = rank_isolation(
        [
            result("a", isolation=Isolation(n_buses=2, p_demand_lost_mw=10.0)),
            result("b", isolation=Isolation(n_buses=1, p_demand_lost_mw=80.0)),
            result("c", isolation=Isolation(n_buses=3, p_demand_lost_mw=0.0)),  # sin demanda
            result("d", branch=("l", 90.0, 150.0)),
            result("e", converged=False, isolation=Isolation(n_buses=1, p_demand_lost_mw=5.0)),
        ]
    )
    assert [(r.rank, r.outage.element_id, r.p_demand_lost_mw) for r in rows] == [
        (1, "b", 80.0),
        (2, "a", 10.0),
    ]


def test_isolation_mark_travels_with_loading_and_voltage_rows():
    iso = Isolation(n_buses=2, p_demand_lost_mw=10.0)
    res = [result("a", branch=("l", 90.0, 150.0), bus=("X|230", 1.0, 0.85, 0.0), isolation=iso)]
    assert rank_loading(res)[0].isolation == iso
    assert rank_voltage(res)[0].isolation == iso


def test_unsolved_rows_sorted_by_name_with_diagnostics():
    rows = unsolved_rows([result("z", converged=False), result("a", converged=False), result("m")])
    assert [r.outage.element_id for r in rows] == ["a", "z"]
    assert rows[0].diagnostics.iterations == 30


# --- resumen (FR-057, SC-017) -------------------------------------------------------------


def test_summarize_counts_cuadran():
    res = [
        result(
            "a", branch=("l", 90.0, 150.0), bus=("X|230", 1.0, 0.85, 0.0)
        ),  # en los dos listados
        result("b", branch=("l", 90.0, 150.0)),
        result("c", isolation=Isolation(n_buses=1, p_demand_lost_mw=80.0)),
        result("d"),  # sin impacto
        result("e", converged=False),
    ]
    s = summarize(res, duration_s=1.5)
    assert (s.n_total, s.n_loading, s.n_voltage, s.n_isolation, s.n_unsolved, s.n_no_impact) == (
        5,
        2,
        1,
        1,
        1,
        1,
    )
    assert s.duration_s == 1.5
    # SC-017: no convergidas + convergidas = total; sin impacto = convergidas − |unión de grupos|.
    assert s.n_unsolved + (s.n_total - s.n_unsolved) == s.n_total
    assert s.n_no_impact == (s.n_total - s.n_unsolved) - 3
