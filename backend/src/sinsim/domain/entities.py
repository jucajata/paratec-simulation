"""Entidades de dominio (data-model.md).

Modelos Pydantic v2 inmutables. Este módulo no importa pandapower, httpx ni FastAPI
(constitución IV). Las tablas normalizadas viajan como DataFrames de pandas en
`SnapshotTables`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

FlowType = Literal["ac", "dc"]
RunStatus = Literal["convergio", "no_convergio"]
VoltageLevel = Literal["STN", "STR", "SDL"]


class Frozen(BaseModel):
    """Base inmutable para todas las entidades."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# --- Snapshot y manifiesto -----------------------------------------------------


class SourceFile(Frozen):
    """Origen de una entidad del snapshot."""

    entity: str
    url: str
    source_modified_at: datetime | None = None
    standard_version: str | None = None


class FileEntry(Frozen):
    """Archivo del snapshot con su checksum."""

    path: str
    sha256: str
    bytes: int


class DispatchVersion(Frozen):
    """Versión del despacho usada cuando XM publica varias el mismo día (D-3)."""

    used: str
    available: list[str]


class Manifest(Frozen):
    """`manifest.json` de un snapshot (contracts/snapshot-format.md)."""

    schema_version: int = 1
    snapshot_date: date
    extracted_at: datetime
    scraper_version: str
    attribution: str
    sources: list[SourceFile]
    dispatch_version: DispatchVersion | None = None
    record_counts: dict[str, int]
    files: list[FileEntry]


class SnapshotSummary(Frozen):
    """Fila de `sinsim snapshots list` y de `GET /api/snapshots` (FR-002)."""

    date: date
    has_paratec: bool
    has_dispatch: bool
    has_demand: bool
    intact: bool


@dataclass(frozen=True)
class SnapshotTables:
    """Tablas normalizadas de un snapshot (data-model.md §2)."""

    buses: pd.DataFrame
    lines: pd.DataFrame
    trafos2w: pd.DataFrame
    trafos3w: pd.DataFrame
    generators: pd.DataFrame
    shunts: pd.DataFrame
    svc_statcom: pd.DataFrame
    dispatch: pd.DataFrame
    demand: pd.DataFrame


@dataclass(frozen=True)
class LoadedSnapshot:
    """Snapshot verificado y cargado en memoria."""

    date: date
    manifest: Manifest
    manifest_sha256: str
    tables: SnapshotTables


# --- Caso de estudio -------------------------------------------------------------


class CaseInputs(Frozen):
    """Entradas que definen un caso; su JSON canónico se hashea en `case_id`."""

    snapshot_date: date
    dispatch_date: date
    period: int = Field(ge=1, le=24)
    snapshot_manifest_sha256: str
    equivalences_sha256: str
    config_sha256: str
    sinsim_version: str


class UnlocatedResource(Frozen):
    """Recurso del despacho con P > 0 sin equivalencia o sin barra (FR-012)."""

    resource: str
    p_mw: float
    reason: str


class UnlocatedDemand(Frozen):
    """Nodo del pronóstico sin barra asociable (FR-014a)."""

    node: str
    vn_kv: float
    p_mw: float
    q_mvar: float
    reason: str


class Transfer(Frozen):
    """Traslado de un generador o una carga a la barra de la frontera STR/SDL (FR-019)."""

    element: str
    kind: Literal["gen", "demand"]
    from_bus: str
    to_bus: str
    p_mw: float
    q_mvar: float


class ExcludedElement(Frozen):
    """Elemento excluido por parámetros faltantes (FR-013)."""

    element: str
    kind: str
    missing_params: list[str]


class ImputedValue(Frozen):
    """Parámetro imputado de forma explícita (FR-013, constitución III.5)."""

    element: str
    kind: str
    param: str
    method: str
    value: float


class NotModeled(Frozen):
    """Elemento conocido que no entra al modelo."""

    element: str
    kind: str
    reason: str


class Island(Frozen):
    """Componente conexa del modelo (FR-016, D-5)."""

    island_id: int
    n_buses: int
    buses: list[str]
    p_gen_lost_mw: float
    p_demand_lost_mw: float
    energized: bool


class Balance(Frozen):
    """Balance del caso (data-model.md §5)."""

    p_scheduled_total_mw: float
    p_located_mw: float
    p_unlocated_mw: float
    coverage_pct: float
    p_demand_mw: float
    p_demand_unlocated_mw: float
    difference_mw: float


class QualityReport(Frozen):
    """Reporte de calidad del caso (HU-2)."""

    unlocated_resources: list[UnlocatedResource]
    unlocated_demand: list[UnlocatedDemand]
    transfers: list[Transfer]
    excluded: list[ExcludedElement]
    imputed: list[ImputedValue]
    not_modeled: list[NotModeled]
    islands: list[Island]
    physical_issues: list[str] = []
    balance: Balance


class StudyCase(Frozen):
    """Caso construido para una fecha y un periodo (data-model.md §4)."""

    case_id: str
    inputs: CaseInputs
    quality: QualityReport
    assumptions: dict[str, Any]
    warnings: list[str]
    created_at: datetime


# --- Ejecución y resultado -------------------------------------------------------


class SolverSettings(Frozen):
    """Parámetros del solver registrados en la trazabilidad (FR-023)."""

    algorithm: str
    tolerance_mva: float
    max_iteration: int
    init: str
    enforce_q_lims: bool
    distributed_slack: bool


class Trace(Frozen):
    """Trazabilidad obligatoria de cada resultado (FR-023, constitución III.7)."""

    snapshot_date: date
    dispatch_date: date
    period: int
    flow_type: FlowType
    pandapower_version: str
    sinsim_version: str
    solver: SolverSettings
    case_id: str


class BusMismatch(Frozen):
    """Barra con desbalance en una no convergencia."""

    bus: str
    mismatch_mva: float


class Diagnostics(Frozen):
    """Diagnóstico de una no convergencia (FR-022, constitución III.8)."""

    iterations: int
    max_mismatch_mva: float
    worst_buses: list[BusMismatch]
    basis: str = "última iteración"
    """Tensión usada para el desbalance: última iteración, última finita o arranque plano."""


class BusResult(Frozen):
    """Resultado por barra (FR-030)."""

    bus_id: str
    vn_kv: float
    vm_pu: float
    vm_kv: float
    va_degree: float
    violation: Literal["low", "high"] | None = None


class BranchResult(Frozen):
    """Resultado por línea o transformador (FR-030)."""

    element_id: str
    kind: Literal["line", "trafo2w", "trafo3w"]
    from_bus: str
    to_bus: str
    p_from_mw: float
    q_from_mvar: float
    p_to_mw: float
    q_to_mvar: float
    i_ka: float
    loading_percent: float
    pl_mw: float
    ql_mvar: float
    overload: bool


class GeneratorResult(Frozen):
    """Resultado por generador (FR-030, FR-024)."""

    gen_id: str
    resource: str
    bus: str
    p_scheduled_mw: float
    p_mw: float
    q_mvar: float
    slack_adjust_mw: float


class LimitInfo(Frozen):
    """Límite aplicado y su fuente (constitución III.9)."""

    name: str
    value: str
    source: str


class ResultSummary(Frozen):
    """Resumen de una ejecución convergida."""

    p_gen_mw: float
    p_load_mw: float
    p_losses_mw: float
    slack_adjust_total_mw: float
    n_voltage_violations: int
    n_overloads: int
    limits: list[LimitInfo]
    warnings: list[str]


class RunResult(Frozen):
    """Valores por elemento de una ejecución convergida (data-model.md §7)."""

    buses: list[BusResult]
    lines: list[BranchResult]
    trafos: list[BranchResult]
    generators: list[GeneratorResult]
    summary: ResultSummary


class Run(Frozen):
    """Ejecución de un flujo sobre un caso (data-model.md §6)."""

    run_id: str
    case_id: str
    flow_type: FlowType
    status: RunStatus
    label: str
    solver: SolverSettings
    trace: Trace
    diagnostics: Diagnostics | None = None
    result: RunResult | None = None
    created_at: datetime


LABEL_AC = "Flujo sobre despacho programado"
LABEL_DC = "Aproximación DC sobre despacho programado"
WARNING_PROGRAM_NOT_REAL_STATE = (
    "PROGRAM_NOT_REAL_STATE: el resultado describe el despacho programado por XM, "
    "no el estado real del SIN."
)
