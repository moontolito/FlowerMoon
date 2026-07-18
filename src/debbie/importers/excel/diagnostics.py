"""Stable structured diagnostics for canonical workbook import."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ImportSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ImportDiagnosticCode(str, Enum):
    WORKBOOK_FORMAT_MISMATCH = "WORKBOOK_FORMAT_MISMATCH"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    UNREADABLE_WORKBOOK = "UNREADABLE_WORKBOOK"
    UNSAFE_WORKBOOK_CONTENT = "UNSAFE_WORKBOOK_CONTENT"
    SIZE_LIMIT_EXCEEDED = "SIZE_LIMIT_EXCEEDED"
    UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
    UNSUPPORTED_UNITS = "UNSUPPORTED_UNITS"
    MISSING_REQUIRED_SHEET = "MISSING_REQUIRED_SHEET"
    DUPLICATE_REQUIRED_SHEET = "DUPLICATE_REQUIRED_SHEET"
    MISSING_REQUIRED_HEADER = "MISSING_REQUIRED_HEADER"
    DUPLICATE_HEADER = "DUPLICATE_HEADER"
    DUPLICATE_METADATA_KEY = "DUPLICATE_METADATA_KEY"
    INVALID_METADATA = "INVALID_METADATA"
    UNKNOWN_METADATA_KEY = "UNKNOWN_METADATA_KEY"
    UNKNOWN_WORKSHEET = "UNKNOWN_WORKSHEET"
    UNKNOWN_COLUMN = "UNKNOWN_COLUMN"
    EMPTY_REQUIRED_VALUE = "EMPTY_REQUIRED_VALUE"
    INVALID_TEXT_VALUE = "INVALID_TEXT_VALUE"
    INVALID_NUMERIC_VALUE = "INVALID_NUMERIC_VALUE"
    NON_FINITE_NUMBER = "NON_FINITE_NUMBER"
    NON_POSITIVE_DIMENSION = "NON_POSITIVE_DIMENSION"
    NEGATIVE_PROCESS_VALUE = "NEGATIVE_PROCESS_VALUE"
    INVALID_INTEGER_VALUE = "INVALID_INTEGER_VALUE"
    INVALID_BOOLEAN_VALUE = "INVALID_BOOLEAN_VALUE"
    DUPLICATE_WORK_KEY = "DUPLICATE_WORK_KEY"
    DUPLICATE_PART_KEY = "DUPLICATE_PART_KEY"
    DUPLICATE_STOCK_KEY = "DUPLICATE_STOCK_KEY"
    UNKNOWN_WORK_REFERENCE = "UNKNOWN_WORK_REFERENCE"
    INVALID_TRIM_FOR_STOCK = "INVALID_TRIM_FOR_STOCK"
    INVALID_EFFECTIVE_STOCK_REGION = "INVALID_EFFECTIVE_STOCK_REGION"
    UNSUPPORTED_FORMULA_VALUE = "UNSUPPORTED_FORMULA_VALUE"
    MERGED_CELL_IN_DATA_TABLE = "MERGED_CELL_IN_DATA_TABLE"
    DOMAIN_VALIDATION_FAILURE = "DOMAIN_VALIDATION_FAILURE"
    INTERNAL_IMPORT_ERROR = "INTERNAL_IMPORT_ERROR"


@dataclass(frozen=True, slots=True)
class ImportDiagnostic:
    severity: ImportSeverity
    code: ImportDiagnosticCode
    message: str
    worksheet: str | None = None
    row: int | None = None
    column: int | None = None
    column_letter: str | None = None
    header: str | None = None
    offending_value: str | None = None
    related_work_key: str | None = None
    related_part_key: str | None = None
    related_stock_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", ImportSeverity(self.severity))
        object.__setattr__(self, "code", ImportDiagnosticCode(self.code))
        if not self.message.strip():
            raise ValueError("diagnostic message must not be empty")


class DiagnosticCollector:
    """Small mutable accumulator kept inside one import call."""

    def __init__(self) -> None:
        self._items: list[ImportDiagnostic] = []

    def add(
        self,
        severity: ImportSeverity,
        code: ImportDiagnosticCode,
        message: str,
        **location: object,
    ) -> None:
        self._items.append(ImportDiagnostic(severity, code, message, **location))

    def error(self, code: ImportDiagnosticCode, message: str, **location: object) -> None:
        self.add(ImportSeverity.ERROR, code, message, **location)

    def info(self, code: ImportDiagnosticCode, message: str, **location: object) -> None:
        self.add(ImportSeverity.INFO, code, message, **location)

    @property
    def has_errors(self) -> bool:
        return any(item.severity is ImportSeverity.ERROR for item in self._items)

    def extend(self, items: tuple[ImportDiagnostic, ...]) -> None:
        self._items.extend(items)

    def freeze(self) -> tuple[ImportDiagnostic, ...]:
        return tuple(self._items)
