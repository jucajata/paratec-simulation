"""Casos de uso sobre snapshots (constitución IV: `api → services → domain`).

CLI y API acceden a los snapshots solo a través de este módulo.
"""

from __future__ import annotations

from datetime import date

from sinsim.domain.entities import LoadedSnapshot, SnapshotSummary
from sinsim.domain.errors import DomainError
from sinsim.domain.ports import SnapshotRepository


def list_snapshots(repo: SnapshotRepository) -> list[SnapshotSummary]:
    """Lista las fechas disponibles con su disponibilidad e integridad (FR-002)."""
    return repo.list_summaries()


def load_verified(repo: SnapshotRepository, snapshot_date: date) -> LoadedSnapshot:
    """Carga un snapshot verificado; lanza `SNAPSHOT_NOT_FOUND` o `SNAPSHOT_CORRUPTED`."""
    return repo.load(snapshot_date)


def require_operating_point(snapshot: LoadedSnapshot) -> None:
    """Exige que el snapshot traiga despacho y demanda (HU-1.4).

    Raises:
        DomainError: `OPERATING_POINT_MISSING` con el dato que falta.
    """
    missing = []
    if snapshot.tables.dispatch.empty:
        missing.append("despacho programado (dDEC)")
    if snapshot.tables.demand.empty:
        missing.append("pronóstico de demanda por barra (PRON_BARRA)")
    if missing:
        raise DomainError(
            "OPERATING_POINT_MISSING",
            f"el snapshot {snapshot.date} no tiene: {', '.join(missing)}",
            user_message=(
                f"La fecha {snapshot.date} no tiene {' ni '.join(missing)}. "
                f"Ejecuta `sinsim scrape --fecha {snapshot.date}` para obtenerlos."
            ),
        )
