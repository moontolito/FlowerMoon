"""Rectangular physical and commercial stock allocation (ALLOCATION-001)."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real

from .errors import InvalidAllocationError
from .geometry_values import Dimensions


def _fraction(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise InvalidAllocationError(f"{field} must be a real number")
    normalized = float(value)
    if not isfinite(normalized):
        raise InvalidAllocationError(f"{field} must be finite")
    return normalized


@dataclass(frozen=True, slots=True)
class StockAllocation:
    full_dimensions: Dimensions
    allocated_dimensions: Dimensions
    commercial_allocation_fraction: float

    def __post_init__(self) -> None:
        if not isinstance(self.full_dimensions, Dimensions):
            raise InvalidAllocationError("full_dimensions must be Dimensions")
        if not isinstance(self.allocated_dimensions, Dimensions):
            raise InvalidAllocationError("allocated_dimensions must be Dimensions")
        # These are authoritative input bounds, not placement predicates. Any
        # overshoot is rejected rather than epsilon-clamped into provenance.
        if self.allocated_dimensions.length > self.full_dimensions.length:
            raise InvalidAllocationError("allocated length must not exceed full length")
        if self.allocated_dimensions.width > self.full_dimensions.width:
            raise InvalidAllocationError("allocated width must not exceed full width")
        commercial = _fraction(
            self.commercial_allocation_fraction, field="commercial allocation fraction"
        )
        physical = self.physical_allocation_fraction
        if physical <= 0.0 or not isfinite(physical):
            raise InvalidAllocationError(
                "physical allocation fraction must be finite and greater than zero"
            )
        if commercial < physical:
            raise InvalidAllocationError(
                "commercial allocation fraction must not be below physical allocation fraction"
            )
        if commercial > 1.0:
            raise InvalidAllocationError("commercial allocation fraction must not exceed one")
        object.__setattr__(self, "commercial_allocation_fraction", commercial)

    @property
    def physical_allocation_fraction(self) -> float:
        length_fraction = self.allocated_dimensions.length / self.full_dimensions.length
        width_fraction = self.allocated_dimensions.width / self.full_dimensions.width
        return length_fraction * width_fraction

    @classmethod
    def full(cls, dimensions: Dimensions) -> "StockAllocation":
        return cls(dimensions, dimensions, 1.0)
