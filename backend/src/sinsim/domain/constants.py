"""Base del sistema (constitución III.2).

Este es el único módulo que define la frecuencia y la potencia base. Ningún otro archivo
las redefine.
"""

F_HZ: float = 60.0
"""Frecuencia nominal del SIN, en Hz."""

S_BASE_MVA: float = 100.0
"""Potencia base para los valores en por unidad, en MVA."""

MIN_VN_KV_DEFAULT: float = 57.5
"""Tensión nominal mínima modelada por defecto (STN + STR), en kV. FR-017."""

PERIODS_PER_DAY: int = 24
"""Periodos horarios por día en los archivos de XM (A-01)."""
