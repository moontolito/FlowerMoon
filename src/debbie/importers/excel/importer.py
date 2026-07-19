"""Public stateless entry point for canonical `.xlsx` import."""

from __future__ import annotations

from os import PathLike
from pathlib import Path

from .constants import (
    ADAPTER_ID,
    ADAPTER_ID_V11,
    DEFAULT_IMPORT_LIMITS,
    DISPATCH_ADAPTER_ID,
    SCHEMA_VERSION,
    SCHEMA_VERSION_V11,
    ImportLimits,
)
from .diagnostics import (
    DiagnosticCollector,
    ImportDiagnostic,
    ImportDiagnosticCode,
    ImportSeverity,
)
from .domain_builder import build_domain
from .models import CanonicalWorkbookImportResult, CanonicalWorkbookV11Records
from .parser import normalize_metadata_key, parse_workbook
from .reader import WorkbookReadProblem, WorkbookSnapshot, read_workbook
from .schema_v11 import build_domain_v11, parse_workbook_v11


def _declared_schema_version(
    snapshot: WorkbookSnapshot,
) -> tuple[str | None, tuple[ImportDiagnostic, ...]]:
    """Validate the version dispatch key without invoking either schema parser."""

    diagnostics = DiagnosticCollector()
    metadata_sheets = [sheet for sheet in snapshot.sheets if sheet.title.strip() == "Debbie"]
    if not metadata_sheets:
        diagnostics.error(
            ImportDiagnosticCode.WORKBOOK_FORMAT_MISMATCH,
            "Required worksheet 'Debbie' is missing",
        )
        return None, diagnostics.freeze()
    if len(metadata_sheets) > 1:
        diagnostics.error(
            ImportDiagnosticCode.DUPLICATE_REQUIRED_SHEET,
            "More than one worksheet normalizes to 'Debbie'",
            worksheet="Debbie",
        )
        return None, diagnostics.freeze()
    sheet = metadata_sheets[0]
    for column, expected in ((1, "Key"), (2, "Value")):
        header_cell = sheet.cell(1, column)
        actual = header_cell.value
        if header_cell.is_formula and actual is None:
            diagnostics.error(
                ImportDiagnosticCode.UNSUPPORTED_FORMULA_VALUE,
                f"Formula in {expected!r} has no usable cached value",
                worksheet=sheet.title,
                row=1,
                column=column,
                column_letter=header_cell.column_letter,
                header=expected,
                offending_value=header_cell.value_repr,
            )
        if not isinstance(actual, str) or normalize_metadata_key(actual) != normalize_metadata_key(
            expected
        ):
            diagnostics.error(
                ImportDiagnosticCode.MISSING_REQUIRED_HEADER,
                f"Debbie metadata cell {sheet.cell(1, column).column_letter}1 must be {expected!r}",
                worksheet=sheet.title,
                row=1,
                column=column,
                column_letter=header_cell.column_letter,
                header=expected,
                offending_value=header_cell.value_repr,
            )
    versions = []
    for row in range(2, sheet.max_row + 1):
        key = sheet.cell(row, 1).value
        if isinstance(key, str) and normalize_metadata_key(key) == normalize_metadata_key(
            "Schema Version"
        ):
            versions.append(sheet.cell(row, 2))
    if not versions:
        diagnostics.error(
            ImportDiagnosticCode.INVALID_METADATA,
            "Required metadata key 'Schema Version' is missing",
            worksheet=sheet.title,
            header="Key",
        )
        return None, diagnostics.freeze()
    if len(versions) > 1:
        diagnostics.error(
            ImportDiagnosticCode.DUPLICATE_METADATA_KEY,
            "Duplicate metadata key 'Schema Version'",
            worksheet=sheet.title,
            row=versions[1].row,
            header="Key",
        )
    version_cell = versions[0]
    value = version_cell.value
    row = version_cell.row
    if version_cell.is_formula and value is None:
        diagnostics.error(
            ImportDiagnosticCode.UNSUPPORTED_FORMULA_VALUE,
            "Formula in 'Schema Version' has no usable cached value",
            worksheet=sheet.title,
            row=row,
            column=version_cell.column,
            column_letter=version_cell.column_letter,
            header="Value",
            offending_value=version_cell.value_repr,
        )
        return None, diagnostics.freeze()
    if not isinstance(value, str) or not value.strip():
        diagnostics.error(
            ImportDiagnosticCode.INVALID_METADATA,
            "Schema Version must be non-empty text",
            worksheet=sheet.title,
            row=row,
            header="Value",
            offending_value=repr(value),
        )
        return None, diagnostics.freeze()
    version = value.strip()
    if version not in {SCHEMA_VERSION, SCHEMA_VERSION_V11}:
        diagnostics.error(
            ImportDiagnosticCode.UNSUPPORTED_SCHEMA_VERSION,
            f"Schema Version {version!r} is unsupported",
            worksheet=sheet.title,
            row=row,
            header="Value",
            offending_value=repr(version),
        )
        return version, diagnostics.freeze()
    return version, diagnostics.freeze()


class CanonicalExcelImporter:
    """Offline, canonical-only, state-free importer for schemas 1.0 and 1.1."""

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
            declared_version, dispatch_diagnostics = _declared_schema_version(snapshot)
            if dispatch_diagnostics:
                adapter_id = (
                    ADAPTER_ID_V11
                    if declared_version == SCHEMA_VERSION_V11
                    else ADAPTER_ID
                    if declared_version == SCHEMA_VERSION
                    else DISPATCH_ADAPTER_ID
                )
                return CanonicalWorkbookImportResult(
                    diagnostics=dispatch_diagnostics,
                    schema_version=declared_version,
                    adapter_id=adapter_id,
                    source_path=source,
                )
            if declared_version == SCHEMA_VERSION_V11:
                parsed = parse_workbook_v11(snapshot, self._limits)
                adapter_id = ADAPTER_ID_V11
            elif declared_version == SCHEMA_VERSION:
                parsed = parse_workbook(snapshot, self._limits)
                adapter_id = ADAPTER_ID
            else:  # Dispatch validation above makes this unreachable.
                raise RuntimeError("schema dispatch produced no supported version")
            if any(
                item.severity is ImportSeverity.ERROR for item in parsed.diagnostics
            ):
                return CanonicalWorkbookImportResult(
                    diagnostics=parsed.diagnostics,
                    format_name=parsed.format_name,
                    schema_version=parsed.schema_version,
                    unit_system=parsed.units,
                    adapter_id=adapter_id,
                    source_path=source,
                )
            if parsed.records is None:
                raise RuntimeError("successful parsing did not produce neutral records")
            if declared_version == SCHEMA_VERSION_V11:
                if not isinstance(parsed.records, CanonicalWorkbookV11Records):
                    raise RuntimeError("schema 1.1 parser returned an incompatible record set")
                built = build_domain_v11(parsed.records, self._limits)
            else:
                built = build_domain(parsed.records, self._limits)
            diagnostics = (*parsed.diagnostics, *built.diagnostics)
            if any(item.severity is ImportSeverity.ERROR for item in diagnostics):
                return CanonicalWorkbookImportResult(
                    diagnostics=diagnostics,
                    format_name=parsed.format_name,
                    schema_version=parsed.schema_version,
                    unit_system=parsed.units,
                    adapter_id=adapter_id,
                    source_path=source,
                )
            return CanonicalWorkbookImportResult(
                works=built.works,
                diagnostics=diagnostics,
                format_name=parsed.format_name,
                schema_version=parsed.schema_version,
                unit_system=parsed.units,
                adapter_id=adapter_id,
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
