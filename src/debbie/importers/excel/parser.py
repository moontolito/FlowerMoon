"""Strict schema recognition, cell parsing, and neutral-record validation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import re
from typing import Callable

from .constants import (
    FORMAT_NAME,
    KNOWN_METADATA,
    METADATA_HEADERS,
    OPTIONAL_PART_HEADERS,
    PART_HEADERS,
    REQUIRED_METADATA,
    REQUIRED_SHEETS,
    SCHEMA_VERSION,
    STOCK_HEADERS,
    UNIT_SYSTEM,
    WORK_HEADERS,
    ImportLimits,
)
from .diagnostics import DiagnosticCollector, ImportDiagnostic, ImportDiagnosticCode
from .models import (
    CanonicalWorkbookRecords,
    PartImportRecord,
    SourceLocation,
    StockImportRecord,
    WorkbookMetadataRecord,
    WorkImportRecord,
)
from .reader import CellSnapshot, SheetSnapshot, WorkbookSnapshot

_WHITESPACE = re.compile(r"\s+")
_NUMERIC_TEXT = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$", re.ASCII)


@dataclass(frozen=True, slots=True)
class ParseOutcome:
    records: CanonicalWorkbookRecords | None
    diagnostics: tuple[ImportDiagnostic, ...]
    format_name: str | None
    schema_version: str | None
    units: str | None


def normalize_header(value: str) -> str:
    return _WHITESPACE.sub(" ", value.strip()).casefold()


def normalize_metadata_key(value: str) -> str:
    """Metadata keys use the documented header-style case-insensitive policy."""

    return normalize_header(value)


def _location(cell: CellSnapshot, sheet: SheetSnapshot, header: str | None = None) -> dict:
    return {
        "worksheet": sheet.title,
        "row": cell.row,
        "column": cell.column,
        "column_letter": cell.column_letter,
        "header": header,
        "offending_value": cell.value_repr,
    }


def _formula_without_cache(
    cell: CellSnapshot,
    sheet: SheetSnapshot,
    header: str,
    diagnostics: DiagnosticCollector,
) -> bool:
    if cell.is_formula and cell.value is None:
        diagnostics.error(
            ImportDiagnosticCode.UNSUPPORTED_FORMULA_VALUE,
            f"Formula in {header!r} has no usable cached value",
            **_location(cell, sheet, header),
        )
        return True
    return False


def _required_text(
    cell: CellSnapshot,
    sheet: SheetSnapshot,
    header: str,
    diagnostics: DiagnosticCollector,
    limits: ImportLimits,
) -> str | None:
    if _formula_without_cache(cell, sheet, header, diagnostics):
        return None
    if cell.value is None or (isinstance(cell.value, str) and not cell.value.strip()):
        diagnostics.error(
            ImportDiagnosticCode.EMPTY_REQUIRED_VALUE,
            f"{header} is required",
            **_location(cell, sheet, header),
        )
        return None
    if cell.is_error or not isinstance(cell.value, str):
        diagnostics.error(
            ImportDiagnosticCode.INVALID_TEXT_VALUE,
            f"{header} must be text",
            **_location(cell, sheet, header),
        )
        return None
    value = cell.value.strip()
    if len(value) > limits.max_text_length:
        diagnostics.error(
            ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
            f"{header} exceeds the {limits.max_text_length}-character limit",
            **_location(cell, sheet, header),
        )
        return None
    return value


def _optional_text(
    cell: CellSnapshot,
    sheet: SheetSnapshot,
    header: str,
    diagnostics: DiagnosticCollector,
    limits: ImportLimits,
) -> str | None:
    if _formula_without_cache(cell, sheet, header, diagnostics):
        return None
    if cell.value is None or (isinstance(cell.value, str) and not cell.value.strip()):
        return None
    if cell.is_error or not isinstance(cell.value, str):
        diagnostics.error(
            ImportDiagnosticCode.INVALID_TEXT_VALUE,
            f"{header} must be text when supplied",
            **_location(cell, sheet, header),
        )
        return None
    value = cell.value.strip()
    if len(value) > limits.max_text_length:
        diagnostics.error(
            ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
            f"{header} exceeds the {limits.max_text_length}-character limit",
            **_location(cell, sheet, header),
        )
        return None
    return value


def _number_value(
    cell: CellSnapshot,
    sheet: SheetSnapshot,
    header: str,
    diagnostics: DiagnosticCollector,
) -> float | None:
    if _formula_without_cache(cell, sheet, header, diagnostics):
        return None
    value = cell.value
    if value is None or (isinstance(value, str) and not value.strip()):
        diagnostics.error(
            ImportDiagnosticCode.EMPTY_REQUIRED_VALUE,
            f"{header} is required",
            **_location(cell, sheet, header),
        )
        return None
    if cell.is_error or isinstance(value, bool):
        diagnostics.error(
            ImportDiagnosticCode.INVALID_NUMERIC_VALUE,
            f"{header} must be a number",
            **_location(cell, sheet, header),
        )
        return None
    if isinstance(value, str):
        text = value.strip()
        non_finite_tokens = {
            "nan",
            "+nan",
            "-nan",
            "inf",
            "+inf",
            "-inf",
            "infinity",
            "+infinity",
            "-infinity",
        }
        if text.casefold() in non_finite_tokens:
            diagnostics.error(
                ImportDiagnosticCode.NON_FINITE_NUMBER,
                f"{header} must be finite",
                **_location(cell, sheet, header),
            )
            return None
        if not _NUMERIC_TEXT.fullmatch(text):
            diagnostics.error(
                ImportDiagnosticCode.INVALID_NUMERIC_VALUE,
                f"{header} must use locale-independent dot-decimal numeric text",
                **_location(cell, sheet, header),
            )
            return None
        number = float(text)
    elif isinstance(value, (int, float)):
        number = float(value)
    else:
        diagnostics.error(
            ImportDiagnosticCode.INVALID_NUMERIC_VALUE,
            f"{header} must be a numeric cell or strict numeric text",
            **_location(cell, sheet, header),
        )
        return None
    if not isfinite(number):
        diagnostics.error(
            ImportDiagnosticCode.NON_FINITE_NUMBER,
            f"{header} must be finite",
            **_location(cell, sheet, header),
        )
        return None
    return number


def _non_negative_number(
    cell: CellSnapshot,
    sheet: SheetSnapshot,
    header: str,
    diagnostics: DiagnosticCollector,
) -> float | None:
    number = _number_value(cell, sheet, header, diagnostics)
    if number is not None and number < 0:
        diagnostics.error(
            ImportDiagnosticCode.NEGATIVE_PROCESS_VALUE,
            f"{header} must be non-negative",
            **_location(cell, sheet, header),
        )
        return None
    return number


def _positive_number(
    cell: CellSnapshot,
    sheet: SheetSnapshot,
    header: str,
    diagnostics: DiagnosticCollector,
) -> float | None:
    number = _number_value(cell, sheet, header, diagnostics)
    if number is not None and number <= 0:
        diagnostics.error(
            ImportDiagnosticCode.NON_POSITIVE_DIMENSION,
            f"{header} must be greater than zero",
            **_location(cell, sheet, header),
        )
        return None
    return number


def _positive_integer(
    cell: CellSnapshot,
    sheet: SheetSnapshot,
    header: str,
    diagnostics: DiagnosticCollector,
    limits: ImportLimits,
) -> int | None:
    if isinstance(cell.value, bool):
        diagnostics.error(
            ImportDiagnosticCode.INVALID_INTEGER_VALUE,
            f"{header} must be a positive integer, not a boolean",
            **_location(cell, sheet, header),
        )
        return None
    number = _number_value(cell, sheet, header, diagnostics)
    if number is None:
        return None
    if not number.is_integer() or number <= 0 or number > limits.max_integer_value:
        diagnostics.error(
            ImportDiagnosticCode.INVALID_INTEGER_VALUE,
            f"{header} must be a positive integer no greater than {limits.max_integer_value}",
            **_location(cell, sheet, header),
        )
        return None
    return int(number)


def _rotation(
    cell: CellSnapshot,
    sheet: SheetSnapshot,
    diagnostics: DiagnosticCollector,
    limits: ImportLimits,
) -> bool | None:
    header = "Allow Rotation"
    value = _required_text(cell, sheet, header, diagnostics, limits)
    if value is None:
        return None
    normalized = value.casefold()
    if normalized == "yes":
        return True
    if normalized == "no":
        return False
    diagnostics.error(
        ImportDiagnosticCode.INVALID_BOOLEAN_VALUE,
        "Allow Rotation accepts only Yes or No",
        **_location(cell, sheet, header),
    )
    return None


def _required_sheet_map(
    workbook: WorkbookSnapshot, diagnostics: DiagnosticCollector
) -> dict[str, SheetSnapshot]:
    by_trimmed_name: dict[str, list[SheetSnapshot]] = {}
    for sheet in workbook.sheets:
        by_trimmed_name.setdefault(sheet.title.strip(), []).append(sheet)
    selected: dict[str, SheetSnapshot] = {}
    for required in REQUIRED_SHEETS:
        matches = by_trimmed_name.get(required, [])
        if not matches:
            code = (
                ImportDiagnosticCode.WORKBOOK_FORMAT_MISMATCH
                if required == "Debbie"
                else ImportDiagnosticCode.MISSING_REQUIRED_SHEET
            )
            diagnostics.error(code, f"Required worksheet {required!r} is missing")
        elif len(matches) > 1:
            diagnostics.error(
                ImportDiagnosticCode.DUPLICATE_REQUIRED_SHEET,
                f"More than one worksheet normalizes to {required!r}",
                worksheet=required,
            )
        else:
            selected[required] = matches[0]
    for normalized, sheets in by_trimmed_name.items():
        if normalized not in REQUIRED_SHEETS:
            for sheet in sheets:
                diagnostics.info(
                    ImportDiagnosticCode.UNKNOWN_WORKSHEET,
                    f"Unknown worksheet {sheet.title!r} was ignored",
                    worksheet=sheet.title,
                )
    return selected


def _merged_table_diagnostics(sheet: SheetSnapshot, diagnostics: DiagnosticCollector) -> None:
    last_non_empty = max(
        (row for row in range(1, sheet.max_row + 1) if sheet.row_has_value(row)),
        default=1,
    )
    for merged in sheet.merged_ranges:
        if merged.min_row <= last_non_empty and merged.max_row >= 1:
            diagnostics.error(
                ImportDiagnosticCode.MERGED_CELL_IN_DATA_TABLE,
                f"Merged range {merged.coordinate} intersects the canonical table",
                worksheet=sheet.title,
                row=merged.min_row,
                column=merged.min_column,
            )


def _header_map(
    sheet: SheetSnapshot,
    required: tuple[str, ...],
    optional: tuple[str, ...],
    diagnostics: DiagnosticCollector,
) -> dict[str, int]:
    canonical = {normalize_header(item): item for item in (*required, *optional)}
    found: dict[str, int] = {}
    seen: dict[str, int] = {}
    for cell in sheet.rows[0] if sheet.rows else ():
        if cell.value is None or (isinstance(cell.value, str) and not cell.value.strip()):
            continue
        if _formula_without_cache(cell, sheet, "header", diagnostics):
            continue
        if cell.is_error or not isinstance(cell.value, str):
            diagnostics.error(
                ImportDiagnosticCode.INVALID_TEXT_VALUE,
                "Canonical headers must be text",
                **_location(cell, sheet),
            )
            continue
        normalized = normalize_header(cell.value)
        if normalized in seen:
            diagnostics.error(
                ImportDiagnosticCode.DUPLICATE_HEADER,
                f"Duplicate normalized header {cell.value.strip()!r}",
                **_location(cell, sheet, cell.value.strip()),
            )
            continue
        seen[normalized] = cell.column
        if normalized in canonical:
            found[canonical[normalized]] = cell.column
        else:
            diagnostics.info(
                ImportDiagnosticCode.UNKNOWN_COLUMN,
                f"Unknown column {cell.value.strip()!r} was ignored",
                **_location(cell, sheet, cell.value.strip()),
            )
    for header in required:
        if header not in found:
            diagnostics.error(
                ImportDiagnosticCode.MISSING_REQUIRED_HEADER,
                f"Required header {header!r} is missing",
                worksheet=sheet.title,
                row=1,
                header=header,
            )
    return found


def _metadata(
    sheet: SheetSnapshot,
    diagnostics: DiagnosticCollector,
    limits: ImportLimits,
) -> WorkbookMetadataRecord:
    _merged_table_diagnostics(sheet, diagnostics)
    for column, expected in enumerate(METADATA_HEADERS, start=1):
        cell = sheet.cell(1, column)
        if _formula_without_cache(cell, sheet, expected, diagnostics):
            continue
        actual = cell.value if isinstance(cell.value, str) else None
        if actual is None or normalize_header(actual) != normalize_header(expected):
            diagnostics.error(
                ImportDiagnosticCode.MISSING_REQUIRED_HEADER,
                f"Debbie metadata cell {cell.column_letter}1 must be {expected!r}",
                **_location(cell, sheet, expected),
            )
    values: dict[str, tuple[str, str]] = {}
    for row in range(2, sheet.max_row + 1):
        if not sheet.row_has_value(row):
            continue
        key_cell = sheet.cell(row, 1)
        value_cell = sheet.cell(row, 2)
        key = _required_text(key_cell, sheet, "Key", diagnostics, limits)
        value = _required_text(value_cell, sheet, "Value", diagnostics, limits)
        if key is None or value is None:
            continue
        normalized = normalize_metadata_key(key)
        if normalized in values:
            diagnostics.error(
                ImportDiagnosticCode.DUPLICATE_METADATA_KEY,
                f"Duplicate metadata key {key!r}",
                **_location(key_cell, sheet, "Key"),
            )
            continue
        values[normalized] = (key, value)

    known = {normalize_metadata_key(item): item for item in KNOWN_METADATA}
    for required in REQUIRED_METADATA:
        if normalize_metadata_key(required) not in values:
            diagnostics.error(
                ImportDiagnosticCode.INVALID_METADATA,
                f"Required metadata key {required!r} is missing",
                worksheet=sheet.title,
                header="Key",
            )
    extras: list[tuple[str, str]] = []
    for normalized, (key, value) in values.items():
        if normalized not in known:
            diagnostics.info(
                ImportDiagnosticCode.UNKNOWN_METADATA_KEY,
                f"Unknown metadata key {key!r} was preserved as provenance",
                worksheet=sheet.title,
                related_work_key=None,
            )
            extras.append((key, value))

    def value_for(key: str) -> str | None:
        item = values.get(normalize_metadata_key(key))
        return item[1] if item else None

    format_name = value_for("Format Name")
    version = value_for("Schema Version")
    units = value_for("Units")
    if format_name is not None and format_name != FORMAT_NAME:
        diagnostics.error(
            ImportDiagnosticCode.WORKBOOK_FORMAT_MISMATCH,
            f"Format Name must be {FORMAT_NAME!r}",
            worksheet=sheet.title,
            header="Value",
            offending_value=repr(format_name),
        )
    if version is not None and version != SCHEMA_VERSION:
        diagnostics.error(
            ImportDiagnosticCode.UNSUPPORTED_SCHEMA_VERSION,
            f"Schema Version {version!r} is unsupported",
            worksheet=sheet.title,
            header="Value",
            offending_value=repr(version),
        )
    if units is not None and units != UNIT_SYSTEM:
        diagnostics.error(
            ImportDiagnosticCode.UNSUPPORTED_UNITS,
            f"Units must be {UNIT_SYSTEM!r}",
            worksheet=sheet.title,
            header="Value",
            offending_value=repr(units),
        )
    optional_extras = [
        (canonical, values[normalize_metadata_key(canonical)][1])
        for canonical in ("Application Version", "Description")
        if normalize_metadata_key(canonical) in values
    ]
    return WorkbookMetadataRecord(
        format_name,
        version,
        units,
        tuple(sorted((*optional_extras, *extras), key=lambda item: item[0].casefold())),
    )


def _parse_rows(
    sheet: SheetSnapshot,
    headers: dict[str, int],
    row_parser: Callable[[SheetSnapshot, int, dict[str, int]], object | None],
) -> list:
    parsed = []
    for row in range(2, sheet.max_row + 1):
        if sheet.row_has_value(row):
            record = row_parser(sheet, row, headers)
            if record is not None:
                parsed.append(record)
    return parsed


def parse_workbook(workbook: WorkbookSnapshot, limits: ImportLimits) -> ParseOutcome:
    diagnostics = DiagnosticCollector()
    sheets = _required_sheet_map(workbook, diagnostics)
    metadata_record = WorkbookMetadataRecord(None, None, None)
    if "Debbie" in sheets:
        metadata_record = _metadata(sheets["Debbie"], diagnostics, limits)

    total_data_rows = sum(
        sum(1 for row in range(2, sheet.max_row + 1) if sheet.row_has_value(row))
        for name, sheet in sheets.items()
        if name in {"Works", "Parts", "Stocks"}
    )
    if total_data_rows > limits.max_total_data_rows:
        diagnostics.error(
            ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
            f"Workbook contains more than {limits.max_total_data_rows} populated data rows",
        )

    works: list[WorkImportRecord] = []
    parts: list[PartImportRecord] = []
    stocks: list[StockImportRecord] = []
    work_key_candidates: list[tuple[str, SourceLocation]] = []
    part_key_candidates: list[tuple[str, str | None, SourceLocation]] = []
    stock_key_candidates: list[tuple[str, str | None, SourceLocation]] = []

    if "Works" in sheets:
        sheet = sheets["Works"]
        _merged_table_diagnostics(sheet, diagnostics)
        headers = _header_map(sheet, WORK_HEADERS, (), diagnostics)

        def parse_work(sheet: SheetSnapshot, row: int, headers: dict[str, int]):
            if any(header not in headers for header in WORK_HEADERS):
                return None
            before = len(diagnostics.freeze())
            cell = lambda header: sheet.cell(row, headers[header])
            values = (
                _required_text(cell("Work Key"), sheet, "Work Key", diagnostics, limits),
                _required_text(cell("Work Name"), sheet, "Work Name", diagnostics, limits),
                _positive_integer(
                    cell("Batch Multiplier"), sheet, "Batch Multiplier", diagnostics, limits
                ),
                _non_negative_number(cell("Kerf (mm)"), sheet, "Kerf (mm)", diagnostics),
                _non_negative_number(
                    cell("Part Clearance (mm)"),
                    sheet,
                    "Part Clearance (mm)",
                    diagnostics,
                ),
                _non_negative_number(
                    cell("Boundary Clearance (mm)"),
                    sheet,
                    "Boundary Clearance (mm)",
                    diagnostics,
                ),
                _non_negative_number(cell("Trim Left (mm)"), sheet, "Trim Left (mm)", diagnostics),
                _non_negative_number(
                    cell("Trim Right (mm)"), sheet, "Trim Right (mm)", diagnostics
                ),
                _non_negative_number(cell("Trim Top (mm)"), sheet, "Trim Top (mm)", diagnostics),
                _non_negative_number(
                    cell("Trim Bottom (mm)"), sheet, "Trim Bottom (mm)", diagnostics
                ),
            )
            if values[0] is not None:
                work_key_candidates.append(
                    (values[0], SourceLocation(sheet.title, row))
                )
            if len(diagnostics.freeze()) != before or any(value is None for value in values):
                return None
            return WorkImportRecord(*values, SourceLocation(sheet.title, row))

        works = _parse_rows(sheet, headers, parse_work)

    if "Parts" in sheets:
        sheet = sheets["Parts"]
        _merged_table_diagnostics(sheet, diagnostics)
        headers = _header_map(sheet, PART_HEADERS, OPTIONAL_PART_HEADERS, diagnostics)

        def parse_part(sheet: SheetSnapshot, row: int, headers: dict[str, int]):
            if any(header not in headers for header in PART_HEADERS):
                return None
            before = len(diagnostics.freeze())
            cell = lambda header: sheet.cell(row, headers[header])
            drawing = (
                _optional_text(cell("Drawing Number"), sheet, "Drawing Number", diagnostics, limits)
                if "Drawing Number" in headers
                else None
            )
            values = (
                _required_text(cell("Work Key"), sheet, "Work Key", diagnostics, limits),
                _required_text(cell("Part Key"), sheet, "Part Key", diagnostics, limits),
                _required_text(cell("Part Name"), sheet, "Part Name", diagnostics, limits),
                _positive_number(cell("Length (mm)"), sheet, "Length (mm)", diagnostics),
                _positive_number(cell("Width (mm)"), sheet, "Width (mm)", diagnostics),
                _positive_integer(cell("Quantity"), sheet, "Quantity", diagnostics, limits),
                _rotation(cell("Allow Rotation"), sheet, diagnostics, limits),
            )
            if values[0] is not None:
                part_key_candidates.append(
                    (values[0], values[1], SourceLocation(sheet.title, row))
                )
            if len(diagnostics.freeze()) != before or any(value is None for value in values):
                return None
            return PartImportRecord(*values, drawing, SourceLocation(sheet.title, row))

        parts = _parse_rows(sheet, headers, parse_part)

    if "Stocks" in sheets:
        sheet = sheets["Stocks"]
        _merged_table_diagnostics(sheet, diagnostics)
        headers = _header_map(sheet, STOCK_HEADERS, (), diagnostics)

        def parse_stock(sheet: SheetSnapshot, row: int, headers: dict[str, int]):
            if any(header not in headers for header in STOCK_HEADERS):
                return None
            before = len(diagnostics.freeze())
            cell = lambda header: sheet.cell(row, headers[header])
            values = (
                _required_text(cell("Work Key"), sheet, "Work Key", diagnostics, limits),
                _required_text(cell("Stock Key"), sheet, "Stock Key", diagnostics, limits),
                _required_text(cell("Stock Name"), sheet, "Stock Name", diagnostics, limits),
                _positive_number(cell("Length (mm)"), sheet, "Length (mm)", diagnostics),
                _positive_number(cell("Width (mm)"), sheet, "Width (mm)", diagnostics),
                _positive_integer(cell("Quantity"), sheet, "Quantity", diagnostics, limits),
            )
            if values[0] is not None:
                stock_key_candidates.append(
                    (values[0], values[1], SourceLocation(sheet.title, row))
                )
            if len(diagnostics.freeze()) != before or any(value is None for value in values):
                return None
            return StockImportRecord(*values, SourceLocation(sheet.title, row))

        stocks = _parse_rows(sheet, headers, parse_stock)

    seen_work_keys: set[str] = set()
    for work_key, source in work_key_candidates:
        if work_key in seen_work_keys:
            diagnostics.error(
                ImportDiagnosticCode.DUPLICATE_WORK_KEY,
                f"Duplicate Work Key {work_key!r}",
                worksheet=source.worksheet,
                row=source.row,
                related_work_key=work_key,
            )
        else:
            seen_work_keys.add(work_key)
    valid_work_keys = {record.work_key for record in works}

    seen_parts: set[tuple[str, str]] = set()
    for work_key, part_key, source in part_key_candidates:
        if work_key not in valid_work_keys:
            diagnostics.error(
                ImportDiagnosticCode.UNKNOWN_WORK_REFERENCE,
                f"Part references unknown Work Key {work_key!r}",
                worksheet=source.worksheet,
                row=source.row,
                related_work_key=work_key,
                related_part_key=part_key,
            )
        if part_key is None:
            continue
        identity = (work_key, part_key)
        if identity in seen_parts:
            diagnostics.error(
                ImportDiagnosticCode.DUPLICATE_PART_KEY,
                f"Duplicate Part Key {part_key!r} in work {work_key!r}",
                worksheet=source.worksheet,
                row=source.row,
                related_work_key=work_key,
                related_part_key=part_key,
            )
        seen_parts.add(identity)

    seen_stocks: set[tuple[str, str]] = set()
    for work_key, stock_key, source in stock_key_candidates:
        if work_key not in valid_work_keys:
            diagnostics.error(
                ImportDiagnosticCode.UNKNOWN_WORK_REFERENCE,
                f"Stock references unknown Work Key {work_key!r}",
                worksheet=source.worksheet,
                row=source.row,
                related_work_key=work_key,
                related_stock_key=stock_key,
            )
        if stock_key is None:
            continue
        identity = (work_key, stock_key)
        if identity in seen_stocks:
            diagnostics.error(
                ImportDiagnosticCode.DUPLICATE_STOCK_KEY,
                f"Duplicate Stock Key {stock_key!r} in work {work_key!r}",
                worksheet=source.worksheet,
                row=source.row,
                related_work_key=work_key,
                related_stock_key=stock_key,
            )
        seen_stocks.add(identity)

    records = CanonicalWorkbookRecords(
        metadata_record,
        tuple(sorted(works, key=lambda item: item.work_key)),
        tuple(sorted(parts, key=lambda item: (item.work_key, item.part_key))),
        tuple(sorted(stocks, key=lambda item: (item.work_key, item.stock_key))),
    )
    return ParseOutcome(
        records,
        diagnostics.freeze(),
        metadata_record.format_name,
        metadata_record.schema_version,
        metadata_record.units,
    )
