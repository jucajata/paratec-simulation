"""Contrato de la API del análisis N-1 (specs/003-contingencias-n1/contracts/openapi-n1.yaml)."""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

from sinsim.api.app import create_app
from sinsim.services import n1

PROBLEM_FIELDS = {"type", "title", "status", "detail", "code", "user_message", "trace_id"}
JOB_FIELDS = {
    "job_id",
    "run_id",
    "status",
    "done",
    "total",
    "started_at",
    "finished_at",
    "result",
    "error",
}


@pytest.fixture
def client(app_context) -> TestClient:
    return TestClient(
        create_app(app_context), raise_server_exceptions=False, base_url="http://127.0.0.1"
    )


@pytest.fixture
def few_outages(monkeypatch: pytest.MonkeyPatch) -> int:
    """Limita el análisis a 5 contingencias en este proceso, para que la prueba sea corta."""
    real = n1.enumerate_outages
    monkeypatch.setattr(n1, "enumerate_outages", lambda net: real(net)[:5])
    monkeypatch.setattr(n1, "default_workers", lambda: 1)
    return 5


def run_id_of(client: TestClient, flow_type: str = "ac") -> tuple[str, str]:
    case = client.post("/api/cases", json={"snapshot_date": "2026-10-20", "period": 19}).json()
    run = client.post(f"/api/cases/{case['case_id']}/runs", json={"flow_type": flow_type}).json()
    assert run["status"] == "convergio"
    return run["run_id"], case["case_id"]


def wait_done(client: TestClient, job_id: str, timeout_s: float = 120.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        r = client.get(f"/api/n1/{job_id}")
        assert r.status_code == 200, r.text
        job = r.json()
        if job["status"] in ("listo", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("el análisis no terminó a tiempo")


def test_start_and_follow_an_analysis(client: TestClient, few_outages: int):
    run_id, case_id = run_id_of(client)
    r = client.post(f"/api/runs/{run_id}/n1")
    assert r.status_code == 202, r.text
    job = r.json()
    assert set(job) == JOB_FIELDS
    assert job["status"] in ("en_cola", "calculando") and job["run_id"] == run_id
    assert job["result"] is None and job["error"] is None
    done = wait_done(client, job["job_id"])
    assert done["status"] == "listo", done
    assert done["done"] == done["total"] == few_outages and done["finished_at"]
    result = done["result"]
    assert result["run_id"] == run_id and result["trace"]["case_id"] == case_id
    assert result["workers"] == 1 and result["analyzed_at"]
    assert any(lim["name"] == "Cargabilidad" and lim["source"] for lim in result["limits"])
    s = result["summary"]
    assert s["n_total"] == few_outages
    assert set(result) >= {"loading", "voltage", "isolation", "unsolved"}
    assert s["n_unsolved"] == len(result["unsolved"])
    assert s["n_loading"] == len(result["loading"]) and s["n_voltage"] == len(result["voltage"])
    for i, row in enumerate(result["loading"], start=1):
        assert row["rank"] == i and row["outage"]["kind"] in (
            "line",
            "trafo2w",
            "gen",
            "compensador",
        )
        assert row["loading_percent"] > row["loading_base_percent"]
    # Las rutas nuevas están en el OpenAPI generado.
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/runs/{run_id}/n1" in paths and "/api/n1/{job_id}" in paths


def test_dc_run_is_rejected_as_base(client: TestClient, few_outages: int):
    run_id, _ = run_id_of(client, "dc")
    r = client.post(f"/api/runs/{run_id}/n1")
    assert r.status_code == 422, r.text
    body = r.json()
    assert set(body) == PROBLEM_FIELDS and body["code"] == "N1_BASE_INVALID"
    assert "flujo AC" in body["user_message"]


def test_unknown_run_and_job(client: TestClient):
    r = client.post("/api/runs/00000000-0000-0000-0000-000000000000/n1")
    assert r.status_code == 404 and r.json()["code"] == "RUN_NOT_FOUND"
    r = client.get("/api/n1/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404 and r.json()["code"] == "N1_JOB_NOT_FOUND"
    assert "mientras la API sigue encendida" in r.json()["user_message"]


def test_only_one_analysis_at_a_time(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    gate = threading.Event()
    real = n1.analyze

    def slow_analyze(run, net_json, cfg, **kwargs):
        assert gate.wait(30), "la prueba no abrió la compuerta"
        return real(run, net_json, cfg, workers=1, outages=[], **kwargs)

    monkeypatch.setattr(n1, "analyze", slow_analyze)
    run_id, _ = run_id_of(client)
    first = client.post(f"/api/runs/{run_id}/n1")
    assert first.status_code == 202, first.text
    second = client.post(f"/api/runs/{run_id}/n1")
    assert second.status_code == 409 and second.json()["code"] == "N1_IN_PROGRESS"
    assert "Espera a que termine" in second.json()["user_message"]
    gate.set()
    done = wait_done(client, first.json()["job_id"])
    assert done["status"] == "listo" and done["result"]["summary"]["n_total"] == 0
    # Terminado el primero, se acepta otro.
    assert client.post(f"/api/runs/{run_id}/n1").status_code == 202


def test_foreign_origin_cannot_start_an_analysis(client: TestClient):
    run_id, _ = run_id_of(client)
    r = client.post(f"/api/runs/{run_id}/n1", headers={"Origin": "https://ajena.example"})
    assert r.status_code == 403 and r.json()["code"] == "ORIGIN_NOT_ALLOWED"
