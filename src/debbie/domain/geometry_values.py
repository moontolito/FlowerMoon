"""Millimetre value objects governed by GEO-001 and GEO-002."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real

from .errors import InvalidDimensionError, InvalidTrimError


def finite_millimetres(value: Real, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise InvalidDimensionError(f"{field} must be a real number in millimetres")
    result = float(value)
    if not isfinite(result):
        raise InvalidDimensionError(f"{field} must be finite")
    return result


def positive_millimetres(value: Real, *, field: str) -> float:
    result = finite_millimetres(value, field=field)
    if result <= 0.0:
        raise InvalidDimensionError(f"{field} must be greater than zero")
    return result


def non_negative_millimetres(value: Real, *, field: str) -> float:
    result = finite_millimetres(value, field=field)
    if result < 0.0:
        raise InvalidDimensionError(f"{field} must be non-negative")
    return result


@dataclass(frozen=True, slots=True)
class Dimensions:
    length: float
    width: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "length", positive_millimetres(self.length, field="length"))
        object.__setattr__(self, "width", positive_millimetres(self.width, field="width"))


@dataclass(frozen=True, slots=True)
class Rectangle:
    """Axis-aligned nominal rectangle in usable-stock coordinates."""

    x: float
    y: float
    length: float
    width: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", non_negative_millimetres(self.x, field="x"))
        object.__setattr__(self, "y", non_negative_millimetres(self.y, field="y"))
        object.__setattr__(self, "length", positive_millimetres(self.length, field="length"))
        object.__setattr__(self, "width", positive_millimetres(self.width, field="width"))

    @property
    def right(self) -> float:
        return self.x + self.length

    @property
    def bottom(self) -> float:
        return self.y + self.width


@dataclass(frozen=True, slots=True)
class Trim:
    """Independent unavailable margins on the four stock sides (TRIM-001)."""

    left: float = 0.0
    right: float = 0.0
    top: float = 0.0
    bottom: float = 0.0

    def __post_init__(self) -> None:
        for field_name in ("left", "right", "top", "bottom"):
            object.__setattr__(
                self,
                field_name,
                non_negative_millimetres(getattr(self, field_name), field=f"trim.{field_name}"),
            )

    def usable_dimensions(self, full: Dimensions) -> Dimensions:
        length = full.length - self.left - self.right
        width = full.width - self.top - self.bottom
        if length <= 0.0 or width <= 0.0:
            raise InvalidTrimError("trim must leave positive usable stock dimensions")
        return Dimensions(length, width)
