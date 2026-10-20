"""Diagnóstico de una no convergencia (FR-022, constitución III.8; research R5).

Usa el estado interno de Newton-Raphson que pandapower deja en `net._ppc` tras fallar. Por
eso la versión de pandapower está fijada y hay una prueba de contrato sobre estas claves.

Si la tensión de la última iteración es NaN (divergencia), se usa la última iteración finita
(`v_debug=True` guarda `Vm_it`/`Va_it`); si tampoco existe, el desbalance en arranque plano
(1 pu, 0°), que muestra dónde está la inyección neta más desequilibrada.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import numpy as np
import pandapower as pp
from pandapower.pypower.makeSbus import makeSbus

from sinsim.domain.entities import BusMismatch, Diagnostics

_ITER = re.compile(r"after (\d+) iterations")


_MAX_REASONABLE_VM = 10.0


def _usable(arr: np.ndarray) -> bool:
    """Tensión utilizable: finita y sin magnitudes absurdas (divergencia numérica)."""
    return (
        bool(arr.size)
        and bool(np.all(np.isfinite(arr)))
        and float(np.abs(arr).max()) < _MAX_REASONABLE_VM
    )


def _voltage_candidates(internal: dict[str, object]) -> Iterator[tuple[np.ndarray, str]]:
    """Estados de tensión, del más informativo al más conservador."""
    v = internal.get("V")
    if v is not None:
        arr = np.asarray(v, dtype=complex)
        if _usable(arr):
            yield arr, "última iteración"
    vm, va = internal.get("Vm_it"), internal.get("Va_it")
    if vm is not None and va is not None:
        vm_arr, va_arr = np.asarray(vm, dtype=float), np.asarray(va, dtype=float)
        if vm_arr.ndim == 2 and vm_arr.shape[1]:
            for col in range(vm_arr.shape[1] - 1, -1, -1):
                candidate = vm_arr[:, col] * np.exp(1j * va_arr[:, col])
                if _usable(candidate):
                    yield candidate, f"última iteración finita ({col})"
    bus = internal.get("bus")
    if bus is not None:
        n = np.asarray(bus).shape[0]
        yield np.ones(n, dtype=complex), "arranque plano (1 pu, 0°)"


def diagnose(net: pp.pandapowerNet, error: Exception, top_n: int = 10) -> Diagnostics:
    """Calcula iteraciones, desbalance máximo y las peores barras.

    Args:
        net: Red tras un `LoadflowNotConverged`.
        error: La excepción, por si `_ppc` no está disponible.
        top_n: Número de barras a listar.

    Returns:
        `Diagnostics`. Si el estado interno no está disponible, solo trae las iteraciones.
    """
    ppc = getattr(net, "_ppc", None) or {}
    iterations = int(ppc.get("iterations", 0) or 0)
    if not iterations:
        m = _ITER.search(str(error))
        iterations = int(m.group(1)) if m else 0
    internal = ppc.get("internal") or {}
    empty = Diagnostics(
        iterations=iterations, max_mismatch_mva=float("nan"), worst_buses=[], basis="no disponible"
    )
    try:
        ybus = internal["Ybus"]
        # Con `enforce_q_lims`, pandapower deja QG = NaN en generadores sin límites de
        # reactiva; para el diagnóstico esas inyecciones indefinidas se toman como 0.
        bus = np.nan_to_num(np.asarray(internal["bus"], dtype=float))
        gen = np.nan_to_num(np.asarray(internal["gen"], dtype=float))
        base_mva = float(ppc.get("baseMVA", net.sn_mva))
        sbus = makeSbus(base_mva, bus, gen)
    except (KeyError, TypeError, ValueError):
        return empty
    magnitude: np.ndarray | None = None
    basis = "no disponible"
    for v, candidate_basis in _voltage_candidates(internal):
        with np.errstate(all="ignore"):
            mis = (v * np.conj(ybus @ v) - sbus) * base_mva
        if np.all(np.isfinite(mis)):
            magnitude, basis = np.abs(mis), candidate_basis
            break
    if magnitude is None:
        return empty
    lookup = np.asarray(net._pd2ppc_lookups["bus"])
    ppc_to_pd: dict[int, int] = {}
    for pd_idx, ppc_idx in enumerate(lookup):
        if ppc_idx >= 0 and int(ppc_idx) not in ppc_to_pd and pd_idx in net.bus.index:
            ppc_to_pd[int(ppc_idx)] = pd_idx
    order = np.argsort(-magnitude)[:top_n]
    worst = []
    for k in order:
        pd_bus = ppc_to_pd.get(int(k))
        name = str(net.bus.at[pd_bus, "name"]) if pd_bus is not None else f"ppc:{k}"
        worst.append(BusMismatch(bus=name, mismatch_mva=float(magnitude[k])))
    return Diagnostics(
        iterations=iterations,
        max_mismatch_mva=float(magnitude.max()) if magnitude.size else float("nan"),
        worst_buses=worst,
        basis=basis,
    )
