"""Explicit errors raised by Debbie domain and geometry validation."""


class DebbieError(Exception):
    """Base class for expected Debbie errors."""


class DomainValidationError(DebbieError, ValueError):
    """A domain value or aggregate invariant is invalid."""


class InvalidDimensionError(DomainValidationError):
    """A dimensional value violates its finite/sign policy."""


class InvalidTrimError(DomainValidationError):
    """Trim consumes all of at least one stock dimension."""


class UnsupportedOrientationError(DomainValidationError):
    """An orientation is unsupported by the MVP or a part type."""


class InvalidQuantityError(DomainValidationError):
    """A quantity or batch multiplier is not a positive integer."""


class OwnershipError(DomainValidationError):
    """Entities from different works were combined."""


class DuplicatePlacementError(DomainValidationError):
    """A part instance occurs more than once in a layout."""


class UnknownReferenceError(DomainValidationError):
    """An entity references an ID not present in its validation context."""


class OutOfBoundsError(DomainValidationError):
    """A placement is outside the effective stock region."""


class OverlapError(DomainValidationError):
    """Two nominal part rectangles overlap."""


class ClearanceViolationError(DomainValidationError):
    """Two parts do not maintain the configured minimum clearance."""
