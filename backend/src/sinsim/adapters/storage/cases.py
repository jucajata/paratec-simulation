"""Persistencia de casos y ejecuciones en `cases/<case_id>/` (implementa `CaseRepository`)."""

from __future__ import annotations

from pathlib import Path

from sinsim.domain.entities import Run, StudyCase
from sinsim.domain.errors import DomainError


class FileCaseRepository:
    """Guarda `case.json`, `net.json` y `runs/<run_id>.json` por caso."""

    def __init__(self, root: Path) -> None:
        """Crea el repositorio sobre `cases/`."""
        self.root = root

    def _dir(self, case_id: str) -> Path:
        return self.root / case_id

    def exists(self, case_id: str) -> bool:
        """Indica si el caso ya fue construido."""
        return (self._dir(case_id) / "case.json").exists()

    def save_case(self, case: StudyCase, net_json: str) -> Path:
        """Guarda el caso y su red."""
        d = self._dir(case.case_id)
        (d / "runs").mkdir(parents=True, exist_ok=True)
        (d / "case.json").write_text(case.model_dump_json(indent=2), encoding="utf-8")
        (d / "net.json").write_text(net_json, encoding="utf-8")
        return d

    def get_case(self, case_id: str) -> StudyCase:
        """Devuelve un caso o lanza `CASE_NOT_FOUND`."""
        p = self._dir(case_id) / "case.json"
        if not p.exists():
            raise DomainError("CASE_NOT_FOUND", f"no existe {p}")
        return StudyCase.model_validate_json(p.read_text(encoding="utf-8"))

    def get_net_json(self, case_id: str) -> str:
        """JSON de pandapower del caso."""
        p = self._dir(case_id) / "net.json"
        if not p.exists():
            raise DomainError("CASE_NOT_FOUND", f"no existe {p}")
        return p.read_text(encoding="utf-8")

    def save_run(self, run: Run) -> Path:
        """Guarda una ejecución bajo su caso."""
        d = self._dir(run.case_id) / "runs"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{run.run_id}.json"
        p.write_text(run.model_dump_json(indent=2), encoding="utf-8")
        return p

    def get_run(self, run_id: str) -> Run:
        """Busca una ejecución en todos los casos o lanza `RUN_NOT_FOUND`."""
        if self.root.exists():
            for p in self.root.glob(f"*/runs/{run_id}.json"):
                return Run.model_validate_json(p.read_text(encoding="utf-8"))
        raise DomainError("RUN_NOT_FOUND", f"no existe la ejecución {run_id}")
