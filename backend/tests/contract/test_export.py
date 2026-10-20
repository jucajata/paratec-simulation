"""Contrato de exportación (contracts/export-format.md, FR-032, SC-007)."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sinsim.adapters.storage.export import CSV_FILES, METADATA_FILE, export_files, write_export
from sinsim.api.app import create_app
from sinsim.config import load_config, sinsim_version
from sinsim.services.build_case import build_case
from sinsim.services.run_flow import run_flow

TRACE_FIELDS = {
    "snapshot_date",
    "dispatch_date",
    "period",
    "flow_type",
    "pandapower_version",
    "sinsim_version",
    "solver",
    "case_id",
}


@pytest.fixture(scope="module")
def case_and_run(fixture_snapshot, equivalences_repo):
    cfg = load_config()
    built = build_case(
        snapshot=fixture_snapshot,
        dispatch_snapshot=fixture_snapshot,
        period=19,
        equivalences=equivalences_repo,
        cfg=cfg,
        sinsim_version=sinsim_version(),
    )
    return built, run_flow(built.case, built.net, "ac", cfg, sinsim_version())


def test_export_files_match_result_value_by_value(case_and_run, tmp_path: Path):
    built, run = case_and_run
    attribution = load_config().config.attribution.text
    written = write_export(built.case, run, attribution, tmp_path / "out")
    assert {p.name for p in written} == set(CSV_FILES) | {METADATA_FILE}
    raw = (tmp_path / "out" / "barras.csv").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r\n" not in raw
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    by_id = {b.bus_id: b for b in run.result.buses}
    assert len(rows) == len(by_id)
    for row in rows:
        b = by_id[row["bus_id"]]
        assert (
            float(row["vm_pu"]) == b.vm_pu
            and float(row["vm_kv"]) == b.vm_kv
            and float(row["va_degree"]) == b.va_degree
        )
        assert row["violation"] == (b.violation or "")
    trafos = list(
        csv.DictReader(
            io.StringIO((tmp_path / "out" / "transformadores.csv").read_text(encoding="utf-8"))
        )
    )
    assert {t["tipo"] for t in trafos} <= {"2w", "3w"} and len(trafos) == len(run.result.trafos)
    gens = list(
        csv.DictReader(
            io.StringIO((tmp_path / "out" / "generadores.csv").read_text(encoding="utf-8"))
        )
    )
    assert len(gens) == len(run.result.generators) and all(
        float(g["p_mw"]) == next(x.p_mw for x in run.result.generators if x.gen_id == g["gen_id"])
        for g in gens[:20]
    )
    meta = json.loads((tmp_path / "out" / METADATA_FILE).read_text(encoding="utf-8"))
    assert set(meta["trace"]) == TRACE_FIELDS and meta["case_id"] == built.case.case_id
    assert meta["attribution"] == attribution and "XM" in meta["attribution"]
    assert meta["label"] == "Flujo sobre despacho programado" and meta["status"] == "convergio"
    assert meta["limits"] and all({"name", "value", "source"} <= set(lim) for lim in meta["limits"])
    assert "quality_summary" in meta and "assumptions" in meta and meta["diagnostics"] is None


def test_no_convergio_export_has_only_metadata(case_and_run):
    built, run = case_and_run
    failed = run.model_copy(update={"status": "no_convergio", "result": None, "diagnostics": None})
    files = export_files(built.case, failed, "x")
    assert set(files) == {METADATA_FILE}
    assert json.loads(files[METADATA_FILE])["status"] == "no_convergio"


def test_api_export_and_topology(app_context):
    client = TestClient(create_app(app_context), raise_server_exceptions=False)
    case = client.post("/api/cases", json={"snapshot_date": "2026-10-20", "period": 19}).json()
    run = client.post(f"/api/cases/{case['case_id']}/runs", json={"flow_type": "ac"}).json()
    r = client.get(f"/api/runs/{run['run_id']}/export")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert set(zf.namelist()) == set(CSV_FILES) | {METADATA_FILE}
        rows = list(csv.DictReader(io.StringIO(zf.read("barras.csv").decode("utf-8"))))
    api_buses = {b["bus_id"]: b for b in run["result"]["buses"]}
    assert all(float(row["vm_pu"]) == api_buses[row["bus_id"]]["vm_pu"] for row in rows)
    t = client.get(f"/api/runs/{run['run_id']}/topology").json()
    assert t["nodes"] and t["edges"]
    assert {"id", "label", "vn_kv", "vm_pu", "violation"} <= set(t["nodes"][0])
    assert {"id", "source", "target", "kind", "loading_percent", "overload"} <= set(t["edges"][0])
    assert {e["kind"] for e in t["edges"]} <= {"line", "trafo2w", "trafo3w"}
    node_ids = {n["id"] for n in t["nodes"]}
    assert all(e["source"] in node_ids and e["target"] in node_ids for e in t["edges"])
    assert client.get("/api/runs/00000000-0000-0000-0000-000000000000/export").status_code == 404
