"""Immutable result contracts for the first Debbie nesting engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from debbie.domain.identifiers import DemandItemId, PartTypeId, WorkId, require_identifier
from debbie.domain.layouts import Layout

from .constants import FEASIBILITY_CLASS, OBJECTIVE_POLICY


class ResultStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED_VALIDATION = "FAILED_VALIDATION"


class UnplacedReasonCode(str, Enum):
    PART_EXCEEDS_ALL_USABLE_STOCK = "PART_EXCEEDS_ALL_USABLE_STOCK"
    INSUFFICIENT_STOCK_QUANTITY = "INSUFFICIENT_STOCK_QUANTITY"
    NO_VALID_PLACEMENT_FOUND = "NO_VALID_PLACEMENT_FOUND"
    ORIENTATION_CONSTRAINT = "ORIENTATION_CONSTRAINT"
    INVALID_INPUT_REJECTED_BEFORE_RUN = "INVALID_INPUT_REJECTED_BEFORE_RUN"


@dataclass(frozen=True, slots=True)
class FeasibilityMetadata:
    classification: str = FEASIBILITY_CLASS
    rectangular: bool = True
    collision_free: bool = True
    non_guillotine: bool = True
    has_toolpath: bool = False
    machine_ready: bool = False


@dataclass(frozen=True, slots=True)
class ObjectiveMetadata:
    policy: tuple[str, ...] = OBJECTIVE_POLICY
    placed_required_demand: int = 0
    physical_stock_sheets_consumed: int = 0
    nominal_full_stock_area_consumed: float = 0.0
    unused_usable_area: float = 0.0
    stable_tie_breakers: tuple[str, ...] = field(default_factory=tuple)
    globally_optimal: bool = False
    result_description: str = "generated result"


@dataclass(frozen=True, slots=True)
class UnplacedDemand:
    work_id: WorkId
    demand_item_id: DemandItemId
    part_type_id: PartTypeId
    remaining_quantity: int
    reason_code: UnplacedReasonCode
    diagnostic_details: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        require_identifier(self.work_id, WorkId, field="unplaced work ID")
        require_identifier(self.demand_item_id, DemandItemId, field="unplaced demand item ID")
        require_identifier(self.part_type_id, PartTypeId, field="unplaced part type ID")
        if (
            isinstance(self.remaining_quantity, bool)
            or not isinstance(self.remaining_quantity, int)
            or self.remaining_quantity <= 0
        ):
            raise ValueError("remaining quantity must be a positive integer")
        object.__setattr__(self, "reason_code", UnplacedReasonCode(self.reason_code))
        object.__setattr__(self, "diagnostic_details", tuple(self.diagnostic_details))


@dataclass(frozen=True, slots=True)
class ValidationDiagnostic:
    reason_code: UnplacedReasonCode
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_code", UnplacedReasonCode(self.reason_code))
        if self.reason_code is not UnplacedReasonCode.INVALID_INPUT_REJECTED_BEFORE_RUN:
            raise ValueError("validation diagnostics require the invalid-input reason code")
        if not self.message.strip():
            raise ValueError("validation diagnostic message must not be empty")


@dataclass(frozen=True, slots=True)
class NestingResult:
    work_id: WorkId
    status: ResultStatus
    strategy_id: str
    strategy_display_name: str
    engine_version: str
    decision_policy_version: str
    layouts: tuple[Layout, ...]
    placed_part_count: int
    requested_part_count: int
    unplaced_demand: tuple[UnplacedDemand, ...]
    objective: ObjectiveMetadata
    feasibility: FeasibilityMetadata = field(default_factory=FeasibilityMetadata)
    diagnostics: tuple[ValidationDiagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        require_identifier(self.work_id, WorkId, field="result work ID")
        object.__setattr__(self, "status", ResultStatus(self.status))
        object.__setattr__(self, "layouts", tuple(self.layouts))
        object.__setattr__(self, "unplaced_demand", tuple(self.unplaced_demand))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.placed_part_count < 0 or self.requested_part_count < 0:
            raise ValueError("result counts must be non-negative")
        actual_placed = sum(len(layout.placements) for layout in self.layouts)
        if actual_placed != self.placed_part_count:
            raise ValueError("placed count does not match result layouts")
        if self.objective.placed_required_demand != self.placed_part_count:
            raise ValueError("objective placed demand does not match result layouts")
        if self.objective.physical_stock_sheets_consumed != len(self.layouts):
            raise ValueError("objective sheet count does not match result layouts")
        if any(layout.work_id != self.work_id for layout in self.layouts):
            raise ValueError("every result layout must belong to the result work")
        placed_ids = [
            placement.part_instance_id
            for layout in self.layouts
            for placement in layout.placements
        ]
        if len(placed_ids) != len(set(placed_ids)):
            raise ValueError("a physical part instance may occur in only one result layout")
        if self.status is ResultStatus.FAILED_VALIDATION:
            if self.layouts or self.placed_part_count:
                raise ValueError("failed validation must not contain placements")
            if self.requested_part_count or self.unplaced_demand:
                raise ValueError("failed validation must not report expanded demand")
            if not self.diagnostics:
                raise ValueError("failed validation requires a structured diagnostic")
            return
        unplaced_quantity = sum(item.remaining_quantity for item in self.unplaced_demand)
        if self.requested_part_count != self.placed_part_count + unplaced_quantity:
            raise ValueError("requested quantity must equal placed plus unplaced quantity")
        if self.status is ResultStatus.COMPLETE and unplaced_quantity:
            raise ValueError("complete result must not contain unplaced demand")
        if self.status is ResultStatus.PARTIAL and unplaced_quantity <= 0:
            raise ValueError("partial result requires positive unplaced demand")
        if self.diagnostics:
            raise ValueError("successful or partial results must not contain validation diagnostics")
