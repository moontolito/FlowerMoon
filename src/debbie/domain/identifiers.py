"""Stable, non-positional, strongly separated domain identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self, TypeVar
from uuid import UUID, uuid4, uuid5

from .errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class Identifier:
    """String-backed identifier with UUID generation and test injection."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise DomainValidationError("identifier value must be a string")
        value = self.value.strip()
        if not value:
            raise DomainValidationError("identifier must not be empty")
        object.__setattr__(self, "value", value)

    @classmethod
    def new(cls) -> Self:
        return cls(str(uuid4()))

    @classmethod
    def deterministic(cls, namespace: UUID, key: str) -> Self:
        if not key:
            raise DomainValidationError("deterministic identifier key must not be empty")
        return cls(str(uuid5(namespace, key)))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class WorkId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class PartTypeId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class DemandItemId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class PartInstanceId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class StockSpecificationId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class StockInstanceId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class LayoutId(Identifier):
    pass


@dataclass(frozen=True, slots=True)
class LayoutInstanceId(Identifier):
    pass


IdentifierType = TypeVar("IdentifierType", bound=Identifier)


def require_identifier(
    value: object, expected_type: type[IdentifierType], *, field: str
) -> IdentifierType:
    """Reject accidental interchange of unrelated identifier types."""

    if type(value) is not expected_type:
        raise DomainValidationError(f"{field} must be {expected_type.__name__}")
    return value
