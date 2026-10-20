import pytest

from sinsim.adapters.sources_to_pandapower import trafos

DECLARED = {"S": (230.0, 115.0)}


def rec(**overrides):
    base = {
        "elementName": "S 1 41.75 MVA 110/13.2 kV",
        "substationName": "S",
        "windingType": "Bidevanado",
        "impedanceHighLowNom": "9.7",
        "impedanceHighMediumNom": "N/A",
        "impedanceMediumLowNom": "N/A",
        "highLowCopperLosses": "200",
        "highMediumCopperLosses": "N/A",
        "mediumLowCopperLosses": "N/A",
        "ironLosses": "30",
        "windingsList": [
            {"nomVoltage": "110", "nomCapacity": "41.75"},
            {"nomVoltage": "13.2", "nomCapacity": "41.75"},
        ],
        "ltcFlag": True,
        "highStep": "19",
        "highStepU": "97.62",
        "normalStep": "10",
        "neutralU": "110",
        "lowStep": "1",
        "lowStepU": "122.37",
        "step": "1.39",
        "elementStateName": "Operación",
    }
    base.update(overrides)
    return base


def test_copper_losses_to_vkr_known_value():
    # 200 kW sobre 41.75 MVA → 200 / 41 750 · 100 = 0.479 %
    assert trafos.copper_losses_to_vkr_percent(200.0, 41.75) == pytest.approx(0.47904, abs=1e-5)


def test_two_winding_transformer_parameters_and_tap_orientation():
    t2, t3 = trafos.parse_transformers([rec()], DECLARED)
    assert t3.empty and len(t2) == 1
    row = t2.iloc[0]
    assert row.hv_bus == "S|115" and row.lv_bus == "S|13.8"  # clases: 110 → 115, 13.2 → 13.8
    assert row.sn_mva == 41.75 and row.vk_percent == 9.7
    assert row.vkr_percent == pytest.approx(0.47904, abs=1e-5)
    assert row.pfe_kw == 30 and row.i0_percent == 0.0
    assert row.tap_side == "hv" and row.tap_pos == 10 and row.tap_neutral == 10
    assert row.tap_min == 1 and row.tap_max == 19
    assert row.tap_step_percent == -1.39  # paso mayor → tensión menor
    assert row.missing_params == []


def test_tap_sign_positive_when_voltage_grows_with_step():
    t2, _ = trafos.parse_transformers([rec(lowStepU="97.62", highStepU="122.37")], DECLARED)
    assert t2.iloc[0].tap_step_percent == 1.39


def test_missing_values_are_reported_not_invented():
    t2, _ = trafos.parse_transformers(
        [rec(highLowCopperLosses="-", ironLosses="N/A", step="-")], DECLARED
    )
    row = t2.iloc[0]
    assert set(row.missing_params) == {"pfe_kw", "vkr_percent"}
    assert row.vkr_percent is None and row.pfe_kw is None
    assert row.tap_side is None and row.tap_step_percent is None


def test_three_winding_with_two_windings_is_two_winding():
    t2, t3 = trafos.parse_transformers([rec(windingType="Tridevanado")], DECLARED)
    assert len(t2) == 1 and t3.empty


def test_three_winding_bases_follow_pandapower_min_pair_capacity():
    data = [
        rec(
            windingType="Tridevanado",
            impedanceHighLowNom="13.22",
            impedanceHighMediumNom="8.05",
            impedanceMediumLowNom="2.01",
            highLowCopperLosses="100",
            highMediumCopperLosses="300",
            mediumLowCopperLosses="100",
            windingsList=[
                {"nomVoltage": "230", "nomCapacity": "150"},
                {"nomVoltage": "115", "nomCapacity": "150"},
                {"nomVoltage": "34.5", "nomCapacity": "50"},
            ],
            neutralU="230",
        )
    ]
    t2, t3 = trafos.parse_transformers(data, DECLARED)
    assert t2.empty and len(t3) == 1
    row = t3.iloc[0]
    assert (row.vk_hv_percent, row.vk_mv_percent, row.vk_lv_percent) == (8.05, 2.01, 13.22)
    assert row.vkr_hv_percent == pytest.approx(300 / (150 * 1000) * 100)  # base min(150,150)
    assert row.vkr_mv_percent == pytest.approx(100 / (50 * 1000) * 100)  # base min(150,50)
    assert row.vkr_lv_percent == pytest.approx(100 / (50 * 1000) * 100)  # base min(150,50)
    assert (row.hv_bus, row.mv_bus, row.lv_bus) == ("S|230", "S|115", "S|34.5")
    assert row.tap_side == "hv"
