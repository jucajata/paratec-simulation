"""Fixtures compartidos. Ninguna prueba accede a PARATEC ni a XM (R-03)."""

from __future__ import annotations

import json
import warnings
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from sinsim.adapters.storage.equivalences import CsvEquivalenceRepository
from sinsim.adapters.storage.snapshots import ParquetSnapshotRepository
from sinsim.bootstrap import AppContext, build_context
from sinsim.domain.entities import LoadedSnapshot, SourceFile
from sinsim.scraper import paratec
from sinsim.scraper.writer import RawSnapshot, write_snapshot

warnings.filterwarnings("ignore", message="numba cannot be imported")

FIXTURES = Path(__file__).parent / "fixtures"
SNAPSHOT_DATE = date(2026, 10, 20)
ATTRIBUTION = (
    "Información proporcionada por XM S.A. E.S.P. – PARATEC y archivos públicos de despacho"
)


def load_fixture_json(name: str) -> list[dict]:
    """Carga el `data` de un fixture de PARATEC."""
    return json.loads((FIXTURES / "paratec" / name).read_text(encoding="utf-8"))["data"]


def build_raw_snapshot(
    *,
    xm_overrides: dict[str, bytes] | None = None,
    paratec_overrides: dict[str, bytes] | None = None,
) -> RawSnapshot:
    """Construye un `RawSnapshot` desde los fixtures, con sustituciones opcionales."""
    par = {ep.entity: (FIXTURES / "paratec" / ep.raw_name).read_bytes() for ep in paratec.ENDPOINTS}
    par.update(paratec_overrides or {})
    xm = {
        "dDEC1020.txt": (FIXTURES / "xm" / "dDEC1020.txt").read_bytes(),
        "PRON_BARRA1020.txt": (FIXTURES / "xm" / "PRON_BARRA1020.txt").read_bytes(),
    }
    xm.update(xm_overrides or {})
    sources = [SourceFile(entity=ep.entity, url=ep.url) for ep in paratec.ENDPOINTS] + [
        SourceFile(
            entity="xm.dispatch",
            url="fixture://dDEC1020.txt",
            source_modified_at=datetime(2026, 10, 19, 14, 5, tzinfo=UTC),
            standard_version="XM-CND-2014-045 ed. 2025",
        ),
        SourceFile(
            entity="xm.demand",
            url="fixture://PRON_BARRA1020.txt",
            source_modified_at=datetime(2026, 10, 19, 7, 46, tzinfo=UTC),
            standard_version="XM-CND-2014-045 ed. 2025",
        ),
    ]
    return RawSnapshot(paratec=par, xm=xm, sources=sources)


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def snapshot_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Escribe el snapshot de fixtures una sola vez por sesión en un directorio temporal."""
    root = tmp_path_factory.mktemp("paratec")
    write_snapshot(
        build_raw_snapshot(),
        root,
        SNAPSHOT_DATE,
        scraper_version="test",
        attribution=ATTRIBUTION,
    )
    return root


@pytest.fixture(scope="session")
def snapshot_repo(snapshot_root: Path) -> ParquetSnapshotRepository:
    return ParquetSnapshotRepository(snapshot_root)


@pytest.fixture(scope="session")
def fixture_snapshot(snapshot_repo: ParquetSnapshotRepository) -> LoadedSnapshot:
    return snapshot_repo.load(SNAPSHOT_DATE)


@pytest.fixture(scope="session")
def equivalences_repo() -> CsvEquivalenceRepository:
    return CsvEquivalenceRepository(FIXTURES / "equivalencias")


def make_context(snapshot_root: Path, cases_dir: Path) -> AppContext:
    """Contexto de aplicación sobre los fixtures y un directorio de casos temporal."""
    return build_context(
        snapshots_dir=snapshot_root,
        equivalences_dir=FIXTURES / "equivalencias",
        cases_dir=cases_dir,
    )


@pytest.fixture
def app_context(snapshot_root: Path, tmp_path: Path) -> AppContext:
    return make_context(snapshot_root, tmp_path / "cases")
