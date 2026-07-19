from __future__ import annotations

import pytest

from debbie.importers.excel import (
    CanonicalExcelImporter,
    ImportDiagnosticCode,
    ImportLimits,
    import_canonical_workbook,
)

from .conftest import DEFAULT_PART, DEFAULT_STOCK_V11, DEFAULT_WORK_V11


def _codes(result):
    return {item.code for item in result.errors}


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (
            [["Key", "Value"], ["Format Name", "Debbie Nesting Workbook"], ["Schema Version", "1.1"], ["Units", "mm"]],
            ImportDiagnosticCode.INVALID_METADATA,
        ),
        (
            [["Key", "Value"], ["Format Name", "Debbie Nesting Workbook"], ["Schema Version", "1.1"], ["Units", "mm"], ["Density Units", "kg/m3"]],
            ImportDiagnosticCode.UNSUPPORTED_DENSITY_UNITS,
        ),
        (
            [["Key", "Value"], ["Format Name", "Wrong"], ["Schema Version", "1.1"], ["Units", "mm"], ["Density Units", "g/cm3"]],
            ImportDiagnosticCode.WORKBOOK_FORMAT_MISMATCH,
        ),
        (
            [["Key", "Value"], ["Format Name", "Debbie Nesting Workbook"], ["Schema Version", "1.1"], ["Schema Version", "1.1"], ["Units", "mm"], ["Density Units", "g/cm3"]],
            ImportDiagnosticCode.DUPLICATE_METADATA_KEY,
        ),
    ],
)
def test_schema_1_1_metadata_validation(workbook_v11_factory, metadata, expected) -> None:
    result = import_canonical_workbook(workbook_v11_factory(metadata=metadata))
    assert not result.success and result.works == ()
    assert expected in _codes(result)


@pytest.mark.parametrize("density_units", ["g/cm³", "kg/dm³"])
def test_density_unit_human_readable_aliases_are_not_canonical(
    workbook_v11_factory, density_units: str
) -> None:
    metadata = [
        ["Key", "Value"],
        ["Format Name", "Debbie Nesting Workbook"],
        ["Schema Version", "1.1"],
        ["Units", "mm"],
        ["Density Units", density_units],
    ]
    result = import_canonical_workbook(workbook_v11_factory(metadata=metadata))
    diagnostic = next(
        item
        for item in result.errors
        if item.code is ImportDiagnosticCode.UNSUPPORTED_DENSITY_UNITS
    )
    assert (
        diagnostic.worksheet,
        diagnostic.row,
        diagnostic.column,
        diagnostic.column_letter,
        diagnostic.header,
    ) == (
        "Debbie", 5, 2, "B", "Value"
    )


def test_unsupported_and_missing_versions_never_fallback(workbook_v11_factory) -> None:
    unsupported = [
        ["Key", "Value"], ["Format Name", "Debbie Nesting Workbook"],
        ["Schema Version", "1.2"], ["Units", "mm"], ["Density Units", "g/cm3"],
    ]
    missing = [
        ["Key", "Value"], ["Format Name", "Debbie Nesting Workbook"],
        ["Units", "mm"], ["Density Units", "g/cm3"],
    ]
    assert ImportDiagnosticCode.UNSUPPORTED_SCHEMA_VERSION in _codes(
        import_canonical_workbook(workbook_v11_factory(metadata=unsupported))
    )
    assert ImportDiagnosticCode.INVALID_METADATA in _codes(
        import_canonical_workbook(workbook_v11_factory(metadata=missing))
    )


def test_schema_version_formula_without_cache_fails_at_dispatch(workbook_v11_factory) -> None:
    def mutate(book):
        book["Debbie"]["B3"] = "=1.1"

    result = import_canonical_workbook(workbook_v11_factory(mutate=mutate))
    assert not result.success
    assert ImportDiagnosticCode.UNSUPPORTED_FORMULA_VALUE in _codes(result)


def test_schema_1_1_metadata_header_formula_without_cache_is_rejected(
    workbook_v11_factory,
) -> None:
    def mutate(book):
        book["Debbie"]["A1"] = '="Key"'

    result = import_canonical_workbook(workbook_v11_factory(mutate=mutate))
    assert not result.success
    assert ImportDiagnosticCode.UNSUPPORTED_FORMULA_VALUE in _codes(result)


@pytest.mark.parametrize(
    ("index", "value", "expected"),
    [
        (2, " ", ImportDiagnosticCode.INVALID_MATERIAL_CATEGORY_KEY),
        (3, " ", ImportDiagnosticCode.INVALID_MATERIAL_CATEGORY_NAME),
        (4, " ", ImportDiagnosticCode.INVALID_MATERIAL_GRADE_KEY),
        (5, " ", ImportDiagnosticCode.INVALID_MATERIAL_GRADE_NAME),
        (6, 0, ImportDiagnosticCode.INVALID_THICKNESS),
        (6, -1, ImportDiagnosticCode.INVALID_THICKNESS),
        (6, "NaN", ImportDiagnosticCode.INVALID_THICKNESS),
        (7, 0, ImportDiagnosticCode.INVALID_DENSITY),
        (7, -1, ImportDiagnosticCode.INVALID_DENSITY),
        (7, "NaN", ImportDiagnosticCode.INVALID_DENSITY),
        (8, "guessed", ImportDiagnosticCode.INVALID_DENSITY_SOURCE),
    ],
)
def test_schema_1_1_material_work_fields_are_strict(
    workbook_v11_factory, index: int, value, expected
) -> None:
    work = [*DEFAULT_WORK_V11]
    work[index] = value
    result = import_canonical_workbook(workbook_v11_factory(works=[work]))
    assert not result.success and expected in _codes(result)
    assert result.records is result.summary is None


def test_schema_1_1_semantic_diagnostics_include_stable_source_keys(
    workbook_v11_factory,
) -> None:
    work = [*DEFAULT_WORK_V11]
    work[7] = 0
    stock = [*DEFAULT_STOCK_V11]
    stock[5] = 1001
    result = import_canonical_workbook(
        workbook_v11_factory(works=[work], stocks=[stock])
    )
    density = next(
        item for item in result.errors if item.code is ImportDiagnosticCode.INVALID_DENSITY
    )
    allocation = next(
        item
        for item in result.errors
        if item.code is ImportDiagnosticCode.ALLOCATED_LENGTH_EXCEEDS_FULL_LENGTH
    )
    assert density.related_work_key == "W-1"
    assert (allocation.related_work_key, allocation.related_stock_key) == ("W-1", "S-1")


@pytest.mark.parametrize(
    ("index", "value", "expected"),
    [
        (3, None, ImportDiagnosticCode.EMPTY_REQUIRED_VALUE),
        (4, None, ImportDiagnosticCode.EMPTY_REQUIRED_VALUE),
        (5, None, ImportDiagnosticCode.EMPTY_REQUIRED_VALUE),
        (6, None, ImportDiagnosticCode.EMPTY_REQUIRED_VALUE),
        (5, 0, ImportDiagnosticCode.NON_POSITIVE_DIMENSION),
        (5, 1001, ImportDiagnosticCode.ALLOCATED_LENGTH_EXCEEDS_FULL_LENGTH),
        (6, 501, ImportDiagnosticCode.ALLOCATED_WIDTH_EXCEEDS_FULL_WIDTH),
        (7, None, ImportDiagnosticCode.EMPTY_REQUIRED_VALUE),
        (7, 0.49, ImportDiagnosticCode.COMMERCIAL_ALLOCATION_BELOW_PHYSICAL),
        (7, 1.01, ImportDiagnosticCode.INVALID_COMMERCIAL_ALLOCATION_FRACTION),
        (7, 0, ImportDiagnosticCode.INVALID_COMMERCIAL_ALLOCATION_FRACTION),
        (7, -1, ImportDiagnosticCode.INVALID_COMMERCIAL_ALLOCATION_FRACTION),
        (7, float("nan"), ImportDiagnosticCode.INVALID_COMMERCIAL_ALLOCATION_FRACTION),
        (7, float("inf"), ImportDiagnosticCode.INVALID_COMMERCIAL_ALLOCATION_FRACTION),
        (7, True, ImportDiagnosticCode.INVALID_COMMERCIAL_ALLOCATION_FRACTION),
    ],
)
def test_schema_1_1_stock_allocation_validation(
    workbook_v11_factory, index: int, value, expected
) -> None:
    stock = [*DEFAULT_STOCK_V11]
    if index == 7 and value == 0.49:
        stock[5] = 500
    stock[index] = value
    result = import_canonical_workbook(workbook_v11_factory(stocks=[stock]))
    assert not result.success and expected in _codes(result)
    assert result.works == ()


@pytest.mark.parametrize("work_index", [12, 13, 14, 15, 16])
def test_partial_allocation_with_boundary_or_any_trim_is_rejected(
    workbook_v11_factory, work_index: int
) -> None:
    work = [*DEFAULT_WORK_V11]
    work[work_index] = 1
    stock = ["W-1", "HALF", "Half", 1000, 500, 500, 500, 1, 1]
    result = import_canonical_workbook(workbook_v11_factory(works=[work], stocks=[stock]))
    assert not result.success
    assert ImportDiagnosticCode.PARTIAL_ALLOCATION_PROCESS_POLICY_UNRESOLVED in _codes(result)


def test_full_allocation_with_trim_remains_supported(workbook_v11_factory) -> None:
    work = [*DEFAULT_WORK_V11]
    work[12:17] = [2, 3, 4, 5, 6]
    assert import_canonical_workbook(workbook_v11_factory(works=[work])).success


def test_partial_allocation_does_not_reject_kerf_or_part_clearance(
    workbook_v11_factory,
) -> None:
    work = [*DEFAULT_WORK_V11]
    work[10:12] = [1, 2]
    stock = ["W-1", "HALF", "Half", 1000, 500, 500, 500, 1, 1]
    assert import_canonical_workbook(
        workbook_v11_factory(works=[work], stocks=[stock])
    ).success


@pytest.mark.parametrize("value", [50, "50%"])
def test_commercial_allocation_requires_a_fraction_not_percent_notation(
    workbook_v11_factory, value
) -> None:
    stock = [*DEFAULT_STOCK_V11]
    stock[7] = value
    result = import_canonical_workbook(workbook_v11_factory(stocks=[stock]))
    assert not result.success
    assert ImportDiagnosticCode.INVALID_COMMERCIAL_ALLOCATION_FRACTION in _codes(result)


def test_commercial_allocation_infinitesimally_below_physical_is_rejected(
    workbook_v11_factory,
) -> None:
    stock = ["W-1", "HALF", "Half", 1000, 500, 500, 500, 0.5 - 1e-15, 1]
    result = import_canonical_workbook(workbook_v11_factory(stocks=[stock]))
    assert ImportDiagnosticCode.COMMERCIAL_ALLOCATION_BELOW_PHYSICAL in _codes(result)


@pytest.mark.parametrize(
    ("sheet", "header"),
    [
        ("Works", "Thickness (mm)"),
        ("Works", "Density (g/cm3)"),
        ("Works", "Density Source"),
        ("Stocks", "Allocated Length (mm)"),
        ("Stocks", "Commercial Allocation Fraction"),
    ],
)
def test_new_required_formula_without_cache_is_rejected(
    workbook_v11_factory, sheet: str, header: str
) -> None:
    def mutate(book):
        worksheet = book[sheet]
        column = next(cell.column for cell in worksheet[1] if cell.value == header)
        worksheet.cell(2, column).value = "=1"

    result = import_canonical_workbook(workbook_v11_factory(mutate=mutate))
    assert not result.success
    assert ImportDiagnosticCode.UNSUPPORTED_FORMULA_VALUE in _codes(result)


def test_schema_headers_do_not_alias_or_fallback(
    workbook_factory, workbook_v11_factory
) -> None:
    def declare_v11(book):
        book["Debbie"]["B3"] = "1.1"
        book["Debbie"].append(["Density Units", "g/cm3"])

    wrong_v11 = import_canonical_workbook(workbook_factory(mutate=declare_v11))
    assert not wrong_v11.success
    assert ImportDiagnosticCode.MISSING_REQUIRED_HEADER in _codes(wrong_v11)

    def declare_v10(book):
        book["Debbie"]["B3"] = "1.0"

    wrong_v10 = import_canonical_workbook(workbook_v11_factory(mutate=declare_v10))
    assert not wrong_v10.success
    assert ImportDiagnosticCode.MISSING_REQUIRED_HEADER in _codes(wrong_v10)


def test_unknown_extra_columns_remain_informational(workbook_v11_factory) -> None:
    def mutate(book):
        book["Works"]["S1"] = "Customer Note"
        book["Works"]["S2"] = "ignored"

    result = import_canonical_workbook(workbook_v11_factory(mutate=mutate))
    assert result.success
    assert ImportDiagnosticCode.UNKNOWN_COLUMN in {item.code for item in result.information}


def test_duplicate_normalized_header_fails(workbook_v11_factory) -> None:
    def mutate(book):
        book["Stocks"]["J1"] = " allocated   length (MM) "

    result = import_canonical_workbook(workbook_v11_factory(mutate=mutate))
    assert not result.success
    assert ImportDiagnosticCode.DUPLICATE_HEADER in _codes(result)


def test_one_invalid_work_or_allocation_makes_multi_work_import_atomic(
    workbook_v11_factory,
) -> None:
    second_work = [*DEFAULT_WORK_V11]
    second_work[0:2] = ["W-2", "Second"]
    second_work[7] = -1
    parts = [DEFAULT_PART, ["W-2", "P-2", "Other", 10, 10, 1, "No", None]]
    stocks = [DEFAULT_STOCK_V11, ["W-2", "S-2", "Other", 100, 100, 100, 100, 1, 1]]
    result = import_canonical_workbook(
        workbook_v11_factory(works=[DEFAULT_WORK_V11, second_work], parts=parts, stocks=stocks)
    )
    assert not result.success
    assert result.works == () and result.records is result.summary is None


def test_errors_from_multiple_rows_are_discoverable(workbook_v11_factory) -> None:
    bad_work = [*DEFAULT_WORK_V11]
    bad_work[6] = 0
    bad_stock = [*DEFAULT_STOCK_V11]
    bad_stock[5] = 2000
    result = import_canonical_workbook(
        workbook_v11_factory(works=[bad_work], stocks=[bad_stock])
    )
    assert not result.success
    assert ImportDiagnosticCode.INVALID_THICKNESS in _codes(result)
    assert ImportDiagnosticCode.ALLOCATED_LENGTH_EXCEEDS_FULL_LENGTH in _codes(result)


def test_schema_1_1_stock_expansion_limit_is_enforced(workbook_v11_factory) -> None:
    stock = [*DEFAULT_STOCK_V11]
    stock[8] = 3
    result = import_canonical_workbook(
        workbook_v11_factory(stocks=[stock]),
        limits=ImportLimits(max_stock_instances=2),
    )
    assert not result.success
    assert ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED in _codes(result)


def test_schema_1_1_demand_expansion_limit_is_enforced(workbook_v11_factory) -> None:
    work = [*DEFAULT_WORK_V11]
    work[9] = 3
    part = [*DEFAULT_PART]
    part[5] = 2
    result = import_canonical_workbook(
        workbook_v11_factory(works=[work], parts=[part]),
        limits=ImportLimits(max_expanded_demand_instances=5),
    )
    assert not result.success
    assert ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED in _codes(result)


def test_work_part_and_stock_keys_remain_case_sensitive(workbook_v11_factory) -> None:
    lower_work = [*DEFAULT_WORK_V11]
    lower_work[0:2] = ["w-1", "Lower"]
    parts = [DEFAULT_PART, ["w-1", "P-1", "Other", 10, 10, 1, "No", None]]
    stocks = [DEFAULT_STOCK_V11, ["w-1", "S-1", "Other", 100, 100, 100, 100, 1, 1]]
    result = import_canonical_workbook(
        workbook_v11_factory(
            works=[DEFAULT_WORK_V11, lower_work], parts=parts, stocks=stocks
        )
    )
    assert result.success and len(result.works) == 2


@pytest.mark.parametrize("value", ["1,5", "1 000", "3 mm", True, float("inf")])
def test_new_numeric_fields_reuse_strict_locale_independent_parser(
    workbook_v11_factory, value
) -> None:
    work = [*DEFAULT_WORK_V11]
    work[6] = value
    result = import_canonical_workbook(workbook_v11_factory(works=[work]))
    assert not result.success
    assert ImportDiagnosticCode.INVALID_THICKNESS in _codes(result)
