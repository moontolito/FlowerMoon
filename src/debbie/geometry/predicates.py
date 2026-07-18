"""Shared nominal-rectangle validation; deliberately no placement search."""

from __future__ import annotations

from collections.abc import Mapping
from math import hypot

from debbie.domain.errors import (
    ClearanceViolationError,
    InvalidDimensionError,
    OutOfBoundsError,
    OverlapError,
    OwnershipError,
    UnknownReferenceError,
)
from debbie.domain.geometry_values import Rectangle, non_negative_millimetres
from debbie.domain.identifiers import PartInstanceId, PartTypeId
from debbie.domain.layouts import Layout, Placement
from debbie.domain.parts import PartInstance, PartType
from debbie.domain.process import ProcessProfile
from debbie.domain.stocks import StockInstance, StockSpecification

from .tolerance import (
    greater_than_or_equal,
    less_than_or_equal,
    strictly_greater,
)


def oriented_placement_bounds(placement: Placement, part_type: PartType) -> Rectangle:
    dimensions = part_type.oriented_dimensions(placement.orientation)
    return Rectangle(placement.x, placement.y, dimensions.length, dimensions.width)


def usable_stock_rectangle(
    stock_specification: StockSpecification, process_profile: ProcessProfile
) -> Rectangle:
    """Return usable-stock coordinates after applying four-sided trim.

    GEO-001 places the model origin at the usable area's top-left, so trim does
    not become a coordinate offset in domain geometry.
    """

    usable = process_profile.trim.usable_dimensions(stock_specification.dimensions)
    return Rectangle(0.0, 0.0, usable.length, usable.width)


def effective_placement_region(
    stock_specification: StockSpecification, process_profile: ProcessProfile
) -> Rectangle:
    usable = usable_stock_rectangle(stock_specification, process_profile)
    clearance = process_profile.boundary_clearance
    length = usable.length - 2.0 * clearance
    width = usable.width - 2.0 * clearance
    if length <= 0.0 or width <= 0.0:
        raise InvalidDimensionError("boundary clearance leaves no positive placement region")
    return Rectangle(clearance, clearance, length, width)


def rectangle_is_contained(inner: Rectangle, outer: Rectangle) -> bool:
    return (
        greater_than_or_equal(inner.x, outer.x)
        and greater_than_or_equal(inner.y, outer.y)
        and less_than_or_equal(inner.right, outer.right)
        and less_than_or_equal(inner.bottom, outer.bottom)
    )


def rectangles_overlap(left: Rectangle, right: Rectangle) -> bool:
    """Detect positive-area overlap; epsilon-close edge contact is not overlap."""

    x_overlap = min(left.right, right.right) - max(left.x, right.x)
    y_overlap = min(left.bottom, right.bottom) - max(left.y, right.y)
    return strictly_greater(x_overlap, 0.0) and strictly_greater(y_overlap, 0.0)


def rectangle_distance(left: Rectangle, right: Rectangle) -> float:
    """Euclidean minimum distance, covering both edge and corner separation."""

    horizontal_gap = max(left.x - right.right, right.x - left.right, 0.0)
    vertical_gap = max(left.y - right.bottom, right.y - left.bottom, 0.0)
    return hypot(horizontal_gap, vertical_gap)


def satisfies_minimum_clearance(
    left: Rectangle, right: Rectangle, minimum_clearance: float
) -> bool:
    minimum_clearance = non_negative_millimetres(
        minimum_clearance, field="minimum clearance"
    )
    if rectangles_overlap(left, right):
        return False
    return greater_than_or_equal(rectangle_distance(left, right), minimum_clearance)


def validate_layout_geometry(
    layout: Layout,
    *,
    stock_instance: StockInstance,
    stock_specification: StockSpecification,
    part_instances: Mapping[PartInstanceId, PartInstance],
    part_types: Mapping[PartTypeId, PartType],
) -> None:
    """Validate all current rectangle invariants for a complete layout."""

    if stock_instance.id != layout.stock_instance_id:
        raise UnknownReferenceError(
            f"layout references stock {layout.stock_instance_id}, not {stock_instance.id}"
        )
    if stock_instance.work_id != layout.work_id:
        raise OwnershipError("layout and stock instance must belong to the same work")
    if stock_instance.specification_id != stock_specification.id:
        raise UnknownReferenceError(
            f"stock instance references specification {stock_instance.specification_id}, "
            f"not {stock_specification.id}"
        )

    region = effective_placement_region(stock_specification, layout.process_profile)
    bounds: list[tuple[Placement, Rectangle]] = []
    for placement in layout.placements:
        try:
            part_instance = part_instances[placement.part_instance_id]
        except KeyError as error:
            raise UnknownReferenceError(
                f"unknown placed part instance: {placement.part_instance_id}"
            ) from error
        if part_instance.work_id != layout.work_id:
            raise OwnershipError("layout and every placed part must belong to the same work")
        try:
            part_type = part_types[part_instance.part_type_id]
        except KeyError as error:
            raise UnknownReferenceError(
                f"unknown part type: {part_instance.part_type_id}"
            ) from error

        placement_bounds = oriented_placement_bounds(placement, part_type)
        if not rectangle_is_contained(placement_bounds, region):
            raise OutOfBoundsError(
                f"part instance {part_instance.id} is outside the effective stock region"
            )
        bounds.append((placement, placement_bounds))

    for index, (left_placement, left_bounds) in enumerate(bounds):
        for right_placement, right_bounds in bounds[index + 1 :]:
            if rectangles_overlap(left_bounds, right_bounds):
                raise OverlapError(
                    f"part instances {left_placement.part_instance_id} and "
                    f"{right_placement.part_instance_id} overlap"
                )
            if not satisfies_minimum_clearance(
                left_bounds,
                right_bounds,
                layout.process_profile.minimum_part_clearance,
            ):
                raise ClearanceViolationError(
                    f"part instances {left_placement.part_instance_id} and "
                    f"{right_placement.part_instance_id} violate minimum clearance"
                )
