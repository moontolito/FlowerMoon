from math import inf, nan
from uuid import NAMESPACE_URL

import pytest

from debbie.domain.errors import DomainValidationError, InvalidDimensionError
from debbie.domain.geometry_values import (
    Dimensions,
    non_negative_millimetres,
    positive_millimetres,
)
from debbie.domain.identifiers import PartTypeId, WorkId


def test_identifier_types_are_not_interchangeably_equal() -> None:
    assert WorkId("same") != PartTypeId("same")


def test_identifier_rejects_non_string_storage_value() -> None:
    with pytest.raises(DomainValidationError):
        WorkId(123)  # type: ignore[arg-type]


def test_identifier_accepts_injected_value_and_serializes_to_string() -> None:
    identifier = WorkId(" work-001 ")
    assert str(identifier) == "work-001"


def test_identifier_generation_produces_distinct_values() -> None:
    assert WorkId.new() != WorkId.new()


def test_identifier_deterministic_generation_is_repeatable() -> None:
    assert WorkId.deterministic(NAMESPACE_URL, "fixture") == WorkId.deterministic(
        NAMESPACE_URL, "fixture"
    )


def test_empty_identifier_is_rejected() -> None:
    with pytest.raises(DomainValidationError):
        WorkId("  ")


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_GEO_001_non_finite_dimensions_are_rejected(value: float) -> None:
    with pytest.raises(InvalidDimensionError):
        Dimensions(value, 1.0)


@pytest.mark.parametrize("value", [0.0, -1.0, True])
def test_positive_millimetres_rejects_non_positive_or_boolean(value: object) -> None:
    with pytest.raises(InvalidDimensionError):
        positive_millimetres(value, field="test")  # type: ignore[arg-type]


def test_non_negative_millimetres_accepts_zero_and_rejects_negative() -> None:
    assert non_negative_millimetres(0, field="test") == 0.0
    with pytest.raises(InvalidDimensionError):
        non_negative_millimetres(-0.01, field="test")


def test_dimensions_preserve_unrounded_float_values() -> None:
    dimensions = Dimensions(1.23456789, 9.87654321)
    assert dimensions.length == 1.23456789
    assert dimensions.width == 9.87654321
