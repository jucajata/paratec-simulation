"""Repositorio de snapshots en `data/paratec/<fecha>/` (implementa `SnapshotRepository`).

Al cargar un snapshot se recalcula el SHA-256 de cada archivo y se compara con el manifiesto;
cualquier diferencia es `SNAPSHOT_CORRUPTED` (FR-006). Las tablas se leen con DuckDB.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from sinsim.adapters.sources_to_pandapower.buses import parse_subareas, parse_substation_coords
from sinsim.adapters.sources_to_pandapower.field_mapping import RESPONSE_DATA
from sinsim.domain.entities import LoadedSnapshot, Manifest, SnapshotSummary, SnapshotTables
from sinsim.domain.errors import DomainError
from sinsim.scraper.writer import NORMALIZED, RAW_PARATEC, TABLE_NAMES, sha256_bytes, sha256_file


class ParquetSnapshotRepository:
    """Lee snapshots inmutables desde el sistema de archivos."""

    def __init__(self, root: Path) -> None:
        """Crea el repositorio sobre un directorio raíz (`data/paratec/`)."""
        self.root = root

    def _dir(self, snapshot_date: date) -> Path:
        return self.root / snapshot_date.isoformat()

    def read_manifest(self, snapshot_date: date) -> tuple[Manifest, str]:
        """Lee el manifiesto y devuelve también su SHA-256."""
        path = self._dir(snapshot_date) / "manifest.json"
        if not path.exists():
            raise DomainError("SNAPSHOT_NOT_FOUND", f"no existe {path.parent}")
        raw = path.read_bytes()
        return Manifest.model_validate_json(raw), sha256_bytes(raw)

    def verify(self, snapshot_date: date) -> list[str]:
        """Devuelve la lista de archivos cuyo checksum no coincide (vacía si está íntegro)."""
        manifest, _ = self.read_manifest(snapshot_date)
        base = self._dir(snapshot_date)
        bad: list[str] = []
        for entry in manifest.files:
            p = base / entry.path
            if not p.exists() or sha256_file(p) != entry.sha256:
                bad.append(entry.path)
        return bad

    def list_summaries(self) -> list[SnapshotSummary]:
        """Lista las fechas disponibles con disponibilidad e integridad (FR-002)."""
        out: list[SnapshotSummary] = []
        if not self.root.exists():
            return out
        for d in sorted(self.root.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            try:
                snapshot_date = date.fromisoformat(d.name)
                manifest, _ = self.read_manifest(snapshot_date)
            except (ValueError, DomainError):
                continue
            counts = manifest.record_counts
            out.append(
                SnapshotSummary(
                    date=snapshot_date,
                    has_paratec=counts.get("normalized.buses", 0) > 0,
                    has_dispatch=counts.get("xm.dispatch.resources", 0) > 0,
                    has_demand=counts.get("xm.demand.nodes", 0) > 0,
                    intact=not self.verify(snapshot_date),
                )
            )
        return out

    def load(self, snapshot_date: date) -> LoadedSnapshot:
        """Carga y verifica un snapshot (FR-006)."""
        manifest, manifest_sha = self.read_manifest(snapshot_date)
        bad = self.verify(snapshot_date)
        if bad:
            raise DomainError(
                "SNAPSHOT_CORRUPTED",
                f"checksum distinto al del manifiesto en: {', '.join(bad)}",
                user_message=(
                    "El snapshot está alterado y no se usa. Archivos afectados: "
                    + ", ".join(bad)
                    + ". Restáuralo desde git o genera uno nuevo con `sinsim scrape`."
                ),
            )
        base = self._dir(snapshot_date) / NORMALIZED
        tables = {name: self._read_table(base / f"{name}.parquet") for name in TABLE_NAMES}
        if not {"subarea", "lat", "lon"} <= set(tables["buses"].columns):
            tables["buses"] = self._with_substation_attrs_from_raw(tables["buses"], snapshot_date)
        return LoadedSnapshot(
            date=snapshot_date,
            manifest=manifest,
            manifest_sha256=manifest_sha,
            tables=SnapshotTables(**tables),
        )

    def _with_substation_attrs_from_raw(
        self, buses: pd.DataFrame, snapshot_date: date
    ) -> pd.DataFrame:
        """Añade `subarea`, `lat` y `lon` a snapshots anteriores a FR-034/FR-035 desde `raw/`.

        `raw/` es inmutable y ya está verificado contra el manifiesto, así que derivar las
        columnas en memoria no altera el snapshot (constitución III.3 y III.4). No escribe nada.
        """
        out = buses.copy()
        raw = sorted(
            (self._dir(snapshot_date) / RAW_PARATEC).glob("*Substation_SubstationInfo.json")
        )
        records: list[dict[str, object]] = []
        if raw:
            payload = json.loads(raw[0].read_text(encoding="utf-8"))
            records = (
                payload.get(RESPONSE_DATA, []) if isinstance(payload, dict) else payload
            ) or []
        subareas = parse_subareas(records)
        coords = parse_substation_coords(records)
        if "subarea" not in out.columns:
            out["subarea"] = out["substation"].map(lambda s: subareas.get(str(s)))
        if "lat" not in out.columns or "lon" not in out.columns:
            out["lat"] = out["substation"].map(lambda s: coords.get(str(s), (None, None))[0])
            out["lon"] = out["substation"].map(lambda s: coords.get(str(s), (None, None))[1])
        return out

    @staticmethod
    def _read_table(path: Path) -> pd.DataFrame:
        if not path.exists():
            raise DomainError("SNAPSHOT_CORRUPTED", f"falta la tabla {path.name}")
        df = duckdb.sql(f"SELECT * FROM read_parquet('{path.as_posix()}')").df()
        if "missing_params" in df.columns:
            df["missing_params"] = df["missing_params"].map(json.loads)
        return df
