import shutil
from datetime import date
from pathlib import Path

import pytest

from sinsim.adapters.storage.snapshots import ParquetSnapshotRepository

DAY = date(2026, 10, 20)


@pytest.fixture
def roots(snapshot_root: Path, tmp_path: Path) -> tuple[Path, Path]:
    """Una raíz escribible vacía y una de solo lectura con el snapshot de fixtures."""
    user = tmp_path / "usuario"
    user.mkdir()
    bundled = tmp_path / "paquete"
    shutil.copytree(snapshot_root, bundled)
    return user, bundled


def test_reads_an_included_snapshot_from_the_read_only_root(roots):
    user, bundled = roots
    repo = ParquetSnapshotRepository(user, read_only_roots=(bundled,))
    assert [s.date for s in repo.list_summaries()] == [DAY]
    assert repo.list_summaries()[0].intact
    assert repo.has(DAY)
    assert repo.load(DAY).date == DAY


def test_a_snapshot_in_the_user_folder_wins_and_is_listed_once(roots):
    user, bundled = roots
    shutil.copytree(bundled / DAY.isoformat(), user / DAY.isoformat())
    repo = ParquetSnapshotRepository(user, read_only_roots=(bundled,))
    assert [s.date for s in repo.list_summaries()] == [DAY]
    assert repo._dir(DAY) == user / DAY.isoformat()


def test_without_read_only_roots_behaves_as_before(roots):
    user, _ = roots
    repo = ParquetSnapshotRepository(user)
    assert repo.list_summaries() == []
    assert not repo.has(DAY)
    assert repo._dir(DAY) == user / DAY.isoformat()
