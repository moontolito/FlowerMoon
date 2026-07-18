"""MVP rectangular orientation policy governed by ROT-001."""

from enum import IntEnum

from .errors import UnsupportedOrientationError


class Orientation(IntEnum):
    ZERO = 0
    DEG_90 = 90

    @classmethod
    def coerce(cls, value: object) -> "Orientation":
        if isinstance(value, bool):
            raise UnsupportedOrientationError(f"unsupported orientation: {value!r}")
        try:
            return cls(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as error:
            raise UnsupportedOrientationError(f"unsupported orientation: {value!r}") from error


DEFAULT_ORIENTATIONS = frozenset({Orientation.ZERO, Orientation.DEG_90})
