"""Errors specific to deterministic nesting orchestration."""

from debbie.domain.errors import DebbieError, DomainValidationError


class NestingInputError(DomainValidationError):
    """A work is valid as data but invalid as a fresh solver input."""


class NestingCancelledError(DebbieError):
    """A caller-requested cancellation interrupted a synchronous solve."""
