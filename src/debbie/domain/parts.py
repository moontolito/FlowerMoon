"""Part definitions, work-owned demand, and deterministic expansion."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import NAMESPACE_URL

from .errors import DomainValidationError, InvalidQuantityError, UnsupportedOrientationError
from .geometry_values import Dimensions
from .identifiers import DemandItemId, PartInstanceId, PartTypeId, WorkId, require_identifier
from .orientation import DEFAULT_ORIENTATIONS, Orientation


def _positive_integer(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvalidQuantityError(f"{field_name} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class PartType:
    id: PartTypeId
    name: str
    dimensions: Dimensions
    allowed_orientations: frozenset[Orientation] = field(default_factory=lambda: DEFAULT_ORIENTATIONS)

    def __post_init__(self) -> None:
        require_identifier(self.id, PartTypeId, field="part type ID")
        name = self.name.strip()
        if not name:
            raise DomainValidationError("part type name must not be empty")
        orientations: set[Orientation] = set()
        for value in self.allowed_orientations:
            orientations.add(Orientation.coerce(value))
        if not orientations:
            raise UnsupportedOrientationError("part type must allow at least one orientation")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "allowed_orientations", frozenset(orientations))

    def oriented_dimensions(self, orientation: Orientation) -> Dimensions:
        orientation = Orientation.coerce(orientation)
        if orientation not in self.allowed_orientations:
            raise UnsupportedOrientationError(
                f"orientation {orientation.value} is not allowed for part type {self.id}"
            )
        if orientation is Orientation.ZERO:
            return self.dimensions
        return Dimensions(self.dimensions.width, self.dimensions.length)


@dataclass(frozen=True, slots=True)
class DemandItem:
    id: DemandItemId
    work_id: WorkId
    part_type_id: PartTypeId
    base_quantity: int

    def __post_init__(self) -> None:
        require_identifier(self.id, DemandItemId, field="demand item ID")
        require_identifier(self.work_id, WorkId, field="demand work ID")
        require_identifier(self.part_type_id, PartTypeId, field="demand part type ID")
        object.__setattr__(
            self, "base_quantity", _positive_integer(self.base_quantity, field_name="base quantity")
        )


@dataclass(frozen=True, slots=True)
class PartInstance:
    id: PartInstanceId
    work_id: WorkId
    demand_item_id: DemandItemId
    part_type_id: PartTypeId
    sequence: int

    def __post_init__(self) -> None:
        require_identifier(self.id, PartInstanceId, field="part instance ID")
        require_identifier(self.work_id, WorkId, field="part instance work ID")
        require_identifier(self.demand_item_id, DemandItemId, field="source demand item ID")
        require_identifier(self.part_type_id, PartTypeId, field="part instance type ID")
        object.__setattr__(self, "sequence", _positive_integer(self.sequence, field_name="sequence"))


def expand_demand_items(
    demand_items: tuple[DemandItem, ...], batch_multiplier: int
) -> tuple[PartInstance, ...]:
    """Expand integer work batches deterministically (BATCH-001).

    Fractional batch rounding remains a pending Product Owner decision and is
    deliberately outside this function.
    """

    batch_multiplier = _positive_integer(batch_multiplier, field_name="batch multiplier")
    seen: set[DemandItemId] = set()
    instances: list[PartInstance] = []
    for demand in demand_items:
        if demand.id in seen:
            raise DomainValidationError(f"duplicate demand item ID: {demand.id}")
        seen.add(demand.id)
        for sequence in range(1, demand.base_quantity * batch_multiplier + 1):
            key = f"debbie/part-instance/{demand.work_id}/{demand.id}/{demand.part_type_id}/{sequence}"
            instances.append(
                PartInstance(
                    id=PartInstanceId.deterministic(NAMESPACE_URL, key),
                    work_id=demand.work_id,
                    demand_item_id=demand.id,
                    part_type_id=demand.part_type_id,
                    sequence=sequence,
                )
            )
    return tuple(instances)
