from dataclasses import replace

import pytest

from debbie.mass import (
    MassCalculationDiagnosticCode,
    MassCalculationStatus,
    calculate_nesting_result_mass,
)
from debbie.domain import (
    DemandItemId,
    Layout,
    LayoutId,
    PartInstanceId,
    Placement,
    ProcessProfile,
    StockInstanceId,
    Trim,
)
from debbie.nesting import LeftToRightNestingSolver, ResultStatus
from debbie.nesting.models import (
    FeasibilityMetadata,
    NestingResult,
    ObjectiveMetadata,
    UnplacedDemand,
    UnplacedReasonCode,
    ValidationDiagnostic,
)

from .helpers import classified_work


def test_WEIGHT_001_complete_result_uses_consumed_stock_only() -> None:
    work = classified_work(
        batch=2,
        parts=(("p", 10, 10, 1),),
        stocks=(("s", 100, 100, 100, 100, 1.0, 3),),
    )
    nesting = LeftToRightNestingSolver().solve(work)
    result = calculate_nesting_result_mass(work, nesting)
    assert nesting.status is ResultStatus.COMPLETE
    assert result.status is MassCalculationStatus.AVAILABLE
    assert result.totals is not None and result.per_product is not None
    one_sheet_mass = 100 * 100 * 3 * 7.9 / 1_000_000
    assert result.totals.gross_physical_allocation_mass_kg == pytest.approx(one_sheet_mass)
    assert result.totals.physical_equivalent_sheets == 1
    assert result.per_product.gross_physical_allocation_mass_kg == pytest.approx(
        one_sheet_mass / 2
    )


def test_ALLOCATION_001_solver_uses_allocated_geometry_but_objective_keeps_full_area() -> None:
    work = classified_work(
        parts=(("p", 100, 100, 1),),
        stocks=(("partial", 200, 100, 100, 100, 1.0, 1),),
    )
    nesting = LeftToRightNestingSolver().solve(work)
    assert nesting.status is ResultStatus.COMPLETE
    assert nesting.objective.nominal_full_stock_area_consumed == 20_000
    assert nesting.layouts[0].placements[0].x == 0
    assert nesting.layouts[0].placements[0].y == 0


def test_ALLOCATION_001_equal_allocations_retain_nominal_full_stock_priority() -> None:
    work = classified_work(
        parts=(("p", 50, 50, 1),),
        stocks=(
            ("large-source", 300, 100, 100, 100, 1.0, 1),
            ("small-source", 200, 100, 100, 100, 1.0, 1),
        ),
    )
    nesting = LeftToRightNestingSolver().solve(work)
    assert str(nesting.layouts[0].stock_instance_id) == "small-source-1"


def test_ALLOCATION_001_full_classified_stock_matches_equivalent_legacy_placements() -> None:
    classified = classified_work(
        parts=(("p", 30, 20, 5),),
        stocks=(("s", 100, 100, 100, 100, 1.0, 1),),
    )
    legacy_specifications = tuple(
        replace(specification, allocation=None)
        for specification in classified.stock_specifications
    )
    legacy = replace(
        classified,
        stock_specifications=legacy_specifications,
        material=None,
        thickness=None,
    )
    classified_result = LeftToRightNestingSolver().solve(classified)
    legacy_result = LeftToRightNestingSolver().solve(legacy)
    classified_placements = tuple(
        (placement.x, placement.y, placement.orientation)
        for layout in classified_result.layouts
        for placement in layout.placements
    )
    legacy_placements = tuple(
        (placement.x, placement.y, placement.orientation)
        for layout in legacy_result.layouts
        for placement in layout.placements
    )
    assert classified_placements == legacy_placements


def test_ALLOCATION_001_half_sheet_cannot_place_in_unallocated_half() -> None:
    work = classified_work(
        parts=(("p", 150, 100, 1),),
        stocks=(("half", 200, 100, 100, 100, 1.0, 1),),
    )
    nesting = LeftToRightNestingSolver().solve(work)
    assert nesting.status is ResultStatus.PARTIAL
    assert nesting.placed_part_count == 0
    assert nesting.layouts == ()


def test_ALLOCATION_001_partial_stock_with_trim_is_isolated_until_policy_is_approved() -> None:
    base = classified_work(
        parts=(("p", 20, 20, 1),),
        stocks=(("half", 200, 100, 100, 100, 1.0, 1),),
    )
    work = replace(base, process_profile=ProcessProfile(trim=Trim(left=1)))
    nesting = LeftToRightNestingSolver().solve(work)
    assert nesting.status is ResultStatus.FAILED_VALIDATION
    assert "not approved" in nesting.diagnostics[0].message


def test_ALLOCATION_001_partial_stock_with_boundary_clearance_is_also_isolated() -> None:
    base = classified_work(
        parts=(("p", 20, 20, 1),),
        stocks=(("half", 200, 100, 100, 100, 1.0, 1),),
    )
    work = replace(base, process_profile=ProcessProfile(boundary_clearance=1))
    assert LeftToRightNestingSolver().solve(work).status is ResultStatus.FAILED_VALIDATION


def test_WEIGHT_001_complete_placed_mass_reconciles_expanded_demand() -> None:
    work = classified_work(batch=3, parts=(("p", 10, 20, 2),))
    result = calculate_nesting_result_mass(work, LeftToRightNestingSolver().solve(work))
    assert result.totals is not None
    expected = 10 * 20 * 3 * 7.9 * 6 / 1_000_000
    assert result.totals.placed_rectangular_part_mass_estimate_kg == pytest.approx(expected)
    assert result.totals.unplaced_rectangular_part_mass_estimate_kg == 0


def test_WEIGHT_001_partial_result_keeps_batch_totals_and_withholds_per_product() -> None:
    work = classified_work(
        parts=(("p", 60, 60, 2),),
        stocks=(("s", 100, 100, 100, 100, 1.0, 1),),
    )
    nesting = LeftToRightNestingSolver().solve(work)
    reasons_before = nesting.unplaced_demand
    result = calculate_nesting_result_mass(work, nesting)
    assert nesting.status is ResultStatus.PARTIAL
    assert result.status is MassCalculationStatus.PARTIAL_RESULT
    assert result.totals is not None
    assert result.totals.placed_rectangular_part_mass_estimate_kg > 0
    assert result.totals.unplaced_rectangular_part_mass_estimate_kg > 0
    assert result.per_product is None
    assert nesting.unplaced_demand == reasons_before


def test_WEIGHT_001_failed_validation_returns_no_consumption_totals() -> None:
    work = classified_work()
    nesting = NestingResult(
        work_id=work.id,
        status=ResultStatus.FAILED_VALIDATION,
        strategy_id="left_to_right_rectangular_v1",
        strategy_display_name="Deterministic Left-to-Right Rectangular Placement",
        engine_version="test",
        decision_policy_version="test",
        layouts=(),
        placed_part_count=0,
        requested_part_count=0,
        unplaced_demand=(),
        objective=ObjectiveMetadata(),
        feasibility=FeasibilityMetadata(),
        diagnostics=(
            ValidationDiagnostic(
                UnplacedReasonCode.INVALID_INPUT_REJECTED_BEFORE_RUN,
                "invalid test input",
            ),
        ),
    )
    result = calculate_nesting_result_mass(work, nesting)
    assert result.status is MassCalculationStatus.FAILED_VALIDATION
    assert result.totals is result.per_product is None
    assert result.diagnostics[0].code is MassCalculationDiagnosticCode.FAILED_NESTING_VALIDATION
    assert result.diagnostics[0].message == "invalid test input"


def test_WEIGHT_001_work_result_mismatch_is_structured() -> None:
    first = classified_work(work_id="first")
    second = classified_work(work_id="second")
    nesting = LeftToRightNestingSolver().solve(first)
    result = calculate_nesting_result_mass(second, nesting)
    assert result.status is MassCalculationStatus.WORK_RESULT_MISMATCH
    assert result.totals is None
    assert result.diagnostics[0].code is MassCalculationDiagnosticCode.WORK_RESULT_MISMATCH


def test_WEIGHT_001_result_calculation_is_deterministic() -> None:
    work = classified_work(
        parts=(("b", 10, 20, 1), ("a", 5, 10, 2)),
        stocks=(("b", 100, 100, 100, 100, 1.0, 1), ("a", 50, 50, 50, 50, 1.0, 1)),
    )
    nesting = LeftToRightNestingSolver().solve(work)
    assert calculate_nesting_result_mass(work, nesting) == calculate_nesting_result_mass(
        work, nesting
    )


def test_WEIGHT_001_reordered_layouts_and_placements_produce_identical_mass() -> None:
    work = classified_work(
        parts=(("p", 40, 40, 6),),
        stocks=(("s", 100, 100, 100, 100, 1.0, 2),),
    )
    nesting = LeftToRightNestingSolver().solve(work)
    reordered_layouts = tuple(
        replace(layout, placements=tuple(reversed(layout.placements)))
        for layout in reversed(nesting.layouts)
    )
    reordered = replace(nesting, layouts=reordered_layouts)
    assert calculate_nesting_result_mass(work, nesting) == calculate_nesting_result_mass(
        work, reordered
    )


def test_WEIGHT_001_calculator_does_not_mutate_inputs() -> None:
    work = classified_work()
    nesting = LeftToRightNestingSolver().solve(work)
    work_snapshot = repr(work)
    result_snapshot = repr(nesting)
    calculate_nesting_result_mass(work, nesting)
    assert repr(work) == work_snapshot
    assert repr(nesting) == result_snapshot


def test_WEIGHT_001_stale_unplaced_demand_is_rejected() -> None:
    work = classified_work(
        parts=(("p", 60, 60, 2),),
        stocks=(("s", 100, 100, 100, 100, 1.0, 1),),
    )
    nesting = LeftToRightNestingSolver().solve(work)
    stale = replace(
        nesting,
        unplaced_demand=(
            replace(nesting.unplaced_demand[0], demand_item_id=DemandItemId("unknown")),
        ),
    )
    result = calculate_nesting_result_mass(work, stale)
    assert result.status is MassCalculationStatus.INVALID_RESULT
    assert result.diagnostics[0].code is MassCalculationDiagnosticCode.RESULT_DATA_MISMATCH


def test_WEIGHT_001_unplaced_quantities_reconcile_per_demand_not_only_by_mass() -> None:
    work = classified_work(
        parts=(("p", 60, 60, 2), ("q", 60, 60, 2)),
    )
    malformed = NestingResult(
        work_id=work.id,
        status=ResultStatus.PARTIAL,
        strategy_id="test",
        strategy_display_name="test",
        engine_version="test",
        decision_policy_version="test",
        layouts=(),
        placed_part_count=0,
        requested_part_count=4,
        unplaced_demand=(
            UnplacedDemand(
                work.id,
                DemandItemId("d-p"),
                work.demand_items[0].part_type_id,
                3,
                UnplacedReasonCode.INSUFFICIENT_STOCK_QUANTITY,
            ),
            UnplacedDemand(
                work.id,
                DemandItemId("d-q"),
                work.demand_items[1].part_type_id,
                1,
                UnplacedReasonCode.INSUFFICIENT_STOCK_QUANTITY,
            ),
        ),
        objective=ObjectiveMetadata(),
    )

    result = calculate_nesting_result_mass(work, malformed)

    assert result.status is MassCalculationStatus.INVALID_RESULT
    assert result.totals is None
    assert result.diagnostics[0].related_demand_item_id == DemandItemId("d-p")


def test_WEIGHT_001_unknown_placed_part_instance_is_rejected() -> None:
    work = classified_work()
    nesting = LeftToRightNestingSolver().solve(work)
    layout = nesting.layouts[0]
    original = layout.placements[0]
    changed_layout = replace(
        layout,
        placements=(
            Placement(
                PartInstanceId("unknown"),
                original.x,
                original.y,
                original.orientation,
            ),
        ),
    )
    stale = replace(nesting, layouts=(changed_layout,))
    result = calculate_nesting_result_mass(work, stale)
    assert result.status is MassCalculationStatus.INVALID_RESULT
    assert result.diagnostics[0].code is MassCalculationDiagnosticCode.RESULT_DATA_MISMATCH


def test_WEIGHT_001_duplicate_consumed_stock_is_rejected_once_not_double_counted() -> None:
    work = classified_work(parts=())
    stock_id = work.stock_instances[0].id
    layouts = (
        Layout(LayoutId("first"), work.id, stock_id, work.process_profile),
        Layout(LayoutId("second"), work.id, stock_id, work.process_profile),
    )
    nesting = NestingResult(
        work_id=work.id,
        status=ResultStatus.COMPLETE,
        strategy_id="test",
        strategy_display_name="test",
        engine_version="test",
        decision_policy_version="test",
        layouts=layouts,
        placed_part_count=0,
        requested_part_count=0,
        unplaced_demand=(),
        objective=ObjectiveMetadata(physical_stock_sheets_consumed=2),
    )
    result = calculate_nesting_result_mass(work, nesting)
    assert result.status is MassCalculationStatus.INVALID_RESULT
    assert result.totals is None
    assert result.diagnostics[0].related_stock_instance_id == stock_id


def test_WEIGHT_001_unknown_consumed_stock_is_rejected() -> None:
    work = classified_work(parts=())
    unknown_id = StockInstanceId("unknown")
    layout = Layout(LayoutId("unknown-layout"), work.id, unknown_id, work.process_profile)
    nesting = NestingResult(
        work_id=work.id,
        status=ResultStatus.COMPLETE,
        strategy_id="test",
        strategy_display_name="test",
        engine_version="test",
        decision_policy_version="test",
        layouts=(layout,),
        placed_part_count=0,
        requested_part_count=0,
        unplaced_demand=(),
        objective=ObjectiveMetadata(physical_stock_sheets_consumed=1),
    )
    result = calculate_nesting_result_mass(work, nesting)
    assert result.status is MassCalculationStatus.INVALID_RESULT
    assert result.diagnostics[0].related_stock_instance_id == unknown_id


def test_WEIGHT_001_empty_layout_is_an_explicit_consumed_stock_reference() -> None:
    work = classified_work(parts=())
    layout = Layout(
        LayoutId("empty-consumed"),
        work.id,
        work.stock_instances[0].id,
        work.process_profile,
    )
    nesting = NestingResult(
        work_id=work.id,
        status=ResultStatus.COMPLETE,
        strategy_id="test",
        strategy_display_name="test",
        engine_version="test",
        decision_policy_version="test",
        layouts=(layout,),
        placed_part_count=0,
        requested_part_count=0,
        unplaced_demand=(),
        objective=ObjectiveMetadata(physical_stock_sheets_consumed=1),
    )
    result = calculate_nesting_result_mass(work, nesting)
    assert result.status is MassCalculationStatus.AVAILABLE
    assert result.totals is not None
    assert result.totals.physical_equivalent_sheets == 1


def test_WEIGHT_001_malformed_complete_with_hidden_unplaced_demand_is_rejected() -> None:
    work = classified_work(
        parts=(("p", 60, 60, 2),),
        stocks=(("s", 100, 100, 100, 100, 1.0, 1),),
    )
    malformed = LeftToRightNestingSolver().solve(work)
    assert malformed.status is ResultStatus.PARTIAL
    object.__setattr__(malformed, "status", ResultStatus.COMPLETE)
    result = calculate_nesting_result_mass(work, malformed)
    assert result.status is MassCalculationStatus.INVALID_RESULT
    assert result.totals is None


def test_WEIGHT_001_unclassified_result_requires_material_data() -> None:
    classified = classified_work()
    legacy = replace(classified, material=None, thickness=None)
    nesting = LeftToRightNestingSolver().solve(legacy)
    result = calculate_nesting_result_mass(legacy, nesting)
    assert result.status is MassCalculationStatus.MATERIAL_DATA_REQUIRED
    assert result.totals is None
