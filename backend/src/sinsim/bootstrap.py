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
from sinsim.config import (
    INSTALLED_MODE,
    LoadedConfig,
    RepoPaths,
    load_config,
    repo_paths,
    resolve_paths,
    sinsim_version,
)
from sinsim.observability import configure_logging
from sinsim.services.n1 import N1Runner
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
    n1_runner: N1Runner


def build_context(
    root: Path | None = None,
    *,
    snapshots_dir: Path | None = None,
    equivalences_dir: Path | None = None,
    cases_dir: Path | None = None,
    config_file: Path | None = None,
) -> AppContext:
    """Construye el contexto; los directorios se pueden sustituir (pruebas).

    Sin `root`, decide entre modo repositorio y modo instalado (FR-040). En modo instalado crea
    la carpeta de datos del usuario si aún no existe.
    """
    configure_logging()
    paths = repo_paths(root) if root is not None else resolve_paths()
    if paths.mode == INSTALLED_MODE:
        for d in (paths.snapshots, paths.cases):
            d.mkdir(parents=True, exist_ok=True)
    cfg = load_config(config_file or paths.config_file)
    return AppContext(
        paths=paths,
        cfg=cfg,
        snapshots=ParquetSnapshotRepository(
            snapshots_dir or paths.snapshots,
            read_only_roots=() if snapshots_dir is not None else paths.bundled_snapshots,
        ),
        equivalences=CsvEquivalenceRepository(equivalences_dir or paths.equivalences),
        cases=FileCaseRepository(cases_dir or paths.cases),
        version=sinsim_version(),
        scrape_runner=ScrapeRunner(),
        n1_runner=N1Runner(),
    )
