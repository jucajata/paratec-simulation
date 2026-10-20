"""Ejecuciones: crear, consultar, topología (FR-033) y exportación (FR-032)."""

from __future__ import annotations

from typing import Any

import pandapower as pp
from fastapi import APIRouter, Request, Response

from sinsim.adapters.storage.export import export_zip
from sinsim.api.routers.snapshots import ctx_of
from sinsim.api.schemas import RunRequest
from sinsim.domain.entities import Run
from sinsim.services.run_flow import run_flow

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
    """Nodos y aristas de la topología lógica con valores para colorear (FR-033)."""
    ctx = ctx_of(request)
    run = ctx.cases.get_run(run_id)
    net = pp.from_json_string(ctx.cases.get_net_json(run.case_id))
    vm: dict[str, float] = {}
    violation: dict[str, str | None] = {}
    loading: dict[str, float] = {}
    overload: dict[str, bool] = {}
    if run.result is not None:
        for b in run.result.buses:
            vm[b.bus_id] = b.vm_pu
            violation[b.bus_id] = b.violation
        for br in run.result.lines + run.result.trafos:
            loading[br.element_id] = br.loading_percent
            overload[br.element_id] = br.overload
    name = net.bus.name.to_dict()
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
        }
        for i, row in net.bus.iterrows()
    ]
    edges: list[dict[str, Any]] = []
    for _, row in net.line.iterrows():
        edges.append(
            _edge(str(row["name"]), name[row.from_bus], name[row.to_bus], "line", loading, overload)
        )
    for _, row in net.trafo.iterrows():
        edges.append(
            _edge(
                str(row["name"]), name[row.hv_bus], name[row.lv_bus], "trafo2w", loading, overload
            )
        )
    for _, row in net.trafo3w.iterrows():
        edges.append(
            _edge(
                str(row["name"]), name[row.hv_bus], name[row.lv_bus], "trafo3w", loading, overload
            )
        )
    return {"nodes": nodes, "edges": edges}


def _edge(
    element_id: str,
    source: str,
    target: str,
    kind: str,
    loading: dict[str, float],
    overload: dict[str, bool],
) -> dict[str, Any]:
    return {
        "id": element_id,
        "source": str(source),
        "target": str(target),
        "kind": kind,
        "loading_percent": loading.get(element_id),
        "overload": overload.get(element_id, False),
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
