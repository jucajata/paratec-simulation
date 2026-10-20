"""Problem Details RFC 9457 extendido (constitución V)."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from sinsim.domain.errors import CATALOG, DomainError

ERROR_TYPE_BASE = "https://github.com/jucajata/paratec-simulation/errors/"
MEDIA_TYPE = "application/problem+json"


def problem_body(
    *, code: str, status: int, title: str, detail: str, user_message: str, trace_id: str
) -> dict[str, Any]:
    """Cuerpo de un Problem Details con los campos extendidos del proyecto."""
    return {
        "type": ERROR_TYPE_BASE + code.lower().replace("_", "-"),
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "user_message": user_message,
        "trace_id": trace_id,
    }


def problem_response(
    *, code: str, status: int, title: str, detail: str, user_message: str, trace_id: str
) -> JSONResponse:
    """Respuesta HTTP `application/problem+json`."""
    body = problem_body(
        code=code,
        status=status,
        title=title,
        detail=detail,
        user_message=user_message,
        trace_id=trace_id,
    )
    return JSONResponse(status_code=status, content=body, media_type=MEDIA_TYPE)


def from_domain_error(exc: DomainError, trace_id: str) -> JSONResponse:
    """Convierte un `DomainError` del catálogo en Problem Details."""
    return problem_response(
        code=exc.code,
        status=exc.http_status,
        title=exc.title,
        detail=exc.detail,
        user_message=exc.user_message,
        trace_id=trace_id,
    )


def internal_error(trace_id: str) -> JSONResponse:
    """500 sin stack trace; solo el `trace_id` para buscar en los logs."""
    spec = CATALOG["INTERNAL_ERROR"]
    return problem_response(
        code=spec.code,
        status=spec.http_status,
        title=spec.title,
        detail="Consulta los logs con el trace_id.",
        user_message=spec.user_message,
        trace_id=trace_id,
    )
