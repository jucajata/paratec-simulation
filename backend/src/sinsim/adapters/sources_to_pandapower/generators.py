"""Unidades de generación de PARATEC → tabla `generators`.

- Hidráulicas y térmicas vienen por unidad (`HydraulicUnit`, `ThermalUnit`), con el nombre de
  su planta. Solares y eólicas vienen por planta; se modelan como una unidad por planta.
- `bus` sale de `connectionPoint` ("GUATAPE 220", "SAN ANTONIO (BOYACA) 115").
- `p_max_mw = ratedNetMaxP` (unidades) o `netEffectiveCapacity` (plantas renovables).
- Límites de reactiva: PARATEC publica magnitudes positivas de absorción (`minQ`) y
  generación (`maxQ`) a P máxima; en el modelo `min_q_mvar = −absorción` y
  `max_q_mvar = +generación`. Si faltan, el generador se conserva con Q libre y queda
  registrado en `missing_params` (no es un parámetro obligatorio para correr el flujo).
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
    parse_connection_point,
)

COLUMNS = [
    "unit_id",
    "unit",
    "plant",
    "bus",
    "substation",
    "vn_kv",
    "p_max_mw",
    "q_absorb_mvar",
    "q_gen_mvar",
    "tech",
    "state",
    "operation_mode",
    "source_id",
    "imputed",
    "imputation_method",
    "missing_params",
]


def _row(
    *,
    unit: str,
    plant: str,
    tech: str,
    rec: Mapping[str, Any],
    p_max: float | None,
    q_absorb: float | None,
    q_gen: float | None,
    source_id: str,
    declared: Declared,
) -> dict[str, Any]:
    missing: list[str] = []
    cp = parse_connection_point(to_text(rec.get("connectionPoint")))
    bus = sub = None
    vn_kv = None
    if cp and cp[0] in declared:
        sub, vn_kv = cp
        bus = canonical_bus_id(sub, vn_kv, declared)
    else:
        missing.append("bus")
    if p_max is None or p_max <= 0:
        missing.append("p_max_mw")
    if q_absorb is None or q_gen is None:
        missing.append("q_limits")
    return {
        "unit_id": f"{tech}:{unit}",
        "unit": unit,
        "plant": plant,
        "bus": bus,
        "substation": sub,
        "vn_kv": vn_kv,
        "p_max_mw": p_max,
        "q_absorb_mvar": q_absorb,
        "q_gen_mvar": q_gen,
        "tech": tech,
        "state": to_text(rec.get("elementStateName")),
        "operation_mode": to_text(rec.get("operationMode")),
        **quality_fields(source_id, missing),
    }


def parse_units(
    data: Iterable[Mapping[str, Any]], tech: str, plant_field: str, declared: Declared
) -> list[dict[str, Any]]:
    """Filas para unidades hidráulicas o térmicas."""
    rows = []
    for idx, rec in enumerate(data):
        unit = to_text(rec.get("elementName")) or f"{tech}-{idx}"
        rows.append(
            _row(
                unit=unit,
                plant=to_text(rec.get(plant_field)) or unit,
                tech=tech,
                rec=rec,
                p_max=to_float(rec.get("ratedNetMaxP")),
                q_absorb=to_float(rec.get("minQ")),
                q_gen=to_float(rec.get("maxQ")),
                source_id=f"{tech}:{idx}",
                declared=declared,
            )
        )
    return rows


def parse_plants(
    data: Iterable[Mapping[str, Any]], tech: str, q_fields: Mapping[str, str], declared: Declared
) -> list[dict[str, Any]]:
    """Filas para plantas solares o eólicas (una unidad equivalente por planta)."""
    absorb_key = next(k for k, v in q_fields.items() if v == "q_absorb_mvar")
    gen_key = next(k for k, v in q_fields.items() if v == "q_gen_mvar")
    rows = []
    for idx, rec in enumerate(data):
        plant = to_text(rec.get("elementName")) or f"{tech}-{idx}"
        rows.append(
            _row(
                unit=plant,
                plant=plant,
                tech=tech,
                rec=rec,
                p_max=to_float(rec.get("netEffectiveCapacity")),
                q_absorb=to_float(rec.get(absorb_key)),
                q_gen=to_float(rec.get(gen_key)),
                source_id=f"{tech}:{idx}",
                declared=declared,
            )
        )
    return rows


def parse_generators(
    hydraulic: Iterable[Mapping[str, Any]],
    thermal: Iterable[Mapping[str, Any]],
    solar: Iterable[Mapping[str, Any]],
    wind: Iterable[Mapping[str, Any]],
    declared: Declared,
) -> pd.DataFrame:
    """Construye la tabla `generators` con las cuatro tecnologías."""
    rows = [
        *parse_units(hydraulic, "hidráulica", fm.HYDRAULIC_PLANT_FIELD, declared),
        *parse_units(thermal, "térmica", fm.THERMAL_PLANT_FIELD, declared),
        *parse_plants(solar, "solar", fm.SOLAR_Q, declared),
        *parse_plants(wind, "eólica", fm.WIND_Q, declared),
    ]
    return pd.DataFrame(rows, columns=COLUMNS)


__all__ = ["COLUMNS", "parse_generators", "parse_plants", "parse_units"]
