from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from debbie.domain import ProcessProfile, Work, WorkId
from debbie.mass import (
    MassCalculationDiagnosticCode,
    MassCalculationStatus,
    MassDiagnosticSeverity,
    calculate_work_mass_plan,
)

from .helpers import classified_work


def test_WEIGHT_001_unclassified_work_returns_structured_unavailable_result() -> None:
    plan = calculate_work_mass_plan(Work(WorkId("legacy"), "Legacy", 1, ProcessProfile()))
    assert plan.status is MassCalculationStatus.MATERIAL_DATA_REQUIRED
    assert plan.totals is plan.per_product is None
    assert plan.diagnostics[0].code is MassCalculationDiagnosticCode.MATERIAL_DATA_REQUIRED
    assert plan.diagnostics[0].severity is MassDiagnosticSeverity.ERROR
    assert plan.diagnostics[0].related_work_id == WorkId("legacy")


def test_WEIGHT_001_single_part_and_batch_expansion() -> None:
    work = classified_work(batch=3, parts=(("p", 10, 20, 2),))
    plan = calculate_work_mass_plan(work)
    assert plan.totals is not None
    assert plan.totals.rectangular_part_mass_estimate_kg == pytest.approx(
        10 * 20 * 3 * 7.9 * 6 / 1_000_000
    )


def test_WEIGHT_001_multiple_parts_use_stable_sum() -> None:
    work = classified_work(parts=(("b", 20, 30, 2), ("a", 10, 10, 3)))
    reversed_work = classified_work(parts=tuple(reversed((
        ("b", 20, 30, 2),
        ("a", 10, 10, 3),
    ))))
    assert calculate_work_mass_plan(work).totals == calculate_work_mass_plan(reversed_work).totals


def test_WEIGHT_001_reordered_stock_definitions_and_instances_are_deterministic() -> None:
    stocks = (
        ("b", 200, 100, 100, 100, 1.0, 2),
        ("a", 100, 100, 50, 100, 0.75, 3),
    )
    forward = calculate_work_mass_plan(classified_work(parts=(), stocks=stocks))
    backward = calculate_work_mass_plan(
        classified_work(parts=(), stocks=tuple(reversed(stocks)))
    )
    assert forward.totals == backward.totals
    assert forward.per_product == backward.per_product


def test_WEIGHT_001_worked_four_and_half_sheet_example() -> None:
    work = classified_work(
        batch=10,
        parts=(),
        stocks=(
            ("full", 2500, 1250, 2500, 1250, 1.0, 4),
            ("half", 2500, 1250, 1250, 1250, 1.0, 1),
        ),
    )
    plan = calculate_work_mass_plan(work)
    assert plan.status is MassCalculationStatus.AVAILABLE
    assert plan.totals is not None and plan.per_product is not None
    assert plan.totals.physical_equivalent_sheets == pytest.approx(4.5)
    assert plan.totals.commercial_equivalent_sheets == pytest.approx(5.0)
    assert plan.totals.gross_physical_allocation_mass_kg == pytest.approx(333.28125)
    assert plan.totals.gross_commercial_allocation_mass_kg == pytest.approx(370.3125)
    assert plan.totals.commercial_allocation_difference_kg == pytest.approx(37.03125)
    assert plan.per_product.gross_physical_allocation_mass_kg == pytest.approx(33.328125)


def test_WEIGHT_001_equal_physical_and_commercial_full_allocation() -> None:
    plan = calculate_work_mass_plan(classified_work(parts=()))
    assert plan.totals is not None
    assert plan.totals.gross_commercial_allocation_mass_kg == pytest.approx(
        plan.totals.gross_physical_allocation_mass_kg
    )
    assert plan.totals.commercial_allocation_difference_kg == pytest.approx(0.0)


def test_WEIGHT_001_insufficient_inventory_keeps_negative_unused_mass() -> None:
    work = classified_work(
        parts=(("p", 100, 100, 2),),
        stocks=(("s", 100, 100, 100, 100, 1.0, 1),),
    )
    plan = calculate_work_mass_plan(work)
    assert plan.status is MassCalculationStatus.INSUFFICIENT_AVAILABLE_STOCK
    assert plan.totals is not None
    assert plan.totals.physical_unused_allocation_mass_kg < 0
    assert plan.per_product is None
    assert plan.diagnostics[0].code is MassCalculationDiagnosticCode.INSUFFICIENT_AVAILABLE_STOCK
    assert plan.diagnostics[0].severity is MassDiagnosticSeverity.WARNING
    assert plan.diagnostics[0].related_work_id == work.id


def test_WEIGHT_001_sub_epsilon_shortage_is_not_treated_as_sufficient() -> None:
    plan = calculate_work_mass_plan(
        classified_work(
            parts=(("p", 100, 100, 1),),
            stocks=(("s", 100, 100, 100, 99.9999999999, 1.0, 1),),
        )
    )
    assert plan.status is MassCalculationStatus.INSUFFICIENT_AVAILABLE_STOCK
    assert plan.totals is not None
    assert -1e-12 < plan.totals.physical_unused_allocation_mass_kg < 0.0


def test_WEIGHT_001_no_stock_is_structured_insufficiency() -> None:
    plan = calculate_work_mass_plan(classified_work(stocks=()))
    assert plan.status is MassCalculationStatus.INSUFFICIENT_AVAILABLE_STOCK
    assert {item.code for item in plan.diagnostics} == {
        MassCalculationDiagnosticCode.NO_STOCK_AVAILABLE,
        MassCalculationDiagnosticCode.INSUFFICIENT_AVAILABLE_STOCK,
    }


def test_WEIGHT_001_empty_work_has_available_zero_totals() -> None:
    plan = calculate_work_mass_plan(classified_work(parts=(), stocks=()))
    assert plan.status is MassCalculationStatus.AVAILABLE
    assert plan.totals is not None
    assert plan.totals.rectangular_part_mass_estimate_kg == 0
    assert plan.totals.gross_physical_allocation_mass_kg == 0


def test_WEIGHT_001_per_product_divides_batch_once() -> None:
    work = classified_work(
        batch=10,
        parts=(("p", 10, 10, 10),),
        stocks=(("s", 100, 100, 100, 100, 1.0, 2),),
    )
    plan = calculate_work_mass_plan(work)
    assert plan.totals is not None and plan.per_product is not None
    assert plan.per_product.rectangular_part_mass_estimate_kg == pytest.approx(
        plan.totals.rectangular_part_mass_estimate_kg / 10
    )
    assert plan.per_product.gross_physical_allocation_mass_kg == pytest.approx(
        plan.totals.gross_physical_allocation_mass_kg / 10
    )


def test_WEIGHT_001_stock_quantity_is_counted_exactly_once() -> None:
    single = calculate_work_mass_plan(
        classified_work(parts=(), stocks=(("s", 100, 100, 100, 100, 1.0, 1),))
    )
    triple = calculate_work_mass_plan(
        classified_work(parts=(), stocks=(("s", 100, 100, 100, 100, 1.0, 3),))
    )
    assert single.totals is not None and triple.totals is not None
    assert triple.totals.gross_physical_allocation_mass_kg == pytest.approx(
        single.totals.gross_physical_allocation_mass_kg * 3
    )


def test_mass_plan_is_immutable() -> None:
    plan = calculate_work_mass_plan(classified_work())
    with pytest.raises(FrozenInstanceError):
        plan.status = MassCalculationStatus.PARTIAL_RESULT  # type: ignore[misc]


def test_WEIGHT_001_many_small_rows_remain_finite_and_order_independent() -> None:
    parts = tuple((f"p-{index:04}", 0.1 + index / 10000, 0.2, 1) for index in range(500))
    forward = calculate_work_mass_plan(classified_work(parts=parts))
    backward = calculate_work_mass_plan(classified_work(parts=tuple(reversed(parts))))
    assert forward.totals == backward.totals


def test_WEIGHT_001_large_finite_dimensions_produce_finite_mass() -> None:
    plan = calculate_work_mass_plan(
        classified_work(
            density=20,
            thickness=100,
            parts=(("large", 1_000_000, 1_000_000, 1),),
            stocks=(("large", 1_000_000, 1_000_000, 1_000_000, 1_000_000, 1.0, 1),),
        )
    )
    assert plan.totals is not None
    assert plan.totals.rectangular_part_mass_estimate_kg == pytest.approx(2_000_000_000)


def test_WEIGHT_001_avoids_intermediate_overflow_when_final_mass_is_finite() -> None:
    plan = calculate_work_mass_plan(
        classified_work(
            density=1,
            thickness=1e-200,
            parts=(("scaled", 1e200, 1e200, 1),),
            stocks=(("scaled", 1e200, 1e200, 1e200, 1e200, 1.0, 1),),
        )
    )
    assert plan.totals is not None
    assert plan.totals.rectangular_part_mass_estimate_kg == pytest.approx(1e194)


def test_WEIGHT_001_very_small_valid_thickness_keeps_nonzero_mass() -> None:
    plan = calculate_work_mass_plan(
        classified_work(
            density=1,
            thickness=1e-100,
            parts=(("small-thickness", 1, 1, 1),),
            stocks=(("s", 1, 1, 1, 1, 1.0, 1),),
        )
    )
    assert plan.totals is not None
    assert plan.totals.rectangular_part_mass_estimate_kg == pytest.approx(1e-106)


def test_WEIGHT_001_normalized_output_is_independent_of_python_hash_seed() -> None:
    script = """
import json
from dataclasses import asdict
from tests.mass.helpers import classified_work
from debbie.mass import calculate_work_mass_plan
work = classified_work(
    batch=7,
    parts=((\"b\", 20, 30, 2), (\"a\", 10, 10, 3)),
    stocks=((\"b\", 200, 100, 100, 100, 1.0, 2), (\"a\", 100, 100, 50, 100, 0.75, 3)),
)
plan = calculate_work_mass_plan(work)
print(json.dumps({\"status\": plan.status.value, \"totals\": asdict(plan.totals), \"per_product\": asdict(plan.per_product)}, sort_keys=True))
"""
    outputs = []
    for seed in ("1", "777"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        source_path = str(Path.cwd() / "src")
        environment["PYTHONPATH"] = os.pathsep.join(
            value for value in (source_path, environment.get("PYTHONPATH", "")) if value
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path.cwd(),
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(json.loads(completed.stdout))
    assert outputs[0] == outputs[1]
