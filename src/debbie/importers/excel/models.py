"""Immutable neutral records and public canonical import result."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from debbie.domain import Work

from .constants import ADAPTER_ID
from .diagnostics import ImportDiagnostic, ImportSeverity


@dataclass(frozen=True, slots=True)
class SourceLocation:
    worksheet: str
    row: int
    column: int | None = None
    header: str | None = None


@dataclass(frozen=True, slots=True)
class WorkbookMetadataRecord:
    format_name: str | None
    schema_version: str | None
    units: str | None
    extra_items: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class WorkImportRecord:
    work_key: str
    work_name: str
    batch_multiplier: int
    kerf: float
    part_clearance: float
    boundary_clearance: float
    trim_left: float
    trim_right: float
    trim_top: float
    trim_bottom: float
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class PartImportRecord:
    work_key: str
    part_key: str
    part_name: str
    length: float
    width: float
    quantity: int
    allow_rotation: bool
    drawing_number: str | None
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class StockImportRecord:
    work_key: str
    stock_key: str
    stock_name: str
    length: float
    width: float
    quantity: int
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class CanonicalWorkbookRecords:
    metadata: WorkbookMetadataRecord
    works: tuple[WorkImportRecord, ...]
    parts: tuple[PartImportRecord, ...]
    stocks: tuple[StockImportRecord, ...]


@dataclass(frozen=True, slots=True)
class ImportSummary:
    work_count: int
    part_type_count: int
    demand_item_count: int
    stock_specification_count: int
    stock_instance_count: int
    drawing_numbers: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CanonicalWorkbookImportResult:
    works: tuple[Work, ...] = field(default_factory=tuple)
    diagnostics: tuple[ImportDiagnostic, ...] = field(default_factory=tuple)
    format_name: str | None = None
    schema_version: str | None = None
    unit_system: str | None = None
    adapter_id: str = ADAPTER_ID
    source_path: Path | None = None
    records: CanonicalWorkbookRecords | None = None
    summary: ImportSummary | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "works", tuple(self.works))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.errors and (
            self.works or self.records is not None or self.summary is not None
        ):
            raise ValueError(
                "failed imports must not expose works, neutral records, or summaries"
            )

    @property
    def success(self) -> bool:
        return not self.errors

    @property
    def errors(self) -> tuple[ImportDiagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.severity is ImportSeverity.ERROR)

    @property
    def warnings(self) -> tuple[ImportDiagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.severity is ImportSeverity.WARNING)

    @property
    def information(self) -> tuple[ImportDiagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.severity is ImportSeverity.INFO)
