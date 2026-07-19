"""Immutable, unit-explicit mass calculation result contracts."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from math import isfinite

from debbie.nesting.models import ResultStatus
from debbie.domain.identifiers import (
    DemandItemId,
    StockInstanceId,
    WorkId,
    require_identifier,
)


def _require_finite_values(value: object) -> None:
    for item in fields(value):  # type: ignore[arg-type]
        field_name = item.name
        field_value = getattr(value, field_name)
        if isinstance(field_value, bool) or not isinstance(field_value, (int, float)):
            raise ValueError(f"{field_name} must be a numeric value")
        if not isfinite(float(field_value)):
            raise ValueError(f"{field_name} must be finite")


class MassCalculationStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_AVAILABLE_STOCK = "INSUFFICIENT_AVAILABLE_STOCK"
    PARTIAL_RESULT = "PARTIAL_RESULT"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    MATERIAL_DATA_REQUIRED = "MATERIAL_DATA_REQUIRED"
    WORK_RESULT_MISMATCH = "WORK_RESULT_MISMATCH"
    INVALID_RESULT = "INVALID_RESULT"


class MassCalculationDiagnosticCode(str, Enum):
    MATERIAL_DATA_REQUIRED = "MATERIAL_DATA_REQUIRED"
    NO_STOCK_AVAILABLE = "NO_STOCK_AVAILABLE"
    INSUFFICIENT_AVAILABLE_STOCK = "INSUFFICIENT_AVAILABLE_STOCK"
    WORK_RESULT_MISMATCH = "WORK_RESULT_MISMATCH"
    RESULT_DATA_MISMATCH = "RESULT_DATA_MISMATCH"
    FAILED_NESTING_VALIDATION = "FAILED_NESTING_VALIDATION"


class MassDiagnosticSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True, slots=True)
class MassCalculationDiagnostic:
    code: MassCalculationDiagnosticCode
    message: str
    severity: MassDiagnosticSeverity = MassDiagnosticSeverity.ERROR
    related_work_id: WorkId | None = None
    related_stock_instance_id: StockInstanceId | None = None
    related_demand_item_id: DemandItemId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", MassCalculationDiagnosticCode(self.code))
        object.__setattr__(self, "severity", MassDiagnosticSeverity(self.severity))
        message = self.message.strip()
        if not message:
            raise ValueError("mass diagnostic message must not be empty")
        object.__setattr__(self, "message", message)
        if self.related_work_id is not None:
            require_identifier(self.related_work_id, WorkId, field="diagnostic Work ID")
        if self.related_stock_instance_id is not None:
            require_identifier(
                self.related_stock_instance_id,
                StockInstanceId,
                field="diagnostic stock instance ID",
            )
        if self.related_demand_item_id is not None:
            require_identifier(
                self.related_demand_item_id,
                DemandItemId,
                field="diagnostic demand item ID",
            )


@dataclass(frozen=True, slots=True)
class WorkMassTotals:
    rectangular_part_mass_estimate_kg: float
    gross_physical_allocation_mass_kg: float
    gross_commercial_allocation_mass_kg: float
    physical_unused_allocation_mass_kg: float
    commercial_allocation_difference_kg: float
    commercial_material_allowance_kg: float
    physical_equivalent_sheets: float
    commercial_equivalent_sheets: float

    def __post_init__(self) -> None:
        _require_finite_values(self)
        if self.physical_equivalent_sheets < 0 or self.commercial_equivalent_sheets < 0:
            raise ValueError("equivalent sheet totals must be non-negative")


@dataclass(frozen=True, slots=True)
class NestingMassTotals:
    placed_rectangular_part_mass_estimate_kg: float
    unplaced_rectangular_part_mass_estimate_kg: float
    gross_physical_allocation_mass_kg: float
    gross_commercial_allocation_mass_kg: float
    physical_unused_allocation_mass_kg: float
    commercial_allocation_difference_kg: float
    commercial_material_allowance_kg: float
    physical_equivalent_sheets: float
    commercial_equivalent_sheets: float

    def __post_init__(self) -> None:
        _require_finite_values(self)
        if self.physical_equivalent_sheets < 0 or self.commercial_equivalent_sheets < 0:
            raise ValueError("equivalent sheet totals must be non-negative")


@dataclass(frozen=True, slots=True)
class MassPerProduct:
    rectangular_part_mass_estimate_kg: float
    gross_physical_allocation_mass_kg: float
    gross_commercial_allocation_mass_kg: float
    physical_unused_allocation_mass_kg: float
    commercial_allocation_difference_kg: float
    commercial_material_allowance_kg: float

    def __post_init__(self) -> None:
        _require_finite_values(self)


@dataclass(frozen=True, slots=True)
class WorkMassPlan:
    status: MassCalculationStatus
    totals: WorkMassTotals | None
    per_product: MassPerProduct | None
    diagnostics: tuple[MassCalculationDiagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", MassCalculationStatus(self.status))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        allowed = {
            MassCalculationStatus.AVAILABLE,
            MassCalculationStatus.INSUFFICIENT_AVAILABLE_STOCK,
            MassCalculationStatus.MATERIAL_DATA_REQUIRED,
        }
        if self.status not in allowed:
            raise ValueError(f"{self.status.value} is not a Work planning status")
        if self.status is MassCalculationStatus.AVAILABLE:
            if self.totals is None or self.per_product is None:
                raise ValueError("available Work mass plan requires totals and per-product values")
        elif self.status is MassCalculationStatus.INSUFFICIENT_AVAILABLE_STOCK:
            if self.totals is None or self.per_product is not None or not self.diagnostics:
                raise ValueError(
                    "insufficient Work mass plan requires totals, diagnostics, and no per-product values"
                )
        elif self.totals is not None or self.per_product is not None or not self.diagnostics:
            raise ValueError("unavailable Work mass plan requires diagnostics and no values")


@dataclass(frozen=True, slots=True)
class NestingMassResult:
    status: MassCalculationStatus
    nesting_status: ResultStatus
    totals: NestingMassTotals | None
    per_product: MassPerProduct | None
    diagnostics: tuple[MassCalculationDiagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", MassCalculationStatus(self.status))
        object.__setattr__(self, "nesting_status", ResultStatus(self.nesting_status))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.status is MassCalculationStatus.AVAILABLE:
            if (
                self.nesting_status is not ResultStatus.COMPLETE
                or self.totals is None
                or self.per_product is None
            ):
                raise ValueError("available result mass requires COMPLETE totals and per-product values")
        elif self.status is MassCalculationStatus.PARTIAL_RESULT:
            if (
                self.nesting_status is not ResultStatus.PARTIAL
                or self.totals is None
                or self.per_product is not None
            ):
                raise ValueError("partial result mass requires PARTIAL totals and no per-product values")
        elif self.totals is not None or self.per_product is not None or not self.diagnostics:
            raise ValueError("unavailable result mass requires diagnostics and no values")
