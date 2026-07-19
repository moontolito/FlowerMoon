"""Pre-run validation and immutable solver preparation."""

from __future__ import annotations

from dataclasses import dataclass

from debbie.domain import (
    DemandItem,
    Orientation,
    PartInstance,
    PartType,
    ProcessProfile,
    StockInstance,
    StockSpecification,
    Work,
    expand_demand_items,
)
from debbie.domain.geometry_values import Dimensions, Rectangle
from debbie.domain.identifiers import PartTypeId, StockSpecificationId
from debbie.domain.errors import DomainValidationError
from debbie.geometry import effective_placement_region

from .errors import NestingInputError
from .ordering import part_instance_order_key, stock_instance_order_key


@dataclass(frozen=True, slots=True)
class PreparedWork:
    work: Work
    part_types: dict
    part_instances: dict
    ordered_part_instances: tuple[PartInstance, ...]
    oriented_dimensions: dict[tuple[PartTypeId, Orientation], Dimensions]
    stock_specifications: dict
    effective_regions: dict[StockSpecificationId, Rectangle]
    stock_instances: dict
    ordered_stock_instances: tuple[StockInstance, ...]


def validate_work_for_nesting(work: Work) -> PreparedWork:
    """Reject invalid/stale solver state before any layout is generated."""

    if not isinstance(work, Work):
        raise TypeError("nest_work requires a Work")
    if work.layouts or work.layout_instances:
        raise NestingInputError("fresh nesting input must not contain existing layout state")
    if not isinstance(work.process_profile, ProcessProfile):
        raise NestingInputError("work process profile must be ProcessProfile")

    typed_collections = (
        (work.part_types, PartType, "part type"),
        (work.demand_items, DemandItem, "demand item"),
        (work.part_instances, PartInstance, "part instance"),
        (work.stock_specifications, StockSpecification, "stock specification"),
        (work.stock_instances, StockInstance, "stock instance"),
    )
    for items, expected_type, label in typed_collections:
        if any(not isinstance(item, expected_type) for item in items):
            raise NestingInputError(f"work contains a non-{label} value")

    part_types: dict = {part.id: part for part in work.part_types}
    approved_orientation_sets = {
        frozenset({Orientation.ZERO}),
        frozenset({Orientation.ZERO, Orientation.DEG_90}),
    }
    for part_type in part_types.values():
        if part_type.allowed_orientations not in approved_orientation_sets:
            raise NestingInputError(
                f"part type {part_type.id} has an orientation set outside ROT-001"
            )
    oriented_dimensions = {
        (part_type.id, orientation): part_type.oriented_dimensions(orientation)
        for part_type in part_types.values()
        for orientation in sorted(part_type.allowed_orientations, key=int)
    }

    expected_instances = expand_demand_items(work.demand_items, work.batch_multiplier)
    if work.part_instances:
        supplied = {instance.id: instance for instance in work.part_instances}
        expected = {instance.id: instance for instance in expected_instances}
        if supplied != expected:
            raise NestingInputError(
                "materialized part instances do not reconcile with deterministic demand expansion"
            )

    stock_specifications: dict = {
        specification.id: specification for specification in work.stock_specifications
    }
    effective_regions: dict[StockSpecificationId, Rectangle] = {}
    for specification in stock_specifications.values():
        allocation = specification.allocation
        if allocation is not None and allocation.physical_allocation_fraction < 1.0:
            trim = work.process_profile.trim
            has_trim = any((trim.left, trim.right, trim.top, trim.bottom))
            if has_trim or work.process_profile.boundary_clearance > 0.0:
                raise NestingInputError(
                    "partial stock allocation with trim or boundary clearance is not approved"
                )
        try:
            effective_regions[specification.id] = effective_placement_region(
                specification, work.process_profile
            )
        except DomainValidationError as error:
            raise NestingInputError(
                f"stock specification {specification.id} has no valid effective region: {error}"
            ) from error

    stock_instances: dict = {instance.id: instance for instance in work.stock_instances}
    instance_map = {instance.id: instance for instance in expected_instances}
    ordered_parts = tuple(
        sorted(
            expected_instances,
            key=lambda item: part_instance_order_key(item, part_types),
        )
    )
    ordered_stocks = tuple(
        sorted(
            work.stock_instances,
            key=lambda item: stock_instance_order_key(item, stock_specifications),
        )
    )
    return PreparedWork(
        work=work,
        part_types=part_types,
        part_instances=instance_map,
        ordered_part_instances=ordered_parts,
        oriented_dimensions=oriented_dimensions,
        stock_specifications=stock_specifications,
        effective_regions=effective_regions,
        stock_instances=stock_instances,
        ordered_stock_instances=ordered_stocks,
    )
