"""Contrato de exportación del análisis N-1 (specs/003-contingencias-n1/contracts/export-n1.md)."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, date, datetime
from pathlib import Path

from sinsim.adapters.storage.export_n1 import (
    CSV_FILES,
    METADATA_FILE,
    export_n1_files,
    write_export_n1,
)
from sinsim.domain.entities import (
    BusMismatch,
    Diagnostics,
    Isolation,
    IsolationRow,
    LimitInfo,
    LoadingRow,
    N1Analysis,
    N1Summary,
    Outage,
    SolverSettings,
    Trace,
    UnsolvedRow,
    VoltageRow,
)

ATTRIBUTION = "Información proporcionada por XM S.A. E.S.P."


def outage(name: str, kind: str = "line", moved: str | None = None) -> Outage:
    return Outage(element_id=name, kind=kind, subarea="Bogotá", angle_ref_moved_to=moved)  # type: ignore[arg-type]


def analysis() -> N1Analysis:
    trace = Trace(
        snapshot_date=date(2026, 10, 20),
        dispatch_date=date(2026, 10, 20),
        period=19,
        flow_type="ac",
        pandapower_version="3.5.6",
        sinsim_version="0.6.0",
        solver=SolverSettings(
            algorithm="nr",
            tolerance_mva=1e-8,
            max_iteration=30,
            init="dc",
            enforce_q_lims=True,
            distributed_slack=True,
        ),
        case_id="c" * 64,
    )
    iso = Isolation(n_buses=2, p_demand_lost_mw=12.5)
    return N1Analysis(
        run_id="run-1",
        trace=trace,
        limits=[LimitInfo(name="Cargabilidad", value="100 %", source="CREG 025/1995")],
        analyzed_at=datetime(2026, 10, 24, 15, 0, tzinfo=UTC),
        workers=11,
        summary=N1Summary(
            n_total=5,
            n_loading=2,
            n_voltage=1,
            n_isolation=1,
            n_unsolved=1,
            n_no_impact=1,
            duration_s=76.2,
        ),
        loading=[
            LoadingRow(
                rank=1,
                outage=outage("line:A - B 1 115 kV"),
                element_id="trafo:T1",
                loading_base_percent=97.3,
                loading_percent=201.4,
                n_elements=3,
                isolation=iso,
            ),
            LoadingRow(
                rank=2,
                outage=outage("G@BUS|230", "gen", moved="OTRA|230"),
                element_id="line:C - D 1 230 kV",
                loading_base_percent=90.0,
                loading_percent=150.0,
                n_elements=1,
                isolation=None,
            ),
        ],
        voltage=[
            VoltageRow(
                rank=1,
                outage=outage("line:A - B 1 115 kV"),
                bus_id="B|115",
                vm_base_pu=0.95,
                vm_pu=0.842,
                deviation_pu=-0.058,
                n_buses=4,
                isolation=iso,
            )
        ],
        isolation=[
            IsolationRow(
                rank=1, outage=outage("line:A - B 1 115 kV"), n_buses=2, p_demand_lost_mw=12.5
            )
        ],
        unsolved=[
            UnsolvedRow(
                outage=outage("line:X - Y 1 115 kV"),
                diagnostics=Diagnostics(
                    iterations=30,
                    max_mismatch_mva=12.3,
                    worst_buses=[
                        BusMismatch(bus="X|115", mismatch_mva=12.3),
                        BusMismatch(bus="Y|115", mismatch_mva=4.0),
                    ],
                ),
            )
        ],
    )


def rows_of(files: dict[str, bytes], name: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(files[name].decode("utf-8"))))


def test_csv_headers_match_the_contract():
    files = export_n1_files(analysis(), ATTRIBUTION)
    assert set(files) == {*CSV_FILES, METADATA_FILE}
    headers = {name: files[name].decode("utf-8").splitlines()[0] for name in CSV_FILES}
    assert headers["n1_cargabilidad.csv"] == (
        "posicion,activo_fuera,tipo_activo,subarea_activo,elemento,cargabilidad_base_pct,"
        "cargabilidad_pct,elementos_que_cuentan,barras_aisladas,demanda_sin_servicio_mw,referencia_movida_a"
    )
    assert headers["n1_tensiones.csv"] == (
        "posicion,activo_fuera,tipo_activo,subarea_activo,barra,v_base_pu,v_pu,distancia_fuera_de_banda_pu,"
        "barras_que_cuentan,barras_aisladas,demanda_sin_servicio_mw,referencia_movida_a"
    )
    assert headers["n1_aislan_demanda.csv"] == (
        "posicion,activo_fuera,tipo_activo,subarea_activo,barras_aisladas,demanda_sin_servicio_mw"
    )
    assert headers["n1_sin_solucion.csv"] == (
        "activo_fuera,tipo_activo,subarea_activo,iteraciones,desbalance_maximo_mva,barras_problematicas"
    )


def test_rows_keep_the_analysis_order_and_blank_columns_when_not_applicable():
    files = export_n1_files(analysis(), ATTRIBUTION)
    loading = rows_of(files, "n1_cargabilidad.csv")
    assert [r["posicion"] for r in loading] == ["1", "2"]
    assert (
        loading[0]["activo_fuera"] == "line:A - B 1 115 kV" and loading[0]["tipo_activo"] == "line"
    )
    assert loading[0]["cargabilidad_pct"] == "201.4" and loading[0]["elementos_que_cuentan"] == "3"
    assert loading[0]["barras_aisladas"] == "2" and loading[0]["demanda_sin_servicio_mw"] == "12.5"
    assert loading[0]["referencia_movida_a"] == ""
    assert loading[1]["barras_aisladas"] == "" and loading[1]["demanda_sin_servicio_mw"] == ""
    assert loading[1]["referencia_movida_a"] == "OTRA|230" and loading[1]["tipo_activo"] == "gen"
    voltage = rows_of(files, "n1_tensiones.csv")
    assert voltage[0]["barra"] == "B|115" and voltage[0]["distancia_fuera_de_banda_pu"] == "-0.058"
    assert voltage[0]["barras_que_cuentan"] == "4" and voltage[0]["v_base_pu"] == "0.95"
    isolation = rows_of(files, "n1_aislan_demanda.csv")
    assert isolation == [
        {
            "posicion": "1",
            "activo_fuera": "line:A - B 1 115 kV",
            "tipo_activo": "line",
            "subarea_activo": "Bogotá",
            "barras_aisladas": "2",
            "demanda_sin_servicio_mw": "12.5",
        }
    ]
    unsolved = rows_of(files, "n1_sin_solucion.csv")
    assert unsolved[0]["iteraciones"] == "30" and unsolved[0]["desbalance_maximo_mva"] == "12.3"
    assert unsolved[0]["barras_problematicas"] == "X|115;Y|115"


def test_metadata_carries_traceability_limits_summary_and_attribution():
    meta = json.loads(export_n1_files(analysis(), ATTRIBUTION)[METADATA_FILE])
    assert meta["tipo"] == "analisis_n1"
    assert (
        meta["snapshot"] == "2026-10-20"
        and meta["despacho"] == "2026-10-20"
        and meta["periodo"] == 19
    )
    assert meta["case_id"] == "c" * 64 and meta["run_id"] == "run-1"
    assert meta["pandapower"] == "3.5.6" and meta["sinsim"] == "0.6.0"
    assert meta["solver"]["algorithm"] == "nr" and meta["solver"]["tolerance_mva"] == 1e-8
    assert meta["limites"] == [
        {"name": "Cargabilidad", "value": "100 %", "source": "CREG 025/1995"}
    ]
    assert meta["analizado_en"].startswith("2026-10-24T15:00:00") and meta["procesos"] == 11
    assert meta["resumen"]["n_total"] == 5 and meta["resumen"]["n_no_impact"] == 1
    assert meta["atribucion"] == ATTRIBUTION


def test_empty_lists_still_write_headers():
    empty = analysis().model_copy(
        update={
            "loading": [],
            "voltage": [],
            "isolation": [],
            "unsolved": [],
            "summary": N1Summary(
                n_total=0,
                n_loading=0,
                n_voltage=0,
                n_isolation=0,
                n_unsolved=0,
                n_no_impact=0,
                duration_s=0.1,
            ),
        }
    )
    files = export_n1_files(empty, ATTRIBUTION)
    for name in CSV_FILES:
        assert files[name].decode("utf-8").count("\n") == 1


def test_write_creates_the_folder_and_replaces_files(tmp_path: Path):
    out = tmp_path / "salida" / "n1"
    written = write_export_n1(analysis(), ATTRIBUTION, out)
    assert {p.name for p in written} == {*CSV_FILES, METADATA_FILE}
    (out / "n1_cargabilidad.csv").write_text("basura", encoding="utf-8")
    write_export_n1(analysis(), ATTRIBUTION, out)
    assert "basura" not in (out / "n1_cargabilidad.csv").read_text(encoding="utf-8")
