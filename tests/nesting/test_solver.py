from __future__ import annotations

from dataclasses import replace

import pytest

from debbie.domain import (
    DemandItem,
    DemandItemId,
    Dimensions,
    Layout,
    LayoutId,
    Orientation,
    PartType,
    PartTypeId,
    ProcessProfile,
    StockInstance,
    StockInstanceId,
    StockSpecification,
    StockSpecificationId,
    Trim,
    Work,
    WorkId,
)
from debbie.geometry import validate_layout_geometry
from debbie.domain.errors import DomainValidationError
from debbie.nesting import (
    DECISION_POLICY_VERSION,
    ENGINE_VERSION,
    FEASIBILITY_CLASS,
    NestingCancelledError,
    STRATEGY_DISPLAY_NAME,
    STRATEGY_ID,
    LeftToRightNestingSolver,
    ObjectiveMetadata,
    ResultStatus,
    UnplacedReasonCode,
    nest_work,
    objective_is_better,
)
from debbie.nesting.candidates import (
    first_valid_placement_candidate,
    iter_placement_candidates,
    valid_placement_candidates,
)
from debbie.nesting.validation import validate_work_for_nesting


def _work(
    *,
    work_id: str = "work",
    parts: tuple[tuple, ...] = (("p", "Part", 10, 10, 1, (0, 90)),),
    stocks: tuple[tuple, ...] = (("s", "Sheet", 100, 100, 1),),
    process: ProcessProfile = ProcessProfile(),
    batch: int = 1,
) -> Work:
    owner = WorkId(work_id)
    part_types = tuple(
        PartType(
            PartTypeId(identifier),
            name,
            Dimensions(length, width),
            frozenset(Orientation(value) for value in orientations),
        )
        for identifier, name, length, width, _, orientations in parts
    )
    demands = tuple(
        DemandItem(DemandItemId(f"d-{identifier}"), owner, PartTypeId(identifier), quantity)
        for identifier, _, _, _, quantity, _ in parts
    )
    specifications = tuple(
        StockSpecification(StockSpecificationId(identifier), name, Dimensions(length, width))
        for identifier, name, length, width, _ in stocks
    )
    instances = tuple(
        StockInstance(
            StockInstanceId(f"{identifier}-{sequence}"),
            owner,
            StockSpecificationId(identifier),
            sequence,
        )
        for identifier, _, _, _, quantity in stocks
        for sequence in range(1, quantity + 1)
    )
    return Work.from_inputs(
        id=owner,
        name=f"Work {work_id}",
        batch_multiplier=batch,
        process_profile=process,
        part_types=part_types,
        demand_items=demands,
        stock_specifications=specifications,
        stock_instances=instances,
    )


def _placements(result) -> tuple[tuple[str, float, float, int], ...]:
    return tuple(
        (
            str(layout.stock_instance_id),
            placement.x,
            placement.y,
            placement.orientation.value,
        )
        for layout in result.layouts
        for placement in layout.placements
    )


def _snapshot(result) -> tuple:
    return (
        result.status.value,
        tuple(
            (
                str(layout.stock_instance_id),
                tuple(
                    (
                        str(item.part_instance_id),
                        item.x,
                        item.y,
                        item.orientation.value,
                    )
                    for item in layout.placements
                ),
            )
            for layout in result.layouts
        ),
        result.objective,
        result.unplaced_demand,
        result.engine_version,
        result.decision_policy_version,
    )


def test_empty_valid_work_is_complete() -> None:
    result = nest_work(_work(parts=(), stocks=()))
    assert result.status is ResultStatus.COMPLETE
    assert result.requested_part_count == result.placed_part_count == 0
    assert result.layouts == result.unplaced_demand == ()


def test_one_part_on_one_stock_sheet_exact_fit() -> None:
    result = nest_work(_work(parts=(("p", "Part", 10, 5, 1, (0,)),), stocks=(("s", "Sheet", 10, 5, 1),)))
    assert result.status is ResultStatus.COMPLETE
    assert _placements(result) == (("s-1", 0.0, 0.0, 0),)


def test_multiple_identical_parts_follow_left_to_right_coordinates() -> None:
    result = nest_work(_work(parts=(("p", "Part", 10, 10, 4, (0,)),), stocks=(("s", "Sheet", 20, 20, 1),)))
    assert _placements(result) == (
        ("s-1", 0.0, 0.0, 0),
        ("s-1", 0.0, 10.0, 0),
        ("s-1", 10.0, 0.0, 0),
        ("s-1", 10.0, 10.0, 0),
    )


def test_larger_part_type_is_normalized_before_smaller_type() -> None:
    work = _work(
        parts=(("small", "Small", 2, 2, 1, (0,)), ("large", "Large", 8, 8, 1, (0,))),
        stocks=(("s", "Sheet", 10, 10, 1),),
    )
    result = nest_work(work)
    placed_ids = [placement.part_instance_id for placement in result.layouts[0].placements]
    placed_types = [
        next(item.part_type_id for item in work.part_instances if item.id == identifier)
        for identifier in placed_ids
    ]
    assert placed_types == [PartTypeId("large"), PartTypeId("small")]


def test_rotation_is_used_when_zero_degrees_does_not_fit() -> None:
    result = nest_work(_work(parts=(("p", "Part", 4, 3, 1, (0, 90)),), stocks=(("s", "Sheet", 3, 4, 1),)))
    assert _placements(result) == (("s-1", 0.0, 0.0, 90),)


def test_asymmetric_trim_reduces_usable_region_without_offsetting_origin() -> None:
    process = ProcessProfile(trim=Trim(left=1, right=1, top=2, bottom=0))
    result = nest_work(_work(parts=(("p", "Part", 10, 10, 1, (0,)),), stocks=(("s", "Sheet", 12, 12, 1),), process=process))
    assert _placements(result) == (("s-1", 0.0, 0.0, 0),)


def test_positive_boundary_clearance_sets_candidate_origin() -> None:
    result = nest_work(_work(parts=(("p", "Part", 8, 8, 1, (0,)),), stocks=(("s", "Sheet", 10, 10, 1),), process=ProcessProfile(boundary_clearance=1)))
    assert _placements(result) == (("s-1", 1.0, 1.0, 0),)


def test_positive_part_clearance_is_used_in_edge_candidates() -> None:
    result = nest_work(_work(parts=(("p", "Part", 5, 5, 2, (0,)),), stocks=(("s", "Sheet", 11, 11, 1),), process=ProcessProfile(minimum_part_clearance=1)))
    assert _placements(result) == (("s-1", 0.0, 0.0, 0), ("s-1", 0.0, 6.0, 0))


def test_zero_clearance_allows_exact_finished_edge_contact() -> None:
    result = nest_work(_work(parts=(("p", "Part", 5, 5, 2, (0,)),), stocks=(("s", "Sheet", 5, 10, 1),)))
    assert _placements(result)[1][1:3] == (0.0, 5.0)


def test_tolerance_edge_fit_uses_central_geometry_epsilon() -> None:
    result = nest_work(_work(parts=(("p", "Part", 10.0005, 5, 1, (0,)),), stocks=(("s", "Sheet", 10, 5, 1),)))
    assert result.status is ResultStatus.COMPLETE


def test_multiple_stock_sizes_prefer_one_sheet_capacity_before_area() -> None:
    result = nest_work(
        _work(
            parts=(("p", "Part", 6, 6, 2, (0,)),),
            stocks=(("small", "Small", 6, 6, 1), ("large", "Large", 6, 12, 1)),
        )
    )
    assert len(result.layouts) == 1
    assert result.layouts[0].stock_instance_id == StockInstanceId("large-1")


def test_multiple_physical_stock_instances_are_each_consumed_once() -> None:
    result = nest_work(_work(parts=(("p", "Part", 4, 4, 2, (0,)),), stocks=(("s", "Sheet", 4, 4, 2),)))
    assert [layout.stock_instance_id for layout in result.layouts] == [
        StockInstanceId("s-1"),
        StockInstanceId("s-2"),
    ]


def test_equal_capacity_unopened_stock_prefers_smaller_nominal_area() -> None:
    result = nest_work(
        _work(
            parts=(("p", "Part", 4, 4, 1, (0,)),),
            stocks=(("large", "Large", 10, 10, 1), ("small", "Small", 5, 5, 1)),
        )
    )
    assert result.layouts[0].stock_instance_id == StockInstanceId("small-1")


def test_work_batch_multiplier_is_expanded_exactly_for_solver_demand() -> None:
    result = nest_work(
        _work(
            parts=(("p", "Part", 2, 2, 2, (0,)),),
            stocks=(("s", "Sheet", 10, 10, 1),),
            batch=3,
        )
    )
    assert result.requested_part_count == result.placed_part_count == 6


def test_kerf_does_not_inflate_solver_geometry() -> None:
    inputs = dict(
        parts=(("p", "Part", 5, 5, 2, (0,)),),
        stocks=(("s", "Sheet", 5, 10, 1),),
    )
    zero = nest_work(_work(**inputs, process=ProcessProfile(kerf=0)))
    wide = nest_work(_work(**inputs, process=ProcessProfile(kerf=8)))
    assert _placements(zero) == _placements(wide)


def test_input_work_remains_unchanged() -> None:
    work = _work(parts=(("p", "Part", 5, 5, 3, (0,)),), stocks=(("s", "Sheet", 10, 10, 1),))
    original = work
    nest_work(work)
    assert work == original
    assert work.layouts == ()


def test_NEST_001_result_declares_non_guillotine_feasibility() -> None:
    result = nest_work(_work())
    assert result.feasibility.classification == FEASIBILITY_CLASS
    assert result.feasibility.rectangular and result.feasibility.collision_free
    assert result.feasibility.non_guillotine
    assert not result.feasibility.has_toolpath and not result.feasibility.machine_ready


def test_NEST_002_candidate_order_prefers_smallest_x_then_y() -> None:
    result = nest_work(_work(parts=(("p", "Part", 5, 5, 3, (0,)),), stocks=(("s", "Sheet", 10, 10, 1),)))
    assert [(item.x, item.y) for item in result.layouts[0].placements] == [
        (0.0, 0.0),
        (0.0, 5.0),
        (5.0, 0.0),
    ]


def test_NEST_002_non_rotated_wins_only_after_x_and_y_tie() -> None:
    tie = nest_work(_work(parts=(("p", "Part", 4, 6, 1, (0, 90)),), stocks=(("s", "Sheet", 10, 10, 1),)))
    assert tie.layouts[0].placements[0].orientation is Orientation.ZERO

    earlier_x = nest_work(
        _work(
            parts=(("block", "A Block", 4, 6, 1, (0,)), ("choice", "B Choice", 4, 6, 1, (0, 90))),
            stocks=(("s", "Sheet", 10, 10, 1),),
        )
    )
    choice = earlier_x.layouts[0].placements[1]
    assert (choice.x, choice.y, choice.orientation) == (0.0, 6.0, Orientation.DEG_90)


def test_NEST_002_input_order_does_not_change_result() -> None:
    parts = (("a", "A", 7, 4, 1, (0, 90)), ("b", "B", 3, 3, 2, (0, 90)))
    stocks = (("small", "Small", 8, 8, 1), ("large", "Large", 12, 8, 1))
    first = nest_work(_work(parts=parts, stocks=stocks))
    second = nest_work(_work(parts=tuple(reversed(parts)), stocks=tuple(reversed(stocks))))
    assert _snapshot(first) == _snapshot(second)


def test_NEST_002_strategy_never_bypasses_geometry_validation(monkeypatch) -> None:
    import debbie.nesting.candidates as candidate_module
    import debbie.nesting.solver as solver_module

    original_incremental = candidate_module.satisfies_minimum_clearance
    original_complete = solver_module.validate_layout_geometry
    incremental_calls = 0
    complete_calls = 0

    def tracked_incremental(*args, **kwargs):
        nonlocal incremental_calls
        incremental_calls += 1
        return original_incremental(*args, **kwargs)

    def tracked_complete(*args, **kwargs):
        nonlocal complete_calls
        complete_calls += 1
        return original_complete(*args, **kwargs)

    monkeypatch.setattr(
        candidate_module, "satisfies_minimum_clearance", tracked_incremental
    )
    monkeypatch.setattr(solver_module, "validate_layout_geometry", tracked_complete)
    result = nest_work(_work(parts=(("p", "Part", 5, 5, 2, (0,)),), stocks=(("s", "Sheet", 10, 5, 1),)))
    assert result.status is ResultStatus.COMPLETE
    assert incremental_calls > 0
    assert complete_calls >= result.placed_part_count + len(result.layouts)


def _candidate_review_context():
    work = _work(
        parts=(("p", "Part", 4, 3, 3, (0, 90)),),
        stocks=(("s", "Sheet", 10, 10, 1),),
        process=ProcessProfile(minimum_part_clearance=0.5),
    )
    prepared = validate_work_for_nesting(work)
    solved = nest_work(work)
    partial = replace(solved.layouts[0], placements=solved.layouts[0].placements[:2])
    placed_ids = {item.part_instance_id for item in partial.placements}
    next_instance = next(
        item for item in prepared.ordered_part_instances if item.id not in placed_ids
    )
    stock = prepared.stock_instances[partial.stock_instance_id]
    specification = prepared.stock_specifications[stock.specification_id]
    arguments = dict(
        part_instance=next_instance,
        part_type=prepared.part_types[next_instance.part_type_id],
        stock_specification=specification,
        part_instances=prepared.part_instances,
        part_types=prepared.part_types,
        oriented_dimensions=prepared.oriented_dimensions,
        effective_region=prepared.effective_regions[specification.id],
    )
    return partial, stock, specification, prepared, arguments


def test_lazy_candidate_search_matches_full_ordered_enumeration() -> None:
    layout, _, _, _, arguments = _candidate_review_context()
    materialized = valid_placement_candidates(layout, **arguments)
    lazy_first = first_valid_placement_candidate(layout, **arguments)
    assert materialized
    assert lazy_first == materialized[0]
    assert tuple(item.ranking_key for item in materialized) == tuple(
        sorted(item.ranking_key for item in materialized)
    )


def test_incremental_candidate_validation_matches_complete_validator_without_pruning() -> None:
    layout, stock, specification, prepared, arguments = _candidate_review_context()
    incremental = valid_placement_candidates(layout, **arguments)
    complete = []
    for candidate in iter_placement_candidates(layout, **arguments):
        candidate_layout = replace(
            layout, placements=(*layout.placements, candidate.placement)
        )
        try:
            validate_layout_geometry(
                candidate_layout,
                stock_instance=stock,
                stock_specification=specification,
                part_instances=prepared.part_instances,
                part_types=prepared.part_types,
            )
        except DomainValidationError:
            continue
        complete.append(candidate)
    assert tuple(item.ranking_key for item in incremental) == tuple(
        item.ranking_key for item in complete
    )


def test_equivalent_physical_stock_reuses_simulation_without_changing_identity(monkeypatch) -> None:
    calls = 0
    original = LeftToRightNestingSolver._simulate_sheet

    def tracked(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(LeftToRightNestingSolver, "_simulate_sheet", tracked)
    result = LeftToRightNestingSolver().solve(
        _work(
            parts=(("p", "Part", 4, 4, 2, (0,)),),
            stocks=(("s", "Sheet", 4, 4, 3),),
        )
    )
    assert calls == 2
    assert [layout.stock_instance_id for layout in result.layouts] == [
        StockInstanceId("s-1"),
        StockInstanceId("s-2"),
    ]


def test_simulation_cache_is_scoped_to_one_solve(monkeypatch) -> None:
    calls = 0
    original = LeftToRightNestingSolver._simulate_sheet

    def tracked(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(LeftToRightNestingSolver, "_simulate_sheet", tracked)
    solver = LeftToRightNestingSolver()
    work = _work(stocks=(("s", "Sheet", 100, 100, 2),))
    first = solver.solve(work)
    second = solver.solve(work)
    assert calls == 2
    assert _snapshot(first) == _snapshot(second)


def test_uncancelled_callback_does_not_change_deterministic_result() -> None:
    work = _work(
        parts=(("p", "Part", 7, 4, 8, (0, 90)),),
        stocks=(("s", "Sheet", 20, 20, 3),),
    )
    assert _snapshot(nest_work(work)) == _snapshot(
        nest_work(work, cancellation_check=lambda: None)
    )


def _objective(*, placed: int, sheets: int, area: float, unused: float) -> ObjectiveMetadata:
    return ObjectiveMetadata(
        placed_required_demand=placed,
        physical_stock_sheets_consumed=sheets,
        nominal_full_stock_area_consumed=area,
        unused_usable_area=unused,
    )


def test_OPT_001_placed_demand_precedes_sheet_count() -> None:
    assert objective_is_better(
        _objective(placed=10, sheets=3, area=300, unused=100),
        _objective(placed=9, sheets=1, area=100, unused=0),
    )


def test_OPT_001_sheet_count_precedes_full_stock_area() -> None:
    assert objective_is_better(
        _objective(placed=10, sheets=1, area=500, unused=400),
        _objective(placed=10, sheets=2, area=200, unused=0),
    )


def test_OPT_001_full_stock_area_precedes_unused_usable_area() -> None:
    assert objective_is_better(
        _objective(placed=10, sheets=1, area=200, unused=100),
        _objective(placed=10, sheets=1, area=300, unused=0),
    )


def test_OPT_001_result_records_objective_values() -> None:
    result = nest_work(_work(parts=(("p", "Part", 5, 5, 1, (0,)),), stocks=(("s", "Sheet", 10, 10, 1),)))
    assert result.objective.placed_required_demand == 1
    assert result.objective.physical_stock_sheets_consumed == 1
    assert result.objective.nominal_full_stock_area_consumed == 100
    assert result.objective.unused_usable_area == 75


def test_OPT_001_no_weighted_score_or_optimality_claim() -> None:
    objective = nest_work(_work()).objective
    assert not hasattr(objective, "weighted_score")
    assert not objective.globally_optimal
    assert "optimal" not in objective.result_description.casefold()


def test_OPT_002_same_input_produces_same_result() -> None:
    work = _work(parts=(("p", "Part", 7, 3, 5, (0, 90)),), stocks=(("s", "Sheet", 15, 15, 2),))
    assert _snapshot(nest_work(work)) == _snapshot(nest_work(work))


def test_OPT_002_reordered_equivalent_input_produces_same_result() -> None:
    test_NEST_002_input_order_does_not_change_result()


def test_OPT_002_result_does_not_depend_on_uuid_sort_order() -> None:
    result = nest_work(
        _work(
            parts=(("000-small", "Small", 2, 2, 1, (0,)), ("zzz-large", "Large", 8, 8, 1, (0,))),
            stocks=(("s", "Sheet", 8, 8, 1),),
        )
    )
    placed = result.layouts[0].placements[0].part_instance_id
    assert "zzz-large" in str(
        next(instance.part_type_id for instance in _work(
            parts=(("000-small", "Small", 2, 2, 1, (0,)), ("zzz-large", "Large", 8, 8, 1, (0,))),
            stocks=(("s", "Sheet", 8, 8, 1),),
        ).part_instances if instance.id == placed)
    )


def test_OPT_002_metadata_records_engine_and_policy_versions() -> None:
    result = nest_work(_work())
    assert (result.engine_version, result.decision_policy_version) == (
        ENGINE_VERSION,
        DECISION_POLICY_VERSION,
    )
    assert (result.strategy_id, result.strategy_display_name) == (
        STRATEGY_ID,
        STRATEGY_DISPLAY_NAME,
    )


def test_NEST_003_partial_result_reconciles_unplaced_quantity() -> None:
    result = nest_work(_work(parts=(("p", "Part", 4, 4, 3, (0,)),), stocks=(("s", "Sheet", 4, 4, 2),)))
    assert result.status is ResultStatus.PARTIAL
    assert result.requested_part_count == result.placed_part_count + sum(
        item.remaining_quantity for item in result.unplaced_demand
    )


def test_oversized_part_reason_is_structured() -> None:
    result = nest_work(_work(parts=(("p", "Part", 5, 5, 1, (0, 90)),), stocks=(("s", "Sheet", 4, 4, 1),)))
    assert result.unplaced_demand[0].reason_code is UnplacedReasonCode.PART_EXCEEDS_ALL_USABLE_STOCK


def test_insufficient_physical_stock_reason_is_structured() -> None:
    result = nest_work(_work(parts=(("p", "Part", 4, 4, 2, (0,)),), stocks=(("s", "Sheet", 4, 4, 1),)))
    assert result.unplaced_demand[0].reason_code is UnplacedReasonCode.INSUFFICIENT_STOCK_QUANTITY


def test_forbidden_rotation_reason_precedes_oversized_reason() -> None:
    result = nest_work(_work(parts=(("p", "Part", 4, 3, 1, (0,)),), stocks=(("s", "Sheet", 3, 4, 1),)))
    assert result.unplaced_demand[0].reason_code is UnplacedReasonCode.ORIENTATION_CONSTRAINT


def test_arrangement_failure_has_no_valid_placement_reason() -> None:
    result = nest_work(
        _work(
            parts=(("a", "A", 4, 3, 1, (0,)), ("b", "B", 3, 4, 1, (0,))),
            stocks=(("s", "Sheet", 6, 6, 1),),
        )
    )
    assert result.unplaced_demand[0].reason_code is UnplacedReasonCode.NO_VALID_PLACEMENT_FOUND


def test_invalid_existing_layout_state_fails_before_run() -> None:
    work = _work()
    layout = Layout(
        LayoutId("existing"),
        work.id,
        work.stock_instances[0].id,
        work.process_profile,
    )
    invalid_solver_input = replace(work, layouts=(layout,))
    result = nest_work(invalid_solver_input)
    assert result.status is ResultStatus.FAILED_VALIDATION
    assert result.layouts == ()
    assert result.diagnostics[0].reason_code is UnplacedReasonCode.INVALID_INPUT_REJECTED_BEFORE_RUN


def test_invalid_process_profile_fails_before_placement() -> None:
    work = _work()
    malformed = replace(work, process_profile="not-a-process-profile")  # type: ignore[arg-type]
    result = nest_work(malformed)
    assert result.status is ResultStatus.FAILED_VALIDATION
    assert result.layouts == ()


def test_orientation_set_outside_ROT_001_fails_before_placement() -> None:
    work = _work(parts=(("p", "Part", 4, 3, 1, (90,)),))
    result = nest_work(work)
    assert result.status is ResultStatus.FAILED_VALIDATION
    assert result.layouts == ()


def test_complete_result_has_no_unplaced_demand() -> None:
    result = nest_work(_work())
    assert result.status is ResultStatus.COMPLETE
    assert result.unplaced_demand == ()


def test_work_isolation_and_solver_state_do_not_cross_runs() -> None:
    first = nest_work(_work(work_id="first"))
    second = nest_work(_work(work_id="second"))
    assert all(layout.work_id == WorkId("first") for layout in first.layouts)
    assert all(layout.work_id == WorkId("second") for layout in second.layouts)
    assert {layout.stock_instance_id for layout in first.layouts} == {StockInstanceId("s-1")}
    assert _snapshot(first)[0] == _snapshot(nest_work(_work(work_id="first")))[0]


def test_cancellation_callback_is_an_active_synchronous_boundary() -> None:
    calls = 0

    def cancel() -> None:
        nonlocal calls
        calls += 1
        raise NestingCancelledError("cancelled for test")

    with pytest.raises(NestingCancelledError):
        nest_work(_work(), cancellation_check=cancel)
    assert calls == 1


def test_per_demand_and_part_type_reconciliation() -> None:
    work = _work(
        parts=(("a", "A", 4, 4, 2, (0,)), ("b", "B", 3, 3, 3, (0,))),
        stocks=(("s", "Sheet", 4, 4, 2),),
    )
    result = nest_work(work)
    requested = {demand.id: demand.base_quantity for demand in work.demand_items}
    placed = {demand.id: 0 for demand in work.demand_items}
    instance_by_id = {instance.id: instance for instance in work.part_instances}
    for layout in result.layouts:
        for placement in layout.placements:
            placed[instance_by_id[placement.part_instance_id].demand_item_id] += 1
    unplaced = {demand.id: 0 for demand in work.demand_items}
    for item in result.unplaced_demand:
        unplaced[item.demand_item_id] += item.remaining_quantity
    assert requested == {key: placed[key] + unplaced[key] for key in requested}


def test_every_result_layout_passes_complete_shared_validator() -> None:
    work = _work(parts=(("p", "Part", 3, 2, 10, (0, 90)),), stocks=(("s", "Sheet", 10, 10, 2),), process=ProcessProfile(minimum_part_clearance=0.5))
    result = nest_work(work)
    stocks = {item.id: item for item in work.stock_instances}
    specifications = {item.id: item for item in work.stock_specifications}
    instances = {item.id: item for item in work.part_instances}
    part_types = {item.id: item for item in work.part_types}
    for layout in result.layouts:
        stock = stocks[layout.stock_instance_id]
        validate_layout_geometry(
            layout,
            stock_instance=stock,
            stock_specification=specifications[stock.specification_id],
            part_instances=instances,
            part_types=part_types,
        )


def test_physical_part_instances_are_unique_across_layouts() -> None:
    result = nest_work(_work(parts=(("p", "Part", 4, 4, 5, (0,)),), stocks=(("s", "Sheet", 4, 4, 5),)))
    identifiers = [placement.part_instance_id for layout in result.layouts for placement in layout.placements]
    assert len(identifiers) == len(set(identifiers)) == 5


@pytest.mark.parametrize(
    ("work", "expected"),
    (
        (_work(parts=(("p", "Exact", 5, 5, 1, (0,)),), stocks=(("s", "Sheet", 5, 5, 1),)), ("COMPLETE", (("s-1", 0.0, 0.0, 0),), ())),
        (_work(parts=(("p", "Left", 5, 5, 3, (0,)),), stocks=(("s", "Sheet", 10, 10, 1),)), ("COMPLETE", (("s-1", 0.0, 0.0, 0), ("s-1", 0.0, 5.0, 0), ("s-1", 5.0, 0.0, 0)), ())),
        (_work(parts=(("p", "Rotate", 4, 3, 1, (0, 90)),), stocks=(("s", "Sheet", 3, 4, 1),)), ("COMPLETE", (("s-1", 0.0, 0.0, 90),), ())),
        (_work(parts=(("p", "Multi", 4, 4, 2, (0,)),), stocks=(("s", "Sheet", 4, 4, 2),)), ("COMPLETE", (("s-1", 0.0, 0.0, 0), ("s-2", 0.0, 0.0, 0)), ())),
        (_work(parts=(("p", "Partial", 5, 5, 2, (0,)),), stocks=(("s", "Sheet", 5, 5, 1),)), ("PARTIAL", (("s-1", 0.0, 0.0, 0),), ("INSUFFICIENT_STOCK_QUANTITY",))),
    ),
)
def test_code_defined_golden_results(work: Work, expected: tuple) -> None:
    result = nest_work(work)
    actual = (
        result.status.value,
        _placements(result),
        tuple(item.reason_code.value for item in result.unplaced_demand),
    )
    assert actual == expected


def test_tens_scale_sanity_without_timing_threshold() -> None:
    result = nest_work(_work(parts=(("p", "Part", 10, 10, 25, (0,)),), stocks=(("s", "Sheet", 50, 50, 1),)))
    assert result.status is ResultStatus.COMPLETE
    assert result.placed_part_count == 25
