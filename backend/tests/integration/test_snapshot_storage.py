"""Escritura atómica, manifiesto, checksums y lectura de snapshots (FR-004 a FR-006, SC-006)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

import pytest

from sinsim.adapters.storage.snapshots import ParquetSnapshotRepository
from sinsim.domain.errors import DomainError
from sinsim.scraper.writer import TABLE_NAMES, write_snapshot
from sinsim.services import snapshots as snapshot_service
from tests.conftest import ATTRIBUTION, SNAPSHOT_DATE, build_raw_snapshot


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def test_written_snapshot_has_manifest_checksums_and_tables(snapshot_root: Path):
    base = snapshot_root / "2026-10-20"
    manifest = json.loads((base / "manifest.json").read_text())
    assert manifest["schema_version"] == 1 and manifest["snapshot_date"] == "2026-10-20"
    assert manifest["attribution"] == ATTRIBUTION
    assert manifest["dispatch_version"] == {"used": "V0", "available": ["V0"]}
    assert {s["entity"] for s in manifest["sources"]} >= {
        "xm.dispatch",
        "xm.demand",
        "paratec.lines",
    }
    xm_sources = [s for s in manifest["sources"] if s["entity"].startswith("xm.")]
    assert all(s["source_modified_at"] and s["standard_version"] for s in xm_sources)
    files = {f["path"]: f for f in manifest["files"]}
    assert (
        "raw/xm/dDEC1020.txt" in files
        and "raw/paratec/reportetransmision__Line_getAll.json" in files
    )
    assert all(f"normalized/{t}.parquet" in files for t in TABLE_NAMES)
    assert "manifest.json" not in files
    for path, entry in files.items():
        assert hashlib.sha256((base / path).read_bytes()).hexdigest() == entry["sha256"]
    counts = manifest["record_counts"]
    assert counts["paratec.lines"] == 929 and counts["xm.dispatch.resources"] == 626
    assert counts["xm.demand.nodes"] == 552 and counts["normalized.buses"] > 1000
    assert not (snapshot_root / ".tmp-2026-10-20").exists()


def test_raw_bytes_are_stored_unmodified(snapshot_root: Path, fixtures_dir: Path):
    stored = (snapshot_root / "2026-10-20" / "raw" / "xm" / "dDEC1020.txt").read_bytes()
    assert stored == (fixtures_dir / "xm" / "dDEC1020.txt").read_bytes()


def test_second_write_for_same_date_is_rejected_without_changes(snapshot_root: Path):
    before = tree_hash(snapshot_root)
    with pytest.raises(DomainError) as exc:
        write_snapshot(
            build_raw_snapshot(), snapshot_root, SNAPSHOT_DATE, scraper_version="t", attribution="x"
        )
    assert exc.value.code == "SNAPSHOT_EXISTS"
    assert tree_hash(snapshot_root) == before


def test_validation_failure_leaves_no_partial_snapshot(tmp_path: Path):
    root = tmp_path / "paratec"
    root.mkdir()
    bad = build_raw_snapshot(paratec_overrides={"paratec.lines": b'{"header": {}, "sin_data": []}'})
    with pytest.raises(DomainError) as exc:
        write_snapshot(bad, root, SNAPSHOT_DATE, scraper_version="t", attribution="x")
    assert exc.value.code == "PARATEC_SCHEMA_CHANGED" and "paratec.lines" in exc.value.detail
    assert list(root.iterdir()) == []


def test_dispatch_total_mismatch_is_validation_failure(tmp_path: Path, fixtures_dir: Path):
    root = tmp_path / "paratec"
    root.mkdir()
    text = (fixtures_dir / "xm" / "dDEC1020.txt").read_bytes().decode("utf-8", errors="replace")
    altered = re.sub(r'^"Total",\s*[\d.]+', '"Total", 9999.0', text, count=1, flags=re.MULTILINE)
    assert altered != text
    bad = build_raw_snapshot(xm_overrides={"dDEC1020.txt": altered.encode("utf-8")})
    with pytest.raises(DomainError) as exc:
        write_snapshot(bad, root, SNAPSHOT_DATE, scraper_version="t", attribution="x")
    assert exc.value.code == "DISPATCH_TOTAL_MISMATCH"
    assert list(root.iterdir()) == []


def test_load_reads_tables_and_list_reports_availability(snapshot_repo: ParquetSnapshotRepository):
    loaded = snapshot_service.load_verified(snapshot_repo, SNAPSHOT_DATE)
    assert loaded.date == SNAPSHOT_DATE and len(loaded.manifest_sha256) == 64
    assert len(loaded.tables.lines) == 929 and isinstance(
        loaded.tables.lines.missing_params.iloc[0], list
    )
    assert loaded.tables.dispatch.resource.nunique() == 626
    summaries = snapshot_service.list_snapshots(snapshot_repo)
    assert [s.date for s in summaries] == [SNAPSHOT_DATE]
    s = summaries[0]
    assert s.has_paratec and s.has_dispatch and s.has_demand and s.intact
    snapshot_service.require_operating_point(loaded)


def test_missing_snapshot_raises_not_found(snapshot_repo: ParquetSnapshotRepository):
    with pytest.raises(DomainError) as exc:
        snapshot_repo.load(date(2000, 1, 1))
    assert exc.value.code == "SNAPSHOT_NOT_FOUND"


def test_altered_byte_is_detected_as_corruption(tmp_path: Path):
    root = tmp_path / "paratec"
    root.mkdir()
    write_snapshot(build_raw_snapshot(), root, SNAPSHOT_DATE, scraper_version="t", attribution="x")
    target = root / "2026-10-20" / "raw" / "xm" / "PRON_BARRA1020.txt"
    data = bytearray(target.read_bytes())
    data[10] ^= 0xFF
    target.write_bytes(bytes(data))
    repo = ParquetSnapshotRepository(root)
    assert repo.list_summaries()[0].intact is False
    with pytest.raises(DomainError) as exc:
        repo.load(SNAPSHOT_DATE)
    assert exc.value.code == "SNAPSHOT_CORRUPTED"
    assert "raw/xm/PRON_BARRA1020.txt" in exc.value.detail
    assert "PRON_BARRA1020.txt" in exc.value.user_message


def test_new_snapshots_store_subarea_and_old_ones_derive_it_from_raw(snapshot_root: Path):
    """FR-034: la subárea viene de PARATEC; un snapshot sin la columna la toma de `raw/`."""
    repo = ParquetSnapshotRepository(snapshot_root)
    buses = repo.load(SNAPSHOT_DATE).tables.buses
    assert "subarea" in buses.columns
    with_subarea = buses[buses.subarea.notna()]
    assert len(with_subarea) > 0.9 * len(buses)
    assert not with_subarea.subarea.str.startswith("SubArea").any()
    before = tree_hash(snapshot_root)
    derived = repo._with_substation_attrs_from_raw(
        buses.drop(columns=["subarea", "lat", "lon"]), SNAPSHOT_DATE
    )
    assert derived.subarea.fillna("").tolist() == buses.subarea.fillna("").tolist()
    # FR-035: coordenadas de PARATEC, idénticas guardadas o derivadas de raw/.
    assert buses.lat.notna().sum() > 0.9 * len(buses)
    assert derived.lat.fillna(0).tolist() == buses.lat.fillna(0).tolist()
    assert derived.lon.fillna(0).tolist() == buses.lon.fillna(0).tolist()
    assert tree_hash(snapshot_root) == before  # no escribe nada en el snapshot
