"""Thin, UI-independent boundaries over the importer and nesting engine."""

from __future__ import annotations

from os import PathLike

from debbie.domain import Work
from debbie.importers.excel import CanonicalWorkbookImportResult, import_canonical_workbook
from debbie.mass import (
    NestingMassResult,
    WorkMassPlan,
    calculate_nesting_result_mass,
    calculate_work_mass_plan,
)
from debbie.nesting import NestingResult, nest_work
from debbie.nesting.solver import CancellationCheck


class ImportService:
    def import_workbook(self, path: str | PathLike[str]) -> CanonicalWorkbookImportResult:
        return import_canonical_workbook(path)


class NestingService:
    def run(
        self, work: Work, *, cancellation_check: CancellationCheck | None = None
    ) -> NestingResult:
        return nest_work(work, cancellation_check=cancellation_check)


class MassService:
    def plan(self, work: Work) -> WorkMassPlan:
        return calculate_work_mass_plan(work)

    def for_result(self, work: Work, result: NestingResult) -> NestingMassResult:
        return calculate_nesting_result_mass(work, result)
