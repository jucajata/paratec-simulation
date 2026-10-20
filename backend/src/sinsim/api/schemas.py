"""Esquemas de entrada de la API (contracts/openapi.yaml). Las salidas son las entidades."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from sinsim.domain.entities import FlowType


class CaseRequest(BaseModel):
    """Cuerpo de `POST /api/cases`."""

    model_config = ConfigDict(extra="forbid")

    snapshot_date: date
    dispatch_date: date | None = None
    period: int = Field(ge=1, le=24)


class RunRequest(BaseModel):
    """Cuerpo de `POST /api/cases/{case_id}/runs`."""

    model_config = ConfigDict(extra="forbid")

    flow_type: FlowType
