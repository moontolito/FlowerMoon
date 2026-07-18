"""Geometry-relevant process values; no toolpath compensation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .geometry_values import Trim, non_negative_millimetres


@dataclass(frozen=True, slots=True)
class ProcessProfile:
    """Immutable effective process snapshot (GEO-003/004, KERF-001)."""

    kerf: float = 0.0
    minimum_part_clearance: float = 0.0
    boundary_clearance: float = 0.0
    trim: Trim = field(default_factory=Trim)

    def __post_init__(self) -> None:
        for field_name in ("kerf", "minimum_part_clearance", "boundary_clearance"):
            object.__setattr__(
                self,
                field_name,
                non_negative_millimetres(getattr(self, field_name), field=field_name),
            )

    @classmethod
    def with_clearance_from_kerf(
        cls, kerf: float, *, boundary_clearance: float = 0.0, trim: Trim | None = None
    ) -> "ProcessProfile":
        """Explicitly initialize, but do not couple, clearance and kerf."""

        return cls(
            kerf=kerf,
            minimum_part_clearance=kerf,
            boundary_clearance=boundary_clearance,
            trim=trim or Trim(),
        )
