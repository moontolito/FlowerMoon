"""Nominal stock definitions and work-owned physical sheets."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import DomainValidationError, InvalidQuantityError
from .geometry_values import Dimensions
from .identifiers import StockInstanceId, StockSpecificationId, WorkId, require_identifier


@dataclass(frozen=True, slots=True)
class StockSpecification:
    id: StockSpecificationId
    name: str
    dimensions: Dimensions

    def __post_init__(self) -> None:
        require_identifier(self.id, StockSpecificationId, field="stock specification ID")
        name = self.name.strip()
        if not name:
            raise DomainValidationError("stock specification name must not be empty")
        object.__setattr__(self, "name", name)


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
