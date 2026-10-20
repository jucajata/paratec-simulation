"""Compensación de PARATEC → tablas `shunts` y `svc_statcom`.

Convención de pandapower para `shunt.q_mvar` (constitución III.1): **positivo = inductivo**
(consume reactiva), **negativo = capacitivo**. Por eso un reactor de derivación entra con
`q_mvar = +nominalCapacity` y un condensador de derivación con `q_mvar = −ratedCapacity`.

La compensación **serie** (condensadores serie, SSSC) no se modela en esta feature; se
conserva en la tabla con `modeled = False` y el motivo, para el reporte de calidad.
Los SVC y STATCOM (derivación) se modelan como fuentes de reactiva (D-6) en `net_builder`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from sinsim.adapters.sources_to_pandapower import field_mapping as fm
from sinsim.adapters.sources_to_pandapower._common import quality_fields, to_float, to_text
from sinsim.adapters.sources_to_pandapower.buses import (
    Declared,
    canonical_bus_id,
    normalize_substation,
)

SHUNT_COLUMNS = [
    "shunt_id",
    "name",
    "substation",
    "bus",
    "vn_kv",
    "q_mvar",
    "kind",
    "modeled",
    "reason",
    "state",
    "source_id",
    "imputed",
    "imputation_method",
    "missing_params",
]
SVC_COLUMNS = [
    "id",
    "name",
    "substation",
    "bus",
    "vn_kv",
    "kind",
    "cap_mvar",
    "ind_mvar",
    "modeled",
    "reason",
    "state",
    "source_id",
    "imputed",
    "imputation_method",
    "missing_params",
]


def _bus(sub: str | None, kv: float | None, declared: Declared) -> str | None:
    norm = normalize_substation(sub) if sub else None
    return canonical_bus_id(norm, kv, declared) if norm and norm in declared and kv else None


def parse_shunts(
    reactors: Iterable[Mapping[str, Any]],
    capacitors: Iterable[Mapping[str, Any]],
    declared: Declared,
) -> pd.DataFrame:
    """Construye la tabla `shunts` con reactores y condensadores."""
    rows: list[dict[str, Any]] = []
    for idx, rec in enumerate(reactors):
        name = to_text(rec.get("elementName")) or f"reactor-{idx}"
        sub, kv, q = (
            to_text(rec.get("subStation")),
            to_float(rec.get("nomU")),
            to_float(rec.get("nominalCapacity")),
        )
        series = to_text(rec.get("compensatorType")) != fm.SHUNT_TYPE_PARALLEL
        missing = [k for k, v in (("bus", _bus(sub, kv, declared)), ("q_mvar", q)) if v is None]
        rows.append(
            {
                "shunt_id": f"reactor:{name}",
                "name": name,
                "substation": sub,
                "bus": _bus(sub, kv, declared),
                "vn_kv": kv,
                "q_mvar": q,
                "kind": "reactor",
                "modeled": not series and not missing,
                "reason": "compensación serie" if series else None,
                "state": to_text(rec.get("elementState")),
                **quality_fields(f"reactor:{idx}", missing),
            }
        )
    for idx, rec in enumerate(capacitors):
        name = to_text(rec.get("elementName")) or f"capacitor-{idx}"
        sub, kv, q = (
            to_text(rec.get("subStation")),
            to_float(rec.get("ratedVoltage")),
            to_float(rec.get("ratedCapacity")),
        )
        series = to_text(rec.get("compensationType")) != fm.SHUNT_TYPE_PARALLEL
        missing = [k for k, v in (("bus", _bus(sub, kv, declared)), ("q_mvar", q)) if v is None]
        rows.append(
            {
                "shunt_id": f"capacitor:{name}",
                "name": name,
                "substation": sub,
                "bus": _bus(sub, kv, declared),
                "vn_kv": kv,
                "q_mvar": -q if q is not None else None,
                "kind": "capacitor",
                "modeled": not series and not missing,
                "reason": "compensación serie" if series else None,
                "state": to_text(rec.get("elementState")),
                **quality_fields(f"capacitor:{idx}", missing),
            }
        )
    return pd.DataFrame(rows, columns=SHUNT_COLUMNS)


def parse_svc_statcom(data: Iterable[Mapping[str, Any]], declared: Declared) -> pd.DataFrame:
    """Construye la tabla `svc_statcom`; SSSC y otros equipos serie quedan `modeled = False`."""
    rows: list[dict[str, Any]] = []
    for idx, rec in enumerate(data):
        name = to_text(rec.get("elementNames")) or f"svc-{idx}"
        kind = (to_text(rec.get("elementType")) or "").upper()
        sub, kv = to_text(rec.get("substationName")), to_float(rec.get("nomVoltage"))
        cap, ind = to_float(rec.get("capacitiveRating")), to_float(rec.get("inductiveRating"))
        bus = _bus(sub, kv, declared)
        missing = [k for k, v in (("bus", bus), ("cap_mvar", cap), ("ind_mvar", ind)) if v is None]
        shunt_kind = kind in {"SVC", "STATCOM"}
        rows.append(
            {
                "id": f"{kind.lower() or 'svc'}:{name}",
                "name": name,
                "substation": sub,
                "bus": bus,
                "vn_kv": kv,
                "kind": kind,
                "cap_mvar": cap,
                "ind_mvar": ind,
                "modeled": shunt_kind and not missing,
                "reason": None if shunt_kind else f"compensación serie ({kind})",
                "state": to_text(rec.get("elementStateName")),
                **quality_fields(f"svc:{idx}", missing),
            }
        )
    return pd.DataFrame(rows, columns=SVC_COLUMNS)


__all__ = ["SHUNT_COLUMNS", "SVC_COLUMNS", "parse_shunts", "parse_svc_statcom"]
