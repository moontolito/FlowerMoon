"""Nominal stock definitions and work-owned physical sheets."""

from __future__ import annotations

from dataclasses import dataclass

from .allocation import StockAllocation
from .errors import DomainValidationError, InvalidQuantityError
from .geometry_values import Dimensions
from .identifiers import StockInstanceId, StockSpecificationId, WorkId, require_identifier


@dataclass(frozen=True, slots=True)
class StockSpecification:
    id: StockSpecificationId
    name: str
    dimensions: Dimensions
    allocation: StockAllocation | None = None

    def __post_init__(self) -> None:
        require_identifier(self.id, StockSpecificationId, field="stock specification ID")
        name = self.name.strip()
        if not name:
            raise DomainValidationError("stock specification name must not be empty")
        if self.allocation is not None:
            if not isinstance(self.allocation, StockAllocation):
                raise DomainValidationError("stock allocation must be StockAllocation or None")
            if self.dimensions != self.allocation.allocated_dimensions:
                raise DomainValidationError(
                    "stock nesting dimensions must equal explicit allocated dimensions"
                )
        object.__setattr__(self, "name", name)

    @property
    def effective_allocation(self) -> StockAllocation:
        """Return explicit allocation or the legacy full-sheet compatibility view."""

        return self.allocation or StockAllocation.full(self.dimensions)

    @property
    def full_dimensions(self) -> Dimensions:
        """Nominal source-sheet dimensions used for provenance and OPT-001."""

        return self.effective_allocation.full_dimensions


@dataclass(frozen=True, slots=True)
class StockInstance:
    id: StockInstanceId
    work_id: WorkId
    specification_id: StockSpecificationId
    sequence: int

    def __post_init__(self) -> None:
        require_identifier(self.id, StockInstanceId, field="stock instance ID")
        require_identifier(self.work_id, WorkId, field="stock instance work ID")
        require_identifier(
            self.specification_id,
            StockSpecificationId,
            field="stock instance specification ID",
        )
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence <= 0:
            raise InvalidQuantityError("stock sequence must be a positive integer")
