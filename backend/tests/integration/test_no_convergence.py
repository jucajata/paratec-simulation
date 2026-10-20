"""FR-022: un flujo que no converge nunca se presenta como resultado válido."""

from __future__ import annotations

import math

from sinsim.config import load_config, sinsim_version
from sinsim.services.build_case import build_case
from sinsim.services.run_flow import run_flow


def test_overloaded_case_reports_no_convergio_with_diagnostics(fixture_snapshot, equivalences_repo):
    cfg = load_config()
    built = build_case(
        snapshot=fixture_snapshot,
        dispatch_snapshot=fixture_snapshot,
        period=19,
        equivalences=equivalences_repo,
        cfg=cfg,
        sinsim_version=sinsim_version(),
    )
    net = built.net
    net.load.p_mw *= 50.0
    net.load.q_mvar *= 50.0
    run = run_flow(built.case, net, "ac", cfg, sinsim_version())
    assert run.status == "no_convergio"
    assert run.result is None
    d = run.diagnostics
    assert d is not None
    assert d.iterations >= 1
    assert d.basis in {"última iteración", "arranque plano (1 pu, 0°)"} or d.basis.startswith(
        "última iteración finita"
    )
    assert d.worst_buses and len(d.worst_buses) <= 10
    assert all("|" in w.bus for w in d.worst_buses)
    assert not math.isnan(d.max_mismatch_mva) and d.max_mismatch_mva > 0
    assert d.worst_buses[0].mismatch_mva == d.max_mismatch_mva
    assert run.trace.case_id == built.case.case_id
