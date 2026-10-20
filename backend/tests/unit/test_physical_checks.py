import pandas as pd

from sinsim.domain.physical_checks import blocking_issues, check_model


def frames(**overrides):
    base = {
        "buses": pd.DataFrame({"bus_id": ["A|230", "B|115"], "vn_kv": [230.0, 115.0]}),
        "lines": pd.DataFrame(
            {
                "line_id": ["l1"],
                "length_km": [10.0],
                "r_ohm_per_km": [0.05],
                "x_ohm_per_km": [0.4],
                "max_i_ka": [1.0],
            }
        ),
        "trafos2w": pd.DataFrame(
            {
                "trafo_id": ["t1"],
                "sn_mva": [150.0],
                "vn_hv_kv": [230.0],
                "vn_lv_kv": [115.0],
                "vk_percent": [12.0],
            }
        ),
        "trafos3w": pd.DataFrame(),
        "generators": pd.DataFrame(
            {
                "gen_id": ["g1"],
                "p_mw": [50.0],
                "p_max_mw": [60.0],
                "min_q_mvar": [-10.0],
                "max_q_mvar": [20.0],
            }
        ),
        "loads": pd.DataFrame({"load_id": ["c1"], "p_mw": [40.0]}),
    }
    base.update(overrides)
    return base


def test_consistent_model_has_no_issues():
    assert check_model(**frames()) == []


def test_impossible_values_are_blocking():
    bad_lines = pd.DataFrame(
        {
            "line_id": ["l1", "l2"],
            "length_km": [0.0, 1.0],
            "r_ohm_per_km": [0.05, -0.1],
            "x_ohm_per_km": [0.4, 0.0],
            "max_i_ka": [1.0, 0.0],
        }
    )
    issues = check_model(**frames(lines=bad_lines))
    checks = {(i.element, i.check) for i in issues}
    assert ("l1", "length_km <=0") in checks and ("l2", "r_ohm_per_km <0") in checks
    assert ("l2", "x_ohm_per_km <=0") in checks and ("l2", "max_i_ka <=0") in checks
    assert all(i.blocking for i in issues) and len(blocking_issues(issues)) == len(issues)
    assert "[bloqueante]" in issues[0].describe()


def test_inverted_q_limits_and_zero_voltage_block():
    gens = pd.DataFrame(
        {
            "gen_id": ["g1"],
            "p_mw": [50.0],
            "p_max_mw": [60.0],
            "min_q_mvar": [30.0],
            "max_q_mvar": [20.0],
        }
    )
    buses = pd.DataFrame({"bus_id": ["A|230"], "vn_kv": [0.0]})
    issues = check_model(**frames(generators=gens, buses=buses))
    assert {i.check for i in issues} == {"min_q_mvar > max_q_mvar", "vn_kv <=0"}


def test_dispatch_above_capacity_is_a_non_blocking_warning():
    gens = pd.DataFrame(
        {
            "gen_id": ["g1"],
            "p_mw": [70.0],
            "p_max_mw": [60.0],
            "min_q_mvar": [-1.0],
            "max_q_mvar": [1.0],
        }
    )
    issues = check_model(**frames(generators=gens))
    assert len(issues) == 1 and not issues[0].blocking and blocking_issues(issues) == []
    assert "[aviso]" in issues[0].describe() and "p_max_mw" in issues[0].check
