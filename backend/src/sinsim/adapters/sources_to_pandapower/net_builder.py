"""Arma el `pandapowerNet` a partir de las tablas del modelo (constitución IV).

El objeto `pandapowerNet` solo se crea y muta aquí y en `services/`. Todos los elementos
llevan en `name` su identificador de dominio para mapear resultados.

Modelado (research R5, R6; D-2, D-6):
- Generador despachado → `gen` PV con `p_mw` programado, `vm_pu` = consigna, límites de Q y
  `slack_weight = p_mw` (referencia distribuida, FR-015). El generador de la barra de ángulo
  lleva `slack=True`.
- SVC/STATCOM → `gen` con `p_mw = 0`, `slack_weight = 0`, `min_q = −inductivo`,
  `max_q = +capacitivo` y la misma consigna.
- Enlace internacional → `sgen` de P fija (NG-11).
- Carga → `load` con `p_mw = Ener.Act. + Perd.PSTR`, `q_mvar = Ener.Reac`; los componentes
  `p_act_mw` y `p_pstr_mw` se conservan como columnas extra (FR-014).
- Reactor/condensador → `shunt` con el signo de pandapower.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandapower as pp
import pandas as pd


@dataclass(frozen=True)
class ModelTables:
    """Tablas ya filtradas y conciliadas que entran al modelo.

    Columnas mínimas:
        buses: bus_id, vn_kv (opcionales: nominal_kv, subarea, lat, lon)
        lines: line_id, from_bus, to_bus, length_km, r_ohm_per_km, x_ohm_per_km, c_nf_per_km,
            max_i_ka, parallel
        trafos2w: trafo_id, hv_bus, lv_bus, sn_mva, vn_hv_kv, vn_lv_kv, vk_percent,
            vkr_percent, pfe_kw, i0_percent, tap_side, tap_min, tap_max, tap_neutral, tap_pos,
            tap_step_percent
        trafos3w: trafo_id, hv_bus, mv_bus, lv_bus, sn_*_mva, vn_*_kv, vk_*_percent,
            vkr_*_percent, pfe_kw, i0_percent, taps
        gens: gen_id, resource, bus, p_mw, p_max_mw, min_q_mvar, max_q_mvar, vm_pu,
            slack_weight, is_angle_ref
        compensators: gen_id, bus, min_q_mvar, max_q_mvar, vm_pu   (SVC/STATCOM)
        sgens: sgen_id, resource, bus, p_mw
        shunts: shunt_id, bus, q_mvar
        loads: load_id, bus, p_mw, q_mvar (opcionales: p_act_mw, p_pstr_mw)
    """

    buses: pd.DataFrame
    lines: pd.DataFrame
    trafos2w: pd.DataFrame
    trafos3w: pd.DataFrame
    gens: pd.DataFrame
    compensators: pd.DataFrame
    sgens: pd.DataFrame
    shunts: pd.DataFrame
    loads: pd.DataFrame


def _f(value: object) -> float:
    """Convierte a float; NaN si el valor no es numérico."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return math.nan


def _subarea(value: object) -> str | None:
    """Subárea de PARATEC o `None` si falta (FR-034); nunca se infiere."""
    return value if isinstance(value, str) and value.strip() else None


def _tap_kwargs(row: pd.Series) -> dict[str, object]:
    if not isinstance(row.get("tap_side"), str):
        return {}
    return {
        "tap_side": row["tap_side"],
        "tap_min": int(row["tap_min"]),
        "tap_max": int(row["tap_max"]),
        "tap_neutral": int(row["tap_neutral"]),
        "tap_pos": int(row["tap_pos"]),
        "tap_step_percent": float(row["tap_step_percent"]),
    }


def build_net(model: ModelTables, f_hz: float, sn_mva: float) -> pp.pandapowerNet:
    """Construye la red pandapower.

    Args:
        model: Tablas del modelo.
        f_hz: Frecuencia del sistema (constante de dominio).
        sn_mva: Potencia base (constante de dominio).

    Returns:
        Red lista para `runpp`/`rundcpp`.
    """
    net = pp.create_empty_network(f_hz=f_hz, sn_mva=sn_mva)
    bus_idx: dict[str, int] = {}
    for _, b in model.buses.iterrows():
        bus_idx[str(b.bus_id)] = pp.create_bus(
            net,
            vn_kv=float(b.vn_kv),
            name=str(b.bus_id),
            nominal_kv=float(b.get("nominal_kv", b.vn_kv)),
            subarea=_subarea(b.get("subarea")),
            lat=_f(b.get("lat")),
            lon=_f(b.get("lon")),
        )

    for _, ln in model.lines.iterrows():
        pp.create_line_from_parameters(
            net,
            from_bus=bus_idx[ln.from_bus],
            to_bus=bus_idx[ln.to_bus],
            length_km=float(ln.length_km),
            r_ohm_per_km=float(ln.r_ohm_per_km),
            x_ohm_per_km=float(ln.x_ohm_per_km),
            c_nf_per_km=float(ln.c_nf_per_km),
            max_i_ka=float(ln.max_i_ka),
            parallel=int(ln.get("parallel", 1) or 1),
            name=str(ln.line_id),
        )

    for _, t in model.trafos2w.iterrows():
        pp.create_transformer_from_parameters(
            net,
            hv_bus=bus_idx[t.hv_bus],
            lv_bus=bus_idx[t.lv_bus],
            sn_mva=float(t.sn_mva),
            vn_hv_kv=float(t.vn_hv_kv),
            vn_lv_kv=float(t.vn_lv_kv),
            vkr_percent=float(t.vkr_percent),
            vk_percent=float(t.vk_percent),
            pfe_kw=float(t.pfe_kw),
            i0_percent=float(t.i0_percent),
            name=str(t.trafo_id),
            **_tap_kwargs(t),
        )

    for _, t in model.trafos3w.iterrows():
        pp.create_transformer3w_from_parameters(
            net,
            hv_bus=bus_idx[t.hv_bus],
            mv_bus=bus_idx[t.mv_bus],
            lv_bus=bus_idx[t.lv_bus],
            sn_hv_mva=float(t.sn_hv_mva),
            sn_mv_mva=float(t.sn_mv_mva),
            sn_lv_mva=float(t.sn_lv_mva),
            vn_hv_kv=float(t.vn_hv_kv),
            vn_mv_kv=float(t.vn_mv_kv),
            vn_lv_kv=float(t.vn_lv_kv),
            vk_hv_percent=float(t.vk_hv_percent),
            vk_mv_percent=float(t.vk_mv_percent),
            vk_lv_percent=float(t.vk_lv_percent),
            vkr_hv_percent=float(t.vkr_hv_percent),
            vkr_mv_percent=float(t.vkr_mv_percent),
            vkr_lv_percent=float(t.vkr_lv_percent),
            pfe_kw=float(t.pfe_kw),
            i0_percent=float(t.i0_percent),
            name=str(t.trafo_id),
            **_tap_kwargs(t),
        )

    for _, g in model.gens.iterrows():
        pp.create_gen(
            net,
            bus=bus_idx[g.bus],
            p_mw=float(g.p_mw),
            vm_pu=float(g.vm_pu),
            min_q_mvar=_f(g.min_q_mvar),
            max_q_mvar=_f(g.max_q_mvar),
            slack=bool(g.is_angle_ref),
            slack_weight=float(g.slack_weight),
            name=str(g.gen_id),
        )
    for _, c in model.compensators.iterrows():
        pp.create_gen(
            net,
            bus=bus_idx[c.bus],
            p_mw=0.0,
            vm_pu=float(c.vm_pu),
            min_q_mvar=_f(c.min_q_mvar),
            max_q_mvar=_f(c.max_q_mvar),
            slack=False,
            slack_weight=0.0,
            name=str(c.gen_id),
        )
    for _, s in model.sgens.iterrows():
        pp.create_sgen(net, bus=bus_idx[s.bus], p_mw=float(s.p_mw), q_mvar=0.0, name=str(s.sgen_id))
    for _, sh in model.shunts.iterrows():
        pp.create_shunt(net, bus=bus_idx[sh.bus], q_mvar=float(sh.q_mvar), name=str(sh.shunt_id))
    for _, ld in model.loads.iterrows():
        # Los dos componentes de la demanda activa viajan como columnas extra de `net.load`
        # (FR-014); pandapower solo usa `p_mw` y `q_mvar` en el cálculo.
        pp.create_load(
            net,
            bus=bus_idx[ld.bus],
            p_mw=float(ld.p_mw),
            q_mvar=float(ld.q_mvar),
            name=str(ld.load_id),
            p_act_mw=_f(ld.get("p_act_mw", math.nan)),
            p_pstr_mw=_f(ld.get("p_pstr_mw", math.nan)),
        )
    return net
