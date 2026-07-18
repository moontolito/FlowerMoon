"""Immutable layouts and nominal placements."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Callable

from .errors import DuplicatePlacementError, InvalidQuantityError, UnknownReferenceError
from .geometry_values import non_negative_millimetres
from .identifiers import (
    LayoutId,
    LayoutInstanceId,
    PartInstanceId,
    StockInstanceId,
    WorkId,
    require_identifier,
)
from .orientation import Orientation
from .process import ProcessProfile


class LayoutStatus(str, Enum):
    """Neutral initial status; completion/release semantics remain pending."""

    DRAFT = "draft"


@dataclass(frozen=True, slots=True)
class Placement:
    part_instance_id: PartInstanceId
    x: float
    y: float
    orientation: Orientation = Orientation.ZERO

    def __post_init__(self) -> None:
        require_identifier(self.part_instance_id, PartInstanceId, field="placed part instance ID")
        object.__setattr__(self, "x", non_negative_millimetres(self.x, field="placement.x"))
        object.__setattr__(self, "y", non_negative_millimetres(self.y, field="placement.y"))
        object.__setattr__(self, "orientation", Orientation.coerce(self.orientation))


LayoutValidator = Callable[["Layout"], None]


@dataclass(frozen=True, slots=True)
class Layout:
    id: LayoutId
    work_id: WorkId
    stock_instance_id: StockInstanceId
    process_profile: ProcessProfile
    placements: tuple[Placement, ...] = field(default_factory=tuple)
    status: LayoutStatus = LayoutStatus.DRAFT

    def __post_init__(self) -> None:
        require_identifier(self.id, LayoutId, field="layout ID")
        require_identifier(self.work_id, WorkId, field="layout work ID")
        require_identifier(self.stock_instance_id, StockInstanceId, field="layout stock instance ID")
        object.__setattr__(self, "placements", tuple(self.placements))
        object.__setattr__(self, "status", LayoutStatus(self.status))
        ids = [placement.part_instance_id for placement in self.placements]
        if len(ids) != len(set(ids)):
            raise DuplicatePlacementError("a part instance may appear only once in a layout")

    def add_placement(self, placement: Placement, *, validate: LayoutValidator) -> "Layout":
        if any(item.part_instance_id == placement.part_instance_id for item in self.placements):
            raise DuplicatePlacementError(f"part instance already placed: {placement.part_instance_id}")
        candidate = replace(self, placements=(*self.placements, placement))
        validate(candidate)
        return candidate

    def replace_placement(self, placement: Placement, *, validate: LayoutValidator) -> "Layout":
        if not any(item.part_instance_id == placement.part_instance_id for item in self.placements):
            raise UnknownReferenceError(f"part instance is not placed: {placement.part_instance_id}")
        candidate = replace(
            self,
            placements=tuple(
                placement if item.part_instance_id == placement.part_instance_id else item
                for item in self.placements
            ),
        )
        validate(candidate)
        return candidate

    def remove_placement(
        self, part_instance_id: PartInstanceId, *, validate: LayoutValidator
    ) -> "Layout":
        remaining = tuple(
            item for item in self.placements if item.part_instance_id != part_instance_id
        )
        if len(remaining) == len(self.placements):
            raise UnknownReferenceError(f"part instance is not placed: {part_instance_id}")
        candidate = replace(self, placements=remaining)
        validate(candidate)
        return candidate


@dataclass(frozen=True, slots=True)
class LayoutInstance:
    """One physical execution of a layout definition; grouping is deferred."""

    id: LayoutInstanceId
    work_id: WorkId
    layout_id: LayoutId
    sequence: int

    def __post_init__(self) -> None:
        require_identifier(self.id, LayoutInstanceId, field="layout instance ID")
        require_identifier(self.work_id, WorkId, field="layout instance work ID")
        require_identifier(self.layout_id, LayoutId, field="layout definition ID")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence <= 0:
            raise InvalidQuantityError("layout instance sequence must be a positive integer")
