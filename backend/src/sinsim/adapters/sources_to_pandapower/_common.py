"""Utilidades compartidas por los adaptadores de fuentes."""

from __future__ import annotations

import math
from typing import Any

from sinsim.adapters.sources_to_pandapower.field_mapping import MISSING_TOKENS

QUALITY_COLUMNS: tuple[str, ...] = ("source_id", "imputed", "imputation_method", "missing_params")
"""Columnas de calidad presentes en todas las tablas normalizadas (constitución III.5)."""


def to_float(value: Any) -> float | None:
    """Convierte un valor de PARATEC a float.

    PARATEC mezcla números, strings con punto o coma decimal y marcadores de faltante
    ("-", "N/A"). Un faltante devuelve `None`.

    Args:
        value: Valor crudo.

    Returns:
        El número, o `None` si falta o no es numérico.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return None if math.isnan(float(value)) else float(value)
    text = str(value).strip()
    if text in MISSING_TOKENS:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def to_text(value: Any) -> str | None:
    """Devuelve el texto limpio o `None` si es un marcador de faltante."""
    if value is None:
        return None
    text = str(value).strip()
    return None if text in MISSING_TOKENS else text


def quality_fields(source_id: str, missing: list[str]) -> dict[str, Any]:
    """Construye las columnas de calidad de una fila normalizada."""
    return {
        "source_id": source_id,
        "imputed": False,
        "imputation_method": None,
        "missing_params": list(missing),
    }


def fmt_kv(kv: float) -> str:
    """Formatea una tensión para un `bus_id` (sin ceros sobrantes)."""
    return f"{kv:g}"
