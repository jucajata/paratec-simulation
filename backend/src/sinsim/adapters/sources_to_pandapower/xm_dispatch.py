"""Despacho programado `dDEC<MMDD>.txt` de XM → tabla `dispatch` (research R2).

Formato (Estándar de Información del Despacho Económico, XM-CND-2014-045 ed. 2025):
una fila por recurso, `"<RECURSO>",v1,...,v24`, con separador "," o ";" y 24 valores en
**MWh por periodo**. La última fila es `"Total"`.

Conversión de unidades (constitución III.1): un periodo dura 1 h, así que la energía en MWh
del periodo es numéricamente igual a la potencia media en MW:
`p_mw = mwh_per_period / 1 h`. Se deja explícita en `mwh_per_period_to_mw`.

Versiones del mismo día (D-3): si existen `dDEC<MMDD>.txt` (V0) y `dDEC<MMDD>_V<n>.txt`,
prevalece la de mayor `n`.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable
from typing import Any

import pandas as pd

from sinsim.domain.constants import PERIODS_PER_DAY
from sinsim.domain.errors import DomainError

STANDARD_VERSION = "XM-CND-2014-045 ed. 2025"
TOTAL_ROW = "Total"
TOTAL_TOLERANCE_MW = 0.01
COLUMNS = ["resource", "period", "p_mw", "source_id"]

_VERSION = re.compile(r"^dDEC(?P<mmdd>\d{4})(?:_V(?P<v>\d+))?\.txt$", re.IGNORECASE)


def mwh_per_period_to_mw(mwh: float, period_hours: float = 1.0) -> float:
    """Energía del periodo (MWh) → potencia media (MW): `mwh / horas`."""
    return mwh / period_hours


def dispatch_version_of(filename: str) -> int | None:
    """Número de versión de un nombre `dDEC<MMDD>[_V<n>].txt`; V0 si no tiene sufijo."""
    m = _VERSION.match(filename)
    if not m:
        return None
    return int(m.group("v") or 0)


def select_dispatch_version(filenames: Iterable[str]) -> tuple[str, list[str]]:
    """Elige el archivo de despacho vigente (mayor `_V<n>`) y lista las versiones.

    Args:
        filenames: Nombres de archivo `dDEC<MMDD>*.txt` disponibles para un día.

    Returns:
        `(nombre elegido, ["V0", "V1", ...])`.

    Raises:
        DomainError: `XM_FILE_SCHEMA_CHANGED` si no hay ningún `dDEC` válido.
    """
    versioned = [(dispatch_version_of(f), f) for f in filenames]
    valid = [(v, f) for v, f in versioned if v is not None]
    if not valid:
        raise DomainError("XM_FILE_SCHEMA_CHANGED", "no se encontró ningún archivo dDEC<MMDD>.txt")
    valid.sort()
    return valid[-1][1], [f"V{v}" for v, _ in valid]


def _split(line: str) -> list[str]:
    delimiter = ";" if line.count(";") >= line.count(",") else ","
    return next(csv.reader(io.StringIO(line), delimiter=delimiter, skipinitialspace=True))


def parse_ddec(text: str, source: str = "dDEC") -> pd.DataFrame:
    """Parsea un archivo `dDEC` y valida su fila `Total`.

    Args:
        text: Contenido del archivo.
        source: Etiqueta de origen para `source_id`.

    Returns:
        DataFrame `dispatch` con `resource`, `period` (1..24), `p_mw`, `source_id`.

    Raises:
        DomainError: `XM_FILE_SCHEMA_CHANGED` si una fila no tiene 24 valores numéricos,
            `DISPATCH_TOTAL_MISMATCH` si la suma de recursos no cuadra con `Total`.
    """
    rows: list[dict[str, Any]] = []
    totals: list[float] | None = None
    sums = [0.0] * PERIODS_PER_DAY
    for n, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        fields = _split(raw)
        name = fields[0].strip().strip('"')
        values = fields[1:]
        if len(values) != PERIODS_PER_DAY:
            raise DomainError(
                "XM_FILE_SCHEMA_CHANGED",
                f"{source} línea {n}: se esperaban {PERIODS_PER_DAY} valores y hay {len(values)}",
            )
        try:
            nums = [float(v.strip()) for v in values]
        except ValueError as exc:
            raise DomainError(
                "XM_FILE_SCHEMA_CHANGED", f"{source} línea {n}: valor no numérico"
            ) from exc
        if name.lower() == TOTAL_ROW.lower():
            totals = nums
            continue
        for period, mwh in enumerate(nums, start=1):
            sums[period - 1] += mwh
            rows.append(
                {
                    "resource": name,
                    "period": period,
                    "p_mw": mwh_per_period_to_mw(mwh),
                    "source_id": f"{source}:{n}",
                }
            )
    if totals is None:
        raise DomainError("XM_FILE_SCHEMA_CHANGED", f"{source}: falta la fila Total")
    for period, (s, t) in enumerate(zip(sums, totals, strict=True), start=1):
        if abs(s - t) > TOTAL_TOLERANCE_MW:
            raise DomainError(
                "DISPATCH_TOTAL_MISMATCH",
                f"{source} periodo {period}: suma de recursos {s:.4f} ≠ Total {t:.4f}",
            )
    return pd.DataFrame(rows, columns=COLUMNS)


__all__ = [
    "COLUMNS",
    "STANDARD_VERSION",
    "dispatch_version_of",
    "mwh_per_period_to_mw",
    "parse_ddec",
    "select_dispatch_version",
]
