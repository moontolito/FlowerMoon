"""Public stateless entry point for canonical `.xlsx` import."""

from __future__ import annotations

from os import PathLike
from pathlib import Path

from .constants import DEFAULT_IMPORT_LIMITS, ImportLimits
from .diagnostics import ImportDiagnostic, ImportDiagnosticCode, ImportSeverity
from .domain_builder import build_domain
from .models import CanonicalWorkbookImportResult
from .parser import parse_workbook
from .reader import WorkbookReadProblem, read_workbook


class CanonicalExcelImporter:
    """Offline, canonical-only, state-free importer for schema 1.0."""

    def __init__(self, *, limits: ImportLimits = DEFAULT_IMPORT_LIMITS) -> None:
        self._limits = limits

    def import_file(self, path: str | PathLike[str]) -> CanonicalWorkbookImportResult:
        try:
            source = Path(path)
        except (TypeError, ValueError) as error:
            return self._failure(
                None,
                ImportDiagnosticCode.INVALID_TEXT_VALUE,
                f"Workbook path is invalid: {type(error).__name__}",
            )
        if source.suffix.casefold() != ".xlsx":
            return self._failure(
                source,
                ImportDiagnosticCode.UNSUPPORTED_FILE_TYPE,
                "Canonical import supports only .xlsx files",
            )
        try:
            snapshot = read_workbook(source, self._limits)
            parsed = parse_workbook(snapshot, self._limits)
            if any(
                item.severity is ImportSeverity.ERROR for item in parsed.diagnostics
            ):
                return CanonicalWorkbookImportResult(
                    diagnostics=parsed.diagnostics,
                    format_name=parsed.format_name,
                    schema_version=parsed.schema_version,
                    unit_system=parsed.units,
                    source_path=source,
                )
            if parsed.records is None:
                raise RuntimeError("successful parsing did not produce neutral records")
            built = build_domain(parsed.records, self._limits)
            diagnostics = (*parsed.diagnostics, *built.diagnostics)
            if any(item.severity is ImportSeverity.ERROR for item in diagnostics):
                return CanonicalWorkbookImportResult(
                    diagnostics=diagnostics,
                    format_name=parsed.format_name,
                    schema_version=parsed.schema_version,
                    unit_system=parsed.units,
                    source_path=source,
                )
            return CanonicalWorkbookImportResult(
                works=built.works,
                diagnostics=diagnostics,
                format_name=parsed.format_name,
                schema_version=parsed.schema_version,
                unit_system=parsed.units,
                source_path=source,
                records=parsed.records,
                summary=built.summary,
            )
        except WorkbookReadProblem as error:
            return self._failure(source, error.code, str(error))
        except Exception as error:  # Public boundary: programming failures stay distinct.
            return self._failure(
                source,
                ImportDiagnosticCode.INTERNAL_IMPORT_ERROR,
                f"Unexpected importer failure ({type(error).__name__})",
            )

    @staticmethod
    def _failure(
        source: Path | None, code: ImportDiagnosticCode, message: str
    ) -> CanonicalWorkbookImportResult:
        return CanonicalWorkbookImportResult(
            diagnostics=(ImportDiagnostic(ImportSeverity.ERROR, code, message),),
            source_path=source,
        )


def import_canonical_workbook(
    path: str | PathLike[str], *, limits: ImportLimits = DEFAULT_IMPORT_LIMITS
) -> CanonicalWorkbookImportResult:
    """Import one canonical workbook without mutating external state."""

    return CanonicalExcelImporter(limits=limits).import_file(path)
