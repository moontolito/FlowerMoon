from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import socket
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from debbie.importers.excel import (
    CanonicalExcelImporter,
    DEFAULT_IMPORT_LIMITS,
    ImportDiagnosticCode,
    import_canonical_workbook,
)

from .conftest import DEFAULT_PART, DEFAULT_STOCK, DEFAULT_WORK


def _assert_code(result, code):
    assert not result.success and result.works == ()
    assert code in {item.code for item in result.errors}


@pytest.mark.parametrize("suffix", [".xls", ".xlsm", ".csv", ".ods", ".zip"])
def test_unsupported_file_types_are_rejected_before_loading(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"unsupported{suffix}"
    path.write_bytes(b"not opened")
    _assert_code(import_canonical_workbook(path), ImportDiagnosticCode.UNSUPPORTED_FILE_TYPE)


def test_missing_file_is_structured(tmp_path: Path) -> None:
    _assert_code(
        import_canonical_workbook(tmp_path / "missing.xlsx"),
        ImportDiagnosticCode.FILE_NOT_FOUND,
    )


def test_corrupt_or_unrelated_zip_xlsx_is_structured(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.xlsx"
    corrupt.write_bytes(b"not a zip")
    _assert_code(import_canonical_workbook(corrupt), ImportDiagnosticCode.UNREADABLE_WORKBOOK)


def test_macro_payload_renamed_to_xlsx_is_rejected(workbook_factory) -> None:
    path = workbook_factory()
    with ZipFile(path, "a", compression=ZIP_DEFLATED) as archive:
        archive.writestr("xl/vbaProject.bin", b"macro payload must never be loaded")
    _assert_code(import_canonical_workbook(path), ImportDiagnosticCode.UNSUPPORTED_FILE_TYPE)


def test_innocent_macro_like_filename_and_binary_text_are_not_rejected(
    workbook_factory,
) -> None:
    path = workbook_factory()
    with ZipFile(path, "a", compression=ZIP_DEFLATED) as archive:
        archive.writestr("xl/notvbaProject.bin", b"macroEnabled is innocent binary text")
        archive.writestr("customXml/innocent.bin", b"<!DOCTYPE is binary here, not XML")
    assert import_canonical_workbook(path).success


def test_encrypted_member_flag_is_reported_as_unreadable(workbook_factory) -> None:
    path = workbook_factory()
    data = bytearray(path.read_bytes())
    central = data.find(b"PK\x01\x02")
    assert central >= 0
    flags = int.from_bytes(data[central + 8 : central + 10], "little") | 0x1
    data[central + 8 : central + 10] = flags.to_bytes(2, "little")
    path.write_bytes(data)
    _assert_code(import_canonical_workbook(path), ImportDiagnosticCode.UNREADABLE_WORKBOOK)


def test_archive_member_paths_are_never_extracted(workbook_factory) -> None:
    path = workbook_factory()
    escaped = path.parent.parent / "debbie-import-escaped.xml"
    assert not escaped.exists()
    with ZipFile(path, "a", compression=ZIP_DEFLATED) as archive:
        archive.writestr("../debbie-import-escaped.xml", b"<innocent />")
    assert import_canonical_workbook(path).success
    assert not escaped.exists()


def test_xml_entity_declaration_is_rejected_before_openpyxl(workbook_factory) -> None:
    path = workbook_factory()
    payload = b'<!DOCTYPE root [<!ENTITY x "expanded">]><root>&x;</root>'
    with ZipFile(path, "a", compression=ZIP_DEFLATED) as archive:
        archive.writestr("customXml/unsafe.xml", payload)
    _assert_code(
        import_canonical_workbook(path),
        ImportDiagnosticCode.UNSAFE_WORKBOOK_CONTENT,
    )


def test_xml_security_tokens_in_comments_and_cdata_are_not_false_positives(
    workbook_factory,
) -> None:
    path = workbook_factory()
    content = b"<!-- <!DOCTYPE innocent> --><root><![CDATA[<!ENTITY text>]]></root>"
    with ZipFile(path, "a", compression=ZIP_DEFLATED) as archive:
        archive.writestr("customXml/innocent.xml", content)
    assert import_canonical_workbook(path).success


def test_utf16_xml_entity_declaration_is_rejected(workbook_factory) -> None:
    path = workbook_factory()
    content = '<!DOCTYPE root [<!ENTITY x "expanded">]><root>&x;</root>'.encode(
        "utf-16"
    )
    with ZipFile(path, "a", compression=ZIP_DEFLATED) as archive:
        archive.writestr("customXml/unsafe-utf16.xml", content)
    _assert_code(
        import_canonical_workbook(path),
        ImportDiagnosticCode.UNSAFE_WORKBOOK_CONTENT,
    )


def test_required_formula_without_cache_is_rejected(workbook_factory) -> None:
    def mutate(book):
        book["Parts"]["D2"] = "=50+50"

    _assert_code(
        import_canonical_workbook(workbook_factory(mutate=mutate)),
        ImportDiagnosticCode.UNSUPPORTED_FORMULA_VALUE,
    )


def test_metadata_header_formula_without_cache_is_rejected(workbook_factory) -> None:
    def mutate(book):
        book["Debbie"]["A1"] = '="Key"'

    _assert_code(
        import_canonical_workbook(workbook_factory(mutate=mutate)),
        ImportDiagnosticCode.UNSUPPORTED_FORMULA_VALUE,
    )


def test_external_link_formula_is_not_followed_or_evaluated(workbook_factory, monkeypatch) -> None:
    def mutate(book):
        book["Parts"]["D2"] = "='https://example.invalid/[remote.xlsx]Sheet1'!A1"

    def forbidden_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    result = import_canonical_workbook(workbook_factory(mutate=mutate))
    _assert_code(result, ImportDiagnosticCode.UNSUPPORTED_FORMULA_VALUE)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda book: book["Debbie"].merge_cells("A2:B2"),
        lambda book: book["Parts"].merge_cells("A1:B1"),
        lambda book: book["Parts"].merge_cells("A2:B2"),
    ],
)
def test_merged_cells_in_canonical_regions_are_rejected(workbook_factory, mutate) -> None:
    _assert_code(
        import_canonical_workbook(workbook_factory(mutate=mutate)),
        ImportDiagnosticCode.MERGED_CELL_IN_DATA_TABLE,
    )


def test_source_file_is_released_after_import_on_windows(workbook_factory) -> None:
    path = workbook_factory()
    result = import_canonical_workbook(path)
    moved = path.with_name("renamed.xlsx")
    path.rename(moved)
    moved.unlink()
    assert result.success and not moved.exists()


def test_importer_reuse_does_not_retain_stale_success(workbook_factory) -> None:
    importer = CanonicalExcelImporter()
    assert importer.import_file(workbook_factory()).success
    invalid = [*DEFAULT_PART]
    invalid[3] = 0
    failed = importer.import_file(workbook_factory(parts=[invalid]))
    assert not failed.success and failed.works == ()


def test_importer_reuse_sequences_never_leak_previous_results(workbook_factory) -> None:
    importer = CanonicalExcelImporter()
    valid_a = workbook_factory()
    valid_b = workbook_factory(
        works=[["W-B", "Work B", 1, 0, 0, 0, 0, 0, 0, 0]],
        parts=[["W-B", "P-B", "Part B", 10, 10, 1, "No", "DRAW-B"]],
        stocks=[["W-B", "S-B", "Stock B", 100, 100, 1]],
    )
    invalid_format = workbook_factory(
        metadata=[
            ["Key", "Value"],
            ["Format Name", "Not Debbie"],
            ["Schema Version", "1.0"],
            ["Units", "mm"],
        ]
    )
    invalid_value = [*DEFAULT_PART]
    invalid_value[3] = 0
    invalid_data = workbook_factory(parts=[invalid_value])

    first_success = importer.import_file(valid_a)
    after_success_failure = importer.import_file(invalid_format)
    assert first_success.success and not after_success_failure.success
    assert after_success_failure.works == ()
    assert after_success_failure.records is None and after_success_failure.summary is None
    assert after_success_failure.source_path == invalid_format
    assert after_success_failure.format_name == "Not Debbie"

    first_failure = importer.import_file(invalid_data)
    after_failure_success = importer.import_file(valid_b)
    assert not first_failure.success and after_failure_success.success
    assert after_failure_success.source_path == valid_b
    assert after_failure_success.works[0].name == "Work B"
    assert after_failure_success.summary.drawing_numbers == (("W-B", "P-B", "DRAW-B"),)

    success_a = importer.import_file(valid_a)
    success_b = importer.import_file(valid_b)
    assert success_a.works[0].id != success_b.works[0].id
    assert success_a.source_path == valid_a and success_b.source_path == valid_b
    assert success_a.summary.drawing_numbers == (("W-1", "P-1", "DWG-001"),)
    assert success_b.summary.drawing_numbers == (("W-B", "P-B", "DRAW-B"),)

    failures = [importer.import_file(invalid_format), importer.import_file(invalid_data)]
    assert all(not result.success and result.works == () for result in failures)
    assert all(result.records is None and result.summary is None for result in failures)
    assert failures[0].source_path != failures[1].source_path
    assert {item.code for item in failures[0].errors} != {
        item.code for item in failures[1].errors
    }


def test_unexpected_failure_is_distinguished_at_public_boundary(
    workbook_factory, monkeypatch
) -> None:
    import debbie.importers.excel.importer as importer_module

    def fail_unexpectedly(*args, **kwargs):
        raise RuntimeError("developer-only detail")

    monkeypatch.setattr(importer_module, "read_workbook", fail_unexpectedly)
    result = import_canonical_workbook(workbook_factory())
    _assert_code(result, ImportDiagnosticCode.INTERNAL_IMPORT_ERROR)
    assert "developer-only detail" not in result.errors[0].message


def test_unexpected_parser_failure_releases_source_file(
    workbook_factory, monkeypatch
) -> None:
    import debbie.importers.excel.importer as importer_module

    path = workbook_factory()
    monkeypatch.setattr(
        importer_module,
        "parse_workbook",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("unexpected")),
    )
    result = import_canonical_workbook(path)
    _assert_code(result, ImportDiagnosticCode.INTERNAL_IMPORT_ERROR)
    renamed = path.with_name("released-after-parser-error.xlsx")
    path.rename(renamed)
    renamed.unlink()
    assert not renamed.exists()


def test_import_does_not_use_network_for_valid_workbook(workbook_factory, monkeypatch) -> None:
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network access attempted")),
    )
    assert import_canonical_workbook(workbook_factory()).success


def test_row_limit_can_be_lowered_for_bounded_testing(workbook_factory) -> None:
    limits = replace(DEFAULT_IMPORT_LIMITS, max_rows_per_sheet=1)
    _assert_code(
        import_canonical_workbook(workbook_factory(), limits=limits),
        ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
    )


def test_column_limit_can_be_lowered_for_bounded_testing(workbook_factory) -> None:
    limits = replace(DEFAULT_IMPORT_LIMITS, max_columns_per_sheet=5)
    _assert_code(
        import_canonical_workbook(workbook_factory(), limits=limits),
        ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
    )


def test_text_limit_is_checked_before_domain_construction(workbook_factory) -> None:
    limits = replace(DEFAULT_IMPORT_LIMITS, max_text_length=4)
    _assert_code(
        import_canonical_workbook(workbook_factory(), limits=limits),
        ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
    )


def test_stock_expansion_limit_is_checked_before_allocation(
    workbook_factory, monkeypatch
) -> None:
    import debbie.importers.excel.domain_builder as builder_module

    stock = [*DEFAULT_STOCK]
    stock[5] = 3
    limits = replace(DEFAULT_IMPORT_LIMITS, max_stock_instances=2)
    monkeypatch.setattr(
        builder_module,
        "stock_instance_id",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("stock IDs must not be allocated beyond the limit")
        ),
    )
    _assert_code(
        import_canonical_workbook(workbook_factory(stocks=[stock]), limits=limits),
        ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
    )


def test_demand_expansion_limit_is_checked_before_materialization(workbook_factory) -> None:
    work = [*DEFAULT_WORK]
    work[2] = 3
    part = [*DEFAULT_PART]
    part[5] = 2
    limits = replace(DEFAULT_IMPORT_LIMITS, max_expanded_demand_instances=5)
    _assert_code(
        import_canonical_workbook(workbook_factory(works=[work], parts=[part]), limits=limits),
        ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
    )


def test_too_many_worksheets_is_bounded(workbook_factory) -> None:
    def mutate(book):
        book.create_sheet("Extra")

    limits = replace(DEFAULT_IMPORT_LIMITS, max_worksheets=4)
    _assert_code(
        import_canonical_workbook(workbook_factory(mutate=mutate), limits=limits),
        ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_file_bytes", 1),
        ("max_archive_members", 1),
        ("max_archive_uncompressed_bytes", 1),
        ("max_archive_member_bytes", 1),
        ("max_archive_compression_ratio", 1),
    ],
)
def test_archive_limits_return_structured_diagnostics(
    workbook_factory, field: str, value: int
) -> None:
    limits = replace(DEFAULT_IMPORT_LIMITS, **{field: value})
    _assert_code(
        import_canonical_workbook(workbook_factory(), limits=limits),
        ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
    )


def test_total_data_row_limit_is_structured(workbook_factory) -> None:
    limits = replace(DEFAULT_IMPORT_LIMITS, max_total_data_rows=2)
    _assert_code(
        import_canonical_workbook(workbook_factory(), limits=limits),
        ImportDiagnosticCode.SIZE_LIMIT_EXCEEDED,
    )


def test_integer_limit_is_structured(workbook_factory) -> None:
    limits = replace(DEFAULT_IMPORT_LIMITS, max_integer_value=1)
    _assert_code(
        import_canonical_workbook(workbook_factory(), limits=limits),
        ImportDiagnosticCode.INVALID_INTEGER_VALUE,
    )


def test_moderate_import_performance_fixture_has_no_timing_threshold(workbook_factory) -> None:
    works = []
    parts = []
    stocks = []
    for work_number in range(5):
        key = f"W-{work_number}"
        works.append([key, f"Work {work_number}", 1, 0.1, 0.2, 0, 0, 0, 0, 0])
        for part_number in range(20):
            parts.append(
                [
                    key,
                    f"P-{part_number}",
                    f"Part {part_number}",
                    10 + part_number,
                    5,
                    1,
                    "Yes",
                    None,
                ]
            )
        for stock_number in range(4):
            stocks.append([key, f"S-{stock_number}", f"Stock {stock_number}", 1000, 500, 1])
    result = import_canonical_workbook(
        workbook_factory(works=works, parts=parts, stocks=stocks)
    )
    assert result.success
    assert result.summary.work_count == 5
    assert result.summary.part_type_count == 100
    assert result.summary.stock_specification_count == 20
