"""Mapa base vectorial para la disposición geográfica (FR-035)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sinsim.api.routers.snapshots import ctx_of
from sinsim.domain.errors import DomainError

router = APIRouter(tags=["geo"])

BASEMAP_FILE = "colombia_departamentos.geojson"


@router.get("/geo/basemap")
def get_basemap(request: Request) -> JSONResponse:
    """Departamentos de Colombia (Natural Earth, dominio público) desde `data/geo/`."""
    path = ctx_of(request).paths.geo / BASEMAP_FILE
    if not path.exists():
        raise DomainError("BASEMAP_NOT_FOUND", f"no existe {path}")
    body: Any = json.loads(path.read_text(encoding="utf-8"))
    return JSONResponse(body, media_type="application/geo+json")
