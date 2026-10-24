"""Exportación del análisis N-1 (FR-059, FR-060; contracts/export-n1.md de la spec 003).

Produce `n1_cargabilidad.csv`, `n1_tensiones.csv`, `n1_aislan_demanda.csv`, `n1_sin_solucion.csv`
y `metadatos.json`. Mismo formato que la exportación de un flujo: UTF-8 sin BOM, separador `,`,
decimal `.` y floats sin redondear (`repr`). Las filas van en el orden de los listados (SC-018)
y cada CSV lleva encabezado aunque no tenga filas.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from sinsim.domain.entities import Isolation, N1Analysis, Outage

CSV_FILES = (
    "n1_cargabilidad.csv",
    "n1_tensiones.csv",
    "n1_aislan_demanda.csv",
    "n1_sin_solucion.csv",
)
METADATA_FILE = "metadatos.json"

_LOADING_FIELDS = (
    "posicion",
    "activo_fuera",
    "tipo_activo",
    "subarea_activo",
    "elemento",
    "cargabilidad_base_pct",
    "cargabilidad_pct",
    "elementos_que_cuentan",
    "barras_aisladas",
    "demanda_sin_servicio_mw",
    "referencia_movida_a",
)
_VOLTAGE_FIELDS = (
    "posicion",
    "activo_fuera",
    "tipo_activo",
    "subarea_activo",
    "barra",
    "v_base_pu",
    "v_pu",
    "distancia_fuera_de_banda_pu",
    "barras_que_cuentan",
    "barras_aisladas",
    "demanda_sin_servicio_mw",
    "referencia_movida_a",
)
_ISOLATION_FIELDS = (
    "posicion",
    "activo_fuera",
    "tipo_activo",
    "subarea_activo",
    "barras_aisladas",
    "demanda_sin_servicio_mw",
)
_UNSOLVED_FIELDS = (
    "activo_fuera",
    "tipo_activo",
    "subarea_activo",
    "iteraciones",
    "desbalance_maximo_mva",
    "barras_problematicas",
)


def _cell(value: object) -> str:
    if value is None:
        return ""
    return repr(value) if isinstance(value, float) else str(value)


def _csv(fields: Sequence[str], rows: Iterable[dict[str, object]]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _cell(row.get(k)) for k in fields})
    return buf.getvalue().encode("utf-8")


def _outage(o: Outage) -> dict[str, object]:
    return {"activo_fuera": o.element_id, "tipo_activo": o.kind, "subarea_activo": o.subarea}


def _isolation(i: Isolation | None) -> dict[str, object]:
    if i is None:
        return {"barras_aisladas": None, "demanda_sin_servicio_mw": None}
    return {"barras_aisladas": i.n_buses, "demanda_sin_servicio_mw": i.p_demand_lost_mw}


def metadata_n1(analysis: N1Analysis, attribution: str) -> dict[str, Any]:
    """Contenido de `metadatos.json` (FR-060)."""
    t = analysis.trace
    return {
        "tipo": "analisis_n1",
        "snapshot": t.snapshot_date.isoformat(),
        "despacho": t.dispatch_date.isoformat(),
        "periodo": t.period,
        "case_id": t.case_id,
        "run_id": analysis.run_id,
        "pandapower": t.pandapower_version,
        "sinsim": t.sinsim_version,
        "solver": t.solver.model_dump(mode="json"),
        "limites": [lim.model_dump(mode="json") for lim in analysis.limits],
        "analizado_en": analysis.analyzed_at.isoformat(),
        "procesos": analysis.workers,
        "resumen": analysis.summary.model_dump(mode="json"),
        "atribucion": attribution,
    }


def export_n1_files(analysis: N1Analysis, attribution: str) -> dict[str, bytes]:
    """Archivos de la exportación: nombre → contenido."""
    loading = (
        {
            "posicion": r.rank,
            **_outage(r.outage),
            "elemento": r.element_id,
            "cargabilidad_base_pct": r.loading_base_percent,
            "cargabilidad_pct": r.loading_percent,
            "elementos_que_cuentan": r.n_elements,
            **_isolation(r.isolation),
            "referencia_movida_a": r.outage.angle_ref_moved_to,
        }
        for r in analysis.loading
    )
    voltage = (
        {
            "posicion": r.rank,
            **_outage(r.outage),
            "barra": r.bus_id,
            "v_base_pu": r.vm_base_pu,
            "v_pu": r.vm_pu,
            "distancia_fuera_de_banda_pu": r.deviation_pu,
            "barras_que_cuentan": r.n_buses,
            **_isolation(r.isolation),
            "referencia_movida_a": r.outage.angle_ref_moved_to,
        }
        for r in analysis.voltage
    )
    isolation = (
        {
            "posicion": r.rank,
            **_outage(r.outage),
            "barras_aisladas": r.n_buses,
            "demanda_sin_servicio_mw": r.p_demand_lost_mw,
        }
        for r in analysis.isolation
    )
    unsolved = (
        {
            **_outage(r.outage),
            "iteraciones": r.diagnostics.iterations,
            "desbalance_maximo_mva": r.diagnostics.max_mismatch_mva,
            "barras_problematicas": ";".join(b.bus for b in r.diagnostics.worst_buses),
        }
        for r in analysis.unsolved
    )
    return {
        "n1_cargabilidad.csv": _csv(_LOADING_FIELDS, loading),
        "n1_tensiones.csv": _csv(_VOLTAGE_FIELDS, voltage),
        "n1_aislan_demanda.csv": _csv(_ISOLATION_FIELDS, isolation),
        "n1_sin_solucion.csv": _csv(_UNSOLVED_FIELDS, unsolved),
        METADATA_FILE: json.dumps(
            metadata_n1(analysis, attribution), ensure_ascii=False, indent=2
        ).encode("utf-8"),
    }


def write_export_n1(analysis: N1Analysis, attribution: str, out_dir: Path) -> list[Path]:
    """Escribe la exportación en una carpeta (la crea si hace falta) y reemplaza lo que haya."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in export_n1_files(analysis, attribution).items():
        path = out_dir / name
        path.write_bytes(content)
        written.append(path)
    return written
