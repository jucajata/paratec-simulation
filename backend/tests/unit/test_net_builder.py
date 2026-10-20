import math

import pandas as pd
import pytest

from sinsim.adapters.sources_to_pandapower.net_builder import ModelTables, build_net
from sinsim.domain.constants import F_HZ, S_BASE_MVA


def tiny_model() -> ModelTables:
    buses = pd.DataFrame(
        {
            "bus_id": ["A|230", "B|230", "B|115"],
            "vn_kv": [230.0, 230.0, 115.0],
            "nominal_kv": [220.0, 230.0, 110.0],
        }
    )
    lines = pd.DataFrame(
        [
            {
                "line_id": "line:A - B 1 230 kV",
                "from_bus": "A|230",
                "to_bus": "B|230",
                "length_km": 50.0,
                "r_ohm_per_km": 0.05,
                "x_ohm_per_km": 0.45,
                "c_nf_per_km": 9.0,
                "max_i_ka": 1.0,
                "parallel": 1,
            }
        ]
    )
    trafos2w = pd.DataFrame(
        [
            {
                "trafo_id": "trafo:B 1 150 MVA 230/115 kV",
                "hv_bus": "B|230",
                "lv_bus": "B|115",
                "sn_mva": 150.0,
                "vn_hv_kv": 230.0,
                "vn_lv_kv": 115.0,
                "vk_percent": 12.0,
                "vkr_percent": 0.3,
                "pfe_kw": 50.0,
                "i0_percent": 0.0,
                "tap_side": "hv",
                "tap_min": 1,
                "tap_max": 21,
                "tap_neutral": 11,
                "tap_pos": 11,
                "tap_step_percent": -1.25,
            }
        ]
    )
    gens = pd.DataFrame(
        [
            {
                "gen_id": "PLANTA@A|230",
                "resource": "PLANTA",
                "bus": "A|230",
                "p_mw": 100.0,
                "p_max_mw": 120.0,
                "min_q_mvar": -40.0,
                "max_q_mvar": 60.0,
                "vm_pu": 1.0,
                "slack_weight": 100.0,
                "is_angle_ref": True,
            },
            {
                "gen_id": "OTRA@B|230",
                "resource": "OTRA",
                "bus": "B|230",
                "p_mw": 20.0,
                "p_max_mw": 30.0,
                "min_q_mvar": math.nan,
                "max_q_mvar": math.nan,
                "vm_pu": 1.0,
                "slack_weight": 20.0,
                "is_angle_ref": False,
            },
        ]
    )
    compensators = pd.DataFrame(
        [
            {
                "gen_id": "svc:B SVC",
                "bus": "B|115",
                "min_q_mvar": -30.0,
                "max_q_mvar": 50.0,
                "vm_pu": 1.0,
            }
        ]
    )
    sgens = pd.DataFrame(
        [{"sgen_id": "link:ECUADOR", "resource": "ECUADOR", "bus": "B|230", "p_mw": 5.0}]
    )
    shunts = pd.DataFrame([{"shunt_id": "reactor:B", "bus": "B|230", "q_mvar": 25.0}])
    loads = pd.DataFrame(
        [
            {
                "load_id": "load:B|115",
                "bus": "B|115",
                "p_mw": 110.0,
                "p_act_mw": 104.0,
                "p_pstr_mw": 6.0,
                "q_mvar": 30.0,
            }
        ]
    )
    return ModelTables(
        buses, lines, trafos2w, pd.DataFrame(), gens, compensators, sgens, shunts, loads
    )


def test_build_net_maps_every_element_with_domain_ids_and_conventions():
    net = build_net(tiny_model(), F_HZ, S_BASE_MVA)
    assert net.f_hz == 60.0 and net.sn_mva == 100.0
    assert net.bus.name.tolist() == ["A|230", "B|230", "B|115"]
    assert net.bus.nominal_kv.tolist() == [220.0, 230.0, 110.0]
    assert net.line.name.iloc[0] == "line:A - B 1 230 kV" and net.line.max_i_ka.iloc[0] == 1.0
    t = net.trafo.iloc[0]
    assert (
        t.tap_side == "hv"
        and t.tap_pos == 11
        and t.tap_step_percent == -1.25
        and t.i0_percent == 0.0
    )
    g = net.gen.set_index("name")
    assert (
        bool(g.loc["PLANTA@A|230", "slack"]) is True
        and g.loc["PLANTA@A|230", "slack_weight"] == 100.0
    )
    assert bool(g.loc["OTRA@B|230", "slack"]) is False and math.isnan(
        g.loc["OTRA@B|230", "min_q_mvar"]
    )
    assert g.loc["svc:B SVC", "p_mw"] == 0.0 and g.loc["svc:B SVC", "slack_weight"] == 0.0
    assert g.loc["svc:B SVC", "min_q_mvar"] == -30.0 and g.loc["svc:B SVC", "max_q_mvar"] == 50.0
    assert net.sgen.p_mw.iloc[0] == 5.0 and net.shunt.q_mvar.iloc[0] == 25.0
    assert net.load.p_mw.iloc[0] == 110.0 and net.load.q_mvar.iloc[0] == 30.0
    # FR-014: los dos componentes de la demanda activa se conservan en la red.
    assert net.load.p_act_mw.iloc[0] == 104.0 and net.load.p_pstr_mw.iloc[0] == 6.0
    assert int(net.gen.slack.sum()) == 1


def test_build_net_without_tap_fields_creates_trafo_without_tap():
    model = tiny_model()
    model.trafos2w.loc[0, "tap_side"] = None
    net = build_net(model, F_HZ, S_BASE_MVA)
    assert pd.isna(net.trafo.tap_pos.iloc[0]) or net.trafo.tap_pos.iloc[0] == 0
    assert len(net.trafo) == 1


def test_tiny_network_converges_with_distributed_slack():
    import pandapower as pp

    net = build_net(tiny_model(), F_HZ, S_BASE_MVA)
    pp.runpp(
        net, distributed_slack=True, enforce_q_lims=True, init="dc", calculate_voltage_angles=True
    )
    assert net.converged
    assert net.res_bus.vm_pu.between(0.9, 1.1).all()
    assert net.res_gen.p_mw.sum() + net.res_sgen.p_mw.sum() == pytest.approx(
        net.res_load.p_mw.sum() + net.res_line.pl_mw.sum() + net.res_trafo.pl_mw.sum(), abs=1e-3
    )
