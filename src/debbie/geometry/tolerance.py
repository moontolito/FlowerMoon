"""The sole geometry tolerance policy for Debbie vNext (GEO-002)."""

from __future__ import annotations

from debbie.domain.geometry_values import finite_millimetres

GEOMETRY_EPSILON_MM = 0.001


def _finite_operands(left: float, right: float) -> tuple[float, float]:
    return (
        finite_millimetres(left, field="left operand"),
        finite_millimetres(right, field="right operand"),
    )


def approximately_equal(left: float, right: float) -> bool:
    """Return true when the absolute difference is at most epsilon."""

    left, right = _finite_operands(left, right)
    return abs(left - right) <= GEOMETRY_EPSILON_MM


def strictly_less(left: float, right: float) -> bool:
    """Return true only when left is more than epsilon below right."""

    left, right = _finite_operands(left, right)
    return left < right - GEOMETRY_EPSILON_MM


def less_than_or_equal(left: float, right: float) -> bool:
    """Return true when left does not exceed right by more than epsilon."""

    left, right = _finite_operands(left, right)
    return left <= right + GEOMETRY_EPSILON_MM


def strictly_greater(left: float, right: float) -> bool:
    """Return true only when left is more than epsilon above right."""

    left, right = _finite_operands(left, right)
    return left > right + GEOMETRY_EPSILON_MM


def greater_than_or_equal(left: float, right: float) -> bool:
    """Return true when left is not below right by more than epsilon."""

    left, right = _finite_operands(left, right)
    return left >= right - GEOMETRY_EPSILON_MM
