"""HU-3: `sinsim scrape` con respuestas grabadas (`httpx.MockTransport`); sin red (R-03, SC-006)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from sinsim import cli
from sinsim.domain.errors import DomainError
from sinsim.scraper import http as scraper_http
from sinsim.scraper import paratec, xm_files
from tests.conftest import FIXTURES, make_context

runner = CliRunner()
LISTING_MODIFIED = "2026-10-19T14:05:11-05:00"


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    if root.exists():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                h.update(p.relative_to(root).as_posix().encode())
                h.update(p.read_bytes())
    return h.hexdigest()


class FakeXm:
    """Simula PARATEC y el portal de archivos de XM con los fixtures."""

    def __init__(self) -> None:
        self.paratec_overrides: dict[str, bytes] = {}
        self.xm_overrides: dict[str, bytes] = {}
        self.fail_with: Exception | None = None
        self.calls: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        if self.fail_with is not None:
            raise self.fail_with
        url = str(request.url)
        for ep in paratec.ENDPOINTS:
            if url == ep.url:
                payload = (
                    self.paratec_overrides.get(ep.entity)
                    or (FIXTURES / "paratec" / ep.raw_name).read_bytes()
                )
                return httpx.Response(
                    200, content=payload, headers={"content-type": "application/json"}
                )
        if url.startswith(xm_files.BASE_URL + "/descarga-archivo"):
            ruta = request.url.params["ruta"]
            name = ruta.rsplit("/", 1)[-1]
            payload = self.xm_overrides.get(name)
            if payload is None:
                src = FIXTURES / "xm" / name
                if not src.exists():
                    return httpx.Response(404)
                payload = src.read_bytes()
            return httpx.Response(200, content=payload, headers={"content-type": "text/plain"})
        if url.startswith(xm_files.BASE_URL):
            prefix = request.url.params["nombre"]
            ruta = request.url.params["ruta"]
            names = ["dDEC1020.txt"] if "DESPACHO" in ruta else ["PRON_BARRA1020.txt"]
            items = [
                {"nombre": n, "fechaModificacion": LISTING_MODIFIED, "tamano": 1}
                for n in names
                if n.startswith(prefix)
            ]
            return httpx.Response(200, json={"data": items})
        return httpx.Response(404)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[FakeXm, Path]:
    fake = FakeXm()
    monkeypatch.setattr(scraper_http, "DEFAULT_TRANSPORT", httpx.MockTransport(fake.handler))
    monkeypatch.setattr(scraper_http.RateLimitedClient, "_wait", lambda self: None)
    data_dir = tmp_path / "paratec"
    data_dir.mkdir()
    context = make_context(data_dir, tmp_path / "cases")
    monkeypatch.setattr(cli, "build_context", lambda: context)
    return fake, data_dir


def test_scrape_creates_a_complete_snapshot(fake):
    fake_xm, data_dir = fake
    result = runner.invoke(cli.app, ["scrape", "--fecha", "2026-10-20"])
    assert result.exit_code == 0, result.output
    snap = data_dir / "2026-10-20"
    manifest = json.loads((snap / "manifest.json").read_text())
    assert manifest["record_counts"]["xm.dispatch.resources"] == 626
    assert manifest["dispatch_version"] == {"used": "V0", "available": ["V0"]}
    xm_sources = [s for s in manifest["sources"] if s["entity"].startswith("xm.")]
    assert {s["entity"] for s in xm_sources} == {"xm.dispatch", "xm.demand"}
    assert all(s["source_modified_at"].startswith("2026-10-19") for s in xm_sources)
    assert all(s["standard_version"] == "XM-CND-2014-045 ed. 2025" for s in xm_sources)
    assert (snap / "raw" / "xm" / "dDEC1020.txt").read_bytes() == (
        FIXTURES / "xm" / "dDEC1020.txt"
    ).read_bytes()
    assert not any(p.name.startswith(".tmp-") for p in data_dir.iterdir())
    assert "Snapshot creado" in result.output and "V0" in result.output
    listed = runner.invoke(cli.app, ["snapshots", "list"])
    assert "2026-10-20" in listed.output
    agents = {c for c in fake_xm.calls}
    assert any("paratecbackend" in c for c in agents) and any("api-portalxm" in c for c in agents)


def test_second_scrape_for_same_date_changes_nothing(fake):
    _, data_dir = fake
    assert runner.invoke(cli.app, ["scrape", "--fecha", "2026-10-20"]).exit_code == 0
    before = tree_hash(data_dir)
    result = runner.invoke(cli.app, ["scrape", "--fecha", "2026-10-20"])
    assert result.exit_code == 1 and "SNAPSHOT_EXISTS" in result.output
    assert tree_hash(data_dir) == before


def test_schema_change_leaves_no_partial_snapshot(fake):
    fake_xm, data_dir = fake
    fake_xm.paratec_overrides["paratec.lines"] = b'{"header": {}, "otra_clave": []}'
    before = tree_hash(data_dir)
    result = runner.invoke(cli.app, ["scrape", "--fecha", "2026-10-20"])
    assert result.exit_code == 4 and "PARATEC_SCHEMA_CHANGED" in result.output
    assert "paratec.lines" in result.output
    assert tree_hash(data_dir) == before and list(data_dir.iterdir()) == []


def test_dispatch_total_mismatch_is_exit_4(fake):
    fake_xm, data_dir = fake
    text = (FIXTURES / "xm" / "dDEC1020.txt").read_bytes().decode("utf-8", errors="replace")
    altered = text.replace('"Total",', '"Total", 9999.0,', 1)
    fake_xm.xm_overrides["dDEC1020.txt"] = altered.encode("utf-8")
    result = runner.invoke(cli.app, ["scrape", "--fecha", "2026-10-20"])
    assert result.exit_code == 4 and (
        "XM_FILE_SCHEMA_CHANGED" in result.output or "DISPATCH_TOTAL_MISMATCH" in result.output
    )
    assert list(data_dir.iterdir()) == []


def test_network_error_is_exit_3_and_data_untouched(fake):
    fake_xm, data_dir = fake
    assert (
        runner.invoke(cli.app, ["scrape", "--fecha", "2026-10-19"]).exit_code == 1
    )  # sin archivos de ese día
    fake_xm.fail_with = httpx.ConnectError("sin conexión")
    before = tree_hash(data_dir)
    result = runner.invoke(cli.app, ["scrape", "--fecha", "2026-10-20"])
    assert result.exit_code == 3 and "NETWORK_ERROR" in result.output
    assert tree_hash(data_dir) == before


def test_missing_day_is_reported_as_not_published(fake):
    _, data_dir = fake
    result = runner.invoke(cli.app, ["scrape", "--fecha", "2026-10-19"])
    assert result.exit_code == 1 and "XM_FILE_NOT_FOUND" in result.output
    assert list(data_dir.iterdir()) == []


def test_parse_listing_is_tolerant_but_strict_on_shape():
    files = xm_files.parse_listing(
        b'[{"nombre": "dDEC1020.txt", "fechaModificacion": "2026-10-19T14:05:11-05:00"}]'
    )
    assert files[0].name == "dDEC1020.txt" and files[0].modified_at is not None
    assert xm_files.parse_listing(b'{"items": [{"name": "X"}]}')[0].modified_at is None
    for bad in (b"no json", b'{"a": 1}', b"[1, 2]", b'[{"sin_nombre": 1}]'):
        with pytest.raises(DomainError) as exc:
            xm_files.parse_listing(bad)
        assert exc.value.code == "XM_FILE_SCHEMA_CHANGED"
