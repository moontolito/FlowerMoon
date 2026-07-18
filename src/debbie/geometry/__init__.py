"""Public geometry validation API."""

from .predicates import (
    effective_placement_region,
    oriented_placement_bounds,
    rectangle_distance,
    rectangle_is_contained,
    rectangles_overlap,
    satisfies_minimum_clearance,
    usable_stock_rectangle,
    validate_layout_geometry,
)
from .tolerance import (
    GEOMETRY_EPSILON_MM,
    approximately_equal,
    greater_than_or_equal,
    less_than_or_equal,
    strictly_greater,
    strictly_less,
)

__all__ = [
    "GEOMETRY_EPSILON_MM",
    "approximately_equal",
    "effective_placement_region",
    "greater_than_or_equal",
    "less_than_or_equal",
    "oriented_placement_bounds",
    "rectangle_distance",
    "rectangle_is_contained",
    "rectangles_overlap",
    "satisfies_minimum_clearance",
    "strictly_greater",
    "strictly_less",
    "usable_stock_rectangle",
    "validate_layout_geometry",
]
