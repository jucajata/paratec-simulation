import pytest

from sinsim.domain.balance import compute_balance


def test_balance_fields_and_coverage():
    b = compute_balance(
        p_scheduled_total_mw=1000.0,
        p_located_mw=950.0,
        p_demand_mw=900.0,
        p_demand_unlocated_mw=50.0,
    )
    assert b.p_unlocated_mw == pytest.approx(50.0)
    assert b.coverage_pct == pytest.approx(95.0)
    assert b.difference_mw == pytest.approx(50.0)
    assert b.p_demand_mw == 900.0 and b.p_demand_unlocated_mw == 50.0


def test_coverage_is_zero_without_scheduled_generation():
    b = compute_balance(
        p_scheduled_total_mw=0.0, p_located_mw=0.0, p_demand_mw=10.0, p_demand_unlocated_mw=0.0
    )
    assert b.coverage_pct == 0.0 and b.difference_mw == -10.0
