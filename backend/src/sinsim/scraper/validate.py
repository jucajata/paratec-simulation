"""Validación de esquema de las fuentes y de las tablas normalizadas (FR-005).

Segundo punto de validación de la constitución V. Cualquier fallo lanza un `DomainError`
con código 4 (`PARATEC_SCHEMA_CHANGED` o `XM_FILE_SCHEMA_CHANGED`) y la entidad afectada.
"""

from __future__ import annotations

import json
from typing import Any

from sinsim.adapters.sources_to_pandapower import (
    buses,
    generators,
    lines,
    shunts,
    trafos,
    xm_demand,
    xm_dispatch,
)
from sinsim.adapters.sources_to_pandapower import field_mapping as fm
from sinsim.domain.constants import PERIODS_PER_DAY
from sinsim.domain.entities import SnapshotTables
from sinsim.domain.errors import DomainError

EXPECTED_COLUMNS: dict[str, list[str]] = {
    "buses": ["bus_id", "substation", "vn_kv", "nominal_kv", "level"],
    "lines": lines.COLUMNS,
    "trafos2w": trafos.COLUMNS_2W,
    "trafos3w": trafos.COLUMNS_3W,
    "generators": generators.COLUMNS,
    "shunts": shunts.SHUNT_COLUMNS,
    "svc_statcom": shunts.SVC_COLUMNS,
    "dispatch": xm_dispatch.COLUMNS,
    "demand": xm_demand.COLUMNS,
}


def parse_paratec_response(entity: str, payload: bytes) -> list[dict[str, Any]]:
    """Valida la envoltura `{"header": ..., "data": [...]}` de PARATEC y devuelve `data`.

    Raises:
        DomainError: `PARATEC_SCHEMA_CHANGED` si el JSON no tiene esa forma.
    """
    code = "PARATEC_SCHEMA_CHANGED"
    try:
        doc = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DomainError(code, f"{entity}: la respuesta no es JSON válido") from exc
    if not isinstance(doc, dict) or fm.RESPONSE_DATA not in doc or fm.RESPONSE_HEADER not in doc:
        raise DomainError(code, f"{entity}: faltan las claves 'header' y 'data'")
    data = doc[fm.RESPONSE_DATA]
    if not isinstance(data, list) or (data and not isinstance(data[0], dict)):
        raise DomainError(code, f"{entity}: 'data' no es una lista de registros")
    if not data:
        raise DomainError("PARATEC_SCHEMA_CHANGED", f"{entity}: 'data' está vacío")
    return data


def validate_tables(tables: SnapshotTables) -> None:
    """Verifica las invariantes estructurales de las tablas normalizadas.

    Raises:
        DomainError: `PARATEC_SCHEMA_CHANGED` o `XM_FILE_SCHEMA_CHANGED` según la tabla.
    """
    for name, expected in EXPECTED_COLUMNS.items():
        df = getattr(tables, name)
        missing = [c for c in expected if c not in df.columns]
        if missing:
            xm = name in {"dispatch", "demand"}
            code = "XM_FILE_SCHEMA_CHANGED" if xm else "PARATEC_SCHEMA_CHANGED"
            raise DomainError(code, f"tabla {name}: faltan columnas {missing}")
    if tables.buses.empty or tables.lines.empty:
        raise DomainError("PARATEC_SCHEMA_CHANGED", "no se obtuvieron barras o líneas")
    if tables.buses.bus_id.duplicated().any():
        raise DomainError("PARATEC_SCHEMA_CHANGED", "bus_id duplicado en la tabla buses")
    for name in ("dispatch", "demand"):
        df = getattr(tables, name)
        if df.empty:
            raise DomainError("XM_FILE_SCHEMA_CHANGED", f"tabla {name} vacía")
        periods = set(df.period.unique().tolist())
        if periods != set(range(1, PERIODS_PER_DAY + 1)):
            raise DomainError("XM_FILE_SCHEMA_CHANGED", f"tabla {name}: periodos {sorted(periods)}")
    counts = tables.dispatch.groupby("resource").size()
    if (counts != PERIODS_PER_DAY).any():
        raise DomainError("XM_FILE_SCHEMA_CHANGED", "dispatch: un recurso no tiene 24 periodos")
    counts = tables.demand.groupby(["node", "vn_kv"]).size()
    if (counts != PERIODS_PER_DAY).any():
        raise DomainError("XM_FILE_SCHEMA_CHANGED", "demand: un nodo no tiene 24 periodos")
    for name, cols in (("dispatch", ["p_mw"]), ("demand", ["p_act_mw", "p_pstr_mw", "q_mvar"])):
        df = getattr(tables, name)
        if df[cols].isna().any().any():
            raise DomainError("XM_FILE_SCHEMA_CHANGED", f"{name}: valores no numéricos")
    levels = set(tables.buses.level.unique().tolist())
    if not levels <= {"STN", "STR", "SDL"}:
        raise DomainError("PARATEC_SCHEMA_CHANGED", f"buses: niveles inesperados {levels}")
    _ = buses  # referencia para las pruebas de contrato
