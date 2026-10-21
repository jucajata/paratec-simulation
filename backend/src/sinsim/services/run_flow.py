"""Ejecución del flujo de potencia sobre un caso (FR-020 a FR-026, FR-030, FR-031).

AC: Newton-Raphson con referencia distribuida y límites de reactiva. Si no converge, el
resultado es `no_convergio` con diagnóstico y sin tablas de resultados (FR-022). DC: `rundcpp`,
etiquetado como aproximación.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any

import pandapower as pp
import pandas as pd

from sinsim.config import LoadedConfig
from sinsim.domain.entities import (
    LABEL_AC,
    LABEL_DC,
    BranchResult,
    BusResult,
    Diagnostics,
    FlowType,
    GeneratorResult,
    ResultSummary,
    Run,
    RunResult,
    RunStatus,
    SolverSettings,
    StudyCase,
    Trace,
)
from sinsim.domain.limits import branch_overload, bus_violation, limit_infos
from sinsim.domain.violations import violations_report
from sinsim.services.diagnostics import diagnose


def solver_settings(cfg: LoadedConfig) -> SolverSettings:
    """Parámetros del solver desde la configuración."""
    s = cfg.config.solver
    return SolverSettings(
        algorithm=s.algorithm,
        tolerance_mva=s.tolerance_mva,
        max_iteration=s.max_iteration,
        init=s.init,
        enforce_q_lims=s.enforce_q_lims,
        distributed_slack=s.distributed_slack,
    )


def run_flow(
    case: StudyCase,
    net: pp.pandapowerNet,
    flow_type: FlowType,
    cfg: LoadedConfig,
    sinsim_version: str,
) -> Run:
    """Corre el flujo y devuelve la ejecución con su trazabilidad.

    Args:
        case: Caso construido.
        net: Red del caso (ya con las islas fuera de servicio).
        flow_type: `"ac"` o `"dc"`.
        cfg: Configuración (solver y límites).
        sinsim_version: Versión de `sinsim`.

    Returns:
        `Run` con `status`, `trace`, y `result` o `diagnostics`.
    """
    settings = solver_settings(cfg)
    trace = Trace(
        snapshot_date=case.inputs.snapshot_date,
        dispatch_date=case.inputs.dispatch_date,
        period=case.inputs.period,
        flow_type=flow_type,
        pandapower_version=pp.__version__,
        sinsim_version=sinsim_version,
        solver=settings,
        case_id=case.case_id,
    )
    run_id = str(uuid.uuid4())
    label = LABEL_DC if flow_type == "dc" else LABEL_AC

    def make(
        status: RunStatus,
        *,
        result: RunResult | None = None,
        diagnostics: Diagnostics | None = None,
    ) -> Run:
        return Run(
            run_id=run_id,
            case_id=case.case_id,
            flow_type=flow_type,
            status=status,
            label=label,
            solver=settings,
            trace=trace,
            diagnostics=diagnostics,
            result=result,
            created_at=datetime.now(UTC),
        )

    if flow_type == "dc":
        pp.rundcpp(net, check_connectivity=True)
        return make("convergio", result=_result(net, case, cfg, dc=True))
    try:
        pp.runpp(
            net,
            algorithm=settings.algorithm,
            init=settings.init,
            max_iteration=settings.max_iteration,
            tolerance_mva=settings.tolerance_mva,
            enforce_q_lims=settings.enforce_q_lims,
            distributed_slack=settings.distributed_slack,
            calculate_voltage_angles=True,
            check_connectivity=True,
            v_debug=True,
        )
    except pp.LoadflowNotConverged as exc:
        return make("no_convergio", diagnostics=diagnose(net, exc))
    return make("convergio", result=_result(net, case, cfg, dc=False))


def _result(net: pp.pandapowerNet, case: StudyCase, cfg: LoadedConfig, *, dc: bool) -> RunResult:
    bands = cfg.config.voltage_bands()
    loading = cfg.config.loading_limit()
    bus_name = net.bus.name.to_dict()
    bus_subarea = subareas_of(net)
    has_nominal = "nominal_kv" in net.bus.columns
    buses: list[BusResult] = []
    for idx, row in net.res_bus.iterrows():
        if not net.bus.at[idx, "in_service"] or pd.isna(row.vm_pu):
            continue
        base_kv = float(net.bus.at[idx, "vn_kv"])
        nominal = float(net.bus.at[idx, "nominal_kv"]) if has_nominal else base_kv
        vm_kv = float(row.vm_pu) * base_kv
        vm_pu = vm_kv / nominal  # pu respecto al nominal declarado por PARATEC
        buses.append(
            BusResult(
                bus_id=str(bus_name[idx]),
                vn_kv=nominal,
                vm_pu=vm_pu,
                vm_kv=vm_kv,
                va_degree=float(row.va_degree),
                violation=None if dc else bus_violation(vm_pu, nominal, bands),
                subarea=bus_subarea.get(idx),
            )
        )

    def branches(
        kind: str,
        table: pd.DataFrame,
        res: pd.DataFrame,
        fb: str,
        tb: str,
        pf: str,
        qf: str,
        pt: str,
        qt: str,
        i: str,
    ) -> list[BranchResult]:
        out = []
        for idx, row in res.iterrows():
            if not table.at[idx, "in_service"] or pd.isna(row[pf]):
                continue
            out.append(
                BranchResult(
                    element_id=str(table.at[idx, "name"]),
                    kind=kind,  # type: ignore[arg-type]
                    from_bus=str(bus_name[table.at[idx, fb]]),
                    to_bus=str(bus_name[table.at[idx, tb]]),
                    p_from_mw=float(row[pf]),
                    q_from_mvar=_nz(row[qf]),
                    p_to_mw=float(row[pt]),
                    q_to_mvar=_nz(row[qt]),
                    i_ka=_nz(row[i]),
                    loading_percent=_nz(row.loading_percent),
                    pl_mw=_nz(row.get("pl_mw", 0.0)),
                    ql_mvar=_nz(row.get("ql_mvar", 0.0)),
                    overload=branch_overload(_nz(row.loading_percent), loading),
                    subarea_from=bus_subarea.get(table.at[idx, fb]),
                    subarea_to=bus_subarea.get(table.at[idx, tb]),
                )
            )
        return out

    lines = branches(
        "line",
        net.line,
        net.res_line,
        "from_bus",
        "to_bus",
        "p_from_mw",
        "q_from_mvar",
        "p_to_mw",
        "q_to_mvar",
        "i_from_ka",
    )
    trafos = branches(
        "trafo2w",
        net.trafo,
        net.res_trafo,
        "hv_bus",
        "lv_bus",
        "p_hv_mw",
        "q_hv_mvar",
        "p_lv_mw",
        "q_lv_mvar",
        "i_hv_ka",
    )
    trafos += branches(
        "trafo3w",
        net.trafo3w,
        net.res_trafo3w,
        "hv_bus",
        "lv_bus",
        "p_hv_mw",
        "q_hv_mvar",
        "p_lv_mw",
        "q_lv_mvar",
        "i_hv_ka",
    )

    gens: list[GeneratorResult] = []
    for idx, row in net.res_gen.iterrows():
        if not net.gen.at[idx, "in_service"] or pd.isna(row.p_mw):
            continue
        name = str(net.gen.at[idx, "name"])
        scheduled = float(net.gen.at[idx, "p_mw"])
        gens.append(
            GeneratorResult(
                gen_id=name,
                resource=name.split("@")[0],
                bus=str(bus_name[net.gen.at[idx, "bus"]]),
                p_scheduled_mw=scheduled,
                p_mw=float(row.p_mw),
                q_mvar=_nz(row.q_mvar),
                slack_adjust_mw=float(row.p_mw) - scheduled,
            )
        )
    p_gen = (
        sum(g.p_mw for g in gens) + float(net.res_sgen.p_mw.sum())
        if len(net.res_sgen)
        else sum(g.p_mw for g in gens)
    )
    p_load = float(net.res_load.p_mw.sum()) if len(net.res_load) else 0.0
    p_losses = sum(b.pl_mw for b in lines + trafos)
    summary = ResultSummary(
        p_gen_mw=p_gen,
        p_load_mw=p_load,
        p_losses_mw=p_losses,
        slack_adjust_total_mw=sum(g.slack_adjust_mw for g in gens),
        n_voltage_violations=sum(1 for b in buses if b.violation),
        n_overloads=sum(1 for b in lines + trafos if b.overload),
        limits=limit_infos(bands, loading),
        warnings=list(case.warnings)
        + (["La aproximación DC no calcula tensiones, reactiva ni pérdidas."] if dc else []),
        violations=violations_report(buses, lines + trafos, bands, loading),
    )
    return RunResult(buses=buses, lines=lines, trafos=trafos, generators=gens, summary=summary)


def subareas_of(net: pp.pandapowerNet) -> dict[Any, str]:
    """Índice de barra → subárea de PARATEC; las barras sin subárea no aparecen (FR-034)."""
    if "subarea" not in net.bus.columns:
        return {}
    return {int(i): str(v) for i, v in net.bus.subarea.items() if isinstance(v, str) and v.strip()}


def _nz(value: object) -> float:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(f) else f
