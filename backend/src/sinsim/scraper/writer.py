"""Escritura atómica de snapshots (constitución III.3, III.4, V).

`write_snapshot` escribe en `<out>/.tmp-<fecha>/`, normaliza raw → Parquet, valida, calcula
los checksums, escribe `manifest.json` y solo al final renombra a `<out>/<fecha>/`. Si algo
falla, borra el temporal y no deja ningún snapshot parcial (FR-005, SC-006).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from sinsim.adapters.sources_to_pandapower import (
    buses,
    generators,
    lines,
    shunts,
    trafos,
    xm_demand,
    xm_dispatch,
)
from sinsim.domain.entities import (
    DispatchVersion,
    FileEntry,
    Manifest,
    SnapshotTables,
    SourceFile,
)
from sinsim.domain.errors import DomainError
from sinsim.scraper import paratec
from sinsim.scraper.validate import parse_paratec_response, validate_tables

RAW_PARATEC = "raw/paratec"
RAW_XM = "raw/xm"
NORMALIZED = "normalized"
TABLE_NAMES = (
    "buses",
    "lines",
    "trafos2w",
    "trafos3w",
    "generators",
    "shunts",
    "svc_statcom",
    "dispatch",
    "demand",
)


@dataclass(frozen=True)
class RawSnapshot:
    """Archivos crudos de un snapshot, tal como se descargaron.

    Attributes:
        paratec: `entity` del catálogo → bytes de la respuesta JSON.
        xm: nombre de archivo (`dDEC1020.txt`, `PRON_BARRA1020.txt`) → bytes.
        sources: origen de cada archivo para el manifiesto.
    """

    paratec: Mapping[str, bytes]
    xm: Mapping[str, bytes]
    sources: list[SourceFile]


def sha256_bytes(data: bytes) -> str:
    """SHA-256 hexadecimal de un bloque de bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """SHA-256 hexadecimal de un archivo, leído por bloques."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize(raw: RawSnapshot) -> tuple[SnapshotTables, DispatchVersion, dict[str, int]]:
    """Convierte los archivos crudos en tablas normalizadas.

    Returns:
        `(tablas, versión del despacho usada, conteo de registros por entidad)`.

    Raises:
        DomainError: si falta una entidad o su esquema no es el esperado.
    """
    data: dict[str, list[dict[str, object]]] = {}
    counts: dict[str, int] = {}
    for ep in paratec.ENDPOINTS:
        if ep.entity not in raw.paratec:
            raise DomainError("PARATEC_SCHEMA_CHANGED", f"falta la entidad {ep.entity}")
        data[ep.entity] = parse_paratec_response(ep.entity, raw.paratec[ep.entity])
        counts[ep.entity] = len(data[ep.entity])

    declared = buses.parse_substations(data["paratec.substations"])
    nominals = buses.parse_nominal_levels(data["paratec.substations"])
    subareas = buses.parse_subareas(data["paratec.substations"])
    coords = buses.parse_substation_coords(data["paratec.substations"])
    line_map = lines.parse_line_map(data["paratec.line_map"])
    lines_df = lines.parse_lines(data["paratec.lines"], line_map, declared)
    t2, t3 = trafos.parse_transformers(data["paratec.transformers"], declared)
    gens = generators.parse_generators(
        data["paratec.hydraulic_units"],
        data["paratec.thermal_units"],
        data["paratec.solar_plants"],
        data["paratec.wind_plants"],
        declared,
    )
    sh = shunts.parse_shunts(data["paratec.reactors"], data["paratec.capacitors"], declared)
    svc = shunts.parse_svc_statcom(data["paratec.svc_statcom"], declared)
    used = (
        set(lines_df.from_bus.dropna())
        | set(lines_df.to_bus.dropna())
        | set(t2.hv_bus.dropna())
        | set(t2.lv_bus.dropna())
        | set(t3.hv_bus.dropna())
        | set(t3.mv_bus.dropna())
        | set(t3.lv_bus.dropna())
        | set(gens.bus.dropna())
        | set(sh.bus.dropna())
        | set(svc.bus.dropna())
    )
    buses_df = buses.build_buses_table(declared, used, nominals, subareas, coords)

    ddec_files = [n for n in raw.xm if xm_dispatch.dispatch_version_of(n) is not None]
    chosen, available = xm_dispatch.select_dispatch_version(ddec_files)
    dispatch = xm_dispatch.parse_ddec(_decode(raw.xm[chosen]), source=chosen)
    pron = [n for n in raw.xm if n.upper().startswith("PRON_BARRA")]
    if not pron:
        raise DomainError("XM_FILE_SCHEMA_CHANGED", "falta el archivo PRON_BARRA<MMDD>")
    demand = xm_demand.parse_pron_barra(_decode(raw.xm[pron[0]]), source=pron[0])

    tables = SnapshotTables(
        buses=buses_df,
        lines=lines_df,
        trafos2w=t2,
        trafos3w=t3,
        generators=gens,
        shunts=sh,
        svc_statcom=svc,
        dispatch=dispatch,
        demand=demand,
    )
    validate_tables(tables)
    counts.update(
        {
            "normalized.buses": len(buses_df),
            "normalized.lines": len(lines_df),
            "normalized.trafos2w": len(t2),
            "normalized.trafos3w": len(t3),
            "normalized.generators": len(gens),
            "normalized.shunts": len(sh),
            "normalized.svc_statcom": len(svc),
            "xm.dispatch.resources": int(dispatch.resource.nunique()),
            "xm.demand.nodes": int(demand.groupby(["node", "vn_kv"]).ngroups),
        }
    )
    used_version = f"V{xm_dispatch.dispatch_version_of(chosen)}"
    return tables, DispatchVersion(used=used_version, available=available), counts


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def write_snapshot(
    raw: RawSnapshot,
    out_dir: Path,
    snapshot_date: date,
    *,
    scraper_version: str,
    attribution: str,
    extracted_at: datetime | None = None,
) -> Path:
    """Escribe un snapshot completo de forma atómica.

    Args:
        raw: Archivos crudos descargados.
        out_dir: Directorio raíz de snapshots (`data/paratec/`).
        snapshot_date: Fecha del snapshot (fecha de operación del despacho).
        scraper_version: Versión de `sinsim` que lo genera.
        attribution: Texto de atribución a XM (constitución III.10).
        extracted_at: Momento de la extracción; por defecto, ahora.

    Returns:
        Ruta final `<out_dir>/<fecha>/`.

    Raises:
        DomainError: `SNAPSHOT_EXISTS` si ya existe; errores de validación con código 4.
    """
    final = out_dir / snapshot_date.isoformat()
    if final.exists():
        raise DomainError("SNAPSHOT_EXISTS", f"ya existe {final}")
    tmp = out_dir / f".tmp-{snapshot_date.isoformat()}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    try:
        for ep in paratec.ENDPOINTS:
            payload = raw.paratec.get(ep.entity)
            if payload is None:
                raise DomainError("PARATEC_SCHEMA_CHANGED", f"falta la entidad {ep.entity}")
            _write_bytes(tmp / RAW_PARATEC / ep.raw_name, payload)
        for name, payload in raw.xm.items():
            _write_bytes(tmp / RAW_XM / name, payload)

        tables, dispatch_version, counts = normalize(raw)
        for table in TABLE_NAMES:
            df: pd.DataFrame = getattr(tables, table)
            (tmp / NORMALIZED).mkdir(exist_ok=True)
            _to_parquet(df, tmp / NORMALIZED / f"{table}.parquet")

        files = [
            FileEntry(
                path=p.relative_to(tmp).as_posix(),
                sha256=sha256_file(p),
                bytes=p.stat().st_size,
            )
            for p in sorted(tmp.rglob("*"))
            if p.is_file()
        ]
        manifest = Manifest(
            snapshot_date=snapshot_date,
            extracted_at=extracted_at or datetime.now(UTC),
            scraper_version=scraper_version,
            attribution=attribution,
            sources=list(raw.sources),
            dispatch_version=dispatch_version,
            record_counts=counts,
            files=files,
        )
        (tmp / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        tmp.rename(final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return final


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _to_parquet(df: pd.DataFrame, path: Path) -> None:
    out = df.copy()
    if "missing_params" in out.columns:
        out["missing_params"] = out["missing_params"].map(json.dumps)
    if "imputation_method" in out.columns:
        out["imputation_method"] = out["imputation_method"].astype("string")
    out.to_parquet(path, index=False)


def read_parquet_table(path: Path) -> pd.DataFrame:
    """Lee una tabla normalizada y restaura `missing_params` como lista."""
    df = pd.read_parquet(path)
    if "missing_params" in df.columns:
        df["missing_params"] = df["missing_params"].map(json.loads)
    return df
