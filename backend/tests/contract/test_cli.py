"""Contrato del CLI (contracts/cli.md): códigos de salida y salida JSON."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sinsim import cli
from tests.conftest import make_context

runner = CliRunner()


@pytest.fixture
def ctx(snapshot_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    context = make_context(snapshot_root, tmp_path / "cases")
    monkeypatch.setattr(cli, "build_context", lambda: context)
    return context


def test_snapshots_list_shows_fixture(ctx):
    result = runner.invoke(cli.app, ["snapshots", "list"])
    assert result.exit_code == 0, result.output
    assert "2026-10-20" in result.output and "sí" in result.output
    result = runner.invoke(cli.app, ["snapshots", "list", "--json"])
    assert result.exit_code == 0 and json.loads(result.output)[0]["date"] == "2026-10-20"


def test_run_converges_and_prints_quality_and_trace(ctx):
    result = runner.invoke(cli.app, ["run", "--fecha", "2026-10-20", "--periodo", "19"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "Reporte de calidad" in out and "Flujo sobre despacho programado" in out
    assert "Estado: convergio" in out and "pandapower 3.5.6" in out
    assert "Peores tensiones" in out and "Mayores cargabilidades" in out
    assert "PROGRAM_NOT_REAL_STATE" in out


def test_run_json_output(ctx):
    result = runner.invoke(cli.app, ["run", "--fecha", "2026-10-20", "--periodo", "19", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert set(data) == {"case", "run"} and data["run"]["status"] == "convergio"
    assert data["case"]["quality"]["balance"]["coverage_pct"] > 80


def test_exit_codes(ctx):
    assert runner.invoke(cli.app, ["run", "--fecha", "2000-01-01", "--periodo", "1"]).exit_code == 1
    assert (
        runner.invoke(cli.app, ["run", "--fecha", "2026-10-20", "--periodo", "25"]).exit_code == 2
    )
    assert runner.invoke(cli.app, ["run", "--fecha", "2026-13-01", "--periodo", "1"]).exit_code == 2
    assert runner.invoke(cli.app, ["run", "--fecha", "2099-01-01", "--periodo", "1"]).exit_code == 2
    assert (
        runner.invoke(
            cli.app, ["run", "--fecha", "2026-10-20", "--periodo", "1", "--tipo", "xx"]
        ).exit_code
        == 2
    )
    r = runner.invoke(cli.app, ["run", "--fecha", "2000-01-01", "--periodo", "1"])
    assert "SNAPSHOT_NOT_FOUND" in r.output and "sinsim scrape" in r.output
