from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from debbie.domain import (
    Density,
    DensitySource,
    Dimensions,
    MaterialCategoryKey,
    MaterialGradeKey,
    MaterialIdentity,
    StockAllocation,
    StockSpecification,
    StockSpecificationId,
    Thickness,
    Work,
    WorkId,
)
from debbie.domain.errors import (
    DomainValidationError,
    InvalidAllocationError,
    InvalidDensityError,
    InvalidMaterialError,
    InvalidThicknessError,
)
from debbie.domain.process import ProcessProfile

from tests.mass.helpers import classified_work


def test_MATERIAL_001_material_identity_trims_text_and_preserves_case_sensitive_keys() -> None:
    material = MaterialIdentity(
        MaterialCategoryKey(" Steel "),
        " Steel display ",
        MaterialGradeKey(" s235 "),
        " S235 display ",
        Density(7.85),
        DensitySource.LIBRARY_DEFAULT,
        " description ",
    )
    assert str(material.category_key) == "Steel"
    assert str(material.grade_key) == "s235"
    assert material.category_display_name == "Steel display"
    assert material.grade_display_name == "S235 display"
    assert material.description == "description"


@pytest.mark.parametrize("key_type", [MaterialCategoryKey, MaterialGradeKey])
@pytest.mark.parametrize("value", ["", "   "])
def test_MATERIAL_001_keys_reject_blank_text(key_type, value: str) -> None:
    with pytest.raises(InvalidMaterialError):
        key_type(value)


@pytest.mark.parametrize("field", ["category", "grade"])
def test_MATERIAL_001_display_names_are_required(field: str) -> None:
    values = {
        "category_key": MaterialCategoryKey("steel"),
        "category_display_name": "Steel",
        "grade_key": MaterialGradeKey("S235"),
        "grade_display_name": "S235",
        "effective_density": Density(7.85),
        "density_source": DensitySource.LIBRARY_DEFAULT,
    }
    values[f"{field}_display_name"] = " "
    with pytest.raises(InvalidMaterialError):
        MaterialIdentity(**values)


def test_MATERIAL_001_blank_optional_description_normalizes_to_none() -> None:
    material = MaterialIdentity(
        MaterialCategoryKey("other"),
        "Other",
        MaterialGradeKey("custom:grade"),
        "Custom",
        Density(1.2),
        DensitySource.EXPLICIT_OVERRIDE,
        "  ",
    )
    assert material.description is None


@pytest.mark.parametrize("value", [0, -1, nan, inf, -inf, True, False, "7.9"])
def test_MATERIAL_001_density_rejects_invalid_values(value) -> None:
    with pytest.raises(InvalidDensityError):
        Density(value)


def test_MATERIAL_001_density_provenance_is_controlled() -> None:
    with pytest.raises(InvalidMaterialError):
        MaterialIdentity(
            MaterialCategoryKey("steel"),
            "Steel",
            MaterialGradeKey("S235"),
            "S235",
            Density(7.85),
            "guessed",  # type: ignore[arg-type]
        )


def test_MATERIAL_001_values_are_immutable_and_value_comparable() -> None:
    first = Density(7.9)
    assert first == Density(7.9)
    with pytest.raises(FrozenInstanceError):
        first.grams_per_cubic_centimetre = 8.0  # type: ignore[misc]


def test_MATERIAL_001_display_metadata_does_not_affect_identity_or_hash() -> None:
    values = (
        MaterialCategoryKey("steel"),
        "Steel",
        MaterialGradeKey("S235"),
        "S235",
        Density(7.85),
        DensitySource.LIBRARY_DEFAULT,
    )
    first = MaterialIdentity(*values, description="first note")
    second = MaterialIdentity(
        values[0],
        "Oțel",
        values[2],
        "S235 localizat",
        values[4],
        values[5],
        description="different note",
    )
    assert first == second
    assert hash(first) == hash(second)


@pytest.mark.parametrize("value", [0, -1, nan, inf, -inf, True, False, "3"])
def test_THICKNESS_001_rejects_invalid_values(value) -> None:
    with pytest.raises(InvalidThicknessError):
        Thickness(value)


def test_THICKNESS_001_value_is_immutable() -> None:
    value = Thickness(3)
    assert value.millimetres == 3.0
    with pytest.raises(FrozenInstanceError):
        value.millimetres = 4  # type: ignore[misc]


@pytest.mark.parametrize(
    ("allocated", "expected"),
    [(Dimensions(2500, 1250), 1.0), (Dimensions(1250, 1250), 0.5), (Dimensions(2500, 625), 0.5)],
)
def test_ALLOCATION_001_derives_physical_fraction(allocated: Dimensions, expected: float) -> None:
    allocation = StockAllocation(Dimensions(2500, 1250), allocated, 1.0)
    assert allocation.physical_allocation_fraction == expected


def test_ALLOCATION_001_custom_rectangle_keeps_unrounded_fraction() -> None:
    allocation = StockAllocation(Dimensions(7, 11), Dimensions(3, 5), 0.5)
    assert allocation.physical_allocation_fraction == pytest.approx(15 / 77, rel=0, abs=1e-16)


def test_ALLOCATION_001_extremely_small_valid_allocation_remains_positive() -> None:
    allocation = StockAllocation(Dimensions(1, 1), Dimensions(1e-100, 1e-100), 1.0)
    assert allocation.physical_allocation_fraction == pytest.approx(1e-200)


def test_ALLOCATION_001_extreme_equal_dimensions_do_not_produce_nan() -> None:
    allocation = StockAllocation(Dimensions(1e308, 1e308), Dimensions(1e308, 1e308), 1.0)
    assert allocation.physical_allocation_fraction == 1.0


def test_ALLOCATION_001_underflowed_physical_fraction_is_rejected() -> None:
    with pytest.raises(InvalidAllocationError):
        StockAllocation(Dimensions(1e300, 1e300), Dimensions(1e-300, 1e-300), 1.0)


@pytest.mark.parametrize(
    "allocated",
    [Dimensions(101, 100), Dimensions(100, 101)],
)
def test_ALLOCATION_001_rejects_allocated_dimensions_outside_full(allocated: Dimensions) -> None:
    with pytest.raises(InvalidAllocationError):
        StockAllocation(Dimensions(100, 100), allocated, 1.0)


@pytest.mark.parametrize("overshoot", [0.0005, 0.002])
def test_ALLOCATION_001_rejects_any_dimension_overshoot_without_clamping(
    overshoot: float,
) -> None:
    with pytest.raises(InvalidAllocationError):
        StockAllocation(
            Dimensions(100, 100),
            Dimensions(100 + overshoot, 100),
            1.0,
        )


def test_ALLOCATION_001_zero_allocated_dimension_is_rejected_by_dimensions() -> None:
    with pytest.raises(DomainValidationError):
        StockAllocation(Dimensions(100, 100), Dimensions(0, 50), 1.0)


@pytest.mark.parametrize("commercial", [0.49, 1.01, nan, inf, True])
def test_ALLOCATION_001_rejects_invalid_commercial_fraction(commercial) -> None:
    with pytest.raises(InvalidAllocationError):
        StockAllocation(Dimensions(100, 100), Dimensions(50, 100), commercial)


@pytest.mark.parametrize("commercial", [0.5, 0.75, 1.0])
def test_ALLOCATION_001_accepts_commercial_fraction_at_or_above_physical(
    commercial: float,
) -> None:
    allocation = StockAllocation(Dimensions(100, 100), Dimensions(50, 100), commercial)
    assert allocation.commercial_allocation_fraction == commercial


def test_ALLOCATION_001_rejects_commercial_fraction_infinitesimally_below_physical() -> None:
    physical = StockAllocation(
        Dimensions(7, 11), Dimensions(3, 5), 1.0
    ).physical_allocation_fraction
    with pytest.raises(InvalidAllocationError):
        StockAllocation(Dimensions(7, 11), Dimensions(3, 5), physical - 1e-16)


def test_stock_legacy_path_has_structural_full_allocation_without_metadata() -> None:
    specification = StockSpecification(
        StockSpecificationId("s"), "Sheet", Dimensions(100, 50)
    )
    assert specification.allocation is None
    assert specification.effective_allocation == StockAllocation.full(Dimensions(100, 50))


def test_stock_explicit_nesting_dimensions_must_equal_allocation() -> None:
    with pytest.raises(DomainValidationError):
        StockSpecification(
            StockSpecificationId("s"),
            "Sheet",
            Dimensions(100, 100),
            StockAllocation(Dimensions(100, 100), Dimensions(50, 100), 1.0),
        )


def test_legacy_work_remains_unclassified_without_invented_values() -> None:
    work = Work(WorkId("w"), "Work", 1, ProcessProfile())
    assert not work.is_material_classified
    assert work.material is None
    assert work.thickness is None


def test_material_and_thickness_must_be_supplied_together() -> None:
    with pytest.raises(DomainValidationError):
        Work(
            WorkId("w"),
            "Work",
            1,
            ProcessProfile(),
            thickness=Thickness(3),
        )


def test_material_classified_work_requires_explicit_stock_allocation() -> None:
    classified = classified_work(stocks=())
    legacy_stock = StockSpecification(
        StockSpecificationId("legacy"), "Legacy", Dimensions(100, 100)
    )
    with pytest.raises(DomainValidationError):
        Work(
            classified.id,
            classified.name,
            classified.batch_multiplier,
            classified.process_profile,
            stock_specifications=(legacy_stock,),
            material=classified.material,
            thickness=classified.thickness,
        )
