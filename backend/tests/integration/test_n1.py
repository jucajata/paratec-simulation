"""Servicio de análisis N-1 (spec 003): SC-015, no convergencia, islas, referencia y determinismo.

Corre sobre el caso del snapshot de fixtures con un puñado de contingencias elegidas; el
análisis completo lo cubre la prueba e2e y el quickstart.
"""

from __future__ import annotations

import networkx as nx
import pandapower as pp
import pandapower.topology as top
import pytest

from sinsim.config import load_config, sinsim_version
from sinsim.domain.errors import DomainError
from sinsim.services import n1
from sinsim.services.build_case import build_case
from sinsim.services.run_flow import bus_vm_nominal, run_flow, solver_settings


@pytest.fixture(scope="module")
def base(fixture_snapshot, equivalences_repo):
    cfg = load_config()
    built = build_case(
        snapshot=fixture_snapshot,
        dispatch_snapshot=fixture_snapshot,
        period=19,
        equivalences=equivalences_repo,
        cfg=cfg,
        sinsim_version=sinsim_version(),
    )
    net_json = pp.to_json(built.net)
    run = run_flow(built.case, built.net, "ac", cfg, sinsim_version())
    assert run.status == "convergio"
    return cfg, built.case, run, net_json


def outage_named(net: pp.pandapowerNet, name: str):
    return next(o for o in n1.enumerate_outages(net) if o.element_id == name)


def meshed_line(net: pp.pandapowerNet) -> str:
    """Una línea que no es puente: sacarla deja la red conexa, sin islas."""
    graph = top.create_nxgraph(net, respect_switches=False, include_out_of_service=False)
    components = nx.number_connected_components(graph)
    for idx, row in net.line[net.line.in_service].iterrows():
        trial = graph.copy()
        trial.remove_edge(row.from_bus, row.to_bus, key=("line", idx))
        if nx.number_connected_components(trial) == components:
            return str(net.line.at[idx, "name"])
    raise AssertionError("el caso no tiene líneas malladas")


def radial_line(net: pp.pandapowerNet) -> str:
    """Una línea en servicio con un extremo de grado 1: sacarla aísla esa barra (FR-055)."""
    graph = top.create_nxgraph(net, respect_switches=False, include_out_of_service=False)
    for idx, row in net.line[net.line.in_service].iterrows():
        if graph.degree(row.from_bus) == 1 or graph.degree(row.to_bus) == 1:
            return str(net.line.at[idx, "name"])
    raise AssertionError("el caso no tiene líneas radiales")


def test_enumerate_outages_covers_lines_trafos_gens_and_compensators(base):
    _, _, _, net_json = base
    net = pp.from_json_string(net_json)
    outages = n1.enumerate_outages(net)
    kinds = {o.kind for o in outages}
    assert kinds == {"line", "trafo2w", "gen", "compensador"}
    assert sum(o.kind == "line" for o in outages) == int(net.line.in_service.sum())
    assert sum(o.kind == "trafo2w" for o in outages) == int(net.trafo.in_service.sum())
    assert sum(o.kind in ("gen", "compensador") for o in outages) == int(net.gen.in_service.sum())
    comp = [o for o in outages if o.kind == "compensador"]
    assert comp and all(o.element_id.startswith(("svc:", "statcom:")) for o in comp)
    assert len({o.element_id for o in outages}) == len(outages)
    assert all(o.subarea for o in outages if o.kind == "line")


def test_worker_base_flow_matches_saved_run(base):
    """R9: el flujo base de cada proceso coincide con la ejecución guardada."""
    cfg, _, run, net_json = base
    worker = n1.init_worker(net_json, solver_settings(cfg).model_dump())
    assert run.result is not None
    saved_vm = {b.bus_id: b.vm_pu for b in run.result.buses}
    worker_vm = {worker.bus_name[i]: vm for i, (vm, _, _) in bus_vm_nominal(worker.net).items()}
    assert worker_vm.keys() == saved_vm.keys()
    assert max(abs(worker_vm[k] - saved_vm[k]) for k in saved_vm) < 1e-6
    saved_loading = {b.element_id: b.loading_percent for b in run.result.lines + run.result.trafos}
    assert max(abs(worker.loading()[k] - saved_loading[k]) for k in saved_loading) < 1e-4


def test_sc015_contingency_matches_manual_flow(base):
    """SC-015: una contingencia da las mismas tensiones y cargabilidades que un flujo a mano."""
    cfg, _, _, net_json = base
    settings = solver_settings(cfg)
    net = pp.from_json_string(net_json)
    name = meshed_line(net)
    worker = n1.init_worker(net_json, settings.model_dump())
    raw = worker.run_outage(outage_named(net, name))
    assert raw.converged and raw.diagnostics is None
    # Flujo a mano: la línea fuera, desde el arranque configurado, sin reutilizar nada.
    manual = pp.from_json_string(net_json)
    manual.line.loc[manual.line.name == name, "in_service"] = False
    pp.runpp(
        manual,
        algorithm=settings.algorithm,
        init=settings.init,
        max_iteration=settings.max_iteration,
        tolerance_mva=settings.tolerance_mva,
        enforce_q_lims=settings.enforce_q_lims,
        distributed_slack=settings.distributed_slack,
        calculate_voltage_angles=True,
        check_connectivity=True,
    )
    manual_vm = {str(manual.bus.name[i]): vm for i, (vm, _, _) in bus_vm_nominal(manual).items()}
    assert name not in raw.loading and raw.isolation is None
    assert raw.vm_pu.keys() == manual_vm.keys()
    assert max(abs(raw.vm_pu[k] - manual_vm[k]) for k in manual_vm) < 1e-6
    compared = 0
    for table, res, p_col in (("line", "res_line", "p_from_mw"), ("trafo", "res_trafo", "p_hv_mw")):
        for idx, row in manual[table][manual[table].in_service].iterrows():
            loading = float(manual[res].at[idx, "loading_percent"])
            if pp.pd.isna(manual[res].at[idx, p_col]) or pp.pd.isna(loading):
                continue
            assert raw.loading[str(row["name"])] == pytest.approx(loading, abs=1e-4)
            compared += 1
    assert compared > 1000


def test_unsolved_contingency_goes_to_sin_solucion_with_diagnostics(base, monkeypatch):
    """Una contingencia cuyo flujo no converge (ni desde DC) va a «Sin solución» (FR-056)."""
    cfg, _, run, net_json = base
    net = pp.from_json_string(net_json)
    target = str(net.line.name.iloc[20])
    others = [str(n) for n in net.line.name.iloc[:2]]
    real_runpp = n1.Worker._runpp

    def runpp_failing_for_target(self: n1.Worker, init: str) -> None:
        out = ~self.net.line.in_service & (self.net.line.name == target)
        if bool(out.any()):
            raise pp.LoadflowNotConverged("Power Flow nr did not converge after 30 iterations!")
        real_runpp(self, init)

    monkeypatch.setattr(n1.Worker, "_runpp", runpp_failing_for_target)
    outages = [outage_named(net, n) for n in [*others, target]]
    analysis = n1.analyze(run, net_json, cfg, workers=1, outages=outages)
    assert analysis.summary.n_total == 3 and analysis.summary.n_unsolved == 1
    row = analysis.unsolved[0]
    assert row.outage.element_id == target
    assert row.diagnostics.iterations >= 1 and row.diagnostics.basis
    listed = {r.outage.element_id for r in analysis.loading + analysis.voltage + analysis.isolation}
    assert target not in listed
    assert analysis.summary.n_no_impact + len(listed) == 2


def test_radial_line_reports_isolation(base):
    cfg, _, run, net_json = base
    net = pp.from_json_string(net_json)
    name = radial_line(net)
    analysis = n1.analyze(run, net_json, cfg, workers=1, outages=[outage_named(net, name)])
    assert analysis.summary.n_unsolved == 0
    worker = n1.init_worker(net_json, solver_settings(cfg).model_dump())
    raw = worker.run_outage(outage_named(net, name))
    assert raw.isolation is not None and raw.isolation.n_buses >= 1
    if raw.isolation.p_demand_lost_mw > 0:
        assert analysis.isolation and analysis.isolation[0].outage.element_id == name
        assert analysis.summary.n_isolation == 1
    else:
        assert not analysis.isolation


def test_outage_of_angle_reference_generator_moves_reference(base):
    cfg, _, _run, net_json = base
    net = pp.from_json_string(net_json)
    ref_gen = str(net.gen.name[net.gen.slack].iloc[0])
    worker = n1.init_worker(net_json, solver_settings(cfg).model_dump())
    raw = worker.run_outage(outage_named(net, ref_gen))
    assert raw.converged
    assert raw.outage.angle_ref_moved_to is not None
    assert raw.outage.angle_ref_moved_to != str(net.bus.name[net.gen.bus[net.gen.slack].iloc[0]])
    # Una contingencia cualquiera no mueve la referencia.
    other = worker.run_outage(outage_named(net, str(net.line.name.iloc[0])))
    assert other.outage.angle_ref_moved_to is None


def test_same_result_with_one_or_several_workers(base):
    """R3 / SC-018: mismas filas y mismo orden sin importar el reparto entre procesos."""
    cfg, _, run, net_json = base
    net = pp.from_json_string(net_json)
    all_outages = n1.enumerate_outages(net)
    picked = (
        all_outages[:4] + all_outages[900:904] + [o for o in all_outages if o.kind == "gen"][:4]
    )
    progress: list[tuple[int, int]] = []
    one = n1.analyze(run, net_json, cfg, workers=1, outages=picked)
    many = n1.analyze(
        run, net_json, cfg, workers=3, outages=picked, progress=lambda d, t: progress.append((d, t))
    )
    strip = {"analyzed_at", "workers", "summary"}
    assert one.model_dump(exclude=strip) == many.model_dump(exclude=strip)
    assert one.summary.model_dump(exclude={"duration_s"}) == many.summary.model_dump(
        exclude={"duration_s"}
    )
    assert many.workers == 3 and one.workers == 1
    assert progress and progress[-1] == (len(picked), len(picked))
    s = many.summary
    assert s.n_total == len(picked) and s.n_unsolved + s.n_no_impact <= s.n_total
    assert many.trace == run.trace and many.run_id == run.run_id
    assert any(lim.name == "Cargabilidad" for lim in many.limits)


def test_base_must_be_a_converged_ac_run(base):
    cfg, case, run, net_json = base
    dc = run_flow(case, pp.from_json_string(net_json), "dc", cfg, sinsim_version())
    with pytest.raises(DomainError) as exc:
        n1.analyze(dc, net_json, cfg, workers=1, outages=[])
    assert exc.value.code == "N1_BASE_INVALID"
    failed = run.model_copy(update={"status": "no_convergio", "result": None})
    with pytest.raises(DomainError) as exc:
        n1.analyze(failed, net_json, cfg, workers=1, outages=[])
    assert exc.value.code == "N1_BASE_INVALID"
