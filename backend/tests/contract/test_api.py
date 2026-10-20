"""Contrato de la API con contracts/openapi.yaml y Problem Details (constitución V)."""

from __future__ import annotations

import re
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
    r = client.get("/api/runs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404 and r.json()["code"] == "RUN_NOT_FOUND"
