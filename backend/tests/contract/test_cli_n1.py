"""Contrato de `sinsim n1` (specs/003-contingencias-n1/contracts/cli-n1.md, HU-8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sinsim import cli
from sinsim.adapters.storage.export_n1 import CSV_FILES, METADATA_FILE
from sinsim.domain.entities import N1Analysis
from sinsim.services import n1
from tests.conftest import make_context

runner = CliRunner()


@pytest.fixture
def ctx(snapshot_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    context = make_context(snapshot_root, tmp_path / "cases")
    monkeypatch.setattr(cli, "build_context", lambda: context)
    real = n1.enumerate_outages
    monkeypatch.setattr(n1, "enumerate_outages", lambda net: real(net)[:4])
    monkeypatch.setattr(n1, "default_workers", lambda: 1)
    return context


def test_n1_writes_the_four_csv_and_metadata(ctx, tmp_path: Path):
    out = tmp_path / "salida"
    result = runner.invoke(
        cli.app, ["n1", "--fecha", "2026-10-20", "--periodo", "19", "--salida", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert {p.name for p in out.iterdir()} == {*CSV_FILES, METADATA_FILE}
    assert "N-1: 4/4 contingencias" in result.output
    assert "Contingencias analizadas: 4" in result.output
    assert "Cargabilidad" in result.output and "Tensiones" in result.output
    meta = json.loads((out / METADATA_FILE).read_text(encoding="utf-8"))
    assert meta["tipo"] == "analisis_n1" and meta["periodo"] == 19
    assert meta["resumen"]["n_total"] == 4 and meta["pandapower"] == "3.5.6"
    assert "XM S.A. E.S.P." in meta["atribucion"]


def test_default_output_folder_and_explicit_dispatch_date(ctx, tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli.app,
        ["n1", "--fecha", "2026-10-20", "--periodo", "7", "--fecha-despacho", "2026-10-20"],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "n1-2026-10-20-p07" / "n1_cargabilidad.csv").exists()


def test_json_output_is_a_valid_analysis(ctx, tmp_path: Path):
    result = runner.invoke(
        cli.app,
        [
            "n1",
            "--fecha",
            "2026-10-20",
            "--periodo",
            "19",
            "--salida",
            str(tmp_path / "o"),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    analysis = N1Analysis.model_validate(json.loads(result.stdout))
    assert analysis.summary.n_total == 4 and analysis.workers == 1
    assert analysis.trace.period == 19 and analysis.trace.flow_type == "ac"


def test_usage_errors(ctx, tmp_path: Path):
    assert runner.invoke(cli.app, ["n1", "--fecha", "2026-10-20", "--periodo", "25"]).exit_code == 2
    assert runner.invoke(cli.app, ["n1", "--fecha", "2026-13-01", "--periodo", "1"]).exit_code == 2
    r = runner.invoke(cli.app, ["n1", "--fecha", "2000-01-01", "--periodo", "1"])
    assert r.exit_code == 1 and "SNAPSHOT_NOT_FOUND" in r.output
    assert not list(tmp_path.glob("n1-*"))


def test_base_that_does_not_converge_exits_4_without_files(ctx, tmp_path: Path, monkeypatch):
    real = cli.build_case

    def overloaded(**kwargs):
        built = real(**kwargs)
        built.net.load.p_mw *= 50.0
        built.net.load.q_mvar *= 50.0
        return built

    monkeypatch.setattr(cli, "build_case", overloaded)
    out = tmp_path / "salida"
    r = runner.invoke(
        cli.app, ["n1", "--fecha", "2026-10-20", "--periodo", "19", "--salida", str(out)]
    )
    assert r.exit_code == 4, r.output
    assert "N1_BASE_INVALID" in r.output and "Diagnóstico" in r.output
    assert not out.exists()
