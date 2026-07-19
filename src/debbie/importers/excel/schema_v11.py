"""Strict parser and domain builder for canonical Excel schema 1.1."""

from __future__ import annotations

from collections import defaultdict
from debbie.domain import (
    DemandItem,
    Density,
    DensitySource,
    Dimensions,
    MaterialCategoryKey,
    MaterialGradeKey,
    MaterialIdentity,
    Orientation,
    PartType,
    ProcessProfile,
    StockAllocation,
    StockInstance,
    StockSpecification,
    Thickness,
    Trim,
    Work,
)
from debbie.domain.errors import DomainValidationError, InvalidTrimError
from debbie.domain.material import (
    MAX_MATERIAL_DESCRIPTION_LENGTH,
    MAX_MATERIAL_KEY_LENGTH,
    MAX_MATERIAL_NAME_LENGTH,
)
from debbie.geometry import effective_placement_region

from .constants import (
    ADAPTER_ID_V11,
    DENSITY_UNIT_SYSTEM,
    FORMAT_NAME,
    KNOWN_METADATA_V11,
    METADATA_HEADERS,
    OPTIONAL_PART_HEADERS,
    OPTIONAL_WORK_HEADERS_V11,
    PART_HEADERS,
    REQUIRED_METADATA_V11,
    SCHEMA_VERSION_V11,
    STOCK_HEADERS_V11,
    UNIT_SYSTEM,
    WORK_HEADERS_V11,
    ImportLimits,
)
from .diagnostics import DiagnosticCollector, ImportDiagnostic, ImportDiagnosticCode
from .domain_builder import DomainBuildOutcome
from .identifiers import (
    demand_item_id,
    part_type_id,
    stock_instance_id,
    stock_specification_id,
    work_id_v11,
)
from .models import (
    CanonicalWorkbookV11Records,
    ImportSummaryV11,
    MaterialImportSummary,
    PartImportRecord,
    SourceLocation,
    StockAllocationImportSummary,
    StockImportRecordV11,
    WorkbookMetadataRecordV11,
    WorkImportRecordV11,
)
from .parser import (
    ParseOutcome,
    _formula_without_cache,
    _header_map,
    _location,
    _merged_table_diagnostics,
    _non_negative_number,
    _number_value,
    _optional_text,
    _parse_rows,
    _positive_integer,
    _positive_number,
    _required_sheet_map,
    _required_text,
    _rotation,
    normalize_header,
    normalize_metadata_key,
)
from .reader import CellSnapshot, SheetSnapshot, WorkbookSnapshot


def _semantic_required_text(
    cell: CellSnapshot,
    sheet: SheetSnapshot,
    header: str,
    diagnostics: DiagnosticCollector,
    limits: ImportLimits,
    *,
    code: ImportDiagnosticCode,
    maximum: int,
    related_work_key: str | None = None,
) -> str | None:
    value = _required_text(cell, sheet, header, diagnostics, limits)
    if value is None:
        diagnostics.error(
            code,
            f"{header} is invalid",
            **_location(cell, sheet, header),
            related_work_key=related_work_key,
        )
        return None
    if len(value) > maximum:
        diagnostics.error(
            code,
            f"{header} must not exceed {maximum} characters",
            **_location(cell, sheet, header),
            related_work_key=related_work_key,
        )
        return None
    return value


def _semantic_positive_number(
    cell: CellSnapshot,
    sheet: SheetSnapshot,
    header: str,
    diagnostics: DiagnosticCollector,
    *,
    code: ImportDiagnosticCode,
    related_work_key: str | None = None,
    related_stock_key: str | None = None,
) -> float | None:
    value = _number_value(cell, sheet, header, diagnostics)
    if value is None:
        diagnostics.error(
            code,
            f"{header} is invalid",
            **_location(cell, sheet, header),
            related_work_key=related_work_key,
            related_stock_key=related_stock_key,
        )
        return None
    if value <= 0.0:
        diagnostics.error(
            code,
            f"{header} must be finite and greater than zero",
            **_location(cell, sheet, header),
            related_work_key=related_work_key,
            related_stock_key=related_stock_key,
        )
        return None
    return value


def _density_source(
    cell: CellSnapshot,
    sheet: SheetSnapshot,
    diagnostics: DiagnosticCollector,
    limits: ImportLimits,
    related_work_key: str | None,
) -> str | None:
    value = _required_text(cell, sheet, "Density Source", diagnostics, limits)
    if value is None:
        diagnostics.error(
            ImportDiagnosticCode.INVALID_DENSITY_SOURCE,
            "Density Source is invalid",
            **_location(cell, sheet, "Density Source"),
            related_work_key=related_work_key,
        )
        return None
    normalized = value.casefold()
    allowed = {item.value: item.value for item in DensitySource}
    if normalized not in allowed:
        diagnostics.error(
            ImportDiagnosticCode.INVALID_DENSITY_SOURCE,
            "Density Source accepts only library_default or explicit_override",
            **_location(cell, sheet, "Density Source"),
            related_work_key=related_work_key,
        )
        return None
    return allowed[normalized]


def _metadata_v11(
    sheet: SheetSnapshot,
    diagnostics: DiagnosticCollector,
    limits: ImportLimits,
) -> WorkbookMetadataRecordV11:
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

    values: dict[str, tuple[str, str, CellSnapshot]] = {}
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
        values[normalized] = (key, value, value_cell)

    for required in REQUIRED_METADATA_V11:
        if normalize_metadata_key(required) not in values:
            diagnostics.error(
                ImportDiagnosticCode.INVALID_METADATA,
                f"Required metadata key {required!r} is missing",
                worksheet=sheet.title,
                header="Key",
            )
    known = {normalize_metadata_key(item) for item in KNOWN_METADATA_V11}
    extras: list[tuple[str, str]] = []
    for normalized, (key, value, _value_cell) in values.items():
        if normalized not in known:
            diagnostics.info(
                ImportDiagnosticCode.UNKNOWN_METADATA_KEY,
                f"Unknown metadata key {key!r} was preserved as provenance",
                worksheet=sheet.title,
            )
            extras.append((key, value))

    def value_for(key: str) -> str | None:
        item = values.get(normalize_metadata_key(key))
        return item[1] if item else None

    def value_location(key: str) -> dict[str, object]:
        item = values[normalize_metadata_key(key)]
        return _location(item[2], sheet, "Value")

    format_name = value_for("Format Name")
    version = value_for("Schema Version")
    units = value_for("Units")
    density_units = value_for("Density Units")
    if format_name is not None and format_name != FORMAT_NAME:
        diagnostics.error(
            ImportDiagnosticCode.WORKBOOK_FORMAT_MISMATCH,
            f"Format Name must be {FORMAT_NAME!r}",
            **value_location("Format Name"),
        )
    if version is not None and version != SCHEMA_VERSION_V11:
        diagnostics.error(
            ImportDiagnosticCode.UNSUPPORTED_SCHEMA_VERSION,
            f"Schema Version {version!r} is unsupported",
            **value_location("Schema Version"),
        )
    if units is not None and units != UNIT_SYSTEM:
        diagnostics.error(
            ImportDiagnosticCode.UNSUPPORTED_UNITS,
            f"Units must be {UNIT_SYSTEM!r}",
            **value_location("Units"),
        )
    if density_units is not None and density_units != DENSITY_UNIT_SYSTEM:
        diagnostics.error(
            ImportDiagnosticCode.UNSUPPORTED_DENSITY_UNITS,
            f"Density Units must be {DENSITY_UNIT_SYSTEM!r}",
            **value_location("Density Units"),
        )
    optional_extras = [
        (canonical, values[normalize_metadata_key(canonical)][1])
        for canonical in ("Application Version", "Description")
        if normalize_metadata_key(canonical) in values
    ]
    return WorkbookMetadataRecordV11(
        format_name,
        version,
        units,
        density_units,
        tuple(sorted((*optional_extras, *extras), key=lambda item: item[0].casefold())),
    )


def parse_workbook_v11(workbook: WorkbookSnapshot, limits: ImportLimits) -> ParseOutcome:
    diagnostics = DiagnosticCollector()
    sheets = _required_sheet_map(workbook, diagnostics)
    metadata = WorkbookMetadataRecordV11(None, None, None, None)
    if "Debbie" in sheets:
        metadata = _metadata_v11(sheets["Debbie"], diagnostics, limits)

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

    works: list[WorkImportRecordV11] = []
    parts: list[PartImportRecord] = []
    stocks: list[StockImportRecordV11] = []
    work_candidates: list[tuple[str, SourceLocation]] = []
    part_candidates: list[tuple[str, str | None, SourceLocation]] = []
    stock_candidates: list[tuple[str, str | None, SourceLocation]] = []

    if "Works" in sheets:
        sheet = sheets["Works"]
        _merged_table_diagnostics(sheet, diagnostics)
        headers = _header_map(
            sheet, WORK_HEADERS_V11, OPTIONAL_WORK_HEADERS_V11, diagnostics
        )

        def parse_work(sheet: SheetSnapshot, row: int, headers: dict[str, int]):
            if any(header not in headers for header in WORK_HEADERS_V11):
                return None
            before = len(diagnostics.freeze())
            cell = lambda header: sheet.cell(row, headers[header])
            work_key = _required_text(cell("Work Key"), sheet, "Work Key", diagnostics, limits)
            values = (
                work_key,
                _required_text(cell("Work Name"), sheet, "Work Name", diagnostics, limits),
                _semantic_required_text(
                    cell("Material Category Key"), sheet, "Material Category Key", diagnostics,
                    limits, code=ImportDiagnosticCode.INVALID_MATERIAL_CATEGORY_KEY,
                    maximum=MAX_MATERIAL_KEY_LENGTH, related_work_key=work_key,
                ),
                _semantic_required_text(
                    cell("Material Category Name"), sheet, "Material Category Name", diagnostics,
                    limits, code=ImportDiagnosticCode.INVALID_MATERIAL_CATEGORY_NAME,
                    maximum=MAX_MATERIAL_NAME_LENGTH, related_work_key=work_key,
                ),
                _semantic_required_text(
                    cell("Material Grade Key"), sheet, "Material Grade Key", diagnostics,
                    limits, code=ImportDiagnosticCode.INVALID_MATERIAL_GRADE_KEY,
                    maximum=MAX_MATERIAL_KEY_LENGTH, related_work_key=work_key,
                ),
                _semantic_required_text(
                    cell("Material Grade Name"), sheet, "Material Grade Name", diagnostics,
                    limits, code=ImportDiagnosticCode.INVALID_MATERIAL_GRADE_NAME,
                    maximum=MAX_MATERIAL_NAME_LENGTH, related_work_key=work_key,
                ),
                _semantic_positive_number(
                    cell("Thickness (mm)"), sheet, "Thickness (mm)", diagnostics,
                    code=ImportDiagnosticCode.INVALID_THICKNESS,
                    related_work_key=work_key,
                ),
                _semantic_positive_number(
                    cell("Density (g/cm3)"), sheet, "Density (g/cm3)", diagnostics,
                    code=ImportDiagnosticCode.INVALID_DENSITY,
                    related_work_key=work_key,
                ),
                _density_source(
                    cell("Density Source"), sheet, diagnostics, limits, work_key
                ),
                (
                    _optional_text(
                        cell("Material Description"), sheet, "Material Description", diagnostics, limits
                    )
                    if "Material Description" in headers else None
                ),
                _positive_integer(
                    cell("Batch Multiplier"), sheet, "Batch Multiplier", diagnostics, limits
                ),
                _non_negative_number(cell("Kerf (mm)"), sheet, "Kerf (mm)", diagnostics),
                _non_negative_number(
                    cell("Part Clearance (mm)"), sheet, "Part Clearance (mm)", diagnostics
                ),
                _non_negative_number(
                    cell("Boundary Clearance (mm)"), sheet,
                    "Boundary Clearance (mm)", diagnostics,
                ),
                _non_negative_number(
                    cell("Trim Left (mm)"), sheet, "Trim Left (mm)", diagnostics
                ),
                _non_negative_number(
                    cell("Trim Right (mm)"), sheet, "Trim Right (mm)", diagnostics
                ),
                _non_negative_number(
                    cell("Trim Top (mm)"), sheet, "Trim Top (mm)", diagnostics
                ),
                _non_negative_number(
                    cell("Trim Bottom (mm)"), sheet, "Trim Bottom (mm)", diagnostics
                ),
            )
            if work_key is not None:
                work_candidates.append((work_key, SourceLocation(sheet.title, row)))
            description = values[9]
            if description is not None and len(description) > MAX_MATERIAL_DESCRIPTION_LENGTH:
                diagnostics.error(
                    ImportDiagnosticCode.INVALID_TEXT_VALUE,
                    f"Material Description must not exceed {MAX_MATERIAL_DESCRIPTION_LENGTH} characters",
                    **_location(cell("Material Description"), sheet, "Material Description"),
                )
            required_values = (*values[:9], *values[10:])
            if len(diagnostics.freeze()) != before or any(v is None for v in required_values):
                return None
            return WorkImportRecordV11(*values, SourceLocation(sheet.title, row))

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
                if "Drawing Number" in headers else None
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
                part_candidates.append((values[0], values[1], SourceLocation(sheet.title, row)))
            if len(diagnostics.freeze()) != before or any(value is None for value in values):
                return None
            return PartImportRecord(*values, drawing, SourceLocation(sheet.title, row))

        parts = _parse_rows(sheet, headers, parse_part)

    if "Stocks" in sheets:
        sheet = sheets["Stocks"]
        _merged_table_diagnostics(sheet, diagnostics)
        headers = _header_map(sheet, STOCK_HEADERS_V11, (), diagnostics)

        def parse_stock(sheet: SheetSnapshot, row: int, headers: dict[str, int]):
            if any(header not in headers for header in STOCK_HEADERS_V11):
                return None
            before = len(diagnostics.freeze())
            cell = lambda header: sheet.cell(row, headers[header])
            work_key = _required_text(
                cell("Work Key"), sheet, "Work Key", diagnostics, limits
            )
            stock_key = _required_text(
                cell("Stock Key"), sheet, "Stock Key", diagnostics, limits
            )
            values = (
                work_key,
                stock_key,
                _required_text(cell("Stock Name"), sheet, "Stock Name", diagnostics, limits),
                _positive_number(
                    cell("Full Length (mm)"), sheet, "Full Length (mm)", diagnostics
                ),
                _positive_number(
                    cell("Full Width (mm)"), sheet, "Full Width (mm)", diagnostics
                ),
                _positive_number(
                    cell("Allocated Length (mm)"), sheet, "Allocated Length (mm)", diagnostics
                ),
                _positive_number(
                    cell("Allocated Width (mm)"), sheet, "Allocated Width (mm)", diagnostics
                ),
                _semantic_positive_number(
                    cell("Commercial Allocation Fraction"), sheet,
                    "Commercial Allocation Fraction", diagnostics,
                    code=ImportDiagnosticCode.INVALID_COMMERCIAL_ALLOCATION_FRACTION,
                    related_work_key=work_key,
                    related_stock_key=stock_key,
                ),
                _positive_integer(cell("Quantity"), sheet, "Quantity", diagnostics, limits),
            )
            if values[0] is not None:
                stock_candidates.append((values[0], values[1], SourceLocation(sheet.title, row)))
            full_l, full_w, allocated_l, allocated_w, commercial = values[3:8]
            if full_l is not None and allocated_l is not None and allocated_l > full_l:
                diagnostics.error(
                    ImportDiagnosticCode.ALLOCATED_LENGTH_EXCEEDS_FULL_LENGTH,
                    "Allocated Length (mm) must not exceed Full Length (mm)",
                    **_location(cell("Allocated Length (mm)"), sheet, "Allocated Length (mm)"),
                    related_work_key=work_key,
                    related_stock_key=stock_key,
                )
            if full_w is not None and allocated_w is not None and allocated_w > full_w:
                diagnostics.error(
                    ImportDiagnosticCode.ALLOCATED_WIDTH_EXCEEDS_FULL_WIDTH,
                    "Allocated Width (mm) must not exceed Full Width (mm)",
                    **_location(cell("Allocated Width (mm)"), sheet, "Allocated Width (mm)"),
                    related_work_key=work_key,
                    related_stock_key=stock_key,
                )
            if commercial is not None and commercial > 1.0:
                diagnostics.error(
                    ImportDiagnosticCode.INVALID_COMMERCIAL_ALLOCATION_FRACTION,
                    "Commercial Allocation Fraction must not exceed one",
                    **_location(
                        cell("Commercial Allocation Fraction"), sheet,
                        "Commercial Allocation Fraction",
                    ),
                    related_work_key=work_key,
                    related_stock_key=stock_key,
                )
            if all(value is not None for value in (full_l, full_w, allocated_l, allocated_w, commercial)):
                physical = (allocated_l / full_l) * (allocated_w / full_w)
                if commercial < physical:
                    diagnostics.error(
                        ImportDiagnosticCode.COMMERCIAL_ALLOCATION_BELOW_PHYSICAL,
                        "Commercial Allocation Fraction must not be below physical allocation",
                        **_location(
                            cell("Commercial Allocation Fraction"), sheet,
                            "Commercial Allocation Fraction",
                        ),
                        related_work_key=work_key,
                        related_stock_key=stock_key,
                    )
            if len(diagnostics.freeze()) != before or any(value is None for value in values):
                return None
            return StockImportRecordV11(*values, SourceLocation(sheet.title, row))

        stocks = _parse_rows(sheet, headers, parse_stock)

    seen_work_keys: set[str] = set()
    for work_key, source in work_candidates:
        if work_key in seen_work_keys:
            diagnostics.error(
                ImportDiagnosticCode.DUPLICATE_WORK_KEY,
                f"Duplicate Work Key {work_key!r}", worksheet=source.worksheet,
                row=source.row, related_work_key=work_key,
            )
        seen_work_keys.add(work_key)
    valid_work_keys = {record.work_key for record in works}

    seen_parts: set[tuple[str, str]] = set()
    for work_key, part_key, source in part_candidates:
        if work_key not in valid_work_keys:
            diagnostics.error(
                ImportDiagnosticCode.UNKNOWN_WORK_REFERENCE,
                f"Part references unknown Work Key {work_key!r}",
                worksheet=source.worksheet, row=source.row,
                related_work_key=work_key, related_part_key=part_key,
            )
        if part_key is not None:
            identity = (work_key, part_key)
            if identity in seen_parts:
                diagnostics.error(
                    ImportDiagnosticCode.DUPLICATE_PART_KEY,
                    f"Duplicate Part Key {part_key!r} in work {work_key!r}",
                    worksheet=source.worksheet, row=source.row,
                    related_work_key=work_key, related_part_key=part_key,
                )
            seen_parts.add(identity)

    seen_stocks: set[tuple[str, str]] = set()
    for work_key, stock_key, source in stock_candidates:
        if work_key not in valid_work_keys:
            diagnostics.error(
                ImportDiagnosticCode.UNKNOWN_WORK_REFERENCE,
                f"Stock references unknown Work Key {work_key!r}",
                worksheet=source.worksheet, row=source.row,
                related_work_key=work_key, related_stock_key=stock_key,
            )
        if stock_key is not None:
            identity = (work_key, stock_key)
            if identity in seen_stocks:
                diagnostics.error(
                    ImportDiagnosticCode.DUPLICATE_STOCK_KEY,
                    f"Duplicate Stock Key {stock_key!r} in work {work_key!r}",
                    worksheet=source.worksheet, row=source.row,
                    related_work_key=work_key, related_stock_key=stock_key,
                )
            seen_stocks.add(identity)

    works_by_key = {record.work_key: record for record in works}
    for stock in stocks:
        work = works_by_key.get(stock.work_key)
        if work is None:
            continue
        partial = (
            stock.allocated_length < stock.full_length
            or stock.allocated_width < stock.full_width
        )
        nonzero_process_boundary = any(
            (
                work.boundary_clearance,
                work.trim_left,
                work.trim_right,
                work.trim_top,
                work.trim_bottom,
            )
        )
        if partial and nonzero_process_boundary:
            diagnostics.error(
                ImportDiagnosticCode.PARTIAL_ALLOCATION_PROCESS_POLICY_UNRESOLVED,
                "Partial allocation with trim or boundary clearance is not approved",
                worksheet=stock.source.worksheet,
                row=stock.source.row,
                related_work_key=stock.work_key,
                related_stock_key=stock.stock_key,
            )

    records = CanonicalWorkbookV11Records(
        metadata,
        tuple(sorted(works, key=lambda item: item.work_key)),
        tuple(sorted(parts, key=lambda item: (item.work_key, item.part_key))),
        tuple(sorted(stocks, key=lambda item: (item.work_key, item.stock_key))),
    )
    return ParseOutcome(
        records, diagnostics.freeze(), metadata.format_name,
        metadata.schema_version, metadata.units,
    )


def build_domain_v11(
    records: CanonicalWorkbookV11Records, limits: ImportLimits
) -> DomainBuildOutcome:
    diagnostics = DiagnosticCollector()
    parts_by_work: dict[str, list[PartImportRecord]] = defaultdict(list)
    stocks_by_work: dict[str, list[StockImportRecordV11]] = defaultdict(list)
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
        owner = work_id_v11(work_record.work_key)
        try:
            material = MaterialIdentity(
                MaterialCategoryKey(work_record.material_category_key),
                work_record.material_category_name,
                MaterialGradeKey(work_record.material_grade_key),
                work_record.material_grade_name,
                Density(work_record.density_g_per_cm3),
                DensitySource(work_record.density_source),
                work_record.material_description,
            )
            thickness = Thickness(work_record.thickness_mm)
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
        except (DomainValidationError, ValueError) as error:
            diagnostics.error(
                ImportDiagnosticCode.CLASSIFIED_WORK_DOMAIN_FAILURE,
                f"Work {work_record.work_key!r} classification is invalid: {error}",
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
                if part.allow_rotation else frozenset({Orientation.ZERO})
            )
            try:
                part_types.append(
                    PartType(type_id, part.part_name, Dimensions(part.length, part.width), orientations)
                )
                demand_items.append(
                    DemandItem(
                        demand_item_id(owner, part.part_key), owner, type_id, part.quantity
                    )
                )
            except DomainValidationError as error:
                diagnostics.error(
                    ImportDiagnosticCode.DOMAIN_VALIDATION_FAILURE,
                    f"Part {part.part_key!r} failed domain validation: {error}",
                    worksheet=part.source.worksheet, row=part.source.row,
                    related_work_key=part.work_key, related_part_key=part.part_key,
                )

        specifications: list[StockSpecification] = []
        instances: list[StockInstance] = []
        for stock in stocks_by_work[work_record.work_key]:
            specification_id = stock_specification_id(owner, stock.stock_key)
            try:
                full = Dimensions(stock.full_length, stock.full_width)
                allocated = Dimensions(stock.allocated_length, stock.allocated_width)
                allocation = StockAllocation(
                    full, allocated, stock.commercial_allocation_fraction
                )
                specification = StockSpecification(
                    specification_id, stock.stock_name, allocated, allocation
                )
                try:
                    process.trim.usable_dimensions(specification.dimensions)
                except InvalidTrimError as error:
                    diagnostics.error(
                        ImportDiagnosticCode.INVALID_TRIM_FOR_STOCK,
                        f"Trim invalidates stock {stock.stock_key!r}: {error}",
                        worksheet=stock.source.worksheet, row=stock.source.row,
                        related_work_key=stock.work_key, related_stock_key=stock.stock_key,
                    )
                    continue
                try:
                    effective_placement_region(specification, process)
                except DomainValidationError as error:
                    diagnostics.error(
                        ImportDiagnosticCode.INVALID_EFFECTIVE_STOCK_REGION,
                        f"Stock {stock.stock_key!r} has no positive effective region: {error}",
                        worksheet=stock.source.worksheet, row=stock.source.row,
                        related_work_key=stock.work_key, related_stock_key=stock.stock_key,
                    )
                    continue
                specifications.append(specification)
                if stock_expansion_allowed:
                    instances.extend(
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
                    worksheet=stock.source.worksheet, row=stock.source.row,
                    related_work_key=stock.work_key, related_stock_key=stock.stock_key,
                )
        prepared.append(
            (
                work_record, owner, material, thickness, process,
                tuple(part_types), tuple(demand_items), tuple(specifications), tuple(instances),
            )
        )

    if diagnostics.has_errors:
        return DomainBuildOutcome((), diagnostics.freeze(), None)

    works: list[Work] = []
    for (
        work_record, owner, material, thickness, process,
        part_types, demand_items, specifications, instances,
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
                    stock_instances=instances,
                    material=material,
                    thickness=thickness,
                )
            )
        except DomainValidationError as error:
            diagnostics.error(
                ImportDiagnosticCode.CLASSIFIED_WORK_DOMAIN_FAILURE,
                f"Work {work_record.work_key!r} failed aggregate validation: {error}",
                worksheet=work_record.source.worksheet, row=work_record.source.row,
                related_work_key=work_record.work_key,
            )
    if diagnostics.has_errors:
        return DomainBuildOutcome((), diagnostics.freeze(), None)

    drawing_numbers = tuple(
        (part.work_key, part.part_key, part.drawing_number)
        for part in records.parts if part.drawing_number is not None
    )
    materials = tuple(
        MaterialImportSummary(
            work.work_key,
            work.material_category_key,
            work.material_category_name,
            work.material_grade_key,
            work.material_grade_name,
            work.thickness_mm,
            work.density_g_per_cm3,
            work.density_source,
            work.material_description,
        )
        for work in records.works
    )
    allocations = tuple(
        StockAllocationImportSummary(
            stock.work_key,
            stock.stock_key,
            stock.full_length,
            stock.full_width,
            stock.allocated_length,
            stock.allocated_width,
            (stock.allocated_length / stock.full_length)
            * (stock.allocated_width / stock.full_width),
            stock.commercial_allocation_fraction,
        )
        for stock in records.stocks
    )
    summary = ImportSummaryV11(
        work_count=len(works),
        part_type_count=len(records.parts),
        demand_item_count=len(records.parts),
        stock_specification_count=len(records.stocks),
        stock_instance_count=total_stock_instances,
        drawing_numbers=drawing_numbers,
        materials=materials,
        stock_allocations=allocations,
        schema_version=SCHEMA_VERSION_V11,
        adapter_id=ADAPTER_ID_V11,
        work_keys=tuple(work.work_key for work in records.works),
        density_units=records.metadata.density_units,
    )
    return DomainBuildOutcome(tuple(works), diagnostics.freeze(), summary)
