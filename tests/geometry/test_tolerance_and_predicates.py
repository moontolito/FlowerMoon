import pytest

from debbie.domain.errors import InvalidDimensionError
from debbie.domain.geometry_values import Dimensions, Rectangle, Trim
from debbie.domain.identifiers import PartInstanceId, PartTypeId
from debbie.domain.layouts import Placement
from debbie.domain.parts import PartType
from debbie.domain.process import ProcessProfile
from debbie.domain.stocks import StockSpecification
from debbie.domain.identifiers import StockSpecificationId
from debbie.geometry.predicates import (
    effective_placement_region,
    oriented_placement_bounds,
    rectangle_distance,
    rectangle_is_contained,
    rectangles_overlap,
    satisfies_minimum_clearance,
    usable_stock_rectangle,
)
from debbie.geometry.tolerance import (
    GEOMETRY_EPSILON_MM,
    approximately_equal,
    greater_than_or_equal,
    less_than_or_equal,
    strictly_greater,
    strictly_less,
)


def test_GEO_002_centralized_epsilon_is_one_micron() -> None:
    assert GEOMETRY_EPSILON_MM == 0.001
    assert approximately_equal(1.0, 1.001)
    assert not approximately_equal(1.0, 1.0011)


def test_GEO_002_comparison_helper_semantics() -> None:
    assert not strictly_less(1.0, 1.001)
    assert strictly_less(1.0, 1.0011)
    assert less_than_or_equal(1.001, 1.0)
    assert not strictly_greater(1.001, 1.0)
    assert strictly_greater(1.0011, 1.0)
    assert greater_than_or_equal(0.999, 1.0)


def test_GEO_002_comparison_helpers_reject_non_finite_operands() -> None:
    with pytest.raises(InvalidDimensionError):
        strictly_less(float("nan"), 1.0)


def test_GEO_001_orientation_bounds_use_nominal_millimetres() -> None:
    part = PartType(PartTypeId("p"), "Part", Dimensions(20, 10))
    placement = Placement(PartInstanceId("i"), 3, 4, 90)
    assert oriented_placement_bounds(placement, part) == Rectangle(3, 4, 10, 20)


def test_TRIM_001_usable_rectangle_origin_is_top_left_of_usable_area() -> None:
    stock = StockSpecification(StockSpecificationId("s"), "Sheet", Dimensions(100, 80))
    process = ProcessProfile(trim=Trim(left=10, right=20, top=5, bottom=15))
    assert usable_stock_rectangle(stock, process) == Rectangle(0, 0, 70, 60)


def test_GEO_004_boundary_clearance_erodes_every_side() -> None:
    stock = StockSpecification(StockSpecificationId("s"), "Sheet", Dimensions(100, 80))
    process = ProcessProfile(boundary_clearance=2)
    assert effective_placement_region(stock, process) == Rectangle(2, 2, 96, 76)


def test_GEO_004_zero_boundary_clearance_allows_exact_contact() -> None:
    assert rectangle_is_contained(Rectangle(0, 0, 100, 80), Rectangle(0, 0, 100, 80))


def test_GEO_002_containment_accepts_epsilon_but_not_more() -> None:
    outer = Rectangle(0, 0, 10, 10)
    assert rectangle_is_contained(Rectangle(0, 0, 10.001, 10), outer)
    assert not rectangle_is_contained(Rectangle(0, 0, 10.0011, 10), outer)


def test_GEO_003_positive_area_overlap_is_rejected_but_touch_is_not_overlap() -> None:
    left = Rectangle(0, 0, 10, 10)
    assert not rectangles_overlap(left, Rectangle(10, 0, 10, 10))
    assert rectangles_overlap(left, Rectangle(9.998, 0, 10, 10))


def test_GEO_003_exact_touch_is_valid_when_clearance_is_zero() -> None:
    assert satisfies_minimum_clearance(Rectangle(0, 0, 10, 10), Rectangle(10, 0, 5, 5), 0)


def test_GEO_003_exact_required_edge_gap_is_valid() -> None:
    assert satisfies_minimum_clearance(Rectangle(0, 0, 10, 10), Rectangle(12, 0, 5, 5), 2)


def test_GEO_003_gap_below_requirement_beyond_epsilon_is_invalid() -> None:
    assert not satisfies_minimum_clearance(
        Rectangle(0, 0, 10, 10), Rectangle(11.9989, 0, 5, 5), 2
    )


def test_GEO_003_gap_within_epsilon_of_requirement_is_valid() -> None:
    assert satisfies_minimum_clearance(
        Rectangle(0, 0, 10, 10), Rectangle(11.999, 0, 5, 5), 2
    )


def test_GEO_003_corner_clearance_uses_euclidean_minimum_distance() -> None:
    left = Rectangle(0, 0, 10, 10)
    right = Rectangle(13, 14, 5, 5)
    assert rectangle_distance(left, right) == 5
    assert satisfies_minimum_clearance(left, right, 5)
    assert not satisfies_minimum_clearance(left, right, 5.01)
