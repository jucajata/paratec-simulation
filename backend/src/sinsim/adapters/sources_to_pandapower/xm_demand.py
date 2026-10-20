"""Pronóstico oficial de demanda por barra `PRON_BARRA<MMDD>` de XM → tabla `demand`.

Formato (XM-CND-2014-045 ed. 2025): `UCP, NODO, kV, CONCEPTO, HORA01..HORA24`, con tres
conceptos por nodo: `Ener.Act.` (MWh), `Ener.Reac`/`Ener.Reac.` (Mvar) y
`Perd.PSTR`/`Perd.PSTR.` (MWh, pérdidas por referir la carga a un nivel de tensión).

Conversión (constitución III.1): periodos de 1 h, así que MWh del periodo = MW medios
(`mwh_per_period_to_mw`). La reactiva se toma en Mvar tal como la define el estándar.
La demanda activa del caso es `Ener.Act. + Perd.PSTR` (clarificación 4); aquí se conservan
los dos componentes por separado (`p_act_mw`, `p_pstr_mw`).
"""

from __future__ import annotations

import csv
import io
from typing import Any

import pandas as pd

from sinsim.adapters.sources_to_pandapower.xm_dispatch import mwh_per_period_to_mw
from sinsim.domain.constants import PERIODS_PER_DAY
from sinsim.domain.errors import DomainError

COLUMNS = ["ucp", "node", "vn_kv", "period", "p_act_mw", "p_pstr_mw", "q_mvar", "source_id"]

_CONCEPTS = {
    "ener.act": "p_act_mw",
    "ener.reac": "q_mvar",
    "perd.pstr": "p_pstr_mw",
}


def normalize_concept(label: str) -> str | None:
    """Normaliza la etiqueta de concepto (con o sin punto final) al nombre de columna."""
    return _CONCEPTS.get(label.strip().rstrip(".").lower())


def parse_pron_barra(text: str, source: str = "PRON_BARRA") -> pd.DataFrame:
    """Parsea un archivo `PRON_BARRA`.

    Args:
        text: Contenido del archivo.
        source: Etiqueta de origen para `source_id`.

    Returns:
        DataFrame `demand` con una fila por (nodo, periodo).

    Raises:
        DomainError: `XM_FILE_SCHEMA_CHANGED` si una fila no tiene el formato esperado o un
            nodo no trae los tres conceptos.
    """
    nodes: dict[tuple[str, str, float], dict[str, Any]] = {}
    for n, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        delimiter = ";" if raw.count(";") >= raw.count(",") else ","
        fields = next(csv.reader(io.StringIO(raw), delimiter=delimiter, skipinitialspace=True))
        if len(fields) != 4 + PERIODS_PER_DAY:
            raise DomainError(
                "XM_FILE_SCHEMA_CHANGED",
                f"{source} línea {n}: se esperaban {4 + PERIODS_PER_DAY} campos "
                f"y hay {len(fields)}",
            )
        ucp, node, kv_text, concept = (f.strip() for f in fields[:4])
        column = normalize_concept(concept)
        if column is None:
            raise DomainError(
                "XM_FILE_SCHEMA_CHANGED", f"{source} línea {n}: concepto desconocido {concept!r}"
            )
        try:
            kv = float(kv_text.replace(",", "."))
            values = [float(v) for v in fields[4:]]
        except ValueError as exc:
            raise DomainError(
                "XM_FILE_SCHEMA_CHANGED", f"{source} línea {n}: valor no numérico"
            ) from exc
        entry = nodes.setdefault((ucp, node, kv), {"source_ids": []})
        entry[column] = values
        entry["source_ids"].append(f"{source}:{n}")
    rows: list[dict[str, Any]] = []
    for (ucp, node, kv), entry in nodes.items():
        missing = [c for c in _CONCEPTS.values() if c not in entry]
        if missing:
            raise DomainError(
                "XM_FILE_SCHEMA_CHANGED",
                f"{source}: el nodo {node} ({kv:g} kV) no trae {', '.join(missing)}",
            )
        for period in range(1, PERIODS_PER_DAY + 1):
            i = period - 1
            rows.append(
                {
                    "ucp": ucp,
                    "node": node,
                    "vn_kv": kv,
                    "period": period,
                    "p_act_mw": mwh_per_period_to_mw(entry["p_act_mw"][i]),
                    "p_pstr_mw": mwh_per_period_to_mw(entry["p_pstr_mw"][i]),
                    "q_mvar": entry["q_mvar"][i],
                    "source_id": ";".join(entry["source_ids"]),
                }
            )
    return pd.DataFrame(rows, columns=COLUMNS)


__all__ = ["COLUMNS", "normalize_concept", "parse_pron_barra"]
