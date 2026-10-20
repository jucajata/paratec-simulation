"""HU-2: el reporte de calidad lista todo lo que no quedó representado (SC-002)."""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from sinsim.config import load_config, sinsim_version
from sinsim.services.build_case import build_case

GHOST = "PLANTA_FANTASMA"


def kv(bus: str) -> float:
    return float(bus.split("|")[1])


@pytest.fixture(scope="module")
def case(fixture_snapshot, equivalences_repo):
    dispatch = fixture_snapshot.tables.dispatch
    extra = pd.DataFrame(
        {
            "resource": [GHOST] * 24,
            "period": list(range(1, 25)),
            "p_mw": [123.4] * 24,
            "source_id": ["test"] * 24,
        }
    )
    tables = dataclasses.replace(
        fixture_snapshot.tables, dispatch=pd.concat([dispatch, extra], ignore_index=True)
    )
    snap = dataclasses.replace(fixture_snapshot, tables=tables)
    return build_case(
        snapshot=snap,
        dispatch_snapshot=snap,
        period=19,
        equivalences=equivalences_repo,
        cfg=load_config(),
        sinsim_version=sinsim_version(),
    ).case


def test_unknown_resource_is_listed_as_unlocated_with_its_mw(case):
    q = case.quality
    ghost = [u for u in q.unlocated_resources if u.resource == GHOST]
    assert len(ghost) == 1 and ghost[0].p_mw == 123.4 and ghost[0].reason == "sin equivalencia"
    assert q.balance.p_unlocated_mw >= 123.4
    assert q.balance.p_scheduled_total_mw == pytest.approx(
        q.balance.p_located_mw + q.balance.p_unlocated_mw
    )


def test_every_dispatched_resource_is_located_or_unlocated(case, fixture_snapshot):
    dispatched = fixture_snapshot.tables.dispatch
    with_p = set(dispatched[(dispatched.period == 19) & (dispatched.p_mw > 0)].resource) | {GHOST}
    located = {f.split("@")[0] for f in case.assumptions["referencia_distribuida"]["factores"]}
    unlocated = {u.resource for u in case.quality.unlocated_resources}
    links = {"ECUADOR230_1", "ECUADOR138_1"}
    assert with_p <= located | unlocated | links, with_p - located - unlocated - links


def test_missing_parameters_are_excluded_or_imputed_explicitly(case):
    q = case.quality
    assert any(
        e.kind == "línea" and set(e.missing_params) >= {"from_bus", "to_bus"} for e in q.excluded
    )
    assert q.imputed and all(im.method.startswith("mediana") and im.value > 0 for im in q.imputed)
    assert {im.param for im in q.imputed} <= {
        "vkr_percent",
        "pfe_kw",
        "vkr_hv_percent",
        "vkr_mv_percent",
        "vkr_lv_percent",
    }


def test_generation_and_demand_below_scope_are_transferred_to_frontier(case):
    gen_transfers = [t for t in case.quality.transfers if t.kind == "gen"]
    dem_transfers = [t for t in case.quality.transfers if t.kind == "demand"]
    assert gen_transfers and dem_transfers
    for t in gen_transfers + dem_transfers:
        assert kv(t.from_bus) < 57.5 <= kv(t.to_bus)
        assert t.from_bus.split("|")[0] == t.to_bus.split("|")[0]
    assert any(t.element.startswith("PORCE III MENOR") for t in gen_transfers)
    assert any(t.element == "ANCONSU4" for t in dem_transfers)


def test_islands_are_reported_with_lost_mw_and_only_one_energized(case):
    islands = case.quality.islands
    assert islands[0].energized and all(not i.energized for i in islands[1:])
    assert all(i.n_buses == len(i.buses) for i in islands)
    assert sum(i.p_gen_lost_mw for i in islands[1:]) > 0
    assert islands[0].p_gen_lost_mw == 0.0 and islands[0].p_demand_lost_mw == 0.0


def test_unlocated_demand_nodes_are_listed(case):
    q = case.quality
    assert q.unlocated_demand and all(u.reason and u.p_mw >= 0 for u in q.unlocated_demand)
    assert q.balance.p_demand_unlocated_mw == pytest.approx(sum(u.p_mw for u in q.unlocated_demand))


def test_balance_summary(case):
    b = case.quality.balance
    assert b.coverage_pct == pytest.approx(b.p_located_mw / b.p_scheduled_total_mw * 100)
    assert b.difference_mw == pytest.approx(b.p_located_mw - b.p_demand_mw)
