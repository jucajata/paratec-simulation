"""`GET /api/snapshots` (FR-002)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from sinsim.bootstrap import AppContext
from sinsim.domain.entities import SnapshotSummary
from sinsim.services import snapshots as snapshot_service

router = APIRouter(tags=["snapshots"])


def ctx_of(request: Request) -> AppContext:
    """Contexto de la aplicación."""
    ctx: AppContext = request.app.state.ctx
    return ctx


@router.get("/snapshots", response_model=list[SnapshotSummary])
def list_snapshots(request: Request) -> list[SnapshotSummary]:
    """Lista las fechas disponibles y qué datos tiene cada una."""
    return snapshot_service.list_snapshots(ctx_of(request).snapshots)
