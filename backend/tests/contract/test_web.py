"""Interfaz servida por la API (FR-045), comando `sinsim serve` (FR-044) y descarga duplicada (FR-043)."""

import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from sinsim import cli
from sinsim.adapters.storage.snapshots import ParquetSnapshotRepository
from sinsim.api.app import create_app
from sinsim.domain.errors import DomainError
from sinsim.services.scrape import scrape_snapshot

runner = CliRunner()


@pytest.fixture
def web_dir(tmp_path: Path) -> Path:
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<!doctype html><title>sinsim</title>", encoding="utf-8")
    (web / "assets" / "app.js").write_text("console.log('sinsim')", encoding="utf-8")
    return web


def test_the_api_serves_the_built_interface_without_hiding_the_api(app_context, web_dir):
    ctx = replace(app_context, paths=replace(app_context.paths, web=web_dir))
    client = TestClient(create_app(ctx))
    home = client.get("/")
    assert home.status_code == 200 and "<title>sinsim</title>" in home.text
    assert client.get("/assets/app.js").status_code == 200
    api = client.get("/api/snapshots")
    assert api.status_code == 200 and api.json()[0]["date"] == "2026-10-20"


def test_without_a_built_interface_only_the_api_answers(app_context):
    ctx = replace(app_context, paths=replace(app_context.paths, web=None))
    client = TestClient(create_app(ctx))
    assert client.get("/").status_code == 404
    assert client.get("/api/snapshots").status_code == 200


@pytest.fixture
def served(app_context, monkeypatch: pytest.MonkeyPatch) -> dict:
    calls: dict = {}
    # Sin interfaz por defecto, aunque el repositorio tenga frontend/dist/ construido.
    without_web = replace(app_context, paths=replace(app_context.paths, web=None))
    monkeypatch.setattr(cli, "build_context", lambda: without_web)
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: calls.update(app=app, **kw))
    monkeypatch.setattr(cli, "_open_when_ready", lambda url: calls.update(opened=url))
    return calls


def test_serve_listens_only_on_localhost_and_opens_the_browser(
    served, app_context, web_dir, monkeypatch
):
    with_web = replace(app_context, paths=replace(app_context.paths, web=web_dir))
    monkeypatch.setattr(cli, "build_context", lambda: with_web)
    result = runner.invoke(cli.app, ["serve", "--puerto", "8123"])
    assert result.exit_code == 0, result.output
    assert served["host"] == "127.0.0.1" and served["port"] == 8123
    assert served["opened"] == "http://127.0.0.1:8123"
    assert "sinsim en http://127.0.0.1:8123" in result.output


def test_serve_without_interface_warns_and_does_not_open(served):
    result = runner.invoke(cli.app, ["serve", "--no-abrir"])
    assert result.exit_code == 0, result.output
    assert served["host"] == "127.0.0.1" and served["port"] == 8000
    assert "opened" not in served
    assert "La interfaz no está incluida" in result.output


def test_an_included_snapshot_is_not_downloaded_again(app_context, snapshot_root, tmp_path):
    bundled = tmp_path / "paquete"
    shutil.copytree(snapshot_root, bundled)
    user = tmp_path / "usuario"
    user.mkdir()
    ctx = replace(
        app_context, snapshots=ParquetSnapshotRepository(user, read_only_roots=(bundled,))
    )
    with pytest.raises(DomainError) as err:
        scrape_snapshot(ctx, date(2026, 10, 20))
    assert err.value.code == "SNAPSHOT_EXISTS"
