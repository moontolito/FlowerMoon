"""Atomic conversion from validated neutral records to Debbie domain objects."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from debbie.domain import (
    DemandItem,
    Dimensions,
    Orientation,
    PartType,
    ProcessProfile,
    StockInstance,
    StockSpecification,
    Trim,
    Work,
)
from debbie.domain.errors import DomainValidationError, InvalidTrimError
from debbie.geometry import effective_placement_region

from .constants import ImportLimits
from .diagnostics import DiagnosticCollector, ImportDiagnostic, ImportDiagnosticCode
from .identifiers import (
    demand_item_id,
    part_type_id,
    stock_instance_id,
    stock_specification_id,
    work_id,
)
from .models import CanonicalWorkbookRecords, ImportSummary


@dataclass(frozen=True, slots=True)
class DomainBuildOutcome:
    works: tuple[Work, ...]
    diagnostics: tuple[ImportDiagnostic, ...]
    summary: ImportSummary | None


def build_domain(
    records: CanonicalWorkbookRecords, limits: ImportLimits
) -> DomainBuildOutcome:
    diagnostics = DiagnosticCollector()
    parts_by_work: dict[str, list] = defaultdict(list)
    stocks_by_work: dict[str, list] = defaultdict(list)
    for part in records.parts:
        parts_by_work[part.work_key].append(part)
    for stock in records.stocks:
        stocks_by_work[stock.work_key].append(stock)

    total_stock_instances = sum(stock.quantity for stock in records.stocks)
    stock_expansion_allowed = total_stock_instances <= limits.max_stock_instances
    if not stock_expansion_allowed:
        diagnostics.error(
            ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
            f"Stock quantity expands to {total_stock_instances} physical sheets; "
            f"the limit is {limits.max_stock_instances}",
        )
    total_demand_instances = sum(
        part.quantity * work.batch_multiplier
        for work in records.works
        for part in parts_by_work[work.work_key]
    )
    if total_demand_instances > limits.max_expanded_demand_instances:
        diagnostics.error(
            ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
            f"Demand expands to {total_demand_instances} physical parts; "
            f"the limit is {limits.max_expanded_demand_instances}",
        )

    prepared: list[tuple] = []
    for work_record in records.works:
        owner = work_id(work_record.work_key)
        try:
            process = ProcessProfile(
                kerf=work_record.kerf,
                minimum_part_clearance=work_record.part_clearance,
                boundary_clearance=work_record.boundary_clearance,
                trim=Trim(
                    left=work_record.trim_left,
                    right=work_record.trim_right,
                    top=work_record.trim_top,
                    bottom=work_record.trim_bottom,
                ),
            )
        except DomainValidationError as error:
            diagnostics.error(
                ImportDiagnosticCode.DOMAIN_VALIDATION_FAILURE,
                f"Work {work_record.work_key!r} process profile is invalid: {error}",
                worksheet=work_record.source.worksheet,
                row=work_record.source.row,
                related_work_key=work_record.work_key,
            )
            continue

        part_types: list[PartType] = []
        demand_items: list[DemandItem] = []
        for part in parts_by_work[work_record.work_key]:
            type_id = part_type_id(owner, part.part_key)
            orientations = (
                frozenset({Orientation.ZERO, Orientation.DEG_90})
                if part.allow_rotation
                else frozenset({Orientation.ZERO})
            )
            try:
                part_types.append(
                    PartType(
                        type_id,
                        part.part_name,
                        Dimensions(part.length, part.width),
                        orientations,
                    )
                )
                demand_items.append(
                    DemandItem(
                        demand_item_id(owner, part.part_key),
                        owner,
                        type_id,
                        part.quantity,
                    )
                )
            except DomainValidationError as error:
                diagnostics.error(
                    ImportDiagnosticCode.DOMAIN_VALIDATION_FAILURE,
                    f"Part {part.part_key!r} failed domain validation: {error}",
                    worksheet=part.source.worksheet,
                    row=part.source.row,
                    related_work_key=part.work_key,
                    related_part_key=part.part_key,
                )

        specifications: list[StockSpecification] = []
        stock_instances: list[StockInstance] = []
        for stock in stocks_by_work[work_record.work_key]:
            specification_id = stock_specification_id(owner, stock.stock_key)
            try:
                specification = StockSpecification(
                    specification_id,
                    stock.stock_name,
                    Dimensions(stock.length, stock.width),
                )
                try:
                    process.trim.usable_dimensions(specification.dimensions)
                except InvalidTrimError as error:
                    diagnostics.error(
                        ImportDiagnosticCode.INVALID_TRIM_FOR_STOCK,
                        f"Trim invalidates stock {stock.stock_key!r}: {error}",
                        worksheet=stock.source.worksheet,
                        row=stock.source.row,
                        related_work_key=stock.work_key,
                        related_stock_key=stock.stock_key,
                    )
                    continue
                try:
                    effective_placement_region(specification, process)
                except DomainValidationError as error:
                    diagnostics.error(
                        ImportDiagnosticCode.INVALID_EFFECTIVE_STOCK_REGION,
                        f"Stock {stock.stock_key!r} has no positive effective region: {error}",
                        worksheet=stock.source.worksheet,
                        row=stock.source.row,
                        related_work_key=stock.work_key,
                        related_stock_key=stock.stock_key,
                    )
                    continue
                specifications.append(specification)
                if stock_expansion_allowed:
                    stock_instances.extend(
                        StockInstance(
                            stock_instance_id(specification_id, sequence),
                            owner,
                            specification_id,
                            sequence,
                        )
                        for sequence in range(1, stock.quantity + 1)
                    )
            except DomainValidationError as error:
                diagnostics.error(
                    ImportDiagnosticCode.DOMAIN_VALIDATION_FAILURE,
                    f"Stock {stock.stock_key!r} failed domain validation: {error}",
                    worksheet=stock.source.worksheet,
                    row=stock.source.row,
                    related_work_key=stock.work_key,
                    related_stock_key=stock.stock_key,
                )
        prepared.append(
            (
                work_record,
                owner,
                process,
                tuple(part_types),
                tuple(demand_items),
                tuple(specifications),
                tuple(stock_instances),
            )
        )

    if diagnostics.has_errors:
        return DomainBuildOutcome((), diagnostics.freeze(), None)

    works: list[Work] = []
    for (
        work_record,
        owner,
        process,
        part_types,
        demand_items,
        specifications,
        stock_instances,
    ) in prepared:
        try:
            works.append(
                Work.from_inputs(
                    id=owner,
                    name=work_record.work_name,
                    batch_multiplier=work_record.batch_multiplier,
                    process_profile=process,
                    part_types=part_types,
                    demand_items=demand_items,
                    stock_specifications=specifications,
                    stock_instances=stock_instances,
                )
            )
        except DomainValidationError as error:
            diagnostics.error(
                ImportDiagnosticCode.DOMAIN_VALIDATION_FAILURE,
                f"Work {work_record.work_key!r} failed aggregate validation: {error}",
                worksheet=work_record.source.worksheet,
                row=work_record.source.row,
                related_work_key=work_record.work_key,
            )
    if diagnostics.has_errors:
        return DomainBuildOutcome((), diagnostics.freeze(), None)

    drawing_numbers = tuple(
        (part.work_key, part.part_key, part.drawing_number)
        for part in records.parts
        if part.drawing_number is not None
    )
    summary = ImportSummary(
        work_count=len(works),
        part_type_count=len(records.parts),
        demand_item_count=len(records.parts),
        stock_specification_count=len(records.stocks),
        stock_instance_count=total_stock_instances,
        drawing_numbers=drawing_numbers,
    )
    return DomainBuildOutcome(tuple(works), diagnostics.freeze(), summary)
