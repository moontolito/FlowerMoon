"""Explicit, non-persistent state for one Debbie desktop session."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from debbie.domain import Work, WorkId
from debbie.importers.excel import CanonicalWorkbookImportResult, ImportDiagnostic
from debbie.nesting import NestingResult
from debbie.mass import NestingMassResult, WorkMassPlan


@dataclass(frozen=True, slots=True)
class OperationToken:
    generation: int
    operation: str
    work_id: WorkId | None = None


@dataclass(slots=True)
class DebbieSession:
    workbook_path: Path | None = None
    import_result: CanonicalWorkbookImportResult | None = None
    works: tuple[Work, ...] = field(default_factory=tuple)
    selected_work_id: WorkId | None = None
    nesting_result: NestingResult | None = None
    result_work_id: WorkId | None = None
    planning_mass: WorkMassPlan | None = None
    planning_mass_work_id: WorkId | None = None
    nesting_mass: NestingMassResult | None = None
    nesting_mass_work_id: WorkId | None = None
    selected_layout_index: int | None = None
    diagnostics: tuple[ImportDiagnostic, ...] = field(default_factory=tuple)
    busy_operation: str | None = None
    status_message: str = "No workbook loaded"
    _generation: int = 0

    @property
    def selected_work(self) -> Work | None:
        return next((work for work in self.works if work.id == self.selected_work_id), None)

    @property
    def visible_result(self) -> NestingResult | None:
        if self.result_work_id == self.selected_work_id:
            return self.nesting_result
        return None

    def begin_import(self) -> OperationToken:
        if self.busy_operation is not None:
            raise RuntimeError("another operation is already running")
        self._generation += 1
        self.busy_operation = "import"
        self.status_message = "Importing workbook…"
        return OperationToken(self._generation, "import")

    def finish_import(
        self,
        token: OperationToken,
        path: str | Path,
        result: CanonicalWorkbookImportResult,
    ) -> bool:
        if not self._accepts(token):
            return False
        self.busy_operation = None
        self.diagnostics = result.diagnostics
        if not result.success:
            self.status_message = "Workbook not loaded; previous project preserved"
            return True
        self.workbook_path = Path(path)
        self.import_result = result
        self.works = tuple(
            sorted(result.works, key=lambda work: (work.name.casefold(), str(work.id)))
        )
        self.selected_work_id = self.works[0].id if self.works else None
        self.nesting_result = None
        self.result_work_id = None
        self.planning_mass = None
        self.planning_mass_work_id = None
        self.nesting_mass = None
        self.nesting_mass_work_id = None
        self.selected_layout_index = None
        self.status_message = f"Loaded {len(self.works)} work(s)"
        return True

    def select_work(self, work_id: WorkId | None) -> None:
        if work_id is not None and not any(work.id == work_id for work in self.works):
            raise ValueError("selected work is not part of the current project")
        self.selected_work_id = work_id
        self.nesting_result = None
        self.result_work_id = None
        self.planning_mass = None
        self.planning_mass_work_id = None
        self.nesting_mass = None
        self.nesting_mass_work_id = None
        self.selected_layout_index = None
        self.status_message = "Work selected" if work_id is not None else "No work selected"

    def begin_nesting(self) -> tuple[OperationToken, Work]:
        work = self.selected_work
        if work is None:
            raise ValueError("nesting requires a selected work")
        if self.busy_operation is not None:
            raise RuntimeError("another operation is already running")
        self._generation += 1
        self.busy_operation = "nesting"
        self.nesting_result = None
        self.result_work_id = None
        self.nesting_mass = None
        self.nesting_mass_work_id = None
        self.selected_layout_index = None
        self.status_message = "Running nesting…"
        return OperationToken(self._generation, "nesting", work.id), work

    def finish_nesting(self, token: OperationToken, result: NestingResult) -> bool:
        if not self._accepts(token):
            return False
        if token.work_id != result.work_id:
            self.busy_operation = None
            self.status_message = "Rejected nesting result for a different work"
            return False
        self.busy_operation = None
        if token.work_id != self.selected_work_id:
            self.status_message = "Discarded stale nesting result"
            return False
        self.nesting_result = result
        self.result_work_id = result.work_id
        self.selected_layout_index = 0 if result.layouts else None
        self.status_message = f"Nesting {result.status.value}"
        return True

    def set_planning_mass(self, work_id: WorkId, plan: WorkMassPlan) -> bool:
        if work_id != self.selected_work_id:
            return False
        self.planning_mass = plan
        self.planning_mass_work_id = work_id
        return True

    def set_nesting_mass(self, work_id: WorkId, result: NestingMassResult) -> bool:
        if work_id != self.selected_work_id or work_id != self.result_work_id:
            return False
        self.nesting_mass = result
        self.nesting_mass_work_id = work_id
        return True

    def fail_operation(self, token: OperationToken, message: str) -> bool:
        if not self._accepts(token):
            return False
        self.busy_operation = None
        self.status_message = message
        return True

    def invalidate_running_operation(self) -> None:
        self._generation += 1
        self.busy_operation = None

    def _accepts(self, token: OperationToken) -> bool:
        return token.generation == self._generation and token.operation == self.busy_operation
