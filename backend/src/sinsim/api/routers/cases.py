"""`POST /api/cases` y `GET /api/cases/{case_id}` (FR-010 a FR-019)."""

from __future__ import annotations

import pandapower as pp
from fastapi import APIRouter, Request, Response, status

from sinsim.api.routers.snapshots import ctx_of
from sinsim.api.schemas import CaseRequest
from sinsim.domain.case_hash import case_id_for
from sinsim.domain.dates import ensure_allowed
from sinsim.domain.entities import StudyCase
from sinsim.services import snapshots as snapshot_service
from sinsim.services.build_case import build_case, make_inputs

router = APIRouter(tags=["cases"])


@router.post("/cases", response_model=StudyCase, status_code=status.HTTP_201_CREATED)
def create_case(body: CaseRequest, request: Request, response: Response) -> StudyCase:
    """Construye un caso; si ya existe uno con el mismo `case_id`, lo devuelve con 200."""
    ctx = ctx_of(request)
    dispatch_date = body.dispatch_date or body.snapshot_date
    ensure_allowed(body.snapshot_date)  # hasta D+1 (FR-039)
    ensure_allowed(dispatch_date)
    snapshot = snapshot_service.load_verified(ctx.snapshots, body.snapshot_date)
    dispatch_snapshot = (
        snapshot
        if dispatch_date == body.snapshot_date
        else snapshot_service.load_verified(ctx.snapshots, dispatch_date)
    )
    inputs = make_inputs(
        snapshot, dispatch_snapshot, body.period, ctx.equivalences, ctx.cfg, ctx.version
    )
    case_id = case_id_for(inputs)
    if ctx.cases.exists(case_id):
        response.status_code = status.HTTP_200_OK
        return ctx.cases.get_case(case_id)
    built = build_case(
        snapshot=snapshot,
        dispatch_snapshot=dispatch_snapshot,
        period=body.period,
        equivalences=ctx.equivalences,
        cfg=ctx.cfg,
        sinsim_version=ctx.version,
        cases=ctx.cases,
    )
    _ = pp  # la red ya quedó persistida por build_case
    return built.case


@router.get("/cases/{case_id}", response_model=StudyCase)
def get_case(case_id: str, request: Request) -> StudyCase:
    """Devuelve un caso con su reporte de calidad (HU-2)."""
    return ctx_of(request).cases.get_case(case_id)
