from __future__ import annotations

import pytest

from debbie.importers.excel import ImportDiagnosticCode, ImportSeverity, import_canonical_workbook

from .conftest import DEFAULT_PART, DEFAULT_STOCK, DEFAULT_WORK


def _codes(result):
    return {item.code for item in result.errors}


def _assert_error(result, code: ImportDiagnosticCode) -> None:
    assert not result.success
    assert result.works == ()
    diagnostic = next(item for item in result.errors if item.code is code)
    assert diagnostic.severity is ImportSeverity.ERROR


def test_missing_debbie_sheet_is_format_mismatch(workbook_factory) -> None:
    path = workbook_factory(mutate=lambda book: book.remove(book["Debbie"]))
    _assert_error(import_canonical_workbook(path), ImportDiagnosticCode.WORKBOOK_FORMAT_MISMATCH)


@pytest.mark.parametrize(
    ("row", "code"),
    [
        (["Format Name", "Not Debbie"], ImportDiagnosticCode.WORKBOOK_FORMAT_MISMATCH),
        (["Schema Version", "2.0"], ImportDiagnosticCode.UNSUPPORTED_SCHEMA_VERSION),
        (["Units", "in"], ImportDiagnosticCode.UNSUPPORTED_UNITS),
    ],
)
def test_invalid_required_metadata_value_fails(workbook_factory, row, code) -> None:
    metadata = [
        ["Key", "Value"],
        ["Format Name", "Debbie Nesting Workbook"],
        ["Schema Version", "1.0"],
        ["Units", "mm"],
    ]
    metadata[{"Format Name": 1, "Schema Version": 2, "Units": 3}[row[0]]] = row
    _assert_error(import_canonical_workbook(workbook_factory(metadata=metadata)), code)


def test_missing_metadata_header_fails(workbook_factory) -> None:
    metadata = [["Wrong", "Value"], ["Format Name", "Debbie Nesting Workbook"]]
    _assert_error(
        import_canonical_workbook(workbook_factory(metadata=metadata)),
        ImportDiagnosticCode.MISSING_REQUIRED_HEADER,
    )


def test_duplicate_metadata_key_is_case_insensitive(workbook_factory) -> None:
    metadata = [
        ["Key", "Value"],
        ["Format Name", "Debbie Nesting Workbook"],
        [" format   name ", "Debbie Nesting Workbook"],
        ["Schema Version", "1.0"],
        ["Units", "mm"],
    ]
    _assert_error(
        import_canonical_workbook(workbook_factory(metadata=metadata)),
        ImportDiagnosticCode.DUPLICATE_METADATA_KEY,
    )


@pytest.mark.parametrize("sheet_name", ["Works", "Parts", "Stocks"])
def test_IMPORT_001_rejects_missing_required_sheet(workbook_factory, sheet_name) -> None:
    path = workbook_factory(mutate=lambda book: book.remove(book[sheet_name]))
    _assert_error(import_canonical_workbook(path), ImportDiagnosticCode.MISSING_REQUIRED_SHEET)


def test_duplicate_trimmed_required_sheet_name_fails(workbook_factory) -> None:
    path = workbook_factory(mutate=lambda book: book.create_sheet(" Works "))
    _assert_error(import_canonical_workbook(path), ImportDiagnosticCode.DUPLICATE_REQUIRED_SHEET)


def test_missing_required_header_fails(workbook_factory) -> None:
    def mutate(book):
        book["Parts"]["D1"] = "Unknown Length"

    result = import_canonical_workbook(workbook_factory(mutate=mutate))
    _assert_error(result, ImportDiagnosticCode.MISSING_REQUIRED_HEADER)


def test_IMPORT_001_rejects_duplicate_header(workbook_factory) -> None:
    def mutate(book):
        book["Parts"]["I1"] = " part   key "

    _assert_error(
        import_canonical_workbook(workbook_factory(mutate=mutate)),
        ImportDiagnosticCode.DUPLICATE_HEADER,
    )


def test_headers_match_case_insensitively_with_collapsed_spaces(workbook_factory) -> None:
    def mutate(book):
        book["Parts"]["A1"] = " work   KEY "
        book["Parts"]["D1"] = " length (MM) "

    assert import_canonical_workbook(workbook_factory(mutate=mutate)).success


def test_alias_guessing_is_not_used(workbook_factory) -> None:
    def mutate(book):
        book["Parts"]["D1"] = "Part Length"

    result = import_canonical_workbook(workbook_factory(mutate=mutate))
    assert ImportDiagnosticCode.MISSING_REQUIRED_HEADER in _codes(result)
    assert ImportDiagnosticCode.UNKNOWN_COLUMN in {item.code for item in result.information}


def test_completely_blank_row_is_ignored(workbook_factory) -> None:
    parts = [DEFAULT_PART, [None] * 8]
    assert import_canonical_workbook(workbook_factory(parts=parts)).success


def test_partially_populated_row_is_not_silently_skipped(workbook_factory) -> None:
    result = import_canonical_workbook(workbook_factory(parts=[DEFAULT_PART, ["W-1", "P-2"]]))
    _assert_error(result, ImportDiagnosticCode.EMPTY_REQUIRED_VALUE)
    assert any(item.row == 3 and item.worksheet == "Parts" for item in result.errors)


@pytest.mark.parametrize(
    ("sheet", "cell", "value", "code"),
    [
        ("Works", "A2", " ", ImportDiagnosticCode.EMPTY_REQUIRED_VALUE),
        ("Parts", "D2", None, ImportDiagnosticCode.EMPTY_REQUIRED_VALUE),
        ("Parts", "D2", "NaN", ImportDiagnosticCode.NON_FINITE_NUMBER),
        ("Parts", "D2", "+Infinity", ImportDiagnosticCode.NON_FINITE_NUMBER),
        ("Parts", "D2", "-inf", ImportDiagnosticCode.NON_FINITE_NUMBER),
        ("Parts", "D2", 0, ImportDiagnosticCode.NON_POSITIVE_DIMENSION),
        ("Parts", "D2", -1, ImportDiagnosticCode.NON_POSITIVE_DIMENSION),
        ("Works", "D2", -0.1, ImportDiagnosticCode.NEGATIVE_PROCESS_VALUE),
        ("Works", "E2", -0.1, ImportDiagnosticCode.NEGATIVE_PROCESS_VALUE),
        ("Works", "C2", 1.5, ImportDiagnosticCode.INVALID_INTEGER_VALUE),
        ("Works", "C2", 0, ImportDiagnosticCode.INVALID_INTEGER_VALUE),
        ("Works", "C2", True, ImportDiagnosticCode.INVALID_INTEGER_VALUE),
        ("Parts", "F2", 2.5, ImportDiagnosticCode.INVALID_INTEGER_VALUE),
        ("Parts", "F2", 0, ImportDiagnosticCode.INVALID_INTEGER_VALUE),
        ("Stocks", "F2", 2.5, ImportDiagnosticCode.INVALID_INTEGER_VALUE),
        ("Stocks", "F2", 0, ImportDiagnosticCode.INVALID_INTEGER_VALUE),
        ("Parts", "G2", "Y", ImportDiagnosticCode.INVALID_BOOLEAN_VALUE),
        ("Parts", "G2", 1, ImportDiagnosticCode.INVALID_TEXT_VALUE),
        ("Parts", "D2", "1,5", ImportDiagnosticCode.INVALID_NUMERIC_VALUE),
        ("Parts", "D2", "1,000", ImportDiagnosticCode.INVALID_NUMERIC_VALUE),
        ("Parts", "D2", "10 mm", ImportDiagnosticCode.INVALID_NUMERIC_VALUE),
    ],
)
def test_strict_value_validation(workbook_factory, sheet, cell, value, code) -> None:
    def mutate(book):
        book[sheet][cell] = value

    result = import_canonical_workbook(workbook_factory(mutate=mutate))
    _assert_error(result, code)
    diagnostic = next(item for item in result.errors if item.code is code)
    assert diagnostic.worksheet == sheet
    assert diagnostic.row == 2


def test_duplicate_work_key_fails_but_duplicate_name_is_allowed(workbook_factory) -> None:
    duplicate = [*DEFAULT_WORK]
    duplicate[1] = "Another Name"
    _assert_error(
        import_canonical_workbook(workbook_factory(works=[DEFAULT_WORK, duplicate])),
        ImportDiagnosticCode.DUPLICATE_WORK_KEY,
    )
    second = ["W-2", DEFAULT_WORK[1], *DEFAULT_WORK[2:]]
    result = import_canonical_workbook(
        workbook_factory(
            works=[DEFAULT_WORK, second],
            parts=[DEFAULT_PART],
            stocks=[DEFAULT_STOCK],
        )
    )
    assert result.success


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        ("part", ImportDiagnosticCode.DUPLICATE_PART_KEY),
        ("stock", ImportDiagnosticCode.DUPLICATE_STOCK_KEY),
    ],
)
def test_duplicate_scoped_key_fails(workbook_factory, kind, code) -> None:
    kwargs = (
        {"parts": [DEFAULT_PART, DEFAULT_PART]}
        if kind == "part"
        else {"stocks": [DEFAULT_STOCK, DEFAULT_STOCK]}
    )
    _assert_error(import_canonical_workbook(workbook_factory(**kwargs)), code)


def test_same_part_and_stock_keys_are_allowed_in_different_works(workbook_factory) -> None:
    works = [DEFAULT_WORK, ["W-2", "Second", 1, 0, 0, 0, 0, 0, 0, 0]]
    parts = [DEFAULT_PART, ["W-2", "P-1", "Panel", 10, 10, 1, "No", None]]
    stocks = [DEFAULT_STOCK, ["W-2", "S-1", "Sheet", 100, 100, 1]]
    path = workbook_factory(works=works, parts=parts, stocks=stocks)
    assert import_canonical_workbook(path).success


@pytest.mark.parametrize("kind", ["part", "stock"])
def test_unknown_work_reference_fails(workbook_factory, kind) -> None:
    if kind == "part":
        row = [*DEFAULT_PART]
        row[0] = "UNKNOWN"
        path = workbook_factory(parts=[row])
    else:
        row = [*DEFAULT_STOCK]
        row[0] = "UNKNOWN"
        path = workbook_factory(stocks=[row])
    result = import_canonical_workbook(path)
    _assert_error(result, ImportDiagnosticCode.UNKNOWN_WORK_REFERENCE)
    assert result.errors[0].related_work_key == "UNKNOWN"


def test_identity_keys_are_case_sensitive(workbook_factory) -> None:
    works = [DEFAULT_WORK, ["w-1", "Lower", 1, 0, 0, 0, 0, 0, 0, 0]]
    parts = [DEFAULT_PART, ["w-1", "P-1", "Lower", 10, 10, 1, "No", None]]
    stocks = [DEFAULT_STOCK, ["w-1", "S-1", "Lower", 100, 100, 1]]
    result = import_canonical_workbook(workbook_factory(works=works, parts=parts, stocks=stocks))
    assert result.success and len(result.works) == 2


def test_trim_that_consumes_stock_is_distinguished(workbook_factory) -> None:
    row = [*DEFAULT_WORK]
    row[6:8] = [500, 500]
    _assert_error(
        import_canonical_workbook(workbook_factory(works=[row])),
        ImportDiagnosticCode.INVALID_TRIM_FOR_STOCK,
    )


def test_boundary_clearance_that_consumes_usable_region_is_distinguished(workbook_factory) -> None:
    row = [*DEFAULT_WORK]
    row[5] = 300
    _assert_error(
        import_canonical_workbook(workbook_factory(works=[row])),
        ImportDiagnosticCode.INVALID_EFFECTIVE_STOCK_REGION,
    )


def test_IMPORT_001_import_is_atomic_across_multiple_works(workbook_factory) -> None:
    works = [DEFAULT_WORK, ["W-2", "Second", 1, 0, 0, 0, 0, 0, 0, 0]]
    parts = [DEFAULT_PART, ["W-2", "P-2", "Bad", 0, 10, 1, "No", None]]
    stocks = [DEFAULT_STOCK, ["W-2", "S-2", "Sheet", 100, 100, 1]]
    result = import_canonical_workbook(workbook_factory(works=works, parts=parts, stocks=stocks))
    assert not result.success and result.works == () and result.records is None


def test_all_discoverable_row_errors_are_returned(workbook_factory) -> None:
    part = ["UNKNOWN", "", "", 0, -1, 1.5, "Maybe", None]
    result = import_canonical_workbook(workbook_factory(parts=[part]))
    assert len(result.errors) >= 5
    assert {
        ImportDiagnosticCode.EMPTY_REQUIRED_VALUE,
        ImportDiagnosticCode.NON_POSITIVE_DIMENSION,
        ImportDiagnosticCode.INVALID_INTEGER_VALUE,
        ImportDiagnosticCode.INVALID_BOOLEAN_VALUE,
        ImportDiagnosticCode.UNKNOWN_WORK_REFERENCE,
    } <= _codes(result)


def test_duplicate_keys_are_discovered_even_when_other_row_values_are_invalid(
    workbook_factory,
) -> None:
    malformed_duplicate = [*DEFAULT_PART]
    malformed_duplicate[2] = ""
    result = import_canonical_workbook(
        workbook_factory(parts=[DEFAULT_PART, malformed_duplicate])
    )
    assert {
        ImportDiagnosticCode.EMPTY_REQUIRED_VALUE,
        ImportDiagnosticCode.DUPLICATE_PART_KEY,
    } <= _codes(result)


def test_diagnostic_contains_stable_cell_provenance(workbook_factory) -> None:
    part = [*DEFAULT_PART]
    part[3] = 0
    result = import_canonical_workbook(workbook_factory(parts=[part]))
    diagnostic = next(
        item for item in result.errors if item.code is ImportDiagnosticCode.NON_POSITIVE_DIMENSION
    )
    assert (
        diagnostic.worksheet,
        diagnostic.row,
        diagnostic.column,
        diagnostic.column_letter,
        diagnostic.header,
        diagnostic.offending_value,
    ) == ("Parts", 2, 4, "D", "Length (mm)", "0")


def test_information_does_not_hide_an_error(workbook_factory) -> None:
    def mutate(book):
        book.create_sheet("Notes")
        book["Parts"]["D2"] = 0

    result = import_canonical_workbook(workbook_factory(mutate=mutate))
    assert not result.success and result.works == ()
    assert result.information and result.errors
