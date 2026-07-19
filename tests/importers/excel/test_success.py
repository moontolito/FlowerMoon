from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import os
import shutil
import subprocess
import sys

from debbie.domain import Orientation
from debbie.importers.excel import (
    ADAPTER_ID,
    ImportDiagnosticCode,
    import_canonical_workbook,
)
from debbie.nesting import ResultStatus, nest_work
from debbie.mass import MassCalculationStatus, calculate_work_mass_plan

from .conftest import DEFAULT_PART, DEFAULT_STOCK, DEFAULT_WORK


def _domain_snapshot(result):
    return tuple(
        (
            str(work.id),
            work.name,
            work.batch_multiplier,
            work.process_profile,
            tuple(
                (
                    str(item.id),
                    item.name,
                    item.dimensions,
                    tuple(sorted(map(int, item.allowed_orientations))),
                )
                for item in work.part_types
            ),
            tuple(
                (str(item.id), str(item.part_type_id), item.base_quantity)
                for item in work.demand_items
            ),
            tuple((str(item.id), item.name, item.dimensions) for item in work.stock_specifications),
            tuple(
                (str(item.id), str(item.specification_id), item.sequence)
                for item in work.stock_instances
            ),
        )
        for work in result.works
    )


def test_IMPORT_001_recognizes_canonical_metadata(workbook_factory) -> None:
    result = import_canonical_workbook(workbook_factory())
    assert result.success
    assert (result.format_name, result.schema_version, result.unit_system) == (
        "Debbie Nesting Workbook",
        "1.0",
        "mm",
    )
    assert result.adapter_id == ADAPTER_ID == "canonical_excel_v1"


def test_IMPORT_001_work_remains_unclassified_for_mass_calculation(workbook_factory) -> None:
    result = import_canonical_workbook(workbook_factory())
    assert result.success
    work = result.works[0]
    assert work.material is None
    assert work.thickness is None
    plan = calculate_work_mass_plan(work)
    assert plan.status is MassCalculationStatus.MATERIAL_DATA_REQUIRED
    assert plan.totals is None


def test_valid_workbook_builds_existing_domain_objects(workbook_factory) -> None:
    result = import_canonical_workbook(workbook_factory())
    work = result.works[0]
    assert work.name == "First Work"
    assert work.batch_multiplier == 1
    assert len(work.part_types) == len(work.demand_items) == 1
    assert len(work.part_instances) == 2
    assert len(work.stock_specifications) == 1
    assert len(work.stock_instances) == 2


def test_IMPORT_001_keeps_kerf_and_clearance_separate(workbook_factory) -> None:
    work_row = [*DEFAULT_WORK]
    work_row[3:6] = [1.25, 2.5, 3.75]
    work = import_canonical_workbook(workbook_factory(works=[work_row])).works[0]
    assert (work.process_profile.kerf, work.process_profile.minimum_part_clearance) == (1.25, 2.5)
    assert work.process_profile.boundary_clearance == 3.75
    assert work.part_types[0].dimensions.length == 100


def test_asymmetric_trim_and_zero_process_values_are_preserved(workbook_factory) -> None:
    row = [*DEFAULT_WORK]
    row[3:] = [0, 0, 0, 1, 2, 3, 4]
    work = import_canonical_workbook(workbook_factory(works=[row])).works[0]
    assert work.process_profile.trim == replace(
        work.process_profile.trim, left=1, right=2, top=3, bottom=4
    )


def test_IMPORT_001_maps_rotation_yes_to_zero_and_ninety(workbook_factory) -> None:
    part = import_canonical_workbook(workbook_factory()).works[0].part_types[0]
    assert part.allowed_orientations == frozenset({Orientation.ZERO, Orientation.DEG_90})


def test_IMPORT_001_maps_rotation_no_to_zero_only(workbook_factory) -> None:
    row = [*DEFAULT_PART]
    row[6] = " no "
    part = import_canonical_workbook(workbook_factory(parts=[row])).works[0].part_types[0]
    assert part.allowed_orientations == frozenset({Orientation.ZERO})


def test_optional_drawing_number_is_retained_as_provenance(workbook_factory) -> None:
    result = import_canonical_workbook(workbook_factory())
    assert result.records.parts[0].drawing_number == "DWG-001"
    assert result.summary.drawing_numbers == (("W-1", "P-1", "DWG-001"),)


def test_multiple_works_remain_isolated(workbook_factory) -> None:
    works = [DEFAULT_WORK, ["W-2", "Second", 2, 0, 0, 0, 0, 0, 0, 0]]
    parts = [DEFAULT_PART, ["W-2", "P-1", "Other", 10, 20, 1, "No", None]]
    stocks = [DEFAULT_STOCK, ["W-2", "S-1", "Other sheet", 200, 100, 1]]
    result = import_canonical_workbook(workbook_factory(works=works, parts=parts, stocks=stocks))
    assert result.success and len(result.works) == 2
    assert result.works[0].id != result.works[1].id
    assert all(item.work_id == work.id for work in result.works for item in work.stock_instances)


def test_unknown_sheet_and_column_produce_information(workbook_factory) -> None:
    def mutate(workbook):
        workbook.create_sheet("Notes")["A1"] = "ignored"
        workbook["Parts"]["I1"] = "Customer Comment"
        workbook["Parts"]["I2"] = "hello"

    result = import_canonical_workbook(workbook_factory(mutate=mutate))
    assert result.success
    assert {item.code for item in result.information} >= {
        ImportDiagnosticCode.UNKNOWN_WORKSHEET,
        ImportDiagnosticCode.UNKNOWN_COLUMN,
    }


def test_unknown_metadata_is_preserved_and_reported(workbook_factory) -> None:
    metadata = [
        ["Key", "Value"],
        ["Format Name", "Debbie Nesting Workbook"],
        ["Schema Version", "1.0"],
        ["Units", "mm"],
        ["Customer", "Moon Works"],
    ]
    result = import_canonical_workbook(workbook_factory(metadata=metadata))
    assert result.success
    assert ("Customer", "Moon Works") in result.records.metadata.extra_items
    assert any(
        item.code is ImportDiagnosticCode.UNKNOWN_METADATA_KEY
        for item in result.information
    )


def test_strict_dot_decimal_numeric_text_is_accepted(workbook_factory) -> None:
    row = [*DEFAULT_PART]
    row[3:6] = ["100.25", "+50.5", "2.0"]
    result = import_canonical_workbook(workbook_factory(parts=[row]))
    assert result.success
    assert result.works[0].part_types[0].dimensions.length == 100.25
    assert result.works[0].demand_items[0].base_quantity == 2


def test_deterministic_ids_repeat_across_imports(workbook_factory) -> None:
    path = workbook_factory()
    assert _domain_snapshot(import_canonical_workbook(path)) == _domain_snapshot(
        import_canonical_workbook(path)
    )


def test_stock_quantity_creates_deterministic_physical_sequences(workbook_factory) -> None:
    path = workbook_factory()
    first = import_canonical_workbook(path).works[0].stock_instances
    second = import_canonical_workbook(path).works[0].stock_instances
    assert [item.sequence for item in first] == [1, 2]
    assert [item.id for item in first] == [item.id for item in second]


def test_IMPORT_001_reordered_rows_produce_equivalent_domain(workbook_factory) -> None:
    works = [DEFAULT_WORK, ["W-2", "Second", 1, 0, 0, 0, 0, 0, 0, 0]]
    parts = [DEFAULT_PART, ["W-2", "P-2", "Other", 20, 10, 1, "No", None]]
    stocks = [DEFAULT_STOCK, ["W-2", "S-2", "Other", 200, 100, 1]]
    first = import_canonical_workbook(workbook_factory(works=works, parts=parts, stocks=stocks))
    second = import_canonical_workbook(
        workbook_factory(
            works=list(reversed(works)),
            parts=list(reversed(parts)),
            stocks=list(reversed(stocks)),
        )
    )
    assert _domain_snapshot(first) == _domain_snapshot(second)


def test_deterministic_ids_do_not_depend_on_file_path(workbook_factory) -> None:
    first_path = workbook_factory()
    second_path = first_path.with_name("same-content-different-path.xlsx")
    shutil.copyfile(first_path, second_path)
    assert _domain_snapshot(import_canonical_workbook(first_path)) == _domain_snapshot(
        import_canonical_workbook(second_path)
    )


def test_deterministic_ids_do_not_depend_on_file_timestamp(workbook_factory) -> None:
    path = workbook_factory()
    first = _domain_snapshot(import_canonical_workbook(path))
    os.utime(path, (1_000_000_000, 1_000_000_000))
    second = _domain_snapshot(import_canonical_workbook(path))
    assert first == second


def test_deterministic_ids_do_not_depend_on_workbook_modified_timestamp(
    workbook_factory,
) -> None:
    first = import_canonical_workbook(
        workbook_factory(
            mutate=lambda book: setattr(
                book.properties, "modified", datetime(2020, 1, 1)
            )
        )
    )
    second = import_canonical_workbook(
        workbook_factory(
            mutate=lambda book: setattr(
                book.properties, "modified", datetime(2030, 12, 31)
            )
        )
    )
    assert _domain_snapshot(first) == _domain_snapshot(second)


def test_deterministic_ids_do_not_depend_on_worksheet_order(workbook_factory) -> None:
    first = import_canonical_workbook(workbook_factory())

    def reverse_required_sheets(book):
        book._sheets = [book["Stocks"], book["Parts"], book["Works"], book["Debbie"]]

    second = import_canonical_workbook(workbook_factory(mutate=reverse_required_sheets))
    assert _domain_snapshot(first) == _domain_snapshot(second)


def test_deterministic_snapshot_is_independent_of_python_hash_seed(workbook_factory) -> None:
    path = workbook_factory()
    script = """
import json
import sys
from debbie.importers.excel import import_canonical_workbook

result = import_canonical_workbook(sys.argv[1])
assert result.success
snapshot = [
    {
        "work": str(work.id),
        "parts": [str(item.id) for item in work.part_types],
        "demands": [str(item.id) for item in work.demand_items],
        "stock_specs": [str(item.id) for item in work.stock_specifications],
        "stocks": [str(item.id) for item in work.stock_instances],
    }
    for work in result.works
]
print(json.dumps(snapshot, sort_keys=True))
"""

    def run(seed: str) -> str:
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, "-c", script, str(path)],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        return completed.stdout.strip()

    assert run("1") == run("777")


def test_imported_work_can_be_passed_to_solver_without_conversion(workbook_factory) -> None:
    result = import_canonical_workbook(workbook_factory())
    work = result.works[0]
    solved = nest_work(work)
    assert solved.status is ResultStatus.COMPLETE
    assert work.layouts == ()
