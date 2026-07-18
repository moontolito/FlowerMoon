"""The single approved deterministic rectangle nesting strategy."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from uuid import NAMESPACE_URL

from debbie.domain import Layout, LayoutId, Orientation, PartInstance, PartType, Work
from debbie.geometry import (
    less_than_or_equal,
    usable_stock_rectangle,
    validate_layout_geometry,
)

from .candidates import PlacementCandidate, first_valid_placement_candidate
from .constants import (
    DECISION_POLICY_VERSION,
    ENGINE_VERSION,
    STRATEGY_DISPLAY_NAME,
    STRATEGY_ID,
)
from .errors import NestingInputError
from .models import (
    FeasibilityMetadata,
    NestingResult,
    ObjectiveMetadata,
    ResultStatus,
    UnplacedDemand,
    UnplacedReasonCode,
    ValidationDiagnostic,
)
from .objectives import evaluate_objective
from .ordering import stock_instance_order_key
from .validation import PreparedWork, validate_work_for_nesting

CancellationCheck = Callable[[], None]


@dataclass(frozen=True, slots=True)
class _UnplacedInstance:
    instance: PartInstance
    reason: UnplacedReasonCode


class LeftToRightNestingSolver:
    """Synchronous, stateless implementation of the NEST-002 strategy."""

    def solve(
        self, work: Work, *, cancellation_check: CancellationCheck | None = None
    ) -> NestingResult:
        check = cancellation_check or (lambda: None)
        check()
        try:
            prepared = validate_work_for_nesting(work)
        except NestingInputError as error:
            return _failed_validation_result(work, str(error))
        check()

        layouts: list[Layout] = []
        used_stock_ids: set = set()
        simulation_cache: dict[tuple, int] = {}
        unplaced: list[_UnplacedInstance] = []
        remaining = list(prepared.ordered_part_instances)
        while remaining:
            check()
            instance = remaining.pop(0)
            part_type = prepared.part_types[instance.part_type_id]
            existing = self._best_existing_candidate(layouts, instance, part_type, prepared)
            if existing is not None:
                layout_index, candidate = existing
                layouts[layout_index] = self._commit_candidate(
                    layouts[layout_index], candidate, prepared
                )
                continue

            unopened = self._select_unopened_stock(
                instance,
                part_type,
                (instance, *remaining),
                used_stock_ids,
                prepared,
                simulation_cache,
            )
            if unopened is not None:
                layout = self._empty_layout(unopened.id, prepared)
                candidate = self._candidate(layout, instance, part_type, prepared)
                if candidate is None:
                    raise RuntimeError("selected stock did not accept its required seed part")
                layouts.append(self._commit_candidate(layout, candidate, prepared))
                used_stock_ids.add(unopened.id)
                continue

            reason = self._classify_unplaced(instance, part_type, layouts, used_stock_ids, prepared)
            unplaced.append(_UnplacedInstance(instance, reason))

        result_layouts = tuple(layouts)
        self._validate_result_layouts(result_layouts, prepared)
        grouped_unplaced = self._group_unplaced(unplaced, prepared)
        self._assert_reconciliation(result_layouts, grouped_unplaced, prepared)
        objective = evaluate_objective(
            result_layouts,
            stock_instances=prepared.stock_instances,
            stock_specifications=prepared.stock_specifications,
            part_instances=prepared.part_instances,
            part_types=prepared.part_types,
        )
        return NestingResult(
            work_id=work.id,
            status=ResultStatus.COMPLETE if not grouped_unplaced else ResultStatus.PARTIAL,
            strategy_id=STRATEGY_ID,
            strategy_display_name=STRATEGY_DISPLAY_NAME,
            engine_version=ENGINE_VERSION,
            decision_policy_version=DECISION_POLICY_VERSION,
            layouts=result_layouts,
            placed_part_count=objective.placed_required_demand,
            requested_part_count=len(prepared.ordered_part_instances),
            unplaced_demand=grouped_unplaced,
            objective=objective,
        )

    def _empty_layout(self, stock_id, prepared: PreparedWork) -> Layout:
        layout_id = LayoutId.deterministic(
            NAMESPACE_URL, f"debbie/layout/{prepared.work.id}/{stock_id}/{STRATEGY_ID}"
        )
        return Layout(
            id=layout_id,
            work_id=prepared.work.id,
            stock_instance_id=stock_id,
            process_profile=prepared.work.process_profile,
        )

    def _candidate(
        self,
        layout: Layout,
        instance: PartInstance,
        part_type: PartType,
        prepared: PreparedWork,
    ) -> PlacementCandidate | None:
        stock = prepared.stock_instances[layout.stock_instance_id]
        specification = prepared.stock_specifications[stock.specification_id]
        return first_valid_placement_candidate(
            layout,
            part_instance=instance,
            part_type=part_type,
            stock_specification=specification,
            part_instances=prepared.part_instances,
            part_types=prepared.part_types,
            oriented_dimensions=prepared.oriented_dimensions,
            effective_region=prepared.effective_regions[specification.id],
        )

    def _commit_candidate(
        self, layout: Layout, candidate: PlacementCandidate, prepared: PreparedWork
    ) -> Layout:
        stock = prepared.stock_instances[layout.stock_instance_id]
        specification = prepared.stock_specifications[stock.specification_id]

        def validate(candidate_layout: Layout) -> None:
            validate_layout_geometry(
                candidate_layout,
                stock_instance=stock,
                stock_specification=specification,
                part_instances=prepared.part_instances,
                part_types=prepared.part_types,
            )

        return layout.add_placement(candidate.placement, validate=validate)

    def _best_existing_candidate(
        self,
        layouts: list[Layout],
        instance: PartInstance,
        part_type: PartType,
        prepared: PreparedWork,
    ) -> tuple[int, PlacementCandidate] | None:
        choices: list[tuple[tuple, int, PlacementCandidate]] = []
        for index, layout in enumerate(layouts):
            candidate = self._candidate(layout, instance, part_type, prepared)
            if candidate is not None:
                choices.append((candidate.ranking_key, index, candidate))
        if not choices:
            return None
        _, index, candidate = min(choices, key=lambda choice: choice[0])
        return index, candidate

    def _select_unopened_stock(
        self,
        seed_instance: PartInstance,
        seed_type: PartType,
        remaining: tuple[PartInstance, ...],
        used_stock_ids: set,
        prepared: PreparedWork,
        simulation_cache: dict[tuple, int],
    ):
        choices: list[tuple[tuple, object]] = []
        for stock in prepared.ordered_stock_instances:
            if stock.id in used_stock_ids:
                continue
            empty = self._empty_layout(stock.id, prepared)
            if self._candidate(empty, seed_instance, seed_type, prepared) is None:
                continue
            simulation_key = (
                stock.specification_id,
                tuple(instance.part_type_id for instance in remaining),
            )
            try:
                simulated_count = simulation_cache[simulation_key]
            except KeyError:
                simulated_count = self._simulate_sheet(empty, remaining, prepared)
                simulation_cache[simulation_key] = simulated_count
            score = (
                -simulated_count,
                *stock_instance_order_key(stock, prepared.stock_specifications),
            )
            choices.append((score, stock))
        return min(choices, key=lambda choice: choice[0])[1] if choices else None

    def _simulate_sheet(
        self, layout: Layout, instances: tuple[PartInstance, ...], prepared: PreparedWork
    ) -> int:
        simulated = layout
        placed = 0
        for instance in instances:
            part_type = prepared.part_types[instance.part_type_id]
            candidate = self._candidate(simulated, instance, part_type, prepared)
            if candidate is not None:
                simulated = self._commit_candidate(simulated, candidate, prepared)
                placed += 1
        return placed

    def _fits_specification(
        self, part_type: PartType, orientation: Orientation, specification, prepared: PreparedWork
    ) -> bool:
        try:
            dimensions = prepared.oriented_dimensions[(part_type.id, orientation)]
        except KeyError:
            dimensions = type(part_type.dimensions)(
                part_type.dimensions.width, part_type.dimensions.length
            )
        region = prepared.effective_regions[specification.id]
        return less_than_or_equal(dimensions.length, region.length) and less_than_or_equal(
            dimensions.width, region.width
        )

    def _classify_unplaced(
        self,
        instance: PartInstance,
        part_type: PartType,
        layouts: list[Layout],
        used_stock_ids: set,
        prepared: PreparedWork,
    ) -> UnplacedReasonCode:
        specifications = tuple(prepared.stock_specifications.values())
        allowed_fit = any(
            self._fits_specification(part_type, orientation, specification, prepared)
            for orientation in part_type.allowed_orientations
            for specification in specifications
        )
        forbidden_ninety_fit = (
            Orientation.DEG_90 not in part_type.allowed_orientations
            and any(
                self._fits_specification(part_type, Orientation.DEG_90, specification, prepared)
                for specification in specifications
            )
        )
        if not allowed_fit:
            if forbidden_ninety_fit:
                return UnplacedReasonCode.ORIENTATION_CONSTRAINT
            return UnplacedReasonCode.PART_EXCEEDS_ALL_USABLE_STOCK

        part_area = part_type.dimensions.length * part_type.dimensions.width
        for layout in layouts:
            stock = prepared.stock_instances[layout.stock_instance_id]
            specification = prepared.stock_specifications[stock.specification_id]
            if not any(
                self._fits_specification(part_type, orientation, specification, prepared)
                for orientation in part_type.allowed_orientations
            ):
                continue
            usable = usable_stock_rectangle(specification, layout.process_profile)
            occupied = sum(
                prepared.part_types[
                    prepared.part_instances[item.part_instance_id].part_type_id
                ].dimensions.length
                * prepared.part_types[
                    prepared.part_instances[item.part_instance_id].part_type_id
                ].dimensions.width
                for item in layout.placements
            )
            if less_than_or_equal(part_area, usable.length * usable.width - occupied):
                return UnplacedReasonCode.NO_VALID_PLACEMENT_FOUND
        if any(
            stock.id not in used_stock_ids
            and any(
                self._fits_specification(
                    part_type,
                    orientation,
                    prepared.stock_specifications[stock.specification_id],
                    prepared,
                )
                for orientation in part_type.allowed_orientations
            )
            for stock in prepared.ordered_stock_instances
        ):
            return UnplacedReasonCode.NO_VALID_PLACEMENT_FOUND
        return UnplacedReasonCode.INSUFFICIENT_STOCK_QUANTITY

    def _group_unplaced(
        self, unplaced: list[_UnplacedInstance], prepared: PreparedWork
    ) -> tuple[UnplacedDemand, ...]:
        counts = Counter(
            (item.instance.demand_item_id, item.instance.part_type_id, item.reason)
            for item in unplaced
        )
        return tuple(
            UnplacedDemand(
                work_id=prepared.work.id,
                demand_item_id=demand_id,
                part_type_id=part_type_id,
                remaining_quantity=quantity,
                reason_code=reason,
                diagnostic_details=(("classification", "deterministic-first-engine"),),
            )
            for (demand_id, part_type_id, reason), quantity in sorted(
                counts.items(),
                key=lambda item: (str(item[0][0]), str(item[0][1]), item[0][2].value),
            )
        )

    def _validate_result_layouts(
        self, layouts: tuple[Layout, ...], prepared: PreparedWork
    ) -> None:
        seen_parts: set = set()
        seen_stocks: set = set()
        for layout in layouts:
            if layout.stock_instance_id in seen_stocks:
                raise RuntimeError("a physical stock instance was consumed twice")
            seen_stocks.add(layout.stock_instance_id)
            stock = prepared.stock_instances[layout.stock_instance_id]
            specification = prepared.stock_specifications[stock.specification_id]
            validate_layout_geometry(
                layout,
                stock_instance=stock,
                stock_specification=specification,
                part_instances=prepared.part_instances,
                part_types=prepared.part_types,
            )
            for placement in layout.placements:
                if placement.part_instance_id in seen_parts:
                    raise RuntimeError("a physical part instance was placed twice")
                seen_parts.add(placement.part_instance_id)

    def _assert_reconciliation(
        self,
        layouts: tuple[Layout, ...],
        unplaced: tuple[UnplacedDemand, ...],
        prepared: PreparedWork,
    ) -> None:
        requested_by_demand = Counter(
            (item.demand_item_id, item.part_type_id)
            for item in prepared.ordered_part_instances
        )
        placed_by_demand = Counter(
            (
                prepared.part_instances[placement.part_instance_id].demand_item_id,
                prepared.part_instances[placement.part_instance_id].part_type_id,
            )
            for layout in layouts
            for placement in layout.placements
        )
        unplaced_by_demand = Counter()
        for item in unplaced:
            unplaced_by_demand[(item.demand_item_id, item.part_type_id)] += item.remaining_quantity
        if requested_by_demand != placed_by_demand + unplaced_by_demand:
            raise RuntimeError("per-demand and per-part-type reconciliation failed")


def _failed_validation_result(work: Work, message: str) -> NestingResult:
    diagnostic = ValidationDiagnostic(
        reason_code=UnplacedReasonCode.INVALID_INPUT_REJECTED_BEFORE_RUN,
        message=message,
    )
    return NestingResult(
        work_id=work.id,
        status=ResultStatus.FAILED_VALIDATION,
        strategy_id=STRATEGY_ID,
        strategy_display_name=STRATEGY_DISPLAY_NAME,
        engine_version=ENGINE_VERSION,
        decision_policy_version=DECISION_POLICY_VERSION,
        layouts=(),
        placed_part_count=0,
        requested_part_count=0,
        unplaced_demand=(),
        objective=ObjectiveMetadata(),
        feasibility=FeasibilityMetadata(),
        diagnostics=(diagnostic,),
    )


def nest_work(
    work: Work, *, cancellation_check: CancellationCheck | None = None
) -> NestingResult:
    """Public stateless API for one work-isolated synchronous solve."""

    return LeftToRightNestingSolver().solve(work, cancellation_check=cancellation_check)
