"""Named lexicographic objective values governed by OPT-001."""

from __future__ import annotations

from debbie.domain.layouts import Layout
from debbie.domain.parts import PartInstance, PartType
from debbie.domain.stocks import StockInstance, StockSpecification
from debbie.geometry import usable_stock_rectangle

from .models import ObjectiveMetadata


def objective_sort_key(objective: ObjectiveMetadata) -> tuple:
    """Return the exact lexicographic comparison key; no weighted score exists."""

    return (
        -objective.placed_required_demand,
        objective.physical_stock_sheets_consumed,
        objective.nominal_full_stock_area_consumed,
        objective.unused_usable_area,
        objective.stable_tie_breakers,
    )


def objective_is_better(left: ObjectiveMetadata, right: ObjectiveMetadata) -> bool:
    return objective_sort_key(left) < objective_sort_key(right)


def evaluate_objective(
    layouts: tuple[Layout, ...],
    *,
    stock_instances: dict,
    stock_specifications: dict,
    part_instances: dict,
    part_types: dict,
) -> ObjectiveMetadata:
    nominal_area = 0.0
    unused_usable_area = 0.0
    tie_breakers: list[str] = []
    for layout in layouts:
        stock: StockInstance = stock_instances[layout.stock_instance_id]
        specification: StockSpecification = stock_specifications[stock.specification_id]
        nominal_full = specification.full_dimensions
        nominal_area += nominal_full.length * nominal_full.width
        usable = usable_stock_rectangle(specification, layout.process_profile)
        placed_area = 0.0
        for placement in layout.placements:
            instance: PartInstance = part_instances[placement.part_instance_id]
            part_type: PartType = part_types[instance.part_type_id]
            placed_area += part_type.dimensions.length * part_type.dimensions.width
            tie_breakers.append(
                f"{stock.id}|{instance.id}|{placement.x:.12g}|{placement.y:.12g}|"
                f"{placement.orientation.value}"
            )
        unused_usable_area += max(0.0, usable.length * usable.width - placed_area)
    return ObjectiveMetadata(
        placed_required_demand=sum(len(layout.placements) for layout in layouts),
        physical_stock_sheets_consumed=len(layouts),
        nominal_full_stock_area_consumed=nominal_area,
        unused_usable_area=unused_usable_area,
        stable_tie_breakers=tuple(tie_breakers),
    )
