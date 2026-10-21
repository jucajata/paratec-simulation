"""Ejecuciones: crear, consultar, topología (FR-033) y exportación (FR-032)."""

from __future__ import annotations

import math
from typing import Any

import pandapower as pp
from fastapi import APIRouter, Request, Response

from sinsim.adapters.storage.export import export_zip
from sinsim.api.routers.snapshots import ctx_of
from sinsim.api.schemas import RunRequest
from sinsim.domain.entities import Run
from sinsim.services.run_flow import run_flow, subareas_of

router = APIRouter(tags=["runs"])


@router.post("/cases/{case_id}/runs", response_model=Run)
def create_run(case_id: str, body: RunRequest, request: Request) -> Run:
    """Ejecuta un flujo AC o DC. Responde 200 también cuando no converge (FR-022)."""
    ctx = ctx_of(request)
    case = ctx.cases.get_case(case_id)
    net = pp.from_json_string(ctx.cases.get_net_json(case_id))
    run = run_flow(case, net, body.flow_type, ctx.cfg, ctx.version)
    ctx.cases.save_run(run)
    return run


@router.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str, request: Request) -> Run:
    """Devuelve una ejecución con sus resultados (FR-030, FR-031)."""
    return ctx_of(request).cases.get_run(run_id)


@router.get("/runs/{run_id}/topology")
def get_topology(run_id: str, request: Request) -> dict[str, list[dict[str, Any]]]:
    """Nodos y aristas de la topología con valores para colorear y leer (FR-033, FR-036).

    Por nodo: tensión, subárea, coordenadas, generación y carga resultantes. Por rama: flujo
    de P y Q en cada extremo, con el signo de pandapower (positivo = sale de `source`).
    """
    ctx = ctx_of(request)
    run = ctx.cases.get_run(run_id)
    net = pp.from_json_string(ctx.cases.get_net_json(run.case_id))
    vm: dict[str, float] = {}
    violation: dict[str, str | None] = {}
    loading: dict[str, float] = {}
    overload: dict[str, bool] = {}
    flows: dict[str, dict[str, float]] = {}
    gen_p: dict[str, float] = {}
    gen_q: dict[str, float] = {}
    slack: dict[str, float] = {}
    vm_kv: dict[str, float] = {}
    va: dict[str, float] = {}
    if run.result is not None:
        for b in run.result.buses:
            vm[b.bus_id] = b.vm_pu
            violation[b.bus_id] = b.violation
            vm_kv[b.bus_id] = b.vm_kv
            va[b.bus_id] = b.va_degree
        for br in run.result.lines + run.result.trafos:
            loading[br.element_id] = br.loading_percent
            overload[br.element_id] = br.overload
            flows[br.element_id] = {
                "p_from_mw": br.p_from_mw,
                "q_from_mvar": br.q_from_mvar,
                "p_to_mw": br.p_to_mw,
                "q_to_mvar": br.q_to_mvar,
                "i_ka": br.i_ka,
                "pl_mw": br.pl_mw,
                "ql_mvar": br.ql_mvar,
            }
        for g in run.result.generators:
            gen_p[g.bus] = gen_p.get(g.bus, 0.0) + g.p_mw
            gen_q[g.bus] = gen_q.get(g.bus, 0.0) + g.q_mvar
            slack[g.bus] = slack.get(g.bus, 0.0) + g.slack_adjust_mw
    name = net.bus.name.to_dict()
    loads = _loads_by_bus(net, name)
    subarea = subareas_of(net)
    nominal = (
        net.bus["nominal_kv"].to_dict()
        if "nominal_kv" in net.bus.columns
        else net.bus.vn_kv.to_dict()
    )
    nodes = [
        {
            "id": str(name[i]),
            "label": str(name[i]),
            "vn_kv": float(nominal[i]),
            "vm_pu": vm.get(str(name[i])),
            "violation": violation.get(str(name[i])),
            "in_service": bool(row.in_service),
            "subarea": subarea.get(int(i)),
            "lat": _coord(row.get("lat")),
            "lon": _coord(row.get("lon")),
            "p_gen_mw": gen_p.get(str(name[i]), 0.0),
            "q_gen_mvar": gen_q.get(str(name[i]), 0.0),
            "slack_adjust_mw": slack.get(str(name[i]), 0.0),
            "vm_kv": vm_kv.get(str(name[i])),
            "va_degree": va.get(str(name[i])),
            **loads.get(str(name[i]), _NO_LOAD),
        }
        for i, row in net.bus.iterrows()
    ]
    edges: list[dict[str, Any]] = []
    for _, row in net.line.iterrows():
        edges.append(
            _edge(
                str(row["name"]),
                name[row.from_bus],
                name[row.to_bus],
                "line",
                loading,
                overload,
                flows,
            )
        )
    for _, row in net.trafo.iterrows():
        edges.append(
            _edge(
                str(row["name"]),
                name[row.hv_bus],
                name[row.lv_bus],
                "trafo2w",
                loading,
                overload,
                flows,
            )
        )
    for _, row in net.trafo3w.iterrows():
        edges.append(
            _edge(
                str(row["name"]),
                name[row.hv_bus],
                name[row.lv_bus],
                "trafo3w",
                loading,
                overload,
                flows,
            )
        )
    unifilares = ctx.cfg.config.unifilares
    subareas = [
        {"name": s, "unifilar_url": unifilares.url_for(s)}
        for s in sorted({str(n["subarea"]) for n in nodes if n["subarea"] and n["in_service"]})
    ]
    return {"nodes": nodes, "edges": edges, "subareas": subareas}


_NO_LOAD: dict[str, float | None] = {
    "p_load_mw": 0.0,
    "q_load_mvar": 0.0,
    "p_load_act_mw": None,
    "p_load_pstr_mw": None,
}


def _loads_by_bus(net: pp.pandapowerNet, name: dict[Any, Any]) -> dict[str, dict[str, Any]]:
    """Carga por barra con sus componentes `Ener.Act.` y `Perd.PSTR` (FR-014, FR-036)."""
    out: dict[str, dict[str, Any]] = {}
    has_parts = {"p_act_mw", "p_pstr_mw"} <= set(net.load.columns)
    bus_in_service = net.bus.in_service.to_dict()
    for _, ld in net.load.iterrows():
        # Las cargas de islas no energizadas no se sirven: no cuentan (coherente con el resumen).
        if not ld.in_service or not bus_in_service.get(ld.bus, False):
            continue
        bus = str(name[ld.bus])
        entry = out.setdefault(bus, dict(_NO_LOAD))
        entry["p_load_mw"] = float(entry["p_load_mw"] or 0.0) + float(ld.p_mw)
        entry["q_load_mvar"] = float(entry["q_load_mvar"] or 0.0) + float(ld.q_mvar)
        if has_parts:
            act, pstr = _coord(ld.p_act_mw), _coord(ld.p_pstr_mw)
            if act is not None:
                entry["p_load_act_mw"] = float(entry["p_load_act_mw"] or 0.0) + act
            if pstr is not None:
                entry["p_load_pstr_mw"] = float(entry["p_load_pstr_mw"] or 0.0) + pstr
    return out


def _coord(value: object) -> float | None:
    """Coordenada de PARATEC o `None` si falta (FR-035)."""
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def _edge(
    element_id: str,
    source: str,
    target: str,
    kind: str,
    loading: dict[str, float],
    overload: dict[str, bool],
    flows: dict[str, dict[str, float]],
) -> dict[str, Any]:
    flow = flows.get(element_id, {})
    return {
        "id": element_id,
        "source": str(source),
        "target": str(target),
        "kind": kind,
        "loading_percent": loading.get(element_id),
        "overload": overload.get(element_id, False),
        "p_from_mw": flow.get("p_from_mw"),
        "q_from_mvar": flow.get("q_from_mvar"),
        "p_to_mw": flow.get("p_to_mw"),
        "q_to_mvar": flow.get("q_to_mvar"),
        "i_ka": flow.get("i_ka"),
        "pl_mw": flow.get("pl_mw"),
        "ql_mvar": flow.get("ql_mvar"),
    }


@router.get("/runs/{run_id}/export")
def get_export(run_id: str, request: Request) -> Response:
    """Descarga la exportación como `.zip` (FR-032)."""
    ctx = ctx_of(request)
    run = ctx.cases.get_run(run_id)
    case = ctx.cases.get_case(run.case_id)
    payload = export_zip(case, run, ctx.cfg.config.attribution.text)
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="sinsim-{run_id}.zip"'},
    )
