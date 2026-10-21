"""Actualización de datos de una fecha (HU-3, FR-003 a FR-007, FR-038).

La orquestación es una sola y la comparten el CLI (`sinsim scrape`) y la API
(`POST /api/snapshots/{fecha}/descarga`): comprobar que no exista el snapshot, descargar PARATEC,
descargar el despacho y la demanda del día, normalizar y escribir de forma atómica.

`ScrapeRunner` ejecuta esa orquestación en un hilo del proceso de la API con un único cupo
(plan D-9): mientras corre una descarga, cualquier otra recibe `SCRAPE_IN_PROGRESS`. El estado
vive en memoria y no sobrevive a un reinicio (NG-09: nada automático ni programado).
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sinsim.domain.entities import (
    ProblemInfo,
    ScrapeJob,
    ScrapeStatus,
    ScrapeStep,
    SnapshotSummary,
)
from sinsim.domain.errors import CATALOG, DomainError, problem_type_url
from sinsim.observability import log_event, new_trace_id

if TYPE_CHECKING:  # evita el ciclo bootstrap → services → bootstrap
    from sinsim.bootstrap import AppContext

log = logging.getLogger("sinsim.scrape")

PARATEC_NOTICE = (
    "PARATEC no tiene histórico: los parámetros técnicos descargados son los vigentes en el "
    "momento de la descarga (extracted_at del manifiesto), no los de la fecha solicitada. El "
    "despacho y el pronóstico de demanda sí son los de la fecha."
)

StepCallback = Callable[[ScrapeStep], None]


@dataclass(frozen=True)
class ScrapeOutcome:
    """Resultado de una descarga terminada."""

    path: Path
    manifest: dict[str, Any]
    summary: SnapshotSummary


def _no_step(_: ScrapeStep) -> None:
    return None


def scrape_snapshot(
    ctx: AppContext,
    day: date,
    *,
    out_dir: Path | None = None,
    on_step: StepCallback = _no_step,
) -> ScrapeOutcome:
    """Descarga PARATEC, despacho y demanda de `day` y escribe el snapshot (FR-003 a FR-007).

    Raises:
        DomainError: `SNAPSHOT_EXISTS`, `NETWORK_ERROR`, `XM_FILE_NOT_FOUND`,
            `PARATEC_SCHEMA_CHANGED`, `XM_FILE_SCHEMA_CHANGED` o `DISPATCH_TOTAL_MISMATCH`.
    """
    from sinsim.scraper import paratec as paratec_client
    from sinsim.scraper import xm_files
    from sinsim.scraper.http import RateLimitedClient
    from sinsim.scraper.writer import RawSnapshot, write_snapshot

    root = out_dir or ctx.snapshots.root
    if (root / day.isoformat()).exists():
        raise DomainError("SNAPSHOT_EXISTS", f"ya existe {root / day.isoformat()}")
    s = ctx.cfg.config.scraper
    with RateLimitedClient(
        user_agent=ctx.cfg.config.user_agent(),
        min_interval_s=s.min_interval_s,
        timeout_s=s.timeout_s,
    ) as client:
        on_step("paratec")
        par, par_sources = paratec_client.fetch_all(client)
        on_step("despacho_y_demanda")
        xm, xm_sources = xm_files.fetch_for_date(client, day)
    on_step("normalizacion")
    raw = RawSnapshot(paratec=par, xm=xm, sources=par_sources + xm_sources)
    final = write_snapshot(
        raw,
        root,
        day,
        scraper_version=ctx.version,
        attribution=ctx.cfg.config.attribution.text,
    )
    manifest = json.loads((final / "manifest.json").read_text(encoding="utf-8"))
    summary = next(
        (row for row in ctx.snapshots.list_summaries() if row.date == day),
        SnapshotSummary(
            date=day, has_paratec=True, has_dispatch=True, has_demand=True, intact=True
        ),
    )
    on_step("listo")
    return ScrapeOutcome(path=final, manifest=manifest, summary=summary)


def problem_of(exc: DomainError, trace_id: str) -> ProblemInfo:
    """Problem Details de un error de dominio, igual al que devuelve la API."""
    return ProblemInfo(
        type=problem_type_url(exc.code),
        title=exc.title,
        status=exc.http_status,
        detail=exc.detail,
        code=exc.code,
        user_message=exc.user_message,
        trace_id=trace_id,
    )


def _internal_problem(trace_id: str) -> ProblemInfo:
    spec = CATALOG["INTERNAL_ERROR"]
    return ProblemInfo(
        type=problem_type_url(spec.code),
        title=spec.title,
        status=spec.http_status,
        detail="Consulta los logs con el trace_id.",
        code=spec.code,
        user_message=spec.user_message,
        trace_id=trace_id,
    )


ScrapeWork = Callable[[StepCallback], ScrapeOutcome]


@dataclass
class _JobState:
    job_id: str
    date: date
    started_at: datetime
    status: ScrapeStatus = "en_cola"
    step: ScrapeStep = "en_cola"
    finished_at: datetime | None = None
    snapshot: SnapshotSummary | None = None
    error: ProblemInfo | None = None

    def to_job(self) -> ScrapeJob:
        return ScrapeJob(
            job_id=self.job_id,
            date=self.date,
            status=self.status,
            step=self.step,
            started_at=self.started_at,
            finished_at=self.finished_at,
            snapshot=self.snapshot,
            error=self.error,
            notice=PARATEC_NOTICE,
        )


@dataclass
class ScrapeRunner:
    """Un cupo de descarga en memoria para la API (plan D-9)."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _jobs: dict[str, _JobState] = field(default_factory=dict)
    _active: str | None = None

    def start(self, day: date, work: ScrapeWork) -> ScrapeJob:
        """Acepta una descarga y la lanza en un hilo.

        Raises:
            DomainError: `SCRAPE_IN_PROGRESS` si ya hay una corriendo.
        """
        with self._lock:
            if self._active is not None:
                active = self._jobs[self._active]
                raise DomainError(
                    "SCRAPE_IN_PROGRESS",
                    f"descarga {active.job_id} de {active.date} en curso",
                    user_message=(
                        f"Ya se está descargando la fecha {active.date}. Espera a que termine "
                        "e inténtalo de nuevo."
                    ),
                )
            state = _JobState(job_id=str(uuid.uuid4()), date=day, started_at=datetime.now(tz=UTC))
            self._jobs[state.job_id] = state
            self._active = state.job_id
        thread = threading.Thread(
            target=self._run, args=(state, work), name=f"scrape-{day}", daemon=True
        )
        thread.start()
        return state.to_job()

    def get(self, job_id: str) -> ScrapeJob:
        """Estado actual de una descarga.

        Raises:
            DomainError: `SCRAPE_JOB_NOT_FOUND`.
        """
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                raise DomainError("SCRAPE_JOB_NOT_FOUND", f"job_id {job_id}")
            return state.to_job()

    def _set_step(self, state: _JobState, step: ScrapeStep) -> None:
        with self._lock:
            state.step = step
            if step not in ("listo", "error"):
                state.status = "descargando"

    def _run(self, state: _JobState, work: ScrapeWork) -> None:
        trace_id = new_trace_id()
        log_event(log, "descarga iniciada", job_id=state.job_id, date=state.date.isoformat())
        try:
            outcome = work(lambda step: self._set_step(state, step))
        except DomainError as exc:
            self._finish(state, error=problem_of(exc, trace_id))
            log_event(log, "descarga fallida", job_id=state.job_id, code=exc.code)
            return
        except Exception:  # nunca un stack trace al usuario (constitución V)
            log.exception("descarga con error no previsto", extra={"extra_fields": {}})
            self._finish(state, error=_internal_problem(trace_id))
            return
        self._finish(state, snapshot=outcome.summary)
        log_event(log, "descarga terminada", job_id=state.job_id, path=str(outcome.path))

    def _finish(
        self,
        state: _JobState,
        *,
        snapshot: SnapshotSummary | None = None,
        error: ProblemInfo | None = None,
    ) -> None:
        with self._lock:
            state.finished_at = datetime.now(tz=UTC)
            state.snapshot = snapshot
            state.error = error
            state.status = "error" if error else "listo"
            state.step = "error" if error else "listo"
            if self._active == state.job_id:
                self._active = None
