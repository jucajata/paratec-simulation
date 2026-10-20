"""Identificador de un caso: SHA-256 del JSON canónico de sus entradas (data-model.md §4).

El hash no incluye el JSON de pandapower (que cambia tras cada flujo) sino las entradas que
determinan el caso: fechas, periodo, checksum del manifiesto, de las equivalencias y de la
configuración, y la versión de `sinsim`.
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel


def canonical_json(model: BaseModel) -> str:
    """Serializa un modelo con claves ordenadas, sin espacios y con floats en `repr`."""
    return json.dumps(
        model.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def case_id_for(model: BaseModel) -> str:
    """SHA-256 hexadecimal del JSON canónico."""
    return hashlib.sha256(canonical_json(model).encode("utf-8")).hexdigest()
