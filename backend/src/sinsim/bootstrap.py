"""Composición de dependencias para el CLI y la API.

Resuelve rutas del repositorio, carga la configuración y construye los repositorios. Es el
único lugar donde los adaptadores concretos se conectan con los servicios (constitución IV).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sinsim.adapters.storage.cases import FileCaseRepository
from sinsim.adapters.storage.equivalences import CsvEquivalenceRepository
from sinsim.adapters.storage.snapshots import ParquetSnapshotRepository
from sinsim.config import LoadedConfig, RepoPaths, load_config, repo_paths, sinsim_version
from sinsim.observability import configure_logging
from sinsim.services.scrape import ScrapeRunner


@dataclass(frozen=True)
class AppContext:
    """Dependencias ya construidas."""

    paths: RepoPaths
    cfg: LoadedConfig
    snapshots: ParquetSnapshotRepository
    equivalences: CsvEquivalenceRepository
    cases: FileCaseRepository
    version: str
    scrape_runner: ScrapeRunner


def build_context(
    root: Path | None = None,
    *,
    snapshots_dir: Path | None = None,
    equivalences_dir: Path | None = None,
    cases_dir: Path | None = None,
    config_file: Path | None = None,
) -> AppContext:
    """Construye el contexto; los directorios se pueden sustituir (pruebas)."""
    configure_logging()
    paths = repo_paths(root)
    cfg = load_config(config_file or paths.config_file)
    return AppContext(
        paths=paths,
        cfg=cfg,
        snapshots=ParquetSnapshotRepository(snapshots_dir or paths.snapshots),
        equivalences=CsvEquivalenceRepository(equivalences_dir or paths.equivalences),
        cases=FileCaseRepository(cases_dir or paths.cases),
        version=sinsim_version(),
        scrape_runner=ScrapeRunner(),
    )
