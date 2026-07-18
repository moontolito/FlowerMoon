from dataclasses import replace

import pytest

from debbie.domain.errors import (
    DomainValidationError,
    InvalidQuantityError,
    InvalidTrimError,
    UnsupportedOrientationError,
)
from debbie.domain.geometry_values import Dimensions, Trim
from debbie.domain.identifiers import (
    DemandItemId,
    PartTypeId,
    StockInstanceId,
    StockSpecificationId,
    WorkId,
)
from debbie.domain.orientation import Orientation
from debbie.domain.parts import DemandItem, PartType, expand_demand_items
from debbie.domain.process import ProcessProfile
from debbie.domain.stocks import StockInstance, StockSpecification


def test_ROT_001_part_type_defaults_to_zero_and_ninety_degrees() -> None:
    part = PartType(PartTypeId("p"), "Panel", Dimensions(20, 10))
    assert part.allowed_orientations == frozenset({Orientation.ZERO, Orientation.DEG_90})


def test_ROT_001_oriented_dimensions_swap_without_mutating_nominal_dimensions() -> None:
    part = PartType(PartTypeId("p"), "Panel", Dimensions(20, 10))
    assert part.oriented_dimensions(Orientation.DEG_90) == Dimensions(10, 20)
    assert part.dimensions == Dimensions(20, 10)


def test_ROT_001_zero_only_part_rejects_ninety_degrees() -> None:
    part = PartType(
        PartTypeId("p"),
        "Panel",
        Dimensions(20, 10),
        frozenset({Orientation.ZERO}),
    )
    with pytest.raises(UnsupportedOrientationError):
        part.oriented_dimensions(Orientation.DEG_90)


@pytest.mark.parametrize("value", [45, 180, -90, "90"])
def test_ROT_001_arbitrary_or_malformed_orientation_is_rejected(value: object) -> None:
    with pytest.raises(UnsupportedOrientationError):
        Orientation.coerce(value)


def test_TRIM_001_asymmetric_trim_calculates_usable_dimensions() -> None:
    trim = Trim(left=10, right=20, top=5, bottom=15)
    assert trim.usable_dimensions(Dimensions(100, 80)) == Dimensions(70, 60)


@pytest.mark.parametrize("trim", [Trim(left=50, right=50), Trim(top=40, bottom=40)])
def test_TRIM_001_trim_that_consumes_a_dimension_is_rejected(trim: Trim) -> None:
    with pytest.raises(InvalidTrimError):
        trim.usable_dimensions(Dimensions(100, 80))


def test_KERF_001_kerf_is_independent_from_clearances_and_nominal_geometry() -> None:
    part = PartType(PartTypeId("p"), "Panel", Dimensions(20, 10))
    process = ProcessProfile(kerf=2, minimum_part_clearance=3, boundary_clearance=4)
    assert process.kerf == 2
    assert process.minimum_part_clearance == 3
    assert process.boundary_clearance == 4
    assert part.dimensions == Dimensions(20, 10)


def test_KERF_001_legacy_helper_initializes_but_does_not_couple_values() -> None:
    process = ProcessProfile.with_clearance_from_kerf(2)
    changed = replace(process, kerf=3)
    assert process.minimum_part_clearance == 2
    assert changed.kerf == 3
    assert changed.minimum_part_clearance == 2


def test_BATCH_001_demand_requires_positive_integer_quantity() -> None:
    with pytest.raises(InvalidQuantityError):
        DemandItem(DemandItemId("d"), WorkId("w"), PartTypeId("p"), 1.5)  # type: ignore[arg-type]


def test_typed_identifiers_are_rejected_in_the_wrong_domain_field() -> None:
    with pytest.raises(DomainValidationError):
        DemandItem(WorkId("wrong"), WorkId("w"), PartTypeId("p"), 1)  # type: ignore[arg-type]


def test_BATCH_001_expansion_conserves_quantity_and_is_deterministic() -> None:
    demand = DemandItem(DemandItemId("d"), WorkId("w"), PartTypeId("p"), 3)
    first = expand_demand_items((demand,), 2)
    second = expand_demand_items((demand,), 2)
    assert len(first) == 6
    assert first == second
    assert [item.sequence for item in first] == [1, 2, 3, 4, 5, 6]
    assert all(item.work_id == WorkId("w") for item in first)


@pytest.mark.parametrize("multiplier", [0, -1, 1.5, True])
def test_BATCH_001_expansion_rejects_invalid_integer_multiplier(multiplier: object) -> None:
    demand = DemandItem(DemandItemId("d"), WorkId("w"), PartTypeId("p"), 1)
    with pytest.raises(InvalidQuantityError):
        expand_demand_items((demand,), multiplier)  # type: ignore[arg-type]


def test_stock_dimensions_remain_full_and_trim_free() -> None:
    specification = StockSpecification(
        StockSpecificationId("s"), "Sheet", Dimensions(100, 80)
    )
    instance = StockInstance(StockInstanceId("i"), WorkId("w"), specification.id, 1)
    assert specification.dimensions == Dimensions(100, 80)
    assert instance.work_id == WorkId("w")
