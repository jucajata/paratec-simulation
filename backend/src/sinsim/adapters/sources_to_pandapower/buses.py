"""Barras del modelo a partir de las subestaciones de PARATEC (FR-017).

Una barra es un par (subestación, clase de tensión). No se modelan secciones de barra ni
interruptores (research R6). El `bus_id` es `"<SUBESTACIÓN>|<kV de clase>"`.

Clases de tensión. En Colombia conviven dos convenciones de nombre para la misma red física:
EPM usa 110 y 220 kV donde ISA y otros usan 115 y 230 kV, y PARATEC además mezcla valores de
máxima tensión (112, 121,4, 238,2). Si cada valor fuera una barra distinta, una subestación
tendría barras "220" y "230" desconectadas y el anillo de transmisión quedaría partido; y si
cada línea uniera barras de 110 y 115 kV, pandapower la trataría como una relación ideal
1:1,045, y en una red mallada esos lazos con relación neta ≠ 1 hacen divergir el flujo.

Por eso el modelo usa **una base única por clase de tensión en toda la red**: 110/115 → 115,
220/230 → 230, 13,2/13,8 → 13,8, etc. (`class_kv`). La tensión nominal **declarada** por
PARATEC para cada barra se conserva en la columna `nominal_kv` y es la que se usa para los
límites en pu y para el reporte (una barra EPM de 110 kV sigue evaluándose contra 110 kV).
Los parámetros en Ω y las relaciones de los transformadores se refieren a esa base común, lo
que es eléctricamente exacto: la base por unidad es una convención, no una propiedad física.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from sinsim.adapters.sources_to_pandapower._common import fmt_kv, quality_fields, to_float
from sinsim.domain.constants import MIN_VN_KV_DEFAULT
from sinsim.domain.entities import VoltageLevel

_CONNECTION_POINT = re.compile(r"^(?P<sub>.+?)\s+(?P<kv>\d+(?:[.,]\d+)?)(?:\s*kV)?$", re.IGNORECASE)
_VOLTAGE_TAG = re.compile(r"^(?P<base>.+?)\s*\((?P<tag>[\d\s\-–.,/kKvV]+)\)\s*$")
_KV_TOLERANCE = 0.10


def normalize_substation(name: str) -> str:
    """Quita de un nombre de subestación un sufijo entre paréntesis que solo contiene tensiones.

    PARATEC publica una misma subestación física como varias entradas con el nivel de tensión
    en el nombre ("CERROMATOSO (230)", "CERROMATOSO (500 - 110)", "LA VIRGINIA (115)"). Si se
    respetaran, el transformador 500/230 y las líneas de 500 kV quedarían en "subestaciones"
    distintas y nunca se tocarían. Las etiquetas de propietario o región ("ANCON SUR (EPM)",
    "BARBOSA (SANTANDER)") no son tensiones y se conservan.
    """
    text = name.strip()
    match = _VOLTAGE_TAG.match(text)
    return match.group("base").strip() if match else text


STANDARD_KV: tuple[float, ...] = (
    13.2,
    13.8,
    34.5,
    44.0,
    57.5,
    66.0,
    110.0,
    115.0,
    138.0,
    220.0,
    230.0,
    500.0,
)
"""Tensiones nominales estándar del SIN que PARATEC utiliza."""

CLASS_OF: dict[float, float] = {
    13.2: 13.8,
    13.8: 13.8,
    34.5: 34.5,
    44.0: 44.0,
    57.5: 57.5,
    66.0: 66.0,
    110.0: 115.0,
    115.0: 115.0,
    138.0: 138.0,
    220.0: 230.0,
    230.0: 230.0,
    500.0: 500.0,
}
"""Nominal estándar → base de clase usada en el modelo."""

Declared = Mapping[str, tuple[float, ...]]
Nominals = Mapping[str, Mapping[float, float]]


def nominal_kv(kv: float) -> float:
    """Nominal estándar más cercano a `kv` si difiere menos del 10 %; si no, `kv`."""
    nearest = min(STANDARD_KV, key=lambda s: abs(s - kv))
    return nearest if abs(nearest - kv) <= _KV_TOLERANCE * max(kv, 1e-9) else kv


def class_kv(kv: float) -> float:
    """Base de clase de una tensión (110/115 → 115, 220/230 → 230, …)."""
    nominal = nominal_kv(kv)
    return CLASS_OF.get(nominal, round(kv, 1))


def level_for(vn_kv: float) -> VoltageLevel:
    """Clasifica una tensión en STN (≥ 220), STR (≥ 57,5) o SDL."""
    if vn_kv >= 220.0:
        return "STN"
    if vn_kv >= MIN_VN_KV_DEFAULT:
        return "STR"
    return "SDL"


def parse_substations(data: Iterable[Mapping[str, Any]]) -> dict[str, tuple[float, ...]]:
    """Extrae las clases de tensión declaradas por subestación.

    Args:
        data: Registros de `Substation/SubstationInfo`.

    Returns:
        Diccionario nombre de subestación → bases de clase presentes, ordenadas.
    """
    declared: dict[str, set[float]] = {}
    for rec in data:
        name = normalize_substation(str(rec.get("elementName", "")))
        if not name:
            continue
        levels = [kv for kv in (to_float(v) for v in rec.get("voltageLevel") or []) if kv]
        declared.setdefault(name, set()).update(class_kv(kv) for kv in levels)
    return {name: tuple(sorted(levels)) for name, levels in declared.items()}


def parse_nominal_levels(data: Iterable[Mapping[str, Any]]) -> dict[str, dict[float, float]]:
    """Tensión nominal declarada por PARATEC para cada (subestación, clase).

    Si una subestación declara varios valores de la misma clase (110 y 115), se conserva el
    nominal estándar más bajo.
    """
    out: dict[str, dict[float, float]] = {}
    for rec in data:
        name = normalize_substation(str(rec.get("elementName", "")))
        if not name:
            continue
        per_class = out.setdefault(name, {})
        for raw in rec.get("voltageLevel") or []:
            kv = to_float(raw)
            if not kv:
                continue
            cls, nom = class_kv(kv), nominal_kv(kv)
            per_class[cls] = min(per_class.get(cls, nom), nom)
    return out


def canonical_kv(substation: str, kv: float, declared: Declared) -> float:
    """Base de clase de `kv` (la subestación no altera el resultado; se mantiene por contrato)."""
    _ = substation, declared
    return class_kv(kv)


def bus_id(substation: str, kv: float) -> str:
    """Construye el identificador `"<SUBESTACIÓN>|<kV>"`."""
    return f"{substation}|{fmt_kv(kv)}"


def canonical_bus_id(substation: str, kv: float, declared: Declared) -> str:
    """`bus_id` con el nombre normalizado y la tensión llevada a su base de clase."""
    return bus_id(normalize_substation(substation), canonical_kv(substation, kv, declared))


def parse_connection_point(text: str | None) -> tuple[str, float] | None:
    """Parsea un punto de conexión de PARATEC como `"GUATAPE 220"` o `"CAÑO LIMON 34.5"`.

    Args:
        text: Texto libre de PARATEC.

    Returns:
        `(subestación, kV)` o `None` si no se puede interpretar.
    """
    if not text:
        return None
    match = _CONNECTION_POINT.match(text.strip())
    if not match:
        return None
    kv = to_float(match.group("kv"))
    if kv is None or kv <= 0:
        return None
    return normalize_substation(match.group("sub")), kv


def build_buses_table(
    declared: Declared, used_bus_ids: Iterable[str], nominals: Nominals | None = None
) -> pd.DataFrame:
    """Construye la tabla `buses` con las clases declaradas y las usadas por otros elementos.

    Args:
        declared: Clases por subestación (`parse_substations`).
        used_bus_ids: Identificadores de barra que referencian líneas, transformadores,
            generadores y compensación (pueden incluir clases SDL no declaradas).
        nominals: Nominal declarado por (subestación, clase) (`parse_nominal_levels`).

    Returns:
        DataFrame con `bus_id`, `substation`, `vn_kv` (base de clase), `nominal_kv`, `level`
        y columnas de calidad.
    """
    nominals = nominals or {}
    ids: dict[str, tuple[str, float]] = {}
    for sub, levels in declared.items():
        for kv in levels:
            ids[bus_id(sub, kv)] = (sub, kv)
    for bid in used_bus_ids:
        if bid in ids:
            continue
        sub, _, kv_text = bid.rpartition("|")
        used_kv = to_float(kv_text)
        if sub and used_kv:
            ids[bid] = (sub, used_kv)
    rows = [
        {
            "bus_id": bid,
            "substation": sub,
            "vn_kv": kv,
            "nominal_kv": nominals.get(sub, {}).get(kv, nominal_kv(kv)),
            "level": level_for(kv),
            **quality_fields(f"substation:{sub}", []),
        }
        for bid, (sub, kv) in sorted(ids.items())
    ]
    return pd.DataFrame(rows, columns=_COLUMNS)


_COLUMNS = [
    "bus_id",
    "substation",
    "vn_kv",
    "nominal_kv",
    "level",
    "source_id",
    "imputed",
    "imputation_method",
    "missing_params",
]

__all__ = [
    "CLASS_OF",
    "STANDARD_KV",
    "build_buses_table",
    "bus_id",
    "canonical_bus_id",
    "canonical_kv",
    "class_kv",
    "level_for",
    "nominal_kv",
    "normalize_substation",
    "parse_connection_point",
    "parse_nominal_levels",
    "parse_substations",
]
