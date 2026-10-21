import math

import pytest

from sinsim.adapters.sources_to_pandapower import lines

DECLARED = {"A": (115.0,), "B": (115.0, 110.0), "C": (230.0,)}


def segment(length, r, x, b):
    return {"length": length, "endurance": r, "reactance": x, "susceptance": b}


def test_susceptance_to_capacitance_known_value():
    # 2.875 µS/km → 2.875e-6 S/km / (2π·60) = 7.626e-9 F/km = 7.626 nF/km
    assert lines.susceptance_to_capacitance_nf_per_km(2.875) == pytest.approx(7.6262, abs=1e-4)


def test_aggregate_segments_is_length_weighted():
    agg = lines.aggregate_segments([segment(1.0, 0.1, 0.4, 2.5), segment(3.0, 0.2, 0.3, 3.0)])
    assert agg["length_km"] == pytest.approx(4.0)
    assert agg["r_ohm_per_km"] == pytest.approx(0.175)
    assert agg["x_ohm_per_km"] == pytest.approx(0.325)
    assert agg["c_nf_per_km"] == pytest.approx(2.875e3 / (2 * math.pi * 60))


def test_aggregate_segments_reports_missing_parameters():
    agg = lines.aggregate_segments([segment(2.0, None, 0.4, 2.5)])
    assert agg["r_ohm_per_km"] is None and agg["x_ohm_per_km"] == pytest.approx(0.4)
    assert lines.aggregate_segments([segment(0, 0.1, 0.4, 2.5)])["length_km"] is None


def test_resolve_endpoints_prefers_map_then_text():
    known = set(DECLARED)
    rec = {"name": "A - B 1 115 kV", "subStation": "A - B"}
    assert lines.resolve_endpoints(rec, {"A - B 1 115 kV": ("B", "A")}, known) == ("B", "A")
    assert lines.resolve_endpoints(rec, {}, known) == ("A", "B")
    assert lines.resolve_endpoints({"name": "x", "subStation": "A - "}, {}, known) is None
    assert lines.resolve_endpoints({"name": "x", "subStation": "A - Z"}, {}, known) is None


def test_parse_lines_builds_pandapower_units_and_flags_missing():
    data = [
        {
            "name": "A - B 1 115 kV",
            "subStation": "A - B",
            "ratedVoltage": 115,
            "ratedCurrent": 620,
            "state": "Operación",
            "typeLines": [segment(1.0, 0.1, 0.4, 2.5), segment(3.0, 0.2, 0.3, 3.0)],
        },
        {
            "name": "A - T 1 115 kV",
            "subStation": "A - ",
            "ratedVoltage": 115,
            "ratedCurrent": None,
            "state": "Operación",
            "typeLines": [segment(1.0, 0.1, 0.4, 2.5)],
        },
    ]
    df = lines.parse_lines(data, {}, DECLARED)
    good, bad = df.iloc[0], df.iloc[1]
    assert good.from_bus == "A|115" and good.to_bus == "B|115"
    assert good.max_i_ka == pytest.approx(0.62)
    assert good.r_ohm_per_km == pytest.approx(0.175)
    assert good.missing_params == []
    assert set(bad.missing_params) == {"from_bus", "to_bus", "max_i_ka"}
    assert bad.from_bus is None


def test_parse_line_map_reads_sub1_sub2():
    feats = [
        {"properties": {"nameLine": "L1", "sub1": "A", "sub2": "B"}},
        {"properties": {"nameLine": "L2", "sub1": "A", "sub2": None}},
    ]
    assert lines.parse_line_map(feats) == {"L1": ("A", "B")}


def test_far_end_from_name_uses_declared_substation_only():
    known = {"JAMONDINO", "PIMAMPIRO", "TESALIA", "JUANCHITO"}
    assert (
        lines.far_end_from_name("JAMONDINO - PIMAMPIRO 1 230 KV", "JAMONDINO", known) == "PIMAMPIRO"
    )
    # El Quimbo no está en el listado de PARATEC: no se inventa un extremo.
    assert lines.far_end_from_name("EL QUIMBO - TESALIA 1 230 kV", "TESALIA", known) is None
    # Dos nombres del mismo patio normalizan igual: sigue siendo un lazo.
    assert (
        lines.far_end_from_name("JUANCHITO - JUANCHITO (EPSA) 1 115 kV", "JUANCHITO", known) is None
    )


def test_resolve_endpoints_repairs_self_loop_with_declared_far_end():
    rec = {"name": "JAMONDINO - PIMAMPIRO 1 230 KV", "subStation": "JAMONDINO - JAMONDINO"}
    line_map = {"JAMONDINO - PIMAMPIRO 1 230 KV": ("JAMONDINO", "JAMONDINO")}
    assert lines.resolve_endpoints(rec, line_map, {"JAMONDINO", "PIMAMPIRO"}) == (
        "JAMONDINO",
        "PIMAMPIRO",
    )
    assert lines.resolve_endpoints(rec, line_map, {"JAMONDINO"}) == ("JAMONDINO", "JAMONDINO")
