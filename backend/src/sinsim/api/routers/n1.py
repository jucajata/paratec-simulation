"""Análisis N-1 desde la interfaz (FR-058; contracts/openapi-n1.yaml de la spec 003).

Se acepta con 202 y se sigue por `GET /api/n1/{job_id}`. Corre en segundo plano con la misma
lógica que `sinsim n1`; hay un único análisis a la vez en toda la API.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from sinsim.api.routers.snapshots import ctx_of
from sinsim.domain.entities import N1Job
from sinsim.services import n1

router = APIRouter(tags=["n1"])


@router.post("/runs/{run_id}/n1", response_model=N1Job, status_code=status.HTTP_202_ACCEPTED)
def start_n1(run_id: str, request: Request) -> N1Job:
    """Lanza el análisis N-1 sobre una ejecución AC convergida (FR-058, FR-061)."""
    ctx = ctx_of(request)
    run = ctx.cases.get_run(run_id)
    n1.require_base(run)
    net_json = ctx.cases.get_net_json(run.case_id)
    cfg = ctx.cfg
    return ctx.n1_runner.start(
        run_id, lambda progress: n1.analyze(run, net_json, cfg, progress=progress)
    )


@router.get("/n1/{job_id}", response_model=N1Job)
def get_n1(job_id: str, request: Request) -> N1Job:
    """Estado del análisis y, al terminar, su resultado completo."""
    return ctx_of(request).n1_runner.get(job_id)
