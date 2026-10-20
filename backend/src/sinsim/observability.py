"""Logs estructurados en JSON con `trace_id` (constitución V).

El `trace_id` se guarda en un `ContextVar`, así que cada petición de la API y cada invocación
del CLI lo fijan una vez y todos los registros emitidos durante ese contexto lo incluyen.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")


def new_trace_id() -> str:
    """Genera y activa un `trace_id` nuevo para el contexto actual."""
    tid = uuid.uuid4().hex
    _trace_id.set(tid)
    return tid


def current_trace_id() -> str:
    """Devuelve el `trace_id` activo, o uno nuevo si no hay ninguno."""
    return _trace_id.get() or new_trace_id()


class JsonFormatter(logging.Formatter):
    """Formatea cada registro como una línea JSON con `trace_id`."""

    def format(self, record: logging.LogRecord) -> str:
        """Serializa el registro.

        Args:
            record: Registro de logging.

        Returns:
            Línea JSON con marca de tiempo, nivel, logger, mensaje, `trace_id` y extras.
        """
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": _trace_id.get() or None,
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Configura el logger raíz para emitir JSON a stderr (idempotente)."""
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(level)


def log_event(logger: logging.Logger, msg: str, **fields: Any) -> None:
    """Emite un registro INFO con campos estructurados adicionales."""
    logger.info(msg, extra={"extra_fields": fields})
