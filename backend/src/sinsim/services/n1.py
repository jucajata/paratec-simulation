"""Análisis de contingencias N-1 (spec 003: FR-049 a FR-052, FR-055, FR-056, FR-058, FR-060).

Sobre una ejecución AC convergida, saca de servicio cada línea, cada transformador y cada
generador, uno a la vez, y corre un flujo AC por contingencia. Cada proceso del pool carga la
red una vez, resuelve el flujo base y atiende lotes de contingencias partiendo siempre del mismo
estado base (research R1 a R3). El criterio de empeoramiento y el orden de los listados viven en
`domain/contingency.py`; aquí solo hay E/S con pandapower (constitución IV).
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pandapower as pp
import pandas as pd

from sinsim.config import LoadedConfig
from sinsim.domain.contingency import (
    ContingencyResult,
    FlowState,
    evaluate,
    rank_isolation,
    rank_loading,
    rank_voltage,
    summarize,
    unsolved_rows,
)
from sinsim.domain.entities import (
    Diagnostics,
    Isolation,
    N1Analysis,
    N1Job,
    N1Status,
    Outage,
    ProblemInfo,
    Run,
)
from sinsim.domain.errors import DomainError
from sinsim.domain.limits import LoadingLimit, VoltageBand, limit_infos
from sinsim.observability import log_event, new_trace_id
from sinsim.services.build_case import choose_angle_ref
from sinsim.services.diagnostics import diagnose
from sinsim.services.islands import detect_and_isolate
from sinsim.services.run_flow import bus_vm_nominal, solver_settings, subareas_of
from sinsim.services.scrape import internal_problem, problem_of

log = logging.getLogger("sinsim.n1")

ProgressCallback = Callable[[int, int], None]
"""`progress(hechas, total)`; se llama al menos al empezar y al terminar."""

_STATE_TABLES = (
    "bus",
    "line",
    "trafo",
    "trafo3w",
    "gen",
    "sgen",
    "load",
    "shunt",
    "ext_grid",
    "switch",
)
_TABLE_OF_KIND = {"line": "line", "trafo2w": "trafo", "gen": "gen", "compensador": "gen"}
_COMPENSATOR_PREFIXES = ("svc:", "statcom:")


def default_workers() -> int:
    """Procesos del pool: todos los núcleos menos uno, mínimo uno (research R2)."""
    return max(1, (os.cpu_count() or 2) - 1)


def enumerate_outages(net: pp.pandapowerNet) -> list[Outage]:
    """Contingencias de un caso: líneas, transformadores y generadores en servicio (FR-049).

    Los compensadores (SVC/STATCOM) son generadores con prefijo `svc:` o `statcom:` en el modelo
    (S25). La subárea es la de la barra de origen (líneas), de alta (transformadores) o de
    conexión (generadores). El modelo solo construye transformadores de dos devanados.
    """
    subarea = subareas_of(net)
    out: list[Outage] = []
    for idx in net.line.index[net.line.in_service]:
        out.append(
            Outage(
                element_id=str(net.line.at[idx, "name"]),
                kind="line",
                subarea=subarea.get(int(net.line.at[idx, "from_bus"])),
            )
        )
    for idx in net.trafo.index[net.trafo.in_service]:
        out.append(
            Outage(
                element_id=str(net.trafo.at[idx, "name"]),
                kind="trafo2w",
                subarea=subarea.get(int(net.trafo.at[idx, "hv_bus"])),
            )
        )
    for idx in net.gen.index[net.gen.in_service]:
        name = str(net.gen.at[idx, "name"])
        out.append(
            Outage(
                element_id=name,
                kind="compensador" if name.startswith(_COMPENSATOR_PREFIXES) else "gen",
                subarea=subarea.get(int(net.gen.at[idx, "bus"])),
            )
        )
    return out


# --- Proceso de cálculo --------------------------------------------------------------------


@dataclass
class RawResult:
    """Lo que un proceso devuelve por contingencia, antes de compararla con el caso base."""

    outage: Outage
    converged: bool
    loading: dict[str, float]
    """`element_id` → cargabilidad (%) de las ramas en servicio."""
    vm_pu: dict[str, float]
    """`bus_id` → tensión en pu del nominal de PARATEC de las barras en servicio."""
    isolation: Isolation | None = None
    diagnostics: Diagnostics | None = None


class Worker:
    """Red cargada una vez con el flujo base resuelto; corre contingencias desde ese estado."""

    def __init__(self, net_json: str, settings: dict[str, Any]) -> None:
        """Carga la red, corre el flujo base y guarda el estado del que parte cada contingencia.

        Raises:
            DomainError: `N1_BASE_INVALID` si el flujo base no converge.
        """
        self.net: pp.pandapowerNet = pp.from_json_string(net_json)
        self.settings = settings
        try:
            self._runpp(init=str(settings["init"]))
        except pp.LoadflowNotConverged as exc:
            raise DomainError("N1_BASE_INVALID", "el flujo base no converge en el proceso") from exc
        self._in_service: dict[str, pd.Series] = {
            t: self.net[t]["in_service"].copy()
            for t in _STATE_TABLES
            if t in self.net and len(self.net[t])
        }
        self._slack: pd.Series = self.net.gen["slack"].copy()
        self._res_bus: pd.DataFrame = self.net.res_bus.copy()
        self.bus_name: dict[int, str] = {int(i): str(n) for i, n in self.net.bus.name.items()}

    def _runpp(self, init: str) -> None:
        s = self.settings
        pp.runpp(
            self.net,
            algorithm=s["algorithm"],
            init=init,
            max_iteration=s["max_iteration"],
            tolerance_mva=s["tolerance_mva"],
            enforce_q_lims=s["enforce_q_lims"],
            distributed_slack=s["distributed_slack"],
            calculate_voltage_angles=True,
            check_connectivity=True,
            v_debug=True,
            numba=False,  # numba no es dependencia; sin esto pandapower avisa en cada proceso
        )

    def _restore(self) -> None:
        """Vuelve al estado base: servicio de todos los elementos, referencia y tensiones."""
        for table, column in self._in_service.items():
            self.net[table]["in_service"] = column.copy()
        self.net.gen["slack"] = self._slack.copy()
        self.net.res_bus = self._res_bus.copy()

    def _ref_bus(self) -> str:
        gens = self.net.gen
        idx = gens.index[gens.slack & gens.in_service][0]
        return self.bus_name[int(gens.at[idx, "bus"])]

    def loading(self) -> dict[str, float]:
        """Cargabilidad de líneas y transformadores en servicio con resultado.

        Mismo criterio que `run_flow._result`: cuenta la rama si tiene flujo calculado y toma
        la cargabilidad como 0 cuando pandapower no puede calcularla (sin corriente nominal).
        """
        out: dict[str, float] = {}
        for table, p_col in (("line", "p_from_mw"), ("trafo", "p_hv_mw"), ("trafo3w", "p_hv_mw")):
            if table not in self.net or not len(self.net[table]):
                continue
            rows, res = self.net[table], self.net["res_" + table]
            for idx, p in res[p_col].items():
                if not rows.at[idx, "in_service"] or pd.isna(p):
                    continue
                loading = res.at[idx, "loading_percent"]
                out[str(rows.at[idx, "name"])] = 0.0 if pd.isna(loading) else float(loading)
        return out

    def _vm(self) -> dict[str, float]:
        return {self.bus_name[i]: vm for i, (vm, _, _) in bus_vm_nominal(self.net).items()}

    def _move_reference(self) -> str:
        """Pasa la referencia de ángulo al generador de reserva (FR-051, research R6)."""
        net = self.net
        on = net.gen[net.gen.in_service]
        gens = pd.DataFrame(
            {
                "bus": [self.bus_name[int(b)] for b in on.bus],
                "p_mw": on.p_mw.astype(float).to_numpy(),
            }
        )
        buses = pd.DataFrame(
            {
                "bus_id": list(self.bus_name.values()),
                "vn_kv": net.bus.vn_kv.astype(float).to_numpy(),
            }
        )
        new_bus, _ = choose_angle_ref(gens, buses, "")
        at_bus = [self.bus_name[int(b)] == new_bus for b in on.bus]
        net.gen.at[int(on.index[at_bus][0]), "slack"] = True
        return new_bus

    def _solve(self) -> Diagnostics | None:
        """Flujo desde la solución base y, si no converge, desde DC (research R4).

        Devuelve `None` si convergió o el diagnóstico si no. Un error del solver distinto de la
        no convergencia se registra y deja la contingencia sin solución (constitución V).
        """
        last: pp.LoadflowNotConverged | None = None
        for init in ("results", "dc"):
            try:
                self._runpp(init=init)
                return None
            except pp.LoadflowNotConverged as exc:
                last = exc
            except Exception as exc:
                log_event(log, "contingencia con error del solver", error=repr(exc))
                return Diagnostics(
                    iterations=0,
                    max_mismatch_mva=0.0,
                    worst_buses=[],
                    basis=f"error del solver: {type(exc).__name__}",
                )
        assert last is not None
        return diagnose(self.net, last)

    def run_outage(self, outage: Outage) -> RawResult:
        """Saca el activo, trata islas y referencia, corre el flujo y extrae los valores."""
        self._restore()
        net = self.net
        table = _TABLE_OF_KIND[outage.kind]
        matches = net[table].index[net[table]["name"] == outage.element_id]
        if len(matches) == 0:
            raise KeyError(f"{outage.element_id} no está en {table}")
        idx = int(matches[0])
        net[table].at[idx, "in_service"] = False
        moved: str | None = None
        if table == "gen" and bool(net.gen.at[idx, "slack"]):
            net.gen.at[idx, "slack"] = False
            moved = self._move_reference()
        outage = outage.model_copy(update={"angle_ref_moved_to": moved})
        isolation: Isolation | None = None
        if table != "gen":
            lost = [i for i in detect_and_isolate(net, self._ref_bus()) if not i.energized]
            if lost:
                isolation = Isolation(
                    n_buses=sum(i.n_buses for i in lost),
                    p_demand_lost_mw=sum(i.p_demand_lost_mw for i in lost),
                )
        diagnostics = self._solve()
        if diagnostics is not None:
            return RawResult(
                outage=outage,
                converged=False,
                loading={},
                vm_pu={},
                isolation=isolation,
                diagnostics=diagnostics,
            )
        return RawResult(
            outage=outage,
            converged=True,
            loading=self.loading(),
            vm_pu=self._vm(),
            isolation=isolation,
        )


_WORKER: Worker | None = None


def init_worker(net_json: str, settings: dict[str, Any]) -> Worker:
    """Inicializador de cada proceso del pool; también lo usan las pruebas en el mismo proceso."""
    global _WORKER
    _WORKER = Worker(net_json, settings)
    return _WORKER


def _run_chunk(outages: Sequence[Outage]) -> list[RawResult]:
    assert _WORKER is not None, "init_worker no corrió en este proceso"
    return [_WORKER.run_outage(o) for o in outages]


# --- Análisis -----------------------------------------------------------------------------


def _to_result(
    raw: RawResult, base: FlowState, bands: Sequence[VoltageBand], limit: LoadingLimit
) -> ContingencyResult:
    if not raw.converged:
        return ContingencyResult(
            outage=raw.outage, evaluation=None, isolation=raw.isolation, diagnostics=raw.diagnostics
        )
    after = FlowState(loading=raw.loading, vm_pu=raw.vm_pu, vn_kv=base.vn_kv)
    return ContingencyResult(
        outage=raw.outage, evaluation=evaluate(base, after, bands, limit), isolation=raw.isolation
    )


def require_base(run: Run) -> None:
    """Exige una ejecución AC convergida como base del análisis (FR-061).

    Raises:
        DomainError: `N1_BASE_INVALID`.
    """
    if run.flow_type != "ac" or run.status != "convergio" or run.result is None:
        raise DomainError(
            "N1_BASE_INVALID", f"ejecución {run.run_id}: flujo {run.flow_type}, {run.status}"
        )


def analyze(
    run: Run,
    net_json: str,
    cfg: LoadedConfig,
    *,
    workers: int | None = None,
    outages: Sequence[Outage] | None = None,
    progress: ProgressCallback | None = None,
) -> N1Analysis:
    """Corre el análisis N-1 sobre una ejecución AC convergida.

    Args:
        run: Ejecución base guardada; sus valores son la referencia de la comparación (R9).
        net_json: Red del caso en JSON de pandapower.
        cfg: Configuración (solver y límites).
        workers: Procesos; por defecto `default_workers()`. Con 1 corre en este proceso.
        outages: Contingencias a correr; por defecto todas (`enumerate_outages`).
        progress: Avance `(hechas, total)`.

    Raises:
        DomainError: `N1_BASE_INVALID` si la ejecución es DC o no convergió (FR-061).
    """
    require_base(run)
    result = run.result
    assert result is not None  # require_base lo garantiza
    base = FlowState(
        loading={b.element_id: b.loading_percent for b in result.lines + result.trafos},
        vm_pu={b.bus_id: b.vm_pu for b in result.buses},
        vn_kv={b.bus_id: b.vn_kv for b in result.buses},
    )
    bands, limit = cfg.config.voltage_bands(), cfg.config.loading_limit()
    settings = solver_settings(cfg).model_dump()
    todo = (
        list(outages) if outages is not None else enumerate_outages(pp.from_json_string(net_json))
    )
    total = len(todo)
    report: ProgressCallback = progress or (lambda _d, _t: None)
    started = time.perf_counter()
    report(0, total)
    raw: dict[str, RawResult] = {}
    n_used = 1 if total <= 1 else min(workers if workers is not None else default_workers(), total)
    if n_used <= 1:
        worker = init_worker(net_json, settings)
        for i, outage in enumerate(todo, start=1):
            raw[outage.element_id] = worker.run_outage(outage)
            report(i, total)
    else:
        # Lotes pequeños para que el avance se actualice cada pocos segundos (FR-058).
        size = max(1, total // (n_used * 16))
        parts = [todo[i : i + size] for i in range(0, total, size)]
        done = 0
        with ProcessPoolExecutor(
            max_workers=n_used, initializer=init_worker, initargs=(net_json, settings)
        ) as pool:
            for future in as_completed([pool.submit(_run_chunk, part) for part in parts]):
                chunk = future.result()
                for r in chunk:
                    raw[r.outage.element_id] = r
                done += len(chunk)
                report(done, total)
    results = [_to_result(raw[o.element_id], base, bands, limit) for o in todo]
    duration = time.perf_counter() - started
    return N1Analysis(
        run_id=run.run_id,
        trace=run.trace,
        limits=limit_infos(bands, limit),
        analyzed_at=datetime.now(UTC),
        workers=n_used,
        summary=summarize(results, duration_s=duration),
        loading=rank_loading(results),
        voltage=rank_voltage(results),
        isolation=rank_isolation(results),
        unsolved=unsolved_rows(results),
    )


# --- Análisis en segundo plano para la API (FR-058) ---------------------------------------

N1Work = Callable[[ProgressCallback], N1Analysis]


@dataclass
class _JobState:
    job_id: str
    run_id: str
    started_at: datetime
    status: N1Status = "en_cola"
    done: int = 0
    total: int = 0
    finished_at: datetime | None = None
    result: N1Analysis | None = None
    error: ProblemInfo | None = None

    def to_job(self) -> N1Job:
        return N1Job(
            job_id=self.job_id,
            run_id=self.run_id,
            status=self.status,
            done=self.done,
            total=self.total,
            started_at=self.started_at,
            finished_at=self.finished_at,
            result=self.result,
            error=self.error,
        )


@dataclass
class N1Runner:
    """Un único cupo de análisis N-1 en memoria para toda la API (plan 003).

    El análisis ocupa casi todos los núcleos, así que dos a la vez solo se estorbarían.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _jobs: dict[str, _JobState] = field(default_factory=dict)
    _active: str | None = None

    def start(self, run_id: str, work: N1Work) -> N1Job:
        """Acepta un análisis y lo lanza en un hilo.

        Raises:
            DomainError: `N1_IN_PROGRESS` si ya hay uno corriendo.
        """
        with self._lock:
            if self._active is not None:
                active = self._jobs[self._active]
                raise DomainError(
                    "N1_IN_PROGRESS",
                    f"análisis {active.job_id} de la ejecución {active.run_id} en curso",
                )
            state = _JobState(
                job_id=str(uuid.uuid4()), run_id=run_id, started_at=datetime.now(tz=UTC)
            )
            self._jobs[state.job_id] = state
            self._active = state.job_id
        threading.Thread(
            target=self._run, args=(state, work), name=f"n1-{state.job_id[:8]}", daemon=True
        ).start()
        return state.to_job()

    def get(self, job_id: str) -> N1Job:
        """Estado actual de un análisis.

        Raises:
            DomainError: `N1_JOB_NOT_FOUND`.
        """
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                raise DomainError("N1_JOB_NOT_FOUND", f"job_id {job_id}")
            return state.to_job()

    def _progress(self, state: _JobState, done: int, total: int) -> None:
        with self._lock:
            state.done, state.total = done, total
            state.status = "calculando"

    def _run(self, state: _JobState, work: N1Work) -> None:
        trace_id = new_trace_id()
        log_event(log, "análisis N-1 iniciado", job_id=state.job_id, run_id=state.run_id)
        try:
            result = work(lambda done, total: self._progress(state, done, total))
        except DomainError as exc:
            self._finish(state, error=problem_of(exc, trace_id))
            log_event(log, "análisis N-1 fallido", job_id=state.job_id, code=exc.code)
            return
        except Exception:  # nunca un stack trace al usuario (constitución V)
            log.exception("análisis N-1 con error no previsto", extra={"extra_fields": {}})
            self._finish(state, error=internal_problem(trace_id))
            return
        self._finish(state, result=result)
        log_event(
            log,
            "análisis N-1 terminado",
            job_id=state.job_id,
            n_total=result.summary.n_total,
            duration_s=round(result.summary.duration_s, 1),
        )

    def _finish(
        self,
        state: _JobState,
        *,
        result: N1Analysis | None = None,
        error: ProblemInfo | None = None,
    ) -> None:
        with self._lock:
            state.finished_at = datetime.now(tz=UTC)
            state.result = result
            state.error = error
            state.status = "error" if error else "listo"
            if result is not None:
                state.done = state.total = result.summary.n_total
            if self._active == state.job_id:
                self._active = None
