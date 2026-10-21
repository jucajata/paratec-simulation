"""Exportación de una ejecución (FR-032, SC-007; contracts/export-format.md).

Produce `barras.csv`, `lineas.csv`, `transformadores.csv`, `generadores.csv` y `metadatos.json`.
Los CSV van en UTF-8 sin BOM, separador `,`, decimal `.` y float64 sin redondear (`repr`), para
que la comparación valor a valor con la API sea exacta. Si la ejecución no convergió, solo se
escribe `metadatos.json` con el diagnóstico (FR-022).
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from sinsim.domain.entities import Run, StudyCase

CSV_FILES = (
    "barras.csv",
    "lineas.csv",
    "transformadores.csv",
    "generadores.csv",
    "violaciones.csv",
)
METADATA_FILE = "metadatos.json"


def _csv(rows: Sequence[BaseModel], extra: dict[str, Any] | None = None) -> bytes:
    """Serializa modelos a CSV; los floats conservan su precisión completa."""
    buf = io.StringIO()
    if not rows:
        return b""
    first = rows[0].model_dump()
    fields = list(first) + list(extra or {})
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        data = row.model_dump()
        data.update(extra or {})
        writer.writerow(
            {
                k: (repr(v) if isinstance(v, float) else ("" if v is None else v))
                for k, v in data.items()
            }
        )
    return buf.getvalue().encode("utf-8")


def _trafos_csv(rows: Iterable[BaseModel]) -> bytes:
    """Transformadores con la columna `tipo` (2w/3w) derivada de `kind`."""
    items = list(rows)
    if not items:
        return b""
    buf = io.StringIO()
    fields = [*items[0].model_dump().keys(), "tipo"]
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in items:
        data = row.model_dump()
        data["tipo"] = "3w" if data.get("kind") == "trafo3w" else "2w"
        writer.writerow(
            {
                k: (repr(v) if isinstance(v, float) else ("" if v is None else v))
                for k, v in data.items()
            }
        )
    return buf.getvalue().encode("utf-8")


def metadata(case: StudyCase, run: Run, attribution: str) -> dict[str, Any]:
    """Contenido de `metadatos.json`."""
    q = case.quality
    result = run.result
    return {
        "trace": run.trace.model_dump(mode="json"),
        "solver": run.solver.model_dump(mode="json"),
        "status": run.status,
        "case_id": case.case_id,
        "label": run.label,
        "quality_summary": {
            "balance": q.balance.model_dump(mode="json"),
            "unlocated_resources": len(q.unlocated_resources),
            "unlocated_demand": len(q.unlocated_demand),
            "transfers": len(q.transfers),
            "excluded": len(q.excluded),
            "imputed": len(q.imputed),
            "not_modeled": len(q.not_modeled),
            "islands": len(q.islands),
            "physical_issues": len(q.physical_issues),
        },
        "assumptions": case.assumptions,
        "limits": [lim.model_dump(mode="json") for lim in result.summary.limits] if result else [],
        "warnings": list(result.summary.warnings) if result else list(case.warnings),
        "diagnostics": run.diagnostics.model_dump(mode="json") if run.diagnostics else None,
        "attribution": attribution,
    }


def export_files(case: StudyCase, run: Run, attribution: str) -> dict[str, bytes]:
    """Archivos de la exportación: nombre → contenido."""
    files: dict[str, bytes] = {
        METADATA_FILE: json.dumps(
            metadata(case, run, attribution), ensure_ascii=False, indent=2
        ).encode("utf-8")
    }
    if run.result is None:
        return files
    r = run.result
    files["barras.csv"] = _csv(r.buses)
    files["lineas.csv"] = _csv(r.lines)
    files["transformadores.csv"] = _trafos_csv(r.trafos)
    files["generadores.csv"] = _csv(r.generators)
    # FR-037: una fila por violación, con límite y fuente; vacío si no hay ninguna.
    files["violaciones.csv"] = (
        _csv(r.summary.violations)
        if r.summary.violations
        else (b"kind,element,subarea,value,limit,deviation,unit,source\n")
    )
    return files


def write_export(case: StudyCase, run: Run, attribution: str, out_dir: Path) -> list[Path]:
    """Escribe la exportación en un directorio y devuelve las rutas creadas."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in export_files(case, run, attribution).items():
        path = out_dir / name
        path.write_bytes(content)
        written.append(path)
    return written


def export_zip(case: StudyCase, run: Run, attribution: str) -> bytes:
    """La exportación como `.zip` en memoria (para la API)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in export_files(case, run, attribution).items():
            zf.writestr(name, content)
    return buf.getvalue()
