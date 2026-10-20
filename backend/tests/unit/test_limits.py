from sinsim.config import load_config
from sinsim.domain.limits import (
    LoadingLimit,
    VoltageBand,
    band_for,
    branch_overload,
    bus_violation,
    limit_infos,
)

BANDS = [
    VoltageBand("500 kV", 400.0, 600.0, 0.90, 1.05, "CREG 025/1995 num. 5.1"),
    VoltageBand("STN", 220.0, 400.0, 0.90, 1.10, "CREG 025/1995 num. 5.1"),
    VoltageBand("STR", 57.5, 220.0, 0.90, 1.10, "CREG 153/2019 art. 1"),
]


def test_band_lookup_uses_half_open_ranges():
    assert band_for(500.0, BANDS).name == "500 kV"
    assert band_for(230.0, BANDS).name == "STN" and band_for(220.0, BANDS).name == "STN"
    assert band_for(115.0, BANDS).name == "STR" and band_for(57.5, BANDS).name == "STR"
    assert band_for(34.5, BANDS) is None


def test_violations_at_exact_limits_are_not_flagged():
    assert bus_violation(0.90, 230.0, BANDS) is None
    assert bus_violation(1.10, 230.0, BANDS) is None
    assert bus_violation(0.8999, 230.0, BANDS) == "low"
    assert bus_violation(1.1001, 230.0, BANDS) == "high"
    assert bus_violation(1.06, 500.0, BANDS) == "high"
    assert bus_violation(1.06, 230.0, BANDS) is None
    assert bus_violation(0.5, 34.5, BANDS) is None  # sin banda configurada


def test_overload_and_limit_infos_cite_sources():
    limit = LoadingLimit(100.0, "CREG 025/1995 Código de Planeamiento num. 5.2")
    assert branch_overload(100.0, limit) is False and branch_overload(100.1, limit) is True
    infos = limit_infos(BANDS, limit)
    assert [i.name for i in infos] == [
        "Tensión 500 kV",
        "Tensión STN",
        "Tensión STR",
        "Cargabilidad",
    ]
    assert all(i.source for i in infos) and infos[-1].value == "100 %"


def test_config_bands_cover_stn_and_str_with_sources():
    cfg = load_config().config
    bands = cfg.voltage_bands()
    assert band_for(500.0, bands).vm_max_pu == 1.05
    assert band_for(230.0, bands).vm_max_pu == 1.10 and band_for(115.0, bands).vm_min_pu == 0.90
    assert all("CREG" in b.source for b in bands)
    assert "CREG" in cfg.loading_limit().source and cfg.loading_limit().max_percent == 100.0
