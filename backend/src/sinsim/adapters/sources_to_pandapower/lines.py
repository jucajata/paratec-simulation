"""Líneas de PARATEC → tabla `lines` en unidades de pandapower (constitución III.1).

Conversiones (documentadas aquí y probadas con valores conocidos):

- PARATEC da cada línea por tramos (`typeLines[]`) con R1 y X1 en Ω/km, B1 en µS/km y la
  longitud del tramo en km. Se agregan en serie:
  - `length_km = Σ lᵢ`
  - `r_ohm_per_km = Σ(rᵢ·lᵢ) / Σ lᵢ`, igual para X
  - `b_us_per_km = Σ(bᵢ·lᵢ) / Σ lᵢ`
- pandapower pide capacitancia en nF/km: `C = B / (2π f)`, con B en S/km y f = 60 Hz:
  `c_nf_per_km = b_us_per_km · 1e-6 / (2π·60) · 1e9 = b_us_per_km · 1e3 / (2π·60)`.
- Límite de corriente (D-4): `max_i_ka = ratedCurrent [A] / 1000`.

Extremos: primero el mapa de PARATEC (`sub1`/`sub2` por nombre de línea), luego el texto
`subStation` "A - B". Si ninguno resuelve dos subestaciones conocidas, la línea queda con
`missing_params = ["from_bus", "to_bus"]` y se excluye (FR-013).
"""

from __future__ import annotations

import math
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
from sinsim.domain.constants import F_HZ

COLUMNS = [
    "line_id",
    "name",
    "from_bus",
    "to_bus",
    "vn_kv",
    "length_km",
    "r_ohm_per_km",
    "x_ohm_per_km",
    "c_nf_per_km",
    "max_i_ka",
    "parallel",
    "state",
    "source_id",
    "imputed",
    "imputation_method",
    "missing_params",
]


def susceptance_to_capacitance_nf_per_km(b_us_per_km: float, f_hz: float = F_HZ) -> float:
    """Convierte susceptancia en µS/km a capacitancia en nF/km: `B·1e3 / (2π f)`."""
    return b_us_per_km * 1e3 / (2.0 * math.pi * f_hz)


def aggregate_segments(segments: Iterable[Mapping[str, Any]]) -> dict[str, float | None]:
    """Agrega los tramos de una línea en parámetros por km ponderados por longitud.

    Args:
        segments: Registros de `typeLines[]`.

    Returns:
        `length_km`, `r_ohm_per_km`, `x_ohm_per_km`, `c_nf_per_km`; `None` donde falte dato.
    """
    total = 0.0
    r_sum = x_sum = b_sum = 0.0
    r_ok = x_ok = b_ok = True
    for seg in segments:
        length = to_float(seg.get("length"))
        if not length or length <= 0:
            continue
        total += length
        r = to_float(seg.get("endurance"))
        x = to_float(seg.get("reactance"))
        b = to_float(seg.get("susceptance"))
        r_ok &= r is not None
        x_ok &= x is not None
        b_ok &= b is not None
        r_sum += (r or 0.0) * length
        x_sum += (x or 0.0) * length
        b_sum += (b or 0.0) * length
    if total <= 0:
        return {"length_km": None, "r_ohm_per_km": None, "x_ohm_per_km": None, "c_nf_per_km": None}
    return {
        "length_km": total,
        "r_ohm_per_km": r_sum / total if r_ok else None,
        "x_ohm_per_km": x_sum / total if x_ok else None,
        "c_nf_per_km": susceptance_to_capacitance_nf_per_km(b_sum / total) if b_ok else None,
    }


def parse_line_map(data: Iterable[Mapping[str, Any]]) -> dict[str, tuple[str, str]]:
    """Extrae `nombre de línea → (sub1, sub2)` del mapa de transmisión de PARATEC."""
    out: dict[str, tuple[str, str]] = {}
    for feature in data:
        props = feature.get("properties") or {}
        name = to_text(props.get("nameLine"))
        s1, s2 = to_text(props.get("sub1")), to_text(props.get("sub2"))
        if name and s1 and s2:
            out[name] = (s1, s2)
    return out


def resolve_endpoints(
    rec: Mapping[str, Any],
    line_map: Mapping[str, tuple[str, str]],
    known_substations: set[str],
) -> tuple[str, str] | None:
    """Resuelve las dos subestaciones de una línea; `None` si no se puede."""
    name = to_text(rec.get("name")) or ""
    if name in line_map:
        s1, s2 = (normalize_substation(s) for s in line_map[name])
        if s1 in known_substations and s2 in known_substations:
            return s1, s2
    parts = [normalize_substation(p) for p in (to_text(rec.get("subStation")) or "").split(" - ")]
    if len(parts) == 2 and all(p in known_substations for p in parts):
        return parts[0], parts[1]
    return None


def parse_lines(
    data: Iterable[Mapping[str, Any]],
    line_map: Mapping[str, tuple[str, str]],
    declared: Declared,
) -> pd.DataFrame:
    """Construye la tabla `lines` a partir de `Line/getAll`.

    Args:
        data: Registros de líneas.
        line_map: Extremos del mapa (`parse_line_map`).
        declared: Niveles declarados por subestación, para canonizar los `bus_id`.

    Returns:
        DataFrame con las columnas de `COLUMNS`.
    """
    known = set(declared)
    rows: list[dict[str, Any]] = []
    for idx, rec in enumerate(data):
        name = to_text(rec.get("name")) or f"line-{idx}"
        missing: list[str] = []
        vn_kv = to_float(rec.get("ratedVoltage"))
        if vn_kv is None:
            missing.append("vn_kv")
        ends = resolve_endpoints(rec, line_map, known)
        from_bus = to_bus = None
        if ends and vn_kv:
            from_bus = canonical_bus_id(ends[0], vn_kv, declared)
            to_bus = canonical_bus_id(ends[1], vn_kv, declared)
        else:
            missing += ["from_bus", "to_bus"]
        agg = aggregate_segments(rec.get("typeLines") or [])
        for key in ("length_km", "r_ohm_per_km", "x_ohm_per_km", "c_nf_per_km"):
            if agg[key] is None:
                missing.append(key)
        rated = to_float(rec.get("ratedCurrent"))
        if rated is None or rated <= 0:
            missing.append("max_i_ka")
        rows.append(
            {
                "line_id": f"line:{name}",
                "name": name,
                "from_bus": from_bus,
                "to_bus": to_bus,
                "vn_kv": vn_kv,
                "length_km": agg["length_km"],
                "r_ohm_per_km": agg["r_ohm_per_km"],
                "x_ohm_per_km": agg["x_ohm_per_km"],
                "c_nf_per_km": agg["c_nf_per_km"],
                "max_i_ka": (rated / 1000.0) if rated else None,
                "parallel": 1,
                "state": to_text(rec.get("state")),
                **quality_fields(f"line:{idx}", missing),
            }
        )
    return pd.DataFrame(rows, columns=COLUMNS)


__all__ = [
    "COLUMNS",
    "aggregate_segments",
    "parse_line_map",
    "parse_lines",
    "resolve_endpoints",
    "susceptance_to_capacitance_nf_per_km",
]

_ = fm  # el mapeo se consulta por nombre en las pruebas de contrato
