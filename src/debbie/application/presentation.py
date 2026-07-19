"""Read-only Desktop presentation state over authoritative backend results."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite

from debbie.domain import DensitySource, Work
from debbie.importers.excel import (
    CanonicalWorkbookImportResult,
    CanonicalWorkbookRecords,
    CanonicalWorkbookV11Records,
    WorkImportRecord,
    WorkImportRecordV11,
)
from debbie.importers.excel.identifiers import stock_specification_id, work_id, work_id_v11
from debbie.geometry import effective_placement_region, usable_stock_rectangle
from debbie.mass import (
    MassCalculationDiagnostic,
    MassCalculationStatus,
    NestingMassResult,
    WorkMassPlan,
)

UNAVAILABLE = "—"


def _display_number(value: float, decimals: int) -> str:
    if not isfinite(value):
        raise ValueError("display values must be finite")
    rounded = round(value, decimals)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{decimals}f}"


def format_mass(value: float) -> str:
    return f"{_display_number(value, 2)} kg"


def format_dimension(value: float) -> str:
    return f"{_display_number(value, 2)} mm"


def format_dimension_value(value: float) -> str:
    """Format a dimension whose table header already carries the mm unit."""

    return _display_number(value, 2)


def format_density(value: float) -> str:
    return f"{_display_number(value, 3)} g/cm³"


def format_fraction(value: float) -> str:
    return f"{_display_number(value * 100.0, 2)}%"


def format_equivalent_sheets(value: float) -> str:
    return f"{_display_number(value, 3)} sheets"


@dataclass(frozen=True, slots=True)
class SummaryItemViewModel:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class DiagnosticViewModel:
    severity: str
    code: str
    message: str
    related: str = ""


@dataclass(frozen=True, slots=True)
class WorkInformationViewModel:
    work_name: str = UNAVAILABLE
    work_key: str = UNAVAILABLE
    schema_version: str = UNAVAILABLE
    material_category: str = UNAVAILABLE
    material_grade: str = UNAVAILABLE
    thickness: str = UNAVAILABLE
    density: str = UNAVAILABLE
    density_source: str = UNAVAILABLE
    batch_multiplier: str = UNAVAILABLE
    material_description: str = UNAVAILABLE
    classification_message: str = "No Work selected"


@dataclass(frozen=True, slots=True)
class MassSummaryViewModel:
    status: MassCalculationStatus | None = None
    message: str = "Mass calculations have not been run."
    items: tuple[SummaryItemViewModel, ...] = field(default_factory=tuple)
    diagnostics: tuple[DiagnosticViewModel, ...] = field(default_factory=tuple)


WorkImportRecordAny = WorkImportRecord | WorkImportRecordV11


@dataclass(frozen=True, slots=True)
class StockAllocationRowViewModel:
    stock_name: str
    stock_key: str
    quantity: int
    full_length_mm: float
    full_width_mm: float
    allocated_length_mm: float
    allocated_width_mm: float
    physical_allocation_fraction: float
    commercial_allocation_fraction: float
    usable_length_mm: float
    usable_width_mm: float
    effective_length_mm: float
    effective_width_mm: float


def work_record_for(
    work: Work,
    records: CanonicalWorkbookRecords | CanonicalWorkbookV11Records | None,
) -> WorkImportRecordAny | None:
    if isinstance(records, CanonicalWorkbookV11Records):
        return next(
            (record for record in records.works if work_id_v11(record.work_key) == work.id),
            None,
        )
    if isinstance(records, CanonicalWorkbookRecords):
        return next(
            (record for record in records.works if work_id(record.work_key) == work.id),
            None,
        )
    return None


def work_key_for(
    work: Work,
    records: CanonicalWorkbookRecords | CanonicalWorkbookV11Records | None,
) -> str:
    record = work_record_for(work, records)
    return record.work_key if record is not None else str(work.id)[:8]


def build_stock_allocation_rows(
    work: Work | None,
    records: CanonicalWorkbookRecords | CanonicalWorkbookV11Records | None,
) -> tuple[StockAllocationRowViewModel, ...]:
    if work is None:
        return ()
    work_record = work_record_for(work, records)
    imported = {}
    if work_record is not None and records is not None:
        imported = {
            stock_specification_id(work.id, item.stock_key): item.stock_key
            for item in records.stocks
            if item.work_key == work_record.work_key
        }
    quantities: dict[object, int] = {}
    for instance in work.stock_instances:
        quantities[instance.specification_id] = (
            quantities.get(instance.specification_id, 0) + 1
        )
    rows = []
    for stock in sorted(
        work.stock_specifications, key=lambda item: (item.name.casefold(), str(item.id))
    ):
        allocation = stock.effective_allocation
        usable = usable_stock_rectangle(stock, work.process_profile)
        effective = effective_placement_region(stock, work.process_profile)
        rows.append(
            StockAllocationRowViewModel(
                stock.name,
                imported.get(stock.id, str(stock.id)[:8]),
                quantities.get(stock.id, 0),
                allocation.full_dimensions.length,
                allocation.full_dimensions.width,
                allocation.allocated_dimensions.length,
                allocation.allocated_dimensions.width,
                allocation.physical_allocation_fraction,
                allocation.commercial_allocation_fraction,
                usable.length,
                usable.width,
                effective.length,
                effective.width,
            )
        )
    return tuple(rows)


def build_work_information(
    work: Work | None, result: CanonicalWorkbookImportResult | None
) -> WorkInformationViewModel:
    if work is None:
        return WorkInformationViewModel()
    records = result.records if result is not None else None
    common = {
        "work_name": work.name,
        "work_key": work_key_for(work, records),
        "schema_version": (result.schema_version or UNAVAILABLE) if result else UNAVAILABLE,
        "batch_multiplier": str(work.batch_multiplier),
    }
    if not work.is_material_classified:
        return WorkInformationViewModel(
            **common,
            classification_message="Material data: Not available in schema 1.0",
        )
    assert work.material is not None and work.thickness is not None
    source = {
        DensitySource.LIBRARY_DEFAULT: "Library default",
        DensitySource.EXPLICIT_OVERRIDE: "Explicit override",
    }[work.material.density_source]
    return WorkInformationViewModel(
        **common,
        material_category=work.material.category_display_name,
        material_grade=work.material.grade_display_name,
        thickness=format_dimension(work.thickness.millimetres),
        density=format_density(
            work.material.effective_density.grams_per_cubic_centimetre
        ),
        density_source=source,
        material_description=work.material.description or UNAVAILABLE,
        classification_message="Classified material data from canonical schema 1.1",
    )


def _diagnostic_view(diagnostic: MassCalculationDiagnostic) -> DiagnosticViewModel:
    related = []
    if diagnostic.related_work_id is not None:
        related.append(f"Work {diagnostic.related_work_id}")
    if diagnostic.related_stock_instance_id is not None:
        related.append(f"Stock {diagnostic.related_stock_instance_id}")
    if diagnostic.related_demand_item_id is not None:
        related.append(f"Demand {diagnostic.related_demand_item_id}")
    return DiagnosticViewModel(
        diagnostic.severity.value.title(),
        diagnostic.code.value,
        diagnostic.message,
        "; ".join(related),
    )


def build_work_mass_summary(plan: WorkMassPlan | None) -> MassSummaryViewModel:
    if plan is None:
        return MassSummaryViewModel()
    diagnostics = tuple(_diagnostic_view(item) for item in plan.diagnostics)
    if plan.status is MassCalculationStatus.MATERIAL_DATA_REQUIRED:
        return MassSummaryViewModel(
            plan.status,
            "Mass calculations unavailable because this Work has no material and thickness classification.",
            diagnostics=diagnostics,
        )
    assert plan.totals is not None
    totals = plan.totals
    items = [
        SummaryItemViewModel("Rectangular Part Mass Estimate", format_mass(totals.rectangular_part_mass_estimate_kg)),
        SummaryItemViewModel("Gross Physical Allocation Mass", format_mass(totals.gross_physical_allocation_mass_kg)),
        SummaryItemViewModel("Gross Commercial Allocation Mass", format_mass(totals.gross_commercial_allocation_mass_kg)),
        SummaryItemViewModel("Physical Unused Allocation Mass", format_mass(totals.physical_unused_allocation_mass_kg)),
        SummaryItemViewModel("Commercial Allocation Difference", format_mass(totals.commercial_allocation_difference_kg)),
        SummaryItemViewModel("Commercial Material Allowance", format_mass(totals.commercial_material_allowance_kg)),
        SummaryItemViewModel("Physical Equivalent Sheets", format_equivalent_sheets(totals.physical_equivalent_sheets)),
        SummaryItemViewModel("Commercial Equivalent Sheets", format_equivalent_sheets(totals.commercial_equivalent_sheets)),
    ]
    if plan.per_product is not None:
        per_product = plan.per_product
        items.extend(
            (
                SummaryItemViewModel("Rectangular Part Mass / Product", format_mass(per_product.rectangular_part_mass_estimate_kg)),
                SummaryItemViewModel("Gross Physical Mass / Product", format_mass(per_product.gross_physical_allocation_mass_kg)),
                SummaryItemViewModel("Gross Commercial Mass / Product", format_mass(per_product.gross_commercial_allocation_mass_kg)),
            )
        )
    message = (
        "Available physical allocation is insufficient for the expanded rectangular demand."
        if plan.status is MassCalculationStatus.INSUFFICIENT_AVAILABLE_STOCK
        else "Planning material totals are available."
    )
    return MassSummaryViewModel(plan.status, message, tuple(items), diagnostics)


def build_nesting_mass_summary(result: NestingMassResult | None) -> MassSummaryViewModel:
    if result is None:
        return MassSummaryViewModel(message="Run nesting to calculate consumed material totals.")
    diagnostics = tuple(_diagnostic_view(item) for item in result.diagnostics)
    if result.totals is None:
        messages = {
            MassCalculationStatus.FAILED_VALIDATION: "Material consumption totals are unavailable because nesting validation failed.",
            MassCalculationStatus.MATERIAL_DATA_REQUIRED: "Material consumption totals are unavailable because this Work has no material and thickness classification.",
            MassCalculationStatus.WORK_RESULT_MISMATCH: "Material consumption totals are unavailable because the Work and result do not match.",
            MassCalculationStatus.INVALID_RESULT: "Material consumption totals are unavailable because result reconciliation failed.",
        }
        return MassSummaryViewModel(
            result.status,
            messages.get(result.status, "Material consumption totals are unavailable."),
            diagnostics=diagnostics,
        )
    totals = result.totals
    items = [
        SummaryItemViewModel("Consumed Gross Physical Allocation Mass", format_mass(totals.gross_physical_allocation_mass_kg)),
        SummaryItemViewModel("Consumed Gross Commercial Allocation Mass", format_mass(totals.gross_commercial_allocation_mass_kg)),
        SummaryItemViewModel("Placed Rectangular Part Mass Estimate", format_mass(totals.placed_rectangular_part_mass_estimate_kg)),
        SummaryItemViewModel("Unplaced Rectangular Part Mass Estimate", format_mass(totals.unplaced_rectangular_part_mass_estimate_kg)),
        SummaryItemViewModel("Physical Unused Allocation Mass", format_mass(totals.physical_unused_allocation_mass_kg)),
        SummaryItemViewModel("Commercial Allocation Difference", format_mass(totals.commercial_allocation_difference_kg)),
        SummaryItemViewModel("Commercial Material Allowance", format_mass(totals.commercial_material_allowance_kg)),
        SummaryItemViewModel("Consumed Physical Equivalent Sheets", format_equivalent_sheets(totals.physical_equivalent_sheets)),
        SummaryItemViewModel("Consumed Commercial Equivalent Sheets", format_equivalent_sheets(totals.commercial_equivalent_sheets)),
    ]
    if result.per_product is not None:
        items.extend(
            (
                SummaryItemViewModel("Consumed Gross Physical Mass / Product", format_mass(result.per_product.gross_physical_allocation_mass_kg)),
                SummaryItemViewModel("Consumed Gross Commercial Mass / Product", format_mass(result.per_product.gross_commercial_allocation_mass_kg)),
                SummaryItemViewModel("Placed Rectangular Mass / Product", format_mass(result.per_product.rectangular_part_mass_estimate_kg)),
            )
        )
    message = (
        "The nesting result is partial. Completed-product gross mass is unavailable."
        if result.status is MassCalculationStatus.PARTIAL_RESULT
        else "All expanded demand was placed."
    )
    return MassSummaryViewModel(result.status, message, tuple(items), diagnostics)
