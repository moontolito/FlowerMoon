from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import fields

import pytest

from debbie.importers.excel import (
    ADAPTER_ID,
    ADAPTER_ID_V11,
    CanonicalExcelImporter,
    CanonicalWorkbookV11Records,
    ImportDiagnosticCode,
    ImportSummary,
    ImportSummaryV11,
    import_canonical_workbook,
)
from debbie.application import DebbieSession
from debbie.desktop.models import PartsTableModel, StocksTableModel
from debbie.mass import calculate_nesting_result_mass, calculate_work_mass_plan
from debbie.nesting import ResultStatus, nest_work

from .conftest import (
    DEFAULT_PART,
    DEFAULT_STOCK_V11,
    DEFAULT_WORK_V11,
)


def _snapshot(result):
    return tuple(
        (
            str(work.id),
            work.name,
            work.material,
            work.thickness,
            tuple((str(part.id), part.name, part.dimensions) for part in work.part_types),
            tuple((str(item.id), str(item.part_type_id), item.base_quantity) for item in work.demand_items),
            tuple(
                (str(stock.id), stock.name, stock.dimensions, stock.allocation)
                for stock in work.stock_specifications
            ),
            tuple((str(item.id), str(item.specification_id), item.sequence) for item in work.stock_instances),
        )
        for work in result.works
    )


def test_schema_1_1_dispatches_to_explicit_adapter_and_builds_classified_work(
    workbook_v11_factory,
) -> None:
    result = import_canonical_workbook(workbook_v11_factory())
    assert result.success
    assert result.adapter_id == ADAPTER_ID_V11 == "canonical_excel_v1_1"
    assert result.schema_version == "1.1"
    assert result.summary.schema_version == "1.1"
    assert result.summary.adapter_id == ADAPTER_ID_V11
    assert result.summary.work_keys == ("W-1",)
    assert result.summary.density_units == "g/cm3"
    assert isinstance(result.records, CanonicalWorkbookV11Records)
    work = result.works[0]
    assert work.is_material_classified
    assert str(work.material.category_key) == "stainless-steel"
    assert str(work.material.grade_key) == "aisi-304"
    assert work.thickness.millimetres == 3
    assert all(stock.allocation is not None for stock in work.stock_specifications)


def test_schema_1_0_adapter_and_unclassified_behavior_are_unchanged(workbook_factory) -> None:
    result = import_canonical_workbook(workbook_factory())
    assert result.success and result.adapter_id == ADAPTER_ID == "canonical_excel_v1"
    assert not result.works[0].is_material_classified
    assert type(result.summary) is ImportSummary
    assert [item.name for item in fields(ImportSummary)] == [
        "work_count",
        "part_type_count",
        "demand_item_count",
        "stock_specification_count",
        "stock_instance_count",
        "drawing_numbers",
    ]


def test_schema_1_1_has_a_version_specific_summary(workbook_v11_factory) -> None:
    result = import_canonical_workbook(workbook_v11_factory())
    assert result.success and type(result.summary) is ImportSummaryV11


@pytest.mark.parametrize("source", ["library_default", " explicit_override "])
def test_density_source_canonical_values_are_case_insensitive_and_trimmed(
    workbook_v11_factory, source: str
) -> None:
    work = [*DEFAULT_WORK_V11]
    work[8] = source.upper()
    result = import_canonical_workbook(workbook_v11_factory(works=[work]))
    assert result.success
    assert result.works[0].material.density_source.value == source.strip().casefold()


def test_optional_description_and_drawing_number_are_preserved(workbook_v11_factory) -> None:
    result = import_canonical_workbook(workbook_v11_factory())
    assert result.records.works[0].material_description == "Production material"
    assert result.records.parts[0].drawing_number == "DWG-001"
    assert result.summary.materials[0].description == "Production material"
    assert result.summary.drawing_numbers == (("W-1", "P-1", "DWG-001"),)


@pytest.mark.parametrize(
    ("allocated_length", "allocated_width", "commercial", "physical"),
    [
        (1000, 500, 1.0, 1.0),
        (500, 500, 0.5, 0.5),
        (1000, 250, 1.0, 0.5),
        (500, 250, 0.25, 0.25),
    ],
)
def test_explicit_allocation_and_physical_fraction_are_preserved(
    workbook_v11_factory,
    allocated_length: float,
    allocated_width: float,
    commercial: float,
    physical: float,
) -> None:
    stock = ["W-1", "S-1", "Sheet", 1000, 500, allocated_length, allocated_width, commercial, 1]
    result = import_canonical_workbook(workbook_v11_factory(stocks=[stock]))
    assert result.success
    allocation = result.works[0].stock_specifications[0].allocation
    assert allocation.physical_allocation_fraction == physical
    assert allocation.commercial_allocation_fraction == commercial
    assert result.summary.stock_allocations[0].physical_allocation_fraction == physical


def test_extreme_valid_allocation_fraction_remains_finite(workbook_v11_factory) -> None:
    stock = ["W-1", "TINY", "Tiny", 1e200, 1, 1, 1, 1e-200, 1]
    result = import_canonical_workbook(workbook_v11_factory(stocks=[stock]))
    assert result.success
    fraction = result.works[0].stock_specifications[0].allocation.physical_allocation_fraction
    assert fraction == pytest.approx(1e-200)


def test_multiple_materials_grades_and_thicknesses_remain_work_isolated(
    workbook_v11_factory,
) -> None:
    second_work = [
        "W-2", "Aluminium", "aluminium", "Aluminium", "6082-t6", "6082-T6",
        2, 2.7, "library_default", 1, 0, 0, 0, 0, 0, 0, 0, None,
    ]
    parts = [DEFAULT_PART, ["W-2", "P-1", "Plate", 50, 40, 1, "No", "AL-1"]]
    stocks = [DEFAULT_STOCK_V11, ["W-2", "S-1", "Al sheet", 500, 250, 500, 250, 1, 1]]
    result = import_canonical_workbook(
        workbook_v11_factory(works=[DEFAULT_WORK_V11, second_work], parts=parts, stocks=stocks)
    )
    assert result.success and len(result.works) == 2
    assert {work.material.effective_density.grams_per_cubic_centimetre for work in result.works} == {7.9, 2.7}
    assert {work.thickness.millimetres for work in result.works} == {3.0, 2.0}


def test_same_material_with_different_thickness_and_same_category_different_grade(
    workbook_v11_factory,
) -> None:
    second = [*DEFAULT_WORK_V11]
    second[0:2] = ["W-2", "Second"]
    second[4:7] = ["aisi-316", "AISI 316", 5]
    parts = [DEFAULT_PART, ["W-2", "P-1", "Other", 100, 50, 1, "Yes", None]]
    stocks = [DEFAULT_STOCK_V11, ["W-2", "S-1", "Sheet", 1000, 500, 1000, 500, 1, 1]]
    result = import_canonical_workbook(
        workbook_v11_factory(works=[DEFAULT_WORK_V11, second], parts=parts, stocks=stocks)
    )
    assert result.success
    assert [str(work.material.category_key) for work in result.works] == [
        "stainless-steel", "stainless-steel"
    ]
    assert {str(work.material.grade_key) for work in result.works} == {"aisi-304", "aisi-316"}


def test_material_display_metadata_does_not_affect_imported_identity_or_hash(
    workbook_v11_factory,
) -> None:
    second = [*DEFAULT_WORK_V11]
    second[0:2] = ["W-2", "Second"]
    second[3] = "Inox"
    second[5] = "304 display alias"
    second[17] = "Different description"
    parts = [DEFAULT_PART, ["W-2", "P-1", "Other", 100, 50, 1, "Yes", None]]
    stocks = [DEFAULT_STOCK_V11, ["W-2", "S-1", "Other", 1000, 500, 1000, 500, 1, 1]]
    result = import_canonical_workbook(
        workbook_v11_factory(works=[DEFAULT_WORK_V11, second], parts=parts, stocks=stocks)
    )
    first, other = (work.material for work in result.works)
    assert first == other
    assert hash(first) == hash(other)


def test_material_metadata_and_density_do_not_affect_deterministic_ids(
    workbook_v11_factory,
) -> None:
    first = import_canonical_workbook(workbook_v11_factory())
    changed = [*DEFAULT_WORK_V11]
    changed[3] = "Inox"
    changed[5] = "304 display alias"
    changed[7] = 8.0
    changed[17] = "Corrected provenance"
    second = import_canonical_workbook(workbook_v11_factory(works=[changed]))
    assert first.success and second.success
    assert _snapshot(first)[0][0] == _snapshot(second)[0][0]
    assert [item.id for item in first.works[0].part_types] == [
        item.id for item in second.works[0].part_types
    ]
    assert [item.id for item in first.works[0].stock_instances] == [
        item.id for item in second.works[0].stock_instances
    ]


def test_worked_four_and_half_sheet_import_mass_example(workbook_v11_factory) -> None:
    work = [*DEFAULT_WORK_V11]
    work[9] = 10
    stocks = [
        ["W-1", "FULL", "Full", 2500, 1250, 2500, 1250, 1, 4],
        ["W-1", "HALF", "Half", 2500, 1250, 1250, 1250, 1, 1],
    ]
    result = import_canonical_workbook(
        workbook_v11_factory(works=[work], parts=[], stocks=stocks)
    )
    assert result.success
    plan = calculate_work_mass_plan(result.works[0])
    assert plan.totals.physical_equivalent_sheets == 4.5
    assert plan.totals.commercial_equivalent_sheets == 5.0
    assert plan.totals.gross_physical_allocation_mass_kg == pytest.approx(333.28125)
    assert plan.totals.gross_commercial_allocation_mass_kg == pytest.approx(370.3125)
    assert plan.totals.commercial_allocation_difference_kg == pytest.approx(37.03125)
    assert plan.per_product.gross_physical_allocation_mass_kg == pytest.approx(33.328125)


def test_full_allocation_import_runs_nesting_and_result_mass(workbook_v11_factory) -> None:
    imported = import_canonical_workbook(workbook_v11_factory())
    nesting = nest_work(imported.works[0])
    mass = calculate_nesting_result_mass(imported.works[0], nesting)
    assert nesting.status is ResultStatus.COMPLETE
    assert mass.totals is not None and mass.per_product is not None


def test_partial_zero_process_import_can_run_nesting(workbook_v11_factory) -> None:
    stock = ["W-1", "HALF", "Half", 1000, 500, 500, 500, 1, 1]
    result = import_canonical_workbook(workbook_v11_factory(stocks=[stock]))
    assert result.success
    assert nest_work(result.works[0]).status is ResultStatus.COMPLETE


def test_read_only_desktop_session_and_existing_tables_accept_schema_1_1(
    workbook_v11_factory,
) -> None:
    path = workbook_v11_factory()
    result = import_canonical_workbook(path)
    session = DebbieSession()
    token = session.begin_import()
    assert session.finish_import(token, path, result)
    assert session.selected_work == result.works[0]

    parts = PartsTableModel()
    stocks = StocksTableModel()
    parts.set_work(session.selected_work, result.records)
    stocks.set_work(session.selected_work, result.records)
    assert parts.rowCount() == 1
    assert stocks.rowCount() == 1


def test_schema_1_1_ids_are_stable_across_rows_sheets_paths_and_repeated_imports(
    workbook_v11_factory,
) -> None:
    second_work = [*DEFAULT_WORK_V11]
    second_work[0:2] = ["W-2", "Second"]
    parts = [DEFAULT_PART, ["W-2", "P-2", "Other", 30, 20, 1, "No", None]]
    stocks = [DEFAULT_STOCK_V11, ["W-2", "S-2", "Other", 200, 100, 200, 100, 1, 1]]
    first_path = workbook_v11_factory(
        works=[DEFAULT_WORK_V11, second_work], parts=parts, stocks=stocks
    )

    def reverse_sheets(book):
        book._sheets = [book["Stocks"], book["Parts"], book["Works"], book["Debbie"]]

    second_path = workbook_v11_factory(
        works=[second_work, DEFAULT_WORK_V11],
        parts=list(reversed(parts)),
        stocks=list(reversed(stocks)),
        mutate=reverse_sheets,
    )
    assert _snapshot(import_canonical_workbook(first_path)) == _snapshot(
        import_canonical_workbook(second_path)
    )
    assert _snapshot(import_canonical_workbook(first_path)) == _snapshot(
        import_canonical_workbook(first_path)
    )


def test_schema_1_1_hash_seed_independence(workbook_v11_factory) -> None:
    path = workbook_v11_factory()
    script = """
import json, sys
from dataclasses import asdict
from debbie.importers.excel import import_canonical_workbook
r = import_canonical_workbook(sys.argv[1])
assert r.success
print(json.dumps({"ids": [[str(w.id), [str(x.id) for x in w.part_types], [str(x.id) for x in w.stock_instances]] for w in r.works], "summary": asdict(r.summary)}, sort_keys=True))
"""
    outputs = []
    for seed in ("1", "777"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, "-c", script, str(path)],
            check=True, capture_output=True, text=True, env=environment,
        )
        outputs.append(json.loads(completed.stdout))
    assert outputs[0] == outputs[1]


def test_schema_1_1_workbook_handles_are_released_on_windows(workbook_v11_factory) -> None:
    path = workbook_v11_factory()
    assert import_canonical_workbook(path).success
    moved = path.with_name("released.xlsx")
    path.rename(moved)
    moved.unlink()


def test_importer_reuse_has_no_stale_success_state(workbook_v11_factory) -> None:
    importer = CanonicalExcelImporter()
    valid = workbook_v11_factory()
    invalid_work = [*DEFAULT_WORK_V11]
    invalid_work[6] = 0
    invalid = workbook_v11_factory(works=[invalid_work])
    assert importer.import_file(valid).success
    failure = importer.import_file(invalid)
    assert not failure.success and failure.works == () and failure.records is failure.summary is None
    assert importer.import_file(valid).success


def test_cross_version_reuse_is_atomic_and_stateless(
    workbook_factory, workbook_v11_factory
) -> None:
    importer = CanonicalExcelImporter()
    valid_v10 = workbook_factory()
    valid_v11 = workbook_v11_factory()
    invalid_v10 = workbook_factory(parts=[["missing", "P", "Bad", 1, 1, 1, "No", None]])
    invalid_v11_work = [*DEFAULT_WORK_V11]
    invalid_v11_work[7] = 0
    invalid_v11 = workbook_v11_factory(works=[invalid_v11_work])

    assert importer.import_file(valid_v10).success
    assert not importer.import_file(invalid_v11).success
    assert importer.import_file(valid_v11).success
    assert not importer.import_file(invalid_v10).success
    assert importer.import_file(valid_v11).success


def test_schema_1_0_and_1_1_logical_work_ids_are_intentionally_distinct(
    workbook_factory, workbook_v11_factory
) -> None:
    v10 = import_canonical_workbook(workbook_factory()).works[0]
    v11 = import_canonical_workbook(workbook_v11_factory()).works[0]
    assert v10.id != v11.id
