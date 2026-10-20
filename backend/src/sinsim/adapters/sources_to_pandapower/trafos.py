"""Transformadores de PARATEC → tablas `trafos2w` y `trafos3w` (constitución III.1).

Reglas (research R6, decisiones del usuario del 2026-10-20):

- Las impedancias % de PARATEC (`impedanceHighLowNom`, `...HighMediumNom`,
  `...MediumLowNom`) entran **sin convertir**, en la convención de pandapower:
  2 devanados `vk_percent = HL`; 3 devanados `vk_hv = HM`, `vk_mv = ML`, `vk_lv = HL`.
- Pérdidas de cobre en kW → `vkr_percent = P_cu / (S_base · 1000) · 100`, con `S_base` la
  base que usa pandapower: `sn_mva` en 2 devanados y `min(S_a, S_b)` del par en 3 devanados.
- `pfe_kw = ironLosses`; `i0_percent = 0` (D-2, PARATEC no lo publica).
- Taps: `tap_min = lowStep`, `tap_max = highStep`, `tap_neutral = tap_pos = normalStep`,
  `tap_step_percent = ±step`. El signo se deduce de los datos: si la tensión del paso bajo
  (`lowStepU`) es mayor que la del paso alto (`highStepU`), un paso mayor reduce la tensión y
  el signo es negativo. El tap va en el devanado cuya tensión coincide con `neutralU` (por
  defecto, el de alta).
- Un "Tridevanado" con solo dos devanados en `windingsList` (terciario de compensación no
  conectado) se modela como transformador de dos devanados.
- "-" y "N/A" son parámetros faltantes (`missing_params`).
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

TAP_COLUMNS = ["tap_side", "tap_min", "tap_max", "tap_neutral", "tap_pos", "tap_step_percent"]
COMMON = ["state", "source_id", "imputed", "imputation_method", "missing_params"]
COLUMNS_2W = [
    "trafo_id",
    "name",
    "substation",
    "hv_bus",
    "lv_bus",
    "sn_mva",
    "vn_hv_kv",
    "vn_lv_kv",
    "vk_percent",
    "vkr_percent",
    "pfe_kw",
    "i0_percent",
    *TAP_COLUMNS,
    *COMMON,
]
COLUMNS_3W = [
    "trafo_id",
    "name",
    "substation",
    "hv_bus",
    "mv_bus",
    "lv_bus",
    "sn_hv_mva",
    "sn_mv_mva",
    "sn_lv_mva",
    "vn_hv_kv",
    "vn_mv_kv",
    "vn_lv_kv",
    "vk_hv_percent",
    "vk_mv_percent",
    "vk_lv_percent",
    "vkr_hv_percent",
    "vkr_mv_percent",
    "vkr_lv_percent",
    "pfe_kw",
    "i0_percent",
    *TAP_COLUMNS,
    *COMMON,
]


def copper_losses_to_vkr_percent(p_cu_kw: float, s_base_mva: float) -> float:
    """`vkr_percent = P_cu[kW] / (S_base[MVA]·1000) · 100`."""
    return p_cu_kw / (s_base_mva * 1000.0) * 100.0


def parse_windings(rec: Mapping[str, Any]) -> list[tuple[float, float]]:
    """Devuelve `[(vn_kv, sn_mva), ...]` ordenado de mayor a menor tensión."""
    out: list[tuple[float, float]] = []
    for w in rec.get("windingsList") or []:
        kv, sn = to_float(w.get("nomVoltage")), to_float(w.get("nomCapacity"))
        if kv and sn:
            out.append((kv, sn))
    return sorted(out, key=lambda t: -t[0])


def tap_fields(rec: Mapping[str, Any], windings: list[tuple[float, float]]) -> dict[str, Any]:
    """Campos del cambiador de tomas; sin cambiador si falta el paso o el rango."""
    step = to_float(rec.get("step"))
    tap_min, tap_max, neutral = (
        to_float(rec.get(k)) for k in ("lowStep", "highStep", "normalStep")
    )
    if step is None or tap_min is None or tap_max is None or neutral is None:
        return dict.fromkeys(TAP_COLUMNS)
    low_u, high_u = to_float(rec.get("lowStepU")), to_float(rec.get("highStepU"))
    sign = -1.0 if (low_u is not None and high_u is not None and low_u > high_u) else 1.0
    side = "hv"
    neutral_u = to_float(rec.get("neutralU"))
    if neutral_u is not None and len(windings) >= 2:
        closest = min(range(len(windings)), key=lambda i: abs(windings[i][0] - neutral_u))
        side = ("hv", "mv", "lv")[closest] if len(windings) == 3 else ("hv", "lv")[min(closest, 1)]
    return {
        "tap_side": side,
        "tap_min": int(tap_min),
        "tap_max": int(tap_max),
        "tap_neutral": int(neutral),
        "tap_pos": int(neutral),
        "tap_step_percent": sign * step,
    }


def parse_transformers(
    data: Iterable[Mapping[str, Any]], declared: Declared
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Construye `trafos2w` y `trafos3w` desde `PowerTransformer/PowerTransformerInfo`.

    Args:
        data: Registros de transformadores.
        declared: Niveles declarados por subestación (canonización de `bus_id`).

    Returns:
        `(trafos2w, trafos3w)`.
    """
    rows2: list[dict[str, Any]] = []
    rows3: list[dict[str, Any]] = []
    for idx, rec in enumerate(data):
        name = to_text(rec.get("elementName")) or f"trafo-{idx}"
        raw_sub = to_text(rec.get("substationName"))
        sub = normalize_substation(raw_sub) if raw_sub else None
        windings = parse_windings(rec)
        missing: list[str] = []
        if not sub or sub not in declared:
            missing.append("substation")
        pfe = to_float(rec.get("ironLosses"))
        if pfe is None:
            missing.append("pfe_kw")
        base: dict[str, Any] = {
            "trafo_id": f"trafo:{name}",
            "name": name,
            "substation": sub,
            "pfe_kw": pfe,
            "i0_percent": 0.0,
            **tap_fields(rec, windings),
            "state": to_text(rec.get("elementStateName")),
        }
        if len(windings) == 2:
            (hv_kv, hv_sn), (lv_kv, lv_sn) = windings
            sn = min(hv_sn, lv_sn)
            vk = to_float(rec.get("impedanceHighLowNom"))
            pcu = to_float(rec.get("highLowCopperLosses"))
            if vk is None:
                missing.append("vk_percent")
            if pcu is None:
                missing.append("vkr_percent")
            rows2.append(
                {
                    **base,
                    "hv_bus": canonical_bus_id(sub, hv_kv, declared) if sub else None,
                    "lv_bus": canonical_bus_id(sub, lv_kv, declared) if sub else None,
                    "sn_mva": sn,
                    "vn_hv_kv": hv_kv,
                    "vn_lv_kv": lv_kv,
                    "vk_percent": vk,
                    "vkr_percent": copper_losses_to_vkr_percent(pcu, sn)
                    if pcu is not None
                    else None,
                    **quality_fields(f"trafo:{idx}", missing),
                }
            )
        elif len(windings) == 3:
            (hv_kv, hv_sn), (mv_kv, mv_sn), (lv_kv, lv_sn) = windings
            vk_hm = to_float(rec.get("impedanceHighMediumNom"))
            vk_ml = to_float(rec.get("impedanceMediumLowNom"))
            vk_hl = to_float(rec.get("impedanceHighLowNom"))
            pcu_hm = to_float(rec.get("highMediumCopperLosses"))
            pcu_ml = to_float(rec.get("mediumLowCopperLosses"))
            pcu_hl = to_float(rec.get("highLowCopperLosses"))
            for key, val in (
                ("vk_hv_percent", vk_hm),
                ("vk_mv_percent", vk_ml),
                ("vk_lv_percent", vk_hl),
            ):
                if val is None:
                    missing.append(key)
            for key, val in (
                ("vkr_hv_percent", pcu_hm),
                ("vkr_mv_percent", pcu_ml),
                ("vkr_lv_percent", pcu_hl),
            ):
                if val is None:
                    missing.append(key)
            rows3.append(
                {
                    **base,
                    "hv_bus": canonical_bus_id(sub, hv_kv, declared) if sub else None,
                    "mv_bus": canonical_bus_id(sub, mv_kv, declared) if sub else None,
                    "lv_bus": canonical_bus_id(sub, lv_kv, declared) if sub else None,
                    "sn_hv_mva": hv_sn,
                    "sn_mv_mva": mv_sn,
                    "sn_lv_mva": lv_sn,
                    "vn_hv_kv": hv_kv,
                    "vn_mv_kv": mv_kv,
                    "vn_lv_kv": lv_kv,
                    "vk_hv_percent": vk_hm,
                    "vk_mv_percent": vk_ml,
                    "vk_lv_percent": vk_hl,
                    "vkr_hv_percent": (
                        copper_losses_to_vkr_percent(pcu_hm, min(hv_sn, mv_sn))
                        if pcu_hm is not None
                        else None
                    ),
                    "vkr_mv_percent": (
                        copper_losses_to_vkr_percent(pcu_ml, min(mv_sn, lv_sn))
                        if pcu_ml is not None
                        else None
                    ),
                    "vkr_lv_percent": (
                        copper_losses_to_vkr_percent(pcu_hl, min(hv_sn, lv_sn))
                        if pcu_hl is not None
                        else None
                    ),
                    **quality_fields(f"trafo:{idx}", missing),
                }
            )
        else:
            missing.append("windings")
            rows2.append(
                {
                    **base,
                    "hv_bus": None,
                    "lv_bus": None,
                    "sn_mva": None,
                    "vn_hv_kv": None,
                    "vn_lv_kv": None,
                    "vk_percent": None,
                    "vkr_percent": None,
                    **quality_fields(f"trafo:{idx}", missing),
                }
            )
    return pd.DataFrame(rows2, columns=COLUMNS_2W), pd.DataFrame(rows3, columns=COLUMNS_3W)


__all__ = [
    "COLUMNS_2W",
    "COLUMNS_3W",
    "copper_losses_to_vkr_percent",
    "parse_transformers",
    "parse_windings",
    "tap_fields",
]

_ = fm
