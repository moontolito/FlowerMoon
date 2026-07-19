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
class WorkbookMetadataRecordV11:
    format_name: str | None
    schema_version: str | None
    units: str | None
    density_units: str | None
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
class WorkImportRecordV11:
    work_key: str
    work_name: str
    material_category_key: str
    material_category_name: str
    material_grade_key: str
    material_grade_name: str
    thickness_mm: float
    density_g_per_cm3: float
    density_source: str
    material_description: str | None
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
class StockImportRecordV11:
    work_key: str
    stock_key: str
    stock_name: str
    full_length: float
    full_width: float
    allocated_length: float
    allocated_width: float
    commercial_allocation_fraction: float
    quantity: int
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class CanonicalWorkbookRecords:
    metadata: WorkbookMetadataRecord
    works: tuple[WorkImportRecord, ...]
    parts: tuple[PartImportRecord, ...]
    stocks: tuple[StockImportRecord, ...]


@dataclass(frozen=True, slots=True)
class CanonicalWorkbookV11Records:
    metadata: WorkbookMetadataRecordV11
    works: tuple[WorkImportRecordV11, ...]
    parts: tuple[PartImportRecord, ...]
    stocks: tuple[StockImportRecordV11, ...]


@dataclass(frozen=True, slots=True)
class MaterialImportSummary:
    work_key: str
    category_key: str
    category_name: str
    grade_key: str
    grade_name: str
    thickness_mm: float
    density_g_per_cm3: float
    density_source: str
    description: str | None


@dataclass(frozen=True, slots=True)
class StockAllocationImportSummary:
    work_key: str
    stock_key: str
    full_length_mm: float
    full_width_mm: float
    allocated_length_mm: float
    allocated_width_mm: float
    physical_allocation_fraction: float
    commercial_allocation_fraction: float


@dataclass(frozen=True, slots=True)
class ImportSummary:
    work_count: int
    part_type_count: int
    demand_item_count: int
    stock_specification_count: int
    stock_instance_count: int
    drawing_numbers: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ImportSummaryV11(ImportSummary):
    materials: tuple[MaterialImportSummary, ...] = field(default_factory=tuple)
    stock_allocations: tuple[StockAllocationImportSummary, ...] = field(default_factory=tuple)
    schema_version: str = "1.1"
    adapter_id: str = "canonical_excel_v1_1"
    work_keys: tuple[str, ...] = field(default_factory=tuple)
    density_units: str = "g/cm3"


@dataclass(frozen=True, slots=True)
class CanonicalWorkbookImportResult:
    works: tuple[Work, ...] = field(default_factory=tuple)
    diagnostics: tuple[ImportDiagnostic, ...] = field(default_factory=tuple)
    format_name: str | None = None
    schema_version: str | None = None
    unit_system: str | None = None
    adapter_id: str = ADAPTER_ID
    source_path: Path | None = None
    records: CanonicalWorkbookRecords | CanonicalWorkbookV11Records | None = None
    summary: ImportSummary | ImportSummaryV11 | None = None

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
