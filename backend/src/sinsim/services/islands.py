"""Detección de islas antes de correr el flujo (FR-016, D-5).

El SIN real no tiene islas; una isla en el modelo es un artefacto de datos faltantes o del
corte de alcance. Solo se energiza la componente que contiene la barra de referencia de
ángulo; las demás se sacan de servicio y se reportan con los MW que quedan fuera.

Esto evita el riesgo verificado en research R5: con `check_connectivity=True`, una isla sin
referencia queda con NaN y `converged=True`.
"""

from __future__ import annotations

import networkx as nx
import pandapower as pp
import pandapower.topology as top
from pandapower.toolbox import set_isolated_areas_out_of_service

from sinsim.domain.entities import Island


def detect_and_isolate(net: pp.pandapowerNet, angle_ref_bus: str) -> list[Island]:
    """Encuentra las componentes conexas, energiza solo la de referencia y reporta el resto.

    Args:
        net: Red ya construida; se muta (`in_service` de las islas secundarias).
        angle_ref_bus: `bus_id` (nombre de barra) de la referencia de ángulo.

    Returns:
        Lista de islas, la energizada primero.
    """
    graph = top.create_nxgraph(net, respect_switches=False, include_out_of_service=False)
    name_of = net.bus.name.to_dict()
    ref_idx = net.bus.index[net.bus.name == angle_ref_bus]
    ref = int(ref_idx[0]) if len(ref_idx) else -1
    components = sorted(nx.connected_components(graph), key=lambda c: (ref not in c, -len(c)))
    islands: list[Island] = []
    for i, comp in enumerate(components):
        buses = sorted(name_of[b] for b in comp)
        energized = ref in comp
        p_gen = float(net.gen.loc[net.gen.bus.isin(comp), "p_mw"].sum()) + float(
            net.sgen.loc[net.sgen.bus.isin(comp), "p_mw"].sum()
        )
        p_load = float(net.load.loc[net.load.bus.isin(comp), "p_mw"].sum())
        islands.append(
            Island(
                island_id=i,
                n_buses=len(comp),
                buses=buses,
                p_gen_lost_mw=0.0 if energized else p_gen,
                p_demand_lost_mw=0.0 if energized else p_load,
                energized=energized,
            )
        )
        if not energized:
            net.bus.loc[list(comp), "in_service"] = False
    if len(islands) > 1:
        set_isolated_areas_out_of_service(net)
    return islands
