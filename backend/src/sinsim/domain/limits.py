"""Límites operativos y detección de violaciones (FR-031, constitución III.9).

Funciones puras. Los valores y sus fuentes vienen de `config/defaults.toml`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sinsim.domain.entities import LimitInfo


@dataclass(frozen=True)
class VoltageBand:
    """Banda de tensión admisible para un rango de tensión nominal `[vn_kv_min, vn_kv_max)`."""

    name: str
    vn_kv_min: float
    vn_kv_max: float
    vm_min_pu: float
    vm_max_pu: float
    source: str


@dataclass(frozen=True)
class LoadingLimit:
    """Cargabilidad máxima en % del valor nominal."""

    max_percent: float
    source: str


def band_for(vn_kv: float, bands: Sequence[VoltageBand]) -> VoltageBand | None:
    """Primera banda cuyo rango de tensión nominal contiene `vn_kv`."""
    for band in bands:
        if band.vn_kv_min <= vn_kv < band.vn_kv_max:
            return band
    return None


def bus_violation(
    vm_pu: float, vn_kv: float, bands: Sequence[VoltageBand]
) -> Literal["low", "high"] | None:
    """`"low"` si `vm_pu` está por debajo del mínimo, `"high"` si supera el máximo, o `None`."""
    band = band_for(vn_kv, bands)
    if band is None:
        return None
    if vm_pu < band.vm_min_pu:
        return "low"
    if vm_pu > band.vm_max_pu:
        return "high"
    return None


def branch_overload(loading_percent: float, limit: LoadingLimit) -> bool:
    """`True` si la cargabilidad supera el límite."""
    return loading_percent > limit.max_percent


def limit_infos(bands: Sequence[VoltageBand], loading: LoadingLimit) -> list[LimitInfo]:
    """Describe los límites aplicados, con su fuente, para el resumen y la exportación."""
    infos = [
        LimitInfo(
            name=f"Tensión {b.name}",
            value=f"{b.vm_min_pu:.2f}–{b.vm_max_pu:.2f} pu",
            source=b.source,
        )
        for b in bands
    ]
    infos.append(
        LimitInfo(name="Cargabilidad", value=f"{loading.max_percent:g} %", source=loading.source)
    )
    return infos
