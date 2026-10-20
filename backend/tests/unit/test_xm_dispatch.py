import pytest

from sinsim.adapters.sources_to_pandapower import xm_dispatch
from sinsim.domain.errors import DomainError


def test_mwh_per_period_to_mw_is_identity_for_one_hour():
    assert xm_dispatch.mwh_per_period_to_mw(405.0) == 405.0
    assert xm_dispatch.mwh_per_period_to_mw(100.0, period_hours=0.5) == 200.0


def test_parse_real_ddec_1020(fixtures_dir):
    text = (fixtures_dir / "xm" / "dDEC1020.txt").read_text(encoding="utf-8", errors="replace")
    df = xm_dispatch.parse_ddec(text, source="dDEC1020.txt")
    assert df.resource.nunique() == 626
    assert (df.groupby("resource").size() == 24).all()
    assert df[(df.resource == "ALBAN") & (df.period == 1)].p_mw.item() == 405.0
    assert "Total" not in set(df.resource)
    assert df.source_id.str.startswith("dDEC1020.txt:").all()


def test_total_mismatch_is_rejected():
    text = '"A",1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1\n"Total",2,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1\n'
    with pytest.raises(DomainError) as exc:
        xm_dispatch.parse_ddec(text)
    assert exc.value.code == "DISPATCH_TOTAL_MISMATCH" and "periodo 1" in exc.value.detail


def test_total_within_tolerance_and_semicolon_separator():
    text = '"A";1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1\n"Total";1.005;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1;1\n'
    assert len(xm_dispatch.parse_ddec(text)) == 24


def test_wrong_number_of_values_or_missing_total():
    with pytest.raises(DomainError) as exc:
        xm_dispatch.parse_ddec('"A",1,2,3\n')
    assert exc.value.code == "XM_FILE_SCHEMA_CHANGED"
    with pytest.raises(DomainError) as exc:
        xm_dispatch.parse_ddec('"A",' + ",".join(["1"] * 24) + "\n")
    assert "Total" in exc.value.detail


def test_select_dispatch_version_prefers_highest_v():
    chosen, available = xm_dispatch.select_dispatch_version(
        ["dDEC1014.txt", "dDEC1014_V1.txt", "PRON_BARRA1014.txt"]
    )
    assert chosen == "dDEC1014_V1.txt" and available == ["V0", "V1"]
    assert xm_dispatch.select_dispatch_version(["dDEC1020.txt"]) == ("dDEC1020.txt", ["V0"])
    assert xm_dispatch.dispatch_version_of("dDEC1020_V3.txt") == 3
    assert xm_dispatch.dispatch_version_of("otro.txt") is None
    with pytest.raises(DomainError):
        xm_dispatch.select_dispatch_version(["otro.txt"])


def test_v0_and_v1_fixtures_differ(fixtures_dir):
    v0 = (fixtures_dir / "xm" / "dDEC1014.txt").read_text(encoding="utf-8", errors="replace")
    v1 = (fixtures_dir / "xm" / "dDEC1014_V1.txt").read_text(encoding="utf-8", errors="replace")
    a, b = xm_dispatch.parse_ddec(v0), xm_dispatch.parse_ddec(v1)
    assert a.p_mw.sum() != b.p_mw.sum()
