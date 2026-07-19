"""Immutable Work-owned sheet thickness (THICKNESS-001)."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real

from .errors import InvalidThicknessError


@dataclass(frozen=True, slots=True)
class Thickness:
    millimetres: float

    def __post_init__(self) -> None:
        value = self.millimetres
        if isinstance(value, bool) or not isinstance(value, Real):
            raise InvalidThicknessError("thickness must be a real number in millimetres")
        normalized = float(value)
        if not isfinite(normalized) or normalized <= 0.0:
            raise InvalidThicknessError("thickness must be finite and greater than zero")
        object.__setattr__(self, "millimetres", normalized)
