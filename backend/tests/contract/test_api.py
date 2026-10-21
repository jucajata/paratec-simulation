"""Contrato de la API con contracts/openapi.yaml y Problem Details (constitución V)."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sinsim.api.app import create_app

CONTRACT = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-flujo-potencia-despacho"
    / "contracts"
    / "openapi.yaml"
)
PROBLEM_FIELDS = {"type", "title", "status", "detail", "code", "user_message", "trace_id"}


@pytest.fixture
def client(app_context) -> TestClient:
    return TestClient(create_app(app_context), raise_server_exceptions=False)


def test_every_contract_path_exists_in_generated_openapi(client: TestClient):
    contract_paths = {
        m.group(1) for m in re.finditer(r"^  (/\S+):", CONTRACT.read_text(encoding="utf-8"), re.M)
    }
    generated = set(client.get("/openapi.json").json()["paths"])
    missing = {
        f"/api{p}"
        for p in contract_paths
        if p not in ("/runs/{run_id}/topology", "/runs/{run_id}/export")
    } - generated
    assert not missing, missing


def test_snapshots_endpoint_lists_fixture(client: TestClient):
    r = client.get("/api/snapshots")
    assert r.status_code == 200
    body = r.json()
    assert body[0]["date"] == "2026-10-20" and body[0]["intact"] is True
    assert body[0]["has_dispatch"] and body[0]["has_demand"] and body[0]["has_paratec"]
    assert "X-Trace-Id" in r.headers


def test_case_creation_is_idempotent_and_runs_converge(client: TestClient):
    r1 = client.post("/api/cases", json={"snapshot_date": "2026-10-20", "period": 19})
    assert r1.status_code == 201, r1.text
    case = r1.json()
    assert len(case["case_id"]) == 64 and case["quality"]["balance"]["coverage_pct"] > 80
    r2 = client.post("/api/cases", json={"snapshot_date": "2026-10-20", "period": 19})
    assert r2.status_code == 200 and r2.json()["case_id"] == case["case_id"]
    assert client.get(f"/api/cases/{case['case_id']}").status_code == 200
    r3 = client.post(f"/api/cases/{case['case_id']}/runs", json={"flow_type": "ac"})
    assert r3.status_code == 200
    run = r3.json()
    assert run["status"] == "convergio" and run["result"] is not None and run["diagnostics"] is None
    assert set(run["trace"]) >= {
        "snapshot_date",
        "dispatch_date",
        "period",
        "flow_type",
        "pandapower_version",
        "sinsim_version",
        "solver",
        "case_id",
    }
    r4 = client.get(f"/api/runs/{run['run_id']}")
    assert r4.status_code == 200 and r4.json()["run_id"] == run["run_id"]

    # FR-034: la topología trae la subárea por nodo y los enlaces a los unifilares de XM.
    r5 = client.get(f"/api/runs/{run['run_id']}/topology")
    assert r5.status_code == 200
    topo = r5.json()
    assert set(topo) == {"nodes", "edges", "subareas"}
    assert all("subarea" in n for n in topo["nodes"])
    names = [s["name"] for s in topo["subareas"]]
    assert names == sorted(names) and "Antioquia" in names
    antioquia = next(s for s in topo["subareas"] if s["name"] == "Antioquia")
    assert antioquia["unifilar_url"].startswith("https://paratec.xm.com.co/unifilares/")
    assert "category=76fd5d96-3e30-44a5-13e2-08dd52a72d2b" in antioquia["unifilar_url"]
    # FR-035: coordenadas de PARATEC por nodo; las que faltan se reportan en la calidad.
    located = [n for n in topo["nodes"] if n["lat"] is not None and n["lon"] is not None]
    assert len(located) > 0.9 * len(topo["nodes"])
    assert all(-5 <= n["lat"] <= 14 and -82.5 <= n["lon"] <= -66 for n in located)
    missing = {n["id"] for n in topo["nodes"] if n["lat"] is None}
    assert missing <= set(case["quality"]["buses_without_coordinates"])
    # FR-036: generación, carga y flujos por elemento, coherentes con el resumen de la corrida.
    summary = run["result"]["summary"]
    p_gen = sum(n["p_gen_mw"] for n in topo["nodes"])
    p_load = sum(n["p_load_mw"] for n in topo["nodes"])
    assert p_gen == pytest.approx(summary["p_gen_mw"], rel=1e-6)
    assert p_load == pytest.approx(summary["p_load_mw"], rel=1e-6)
    parts = [n for n in topo["nodes"] if n["p_load_act_mw"] is not None]
    assert parts and all(
        n["p_load_act_mw"] + n["p_load_pstr_mw"] == pytest.approx(n["p_load_mw"], abs=1e-6)
        for n in parts
    )
    with_flow = [e for e in topo["edges"] if e["p_from_mw"] is not None]
    assert len(with_flow) > 0.9 * len(topo["edges"])
    losses = sum(e["p_from_mw"] + e["p_to_mw"] for e in with_flow)
    assert losses == pytest.approx(summary["p_losses_mw"], rel=0.05)
    assert all(k in topo["nodes"][0] for k in ("vm_kv", "va_degree", "slack_adjust_mw"))
    assert all(k in topo["edges"][0] for k in ("i_ka", "pl_mw", "ql_mvar"))
    # FR-037: el reporte de violaciones coincide con los contadores del resumen.
    viol = summary["violations"]
    kinds = [v["kind"] for v in viol]
    assert (
        kinds.count("tension_baja") + kinds.count("tension_alta") == summary["n_voltage_violations"]
    )
    assert kinds.count("sobrecarga") == summary["n_overloads"]
    assert all(v["deviation"] > 0 and v["source"] for v in viol)


def test_basemap_is_served_offline_as_geojson(client: TestClient):
    r = client.get("/api/geo/basemap")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/geo+json")
    fc = r.json()
    assert fc["type"] == "FeatureCollection" and "Natural Earth" in fc["attribution"]
    kinds = [f["properties"]["kind"] for f in fc["features"]]
    assert kinds.count("departamento") == 33 and kinds.count("pais_vecino") == 5


def test_errors_are_problem_details(client: TestClient):
    r = client.get("/api/cases/" + "0" * 64)
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert set(body) == PROBLEM_FIELDS and body["code"] == "CASE_NOT_FOUND"
    assert body["type"].endswith("/errors/case-not-found")
    r = client.post("/api/cases", json={"snapshot_date": "2000-01-01", "period": 1})
    assert r.status_code == 404 and r.json()["code"] == "SNAPSHOT_NOT_FOUND"
    r = client.post("/api/cases", json={"snapshot_date": "2026-10-20", "period": 25})
    assert (
        r.status_code == 422
        and r.json()["code"] == "REQUEST_INVALID"
        and set(r.json()) == PROBLEM_FIELDS
    )
    r = client.post("/api/cases", json={"snapshot_date": "2099-01-01", "period": 1})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_DATE"
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    r = client.post("/api/cases", json={"snapshot_date": tomorrow, "period": 1})
    assert r.status_code == 404 and r.json()["code"] == "SNAPSHOT_NOT_FOUND"  # D+1 pasa la fecha
    r = client.get("/api/runs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404 and r.json()["code"] == "RUN_NOT_FOUND"


def test_large_responses_are_gzip_compressed_when_accepted(client: TestClient):
    r = client.get("/api/geo/basemap", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.headers.get("content-encoding") == "gzip"
    assert (
        r.json()["type"] == "FeatureCollection"
    )  # el cliente lo descomprime de forma transparente
