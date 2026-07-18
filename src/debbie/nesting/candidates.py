"""Lazy geometry-edge candidate generation for NEST-002."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from debbie.domain.geometry_values import Dimensions, Rectangle
from debbie.domain.identifiers import PartInstanceId, PartTypeId, StockInstanceId
from debbie.domain.layouts import Layout, Placement
from debbie.domain.orientation import Orientation
from debbie.domain.parts import PartInstance, PartType
from debbie.domain.stocks import StockSpecification
from debbie.geometry import (
    approximately_equal,
    effective_placement_region,
    less_than_or_equal,
    oriented_placement_bounds,
    satisfies_minimum_clearance,
)


@dataclass(frozen=True, slots=True)
class PlacementCandidate:
    stock_instance_id: StockInstanceId
    part_instance_id: PartInstanceId
    placement: Placement
    bounds: Rectangle

    @property
    def ranking_key(self) -> tuple[float | int | str, ...]:
        return (
            self.placement.x,
            self.placement.y,
            0 if self.placement.orientation is Orientation.ZERO else 1,
            str(self.part_instance_id),
            str(self.stock_instance_id),
        )


def _deduplicated(values: list[float]) -> tuple[float, ...]:
    """Sort once and merge only coordinates equivalent under GEO-002."""

    result: list[float] = []
    for value in sorted(values):
        if not result or not approximately_equal(value, result[-1]):
            result.append(value)
    return tuple(result)


def _placement_bounds(
    placement: Placement,
    part_instance: PartInstance,
    *,
    part_types: Mapping[PartTypeId, PartType],
    oriented_dimensions: Mapping[tuple[PartTypeId, Orientation], Dimensions] | None,
) -> Rectangle:
    if oriented_dimensions is None:
        return oriented_placement_bounds(placement, part_types[part_instance.part_type_id])
    dimensions = oriented_dimensions[(part_instance.part_type_id, placement.orientation)]
    return Rectangle(placement.x, placement.y, dimensions.length, dimensions.width)


def candidate_coordinate_axes(
    layout: Layout,
    *,
    stock_specification: StockSpecification,
    part_instances: Mapping[PartInstanceId, PartInstance],
    part_types: Mapping[PartTypeId, PartType],
    oriented_dimensions: Mapping[tuple[PartTypeId, Orientation], Dimensions] | None = None,
    effective_region: Rectangle | None = None,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Compute each relevant axis once for one immutable layout state."""

    region = effective_region or effective_placement_region(
        stock_specification, layout.process_profile
    )
    x_values = [region.x]
    y_values = [region.y]
    clearance = layout.process_profile.minimum_part_clearance
    for existing in layout.placements:
        instance = part_instances[existing.part_instance_id]
        bounds = _placement_bounds(
            existing,
            instance,
            part_types=part_types,
            oriented_dimensions=oriented_dimensions,
        )
        x_values.append(bounds.right + clearance)
        y_values.append(bounds.bottom + clearance)
    return _deduplicated(x_values), _deduplicated(y_values)


def edge_candidate_coordinates(
    layout: Layout,
    *,
    stock_specification: StockSpecification,
    part_instances: Mapping[PartInstanceId, PartInstance],
    part_types: Mapping[PartTypeId, PartType],
) -> tuple[tuple[float, float], ...]:
    """Exhaustive coordinate helper retained for tests and review tooling."""

    x_values, y_values = candidate_coordinate_axes(
        layout,
        stock_specification=stock_specification,
        part_instances=part_instances,
        part_types=part_types,
    )
    return tuple((x, y) for x in x_values for y in y_values)


def _existing_bounds(
    layout: Layout,
    *,
    part_instances: Mapping[PartInstanceId, PartInstance],
    part_types: Mapping[PartTypeId, PartType],
    oriented_dimensions: Mapping[tuple[PartTypeId, Orientation], Dimensions] | None,
) -> tuple[Rectangle, ...]:
    return tuple(
        _placement_bounds(
            placement,
            part_instances[placement.part_instance_id],
            part_types=part_types,
            oriented_dimensions=oriented_dimensions,
        )
        for placement in layout.placements
    )


def iter_placement_candidates(
    layout: Layout,
    *,
    part_instance: PartInstance,
    part_type: PartType,
    stock_specification: StockSpecification,
    part_instances: Mapping[PartInstanceId, PartInstance],
    part_types: Mapping[PartTypeId, PartType],
    oriented_dimensions: Mapping[tuple[PartTypeId, Orientation], Dimensions] | None = None,
    effective_region: Rectangle | None = None,
) -> Iterator[PlacementCandidate]:
    """Yield only boundary-feasible candidates in exact X/Y/orientation order.

    Boundary pruning is contract-equivalent because a rejected rectangle cannot
    pass the authoritative containment predicate. No collision candidate that
    could be selected is reordered or omitted.
    """

    region = effective_region or effective_placement_region(
        stock_specification, layout.process_profile
    )
    x_values, y_values = candidate_coordinate_axes(
        layout,
        stock_specification=stock_specification,
        part_instances=part_instances,
        part_types=part_types,
        oriented_dimensions=oriented_dimensions,
        effective_region=region,
    )
    dimensions_by_orientation = {
        orientation: (
            oriented_dimensions[(part_type.id, orientation)]
            if oriented_dimensions is not None
            else part_type.oriented_dimensions(orientation)
        )
        for orientation in sorted(part_type.allowed_orientations, key=int)
    }
    for x in x_values:
        for y in y_values:
            for orientation, dimensions in dimensions_by_orientation.items():
                if not less_than_or_equal(x + dimensions.length, region.right):
                    continue
                if not less_than_or_equal(y + dimensions.width, region.bottom):
                    continue
                placement = Placement(part_instance.id, x, y, orientation)
                yield PlacementCandidate(
                    stock_instance_id=layout.stock_instance_id,
                    part_instance_id=part_instance.id,
                    placement=placement,
                    bounds=Rectangle(x, y, dimensions.length, dimensions.width),
                )


def candidate_satisfies_existing_geometry(
    candidate: PlacementCandidate,
    *,
    existing_bounds: tuple[Rectangle, ...],
    minimum_part_clearance: float,
) -> bool:
    """Apply the shared collision/clearance predicate only to the new part."""

    return all(
        satisfies_minimum_clearance(
            candidate.bounds, existing, minimum_part_clearance
        )
        for existing in existing_bounds
    )


def iter_valid_placement_candidates(
    layout: Layout,
    *,
    part_instance: PartInstance,
    part_type: PartType,
    stock_specification: StockSpecification,
    part_instances: Mapping[PartInstanceId, PartInstance],
    part_types: Mapping[PartTypeId, PartType],
    oriented_dimensions: Mapping[tuple[PartTypeId, Orientation], Dimensions] | None = None,
    effective_region: Rectangle | None = None,
) -> Iterator[PlacementCandidate]:
    existing = _existing_bounds(
        layout,
        part_instances=part_instances,
        part_types=part_types,
        oriented_dimensions=oriented_dimensions,
    )
    for candidate in iter_placement_candidates(
        layout,
        part_instance=part_instance,
        part_type=part_type,
        stock_specification=stock_specification,
        part_instances=part_instances,
        part_types=part_types,
        oriented_dimensions=oriented_dimensions,
        effective_region=effective_region,
    ):
        if candidate_satisfies_existing_geometry(
            candidate,
            existing_bounds=existing,
            minimum_part_clearance=layout.process_profile.minimum_part_clearance,
        ):
            yield candidate


def first_valid_placement_candidate(
    layout: Layout,
    *,
    part_instance: PartInstance,
    part_type: PartType,
    stock_specification: StockSpecification,
    part_instances: Mapping[PartInstanceId, PartInstance],
    part_types: Mapping[PartTypeId, PartType],
    oriented_dimensions: Mapping[tuple[PartTypeId, Orientation], Dimensions] | None = None,
    effective_region: Rectangle | None = None,
) -> PlacementCandidate | None:
    return next(
        iter_valid_placement_candidates(
            layout,
            part_instance=part_instance,
            part_type=part_type,
            stock_specification=stock_specification,
            part_instances=part_instances,
            part_types=part_types,
            oriented_dimensions=oriented_dimensions,
            effective_region=effective_region,
        ),
        None,
    )


def valid_placement_candidates(
    layout: Layout,
    *,
    part_instance: PartInstance,
    part_type: PartType,
    stock_specification: StockSpecification,
    part_instances: Mapping[PartInstanceId, PartInstance],
    part_types: Mapping[PartTypeId, PartType],
    oriented_dimensions: Mapping[tuple[PartTypeId, Orientation], Dimensions] | None = None,
    effective_region: Rectangle | None = None,
) -> tuple[PlacementCandidate, ...]:
    """Materialize the ordered stream for exhaustive equivalence tests only."""

    return tuple(
        iter_valid_placement_candidates(
            layout,
            part_instance=part_instance,
            part_type=part_type,
            stock_specification=stock_specification,
            part_instances=part_instances,
            part_types=part_types,
            oriented_dimensions=oriented_dimensions,
            effective_region=effective_region,
        )
    )
