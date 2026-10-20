"""SC-005: redes de referencia con solución conocida reproducidas con error ≤ 1e-6 pu.

Dos referencias:
1. Un solver independiente de Newton-Raphson (Gauss-Seidel, `pandapower.pypower.gausspf`)
   con tolerancia 1e-10 sobre la misma red: el cálculo bajo prueba, con los parámetros del
   solver de `config/defaults.toml`, debe coincidir a 1e-6 pu.
2. La solución publicada por MATPOWER para `case9` (precisión de 4 decimales).
"""

from __future__ import annotations

import copy

import numpy as np
import pandapower as pp
import pandapower.networks as pn
import pytest

from sinsim.config import load_config

MATPOWER_CASE9_VM = [1.0000, 1.0000, 1.0000, 0.9870, 0.9755, 1.0034, 0.9856, 0.9962, 0.9576]


def run_with_project_settings(net: pp.pandapowerNet) -> None:
    s = load_config().config.solver
    pp.runpp(
        net,
        algorithm=s.algorithm,
        init=s.init,
        max_iteration=s.max_iteration,
        tolerance_mva=s.tolerance_mva,
        enforce_q_lims=False,
        distributed_slack=False,
        calculate_voltage_angles=True,
    )


@pytest.mark.parametrize("case", ["case9", "case14", "case30"])
def test_newton_raphson_matches_independent_gauss_seidel(case: str):
    net = getattr(pn, case)()
    ref = copy.deepcopy(net)
    pp.runpp(
        ref, algorithm="gs", max_iteration=20000, tolerance_mva=1e-10, calculate_voltage_angles=True
    )
    assert ref.converged
    run_with_project_settings(net)
    assert net.converged
    assert np.max(np.abs(net.res_bus.vm_pu.values - ref.res_bus.vm_pu.values)) < 1e-6
    assert np.max(np.abs(net.res_bus.va_degree.values - ref.res_bus.va_degree.values)) < 1e-4


def test_case9_matches_published_matpower_solution():
    net = pn.case9()
    run_with_project_settings(net)
    assert net.res_bus.vm_pu.values == pytest.approx(MATPOWER_CASE9_VM, abs=1e-4)
