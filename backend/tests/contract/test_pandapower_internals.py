"""Contrato con la versión fijada de pandapower: el diagnóstico depende de `net._ppc`."""

from __future__ import annotations

import pandapower as pp
import pandapower.networks as pn
import pytest

from sinsim.services.diagnostics import diagnose


def test_pinned_version():
    assert pp.__version__ == "3.5.6"


def test_internal_state_is_available_after_non_convergence():
    net = pn.case9()
    net.load.p_mw *= 100
    with pytest.raises(pp.LoadflowNotConverged) as exc:
        pp.runpp(net, max_iteration=10, init="flat", v_debug=True)
    ppc = net._ppc
    assert "iterations" in ppc and ppc["iterations"] == 10
    internal = ppc["internal"]
    for key in ("V", "Ybus", "bus", "gen", "Vm_it", "Va_it"):
        assert key in internal
    assert "bus" in net._pd2ppc_lookups
    d = diagnose(net, exc.value)
    assert d.iterations == 10 and len(d.worst_buses) == 9
    assert (
        d.basis in {"última iteración"}
        or d.basis.startswith("última iteración finita")
        or d.basis.startswith("arranque")
    )
