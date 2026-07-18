"""Public API for Debbie's first deterministic rectangle nesting engine."""

from .constants import (
    DECISION_POLICY_VERSION,
    ENGINE_VERSION,
    FEASIBILITY_CLASS,
    STRATEGY_DISPLAY_NAME,
    STRATEGY_ID,
)
from .errors import NestingCancelledError, NestingInputError
from .models import (
    FeasibilityMetadata,
    NestingResult,
    ObjectiveMetadata,
    ResultStatus,
    UnplacedDemand,
    UnplacedReasonCode,
    ValidationDiagnostic,
)
from .objectives import objective_is_better, objective_sort_key
from .solver import LeftToRightNestingSolver, nest_work

__all__ = [
    "DECISION_POLICY_VERSION",
    "ENGINE_VERSION",
    "FEASIBILITY_CLASS",
    "STRATEGY_DISPLAY_NAME",
    "STRATEGY_ID",
    "FeasibilityMetadata",
    "LeftToRightNestingSolver",
    "NestingCancelledError",
    "NestingInputError",
    "NestingResult",
    "ObjectiveMetadata",
    "ResultStatus",
    "UnplacedDemand",
    "UnplacedReasonCode",
    "ValidationDiagnostic",
    "nest_work",
    "objective_is_better",
    "objective_sort_key",
]
