from sinsim.domain.entities import BranchResult, BusResult
from sinsim.domain.limits import LoadingLimit, VoltageBand
from sinsim.domain.violations import violations_report

BANDS = [
    VoltageBand("STN", 220.0, 400.0, 0.90, 1.10, "CREG 025/1995"),
    VoltageBand("STR", 57.5, 220.0, 0.90, 1.10, "CREG 153/2019"),
]
LOADING = LoadingLimit(100.0, "CREG 025/1995")


def bus(bus_id: str, vn: float, vm: float, violation):
    return BusResult(
        bus_id=bus_id,
        vn_kv=vn,
        vm_pu=vm,
        vm_kv=vm * vn,
        va_degree=0,
        violation=violation,
        subarea="X",
    )


def branch(element_id: str, loading: float, overload: bool, sa_from="A", sa_to="A"):
    return BranchResult(
        element_id=element_id,
        kind="line",
        from_bus="a",
        to_bus="b",
        p_from_mw=1,
        q_from_mvar=0,
        p_to_mw=-1,
        q_to_mvar=0,
        i_ka=0.1,
        loading_percent=loading,
        pl_mw=0,
        ql_mvar=0,
        overload=overload,
        subarea_from=sa_from,
        subarea_to=sa_to,
    )


def test_report_groups_and_orders_by_deviation_with_limit_and_source():
    buses = [
        bus("B1|230", 230, 0.88, "low"),
        bus("B2|115", 110, 0.85, "low"),
        bus("B3|230", 230, 1.12, "high"),
        bus("OK|230", 230, 1.0, None),
    ]
    branches = [
        branch("L1", 106.0, True),
        branch("L2", 120.0, True, "A", "B"),
        branch("L3", 90.0, False),
    ]
    report = violations_report(buses, branches, BANDS, LOADING)
    assert [v.kind for v in report] == [
        "tension_baja",
        "tension_baja",
        "tension_alta",
        "sobrecarga",
        "sobrecarga",
    ]
    assert [v.element for v in report] == ["B2|115", "B1|230", "B3|230", "L2", "L1"]
    low = report[0]
    assert (
        low.limit == 0.90
        and low.deviation == 0.90 - 0.85
        and low.unit == "pu"
        and low.source == "CREG 153/2019"
    )
    over = report[3]
    assert (
        over.limit == 100.0 and over.deviation == 20.0 and over.unit == "%" and over.subarea is None
    )
    assert report[4].subarea == "A"
