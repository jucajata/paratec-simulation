"""HU-1: construir el caso y correr el flujo sobre el snapshot de fixtures."""

from __future__ import annotations

import dataclasses
from datetime import date
from pathlib import Path

import pandapower as pp
import pytest

from sinsim.adapters.storage.snapshots import ParquetSnapshotRepository
from sinsim.config import load_config, sinsim_version
from sinsim.domain.entities import LABEL_AC, LABEL_DC
from sinsim.domain.errors import DomainError
from sinsim.scraper.writer import write_snapshot
from sinsim.services.build_case import build_case
from sinsim.services.run_flow import run_flow
from tests.conftest import ATTRIBUTION, SNAPSHOT_DATE, build_raw_snapshot


@pytest.fixture(scope="module")
def built(fixture_snapshot, equivalences_repo):
    cfg = load_config()
    return build_case(
        snapshot=fixture_snapshot,
        dispatch_snapshot=fixture_snapshot,
        period=19,
        equivalences=equivalences_repo,
        cfg=cfg,
        sinsim_version=sinsim_version(),
    )


def test_case_has_complete_inputs_quality_and_assumptions(
    built, fixture_snapshot, equivalences_repo
):
    case = built.case
    assert len(case.case_id) == 64
    i = case.inputs
    assert i.snapshot_date == i.dispatch_date == SNAPSHOT_DATE and i.period == 19
    assert i.snapshot_manifest_sha256 == fixture_snapshot.manifest_sha256
    assert i.equivalences_sha256 == equivalences_repo.sha256
    q = case.quality
    assert q.balance.coverage_pct > 80 and q.balance.p_located_mw > 10_000
    assert q.islands and q.islands[0].energized and q.islands[0].n_buses > 500
    assert all(not isl.energized for isl in q.islands[1:])
    assert len(q.imputed) > 100 and all(
        im.param in {"vkr_percent", "pfe_kw", "vkr_hv_percent", "vkr_mv_percent", "vkr_lv_percent"}
        for im in q.imputed
    )
    for key in (
        "consigna_tension_pu",
        "barra_referencia_angulo",
        "referencia_distribuida",
        "taps",
        "i0_percent",
        "imputacion",
    ):
        assert key in case.assumptions
    assert case.assumptions["consigna_tension_pu"]["valor"] == 1.0
    # FR-018: consigna y límites de reactiva por generador, con la fuente de cada valor.
    gens = case.assumptions["generadores"]
    assert len(gens) > 50 and all(
        g["vm_pu"] == 1.0 and g["fuente_vm"] and g["fuente_q"] and g["gen_id"] and g["barra"]
        for g in gens
    )
    assert any(g["q_min_mvar"] is not None and g["q_max_mvar"] is not None for g in gens)
    # FR-014: la demanda activa de cada barra conserva `Ener.Act.` y `Perd.PSTR` por separado.
    demand = case.assumptions["demanda_por_barra"]["barras"]
    assert len(demand) > 50 and all(g["p_pstr_mw"] >= 0 for g in demand)
    assert sum(d["p_act_mw"] + d["p_pstr_mw"] for d in demand) == pytest.approx(
        q.balance.p_demand_mw, rel=1e-9
    )
    assert any(w.startswith("PROGRAM_NOT_REAL_STATE") for w in case.warnings)
    assert not any(w.startswith("DATES_DIFFER") for w in case.warnings)


def test_ac_flow_converges_with_full_trace_and_coherent_summary(built):
    cfg = load_config()
    run = run_flow(built.case, built.net, "ac", cfg, sinsim_version())
    assert run.status == "convergio" and run.result is not None and run.diagnostics is None
    assert run.label == LABEL_AC
    t = run.trace
    assert t.snapshot_date == SNAPSHOT_DATE and t.period == 19 and t.flow_type == "ac"
    assert t.pandapower_version == pp.__version__ and t.sinsim_version == sinsim_version()
    assert t.case_id == built.case.case_id and t.solver.algorithm == "nr"
    s = run.result.summary
    assert s.p_gen_mw == pytest.approx(s.p_load_mw + s.p_losses_mw, rel=0.02)
    assert s.p_losses_mw > 0 and len(s.limits) == 4
    assert (
        len(run.result.buses) > 500
        and len(run.result.lines) > 800
        and len(run.result.generators) > 150
    )
    b = run.result.buses[0]
    assert b.vm_kv == pytest.approx(b.vm_pu * b.vn_kv)
    assert any(g.slack_adjust_mw != 0 for g in run.result.generators)
    assert s.slack_adjust_total_mw == pytest.approx(
        sum(g.slack_adjust_mw for g in run.result.generators)
    )
    # FR-034: subárea de PARATEC en barras y ramas; las barras sin ella se reportan.
    with_sub = [b for b in run.result.buses if b.subarea]
    assert len(with_sub) > 0.9 * len(run.result.buses)
    assert not any(b.subarea.startswith("SubArea") for b in with_sub)
    assert any(
        br.subarea_from and br.subarea_to and br.subarea_from != br.subarea_to
        for br in run.result.lines
    )
    missing = set(built.case.quality.buses_without_subarea)
    assert {b.bus_id for b in run.result.buses if not b.subarea} <= missing
    # Ninguna rama del resultado une una barra consigo misma; esas líneas se reportan.
    assert not any(br.from_bus == br.to_bus for br in run.result.lines + run.result.trafos)
    assert any("misma barra" in n.reason for n in built.case.quality.not_modeled)


def test_dc_flow_is_labelled_as_approximation(built):
    cfg = load_config()
    run = run_flow(
        built.case, pp.from_json_string(pp.to_json(built.net)), "dc", cfg, sinsim_version()
    )
    assert run.status == "convergio" and run.label == LABEL_DC
    assert all(b.vm_pu > 0 for b in run.result.buses)
    assert run.result.summary.p_losses_mw == 0.0
    assert any("DC" in w for w in run.result.summary.warnings)


def test_dates_differ_warning(tmp_path: Path, fixture_snapshot, equivalences_repo):
    root = tmp_path / "paratec"
    root.mkdir()
    other = date(2026, 10, 19)
    write_snapshot(build_raw_snapshot(), root, other, scraper_version="t", attribution=ATTRIBUTION)
    dispatch_snapshot = ParquetSnapshotRepository(root).load(other)
    built = build_case(
        snapshot=fixture_snapshot,
        dispatch_snapshot=dispatch_snapshot,
        period=1,
        equivalences=equivalences_repo,
        cfg=load_config(),
        sinsim_version=sinsim_version(),
    )
    assert any(w.startswith("DATES_DIFFER") for w in built.case.warnings)
    assert built.case.inputs.dispatch_date == other


def test_missing_operating_point_blocks_execution(fixture_snapshot, equivalences_repo):
    empty = dataclasses.replace(
        fixture_snapshot,
        tables=dataclasses.replace(
            fixture_snapshot.tables, dispatch=fixture_snapshot.tables.dispatch.iloc[0:0]
        ),
    )
    with pytest.raises(DomainError) as exc:
        build_case(
            snapshot=fixture_snapshot,
            dispatch_snapshot=empty,
            period=1,
            equivalences=equivalences_repo,
            cfg=load_config(),
            sinsim_version="t",
        )
    assert exc.value.code == "OPERATING_POINT_MISSING" and "dDEC" in exc.value.detail
    assert "sinsim scrape" in exc.value.user_message


def test_period_out_of_range(fixture_snapshot, equivalences_repo):
    with pytest.raises(DomainError) as exc:
        build_case(
            snapshot=fixture_snapshot,
            dispatch_snapshot=fixture_snapshot,
            period=25,
            equivalences=equivalences_repo,
            cfg=load_config(),
            sinsim_version="t",
        )
    assert exc.value.code == "PERIOD_OUT_OF_RANGE"
