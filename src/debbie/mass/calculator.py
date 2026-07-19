"""Deterministic pre-nesting and result-specific mass calculations."""

from __future__ import annotations

from math import frexp, fsum, isfinite, ldexp

from debbie.domain import StockAllocation, Work
from debbie.domain.parts import PartType
from debbie.domain.stocks import StockInstance, StockSpecification
from debbie.nesting.models import NestingResult, ResultStatus

from .models import (
    MassCalculationDiagnostic,
    MassCalculationDiagnosticCode,
    MassCalculationStatus,
    MassDiagnosticSeverity,
    MassPerProduct,
    NestingMassResult,
    NestingMassTotals,
    WorkMassPlan,
    WorkMassTotals,
)

MILLIMETRE_DENSITY_TO_KILOGRAM_DIVISOR = 1_000_000.0
MASS_COMPARISON_EPSILON_KG = 1e-12


def _rectangular_mass_kg(
    length_mm: float, width_mm: float, thickness_mm: float, density_g_per_cm3: float
) -> float:
    mantissa = 1.0
    exponent = 0
    for factor in (
        length_mm,
        width_mm,
        thickness_mm,
        density_g_per_cm3,
        1.0 / MILLIMETRE_DENSITY_TO_KILOGRAM_DIVISOR,
    ):
        factor_mantissa, factor_exponent = frexp(factor)
        mantissa *= factor_mantissa
        exponent += factor_exponent
        mantissa, normalization_exponent = frexp(mantissa)
        exponent += normalization_exponent
    result = ldexp(mantissa, exponent)
    if not isfinite(result):
        raise OverflowError("rectangular mass is outside the finite float range")
    return result


def _material_required(work: Work) -> MassCalculationDiagnostic:
    return MassCalculationDiagnostic(
        MassCalculationDiagnosticCode.MATERIAL_DATA_REQUIRED,
        "Work requires explicit material density and thickness for mass calculation",
        related_work_id=work.id,
    )


def _classified_values(work: Work) -> tuple[float, float] | None:
    if not work.is_material_classified:
        return None
    assert work.material is not None and work.thickness is not None
    return (
        work.thickness.millimetres,
        work.material.effective_density.grams_per_cubic_centimetre,
    )


def _allocation_for(
    specification: StockSpecification, *, require_explicit: bool = True
) -> StockAllocation:
    if require_explicit and specification.allocation is None:
        raise RuntimeError("classified Work contains a stock without explicit allocation")
    return specification.effective_allocation


def _stock_mass_terms(
    instances: tuple[StockInstance, ...],
    specifications: dict,
    *,
    thickness_mm: float,
    density_g_per_cm3: float,
) -> tuple[float, float, float, float]:
    physical_masses: list[float] = []
    commercial_masses: list[float] = []
    physical_fractions: list[float] = []
    commercial_fractions: list[float] = []
    for instance in sorted(instances, key=lambda item: str(item.id)):
        specification: StockSpecification = specifications[instance.specification_id]
        allocation = _allocation_for(specification)
        physical_masses.append(
            _rectangular_mass_kg(
                allocation.allocated_dimensions.length,
                allocation.allocated_dimensions.width,
                thickness_mm,
                density_g_per_cm3,
            )
        )
        full_mass = _rectangular_mass_kg(
            allocation.full_dimensions.length,
            allocation.full_dimensions.width,
            thickness_mm,
            density_g_per_cm3,
        )
        commercial_masses.append(full_mass * allocation.commercial_allocation_fraction)
        physical_fractions.append(allocation.physical_allocation_fraction)
        commercial_fractions.append(allocation.commercial_allocation_fraction)
    return (
        fsum(physical_masses),
        fsum(commercial_masses),
        fsum(physical_fractions),
        fsum(commercial_fractions),
    )


def _part_mass_kg(
    part_type: PartType, *, thickness_mm: float, density_g_per_cm3: float
) -> float:
    return _rectangular_mass_kg(
        part_type.dimensions.length,
        part_type.dimensions.width,
        thickness_mm,
        density_g_per_cm3,
    )


def _per_product_from_plan(totals: WorkMassTotals, batch_multiplier: int) -> MassPerProduct:
    divisor = float(batch_multiplier)
    return MassPerProduct(
        rectangular_part_mass_estimate_kg=totals.rectangular_part_mass_estimate_kg / divisor,
        gross_physical_allocation_mass_kg=totals.gross_physical_allocation_mass_kg / divisor,
        gross_commercial_allocation_mass_kg=totals.gross_commercial_allocation_mass_kg
        / divisor,
        physical_unused_allocation_mass_kg=totals.physical_unused_allocation_mass_kg / divisor,
        commercial_allocation_difference_kg=totals.commercial_allocation_difference_kg
        / divisor,
        commercial_material_allowance_kg=totals.commercial_material_allowance_kg / divisor,
    )


def calculate_work_mass_plan(work: Work) -> WorkMassPlan:
    """Calculate available-inventory and expanded-demand planning values."""

    if not isinstance(work, Work):
        raise TypeError("calculate_work_mass_plan requires a Work")
    classified = _classified_values(work)
    if classified is None:
        return WorkMassPlan(
            MassCalculationStatus.MATERIAL_DATA_REQUIRED,
            None,
            None,
            (_material_required(work),),
        )
    thickness_mm, density = classified
    part_types = {item.id: item for item in work.part_types}
    part_terms = [
        _part_mass_kg(
            part_types[demand.part_type_id],
            thickness_mm=thickness_mm,
            density_g_per_cm3=density,
        )
        * demand.base_quantity
        * work.batch_multiplier
        for demand in sorted(work.demand_items, key=lambda item: str(item.id))
    ]
    rectangular_mass = fsum(part_terms)
    specifications = {item.id: item for item in work.stock_specifications}
    physical, commercial, physical_sheets, commercial_sheets = _stock_mass_terms(
        work.stock_instances,
        specifications,
        thickness_mm=thickness_mm,
        density_g_per_cm3=density,
    )
    totals = WorkMassTotals(
        rectangular_part_mass_estimate_kg=rectangular_mass,
        gross_physical_allocation_mass_kg=physical,
        gross_commercial_allocation_mass_kg=commercial,
        physical_unused_allocation_mass_kg=physical - rectangular_mass,
        commercial_allocation_difference_kg=commercial - physical,
        commercial_material_allowance_kg=commercial - rectangular_mass,
        physical_equivalent_sheets=physical_sheets,
        commercial_equivalent_sheets=commercial_sheets,
    )
    diagnostics: list[MassCalculationDiagnostic] = []
    insufficient = physical < rectangular_mass
    if not work.stock_instances and rectangular_mass > 0.0:
        diagnostics.append(
            MassCalculationDiagnostic(
                MassCalculationDiagnosticCode.NO_STOCK_AVAILABLE,
                "Work has expanded demand but no available stock instances",
                MassDiagnosticSeverity.WARNING,
                related_work_id=work.id,
            )
        )
    if insufficient:
        diagnostics.append(
            MassCalculationDiagnostic(
                MassCalculationDiagnosticCode.INSUFFICIENT_AVAILABLE_STOCK,
                "Available physical allocation mass is below rectangular demand estimate",
                MassDiagnosticSeverity.WARNING,
                related_work_id=work.id,
            )
        )
    status = (
        MassCalculationStatus.INSUFFICIENT_AVAILABLE_STOCK
        if insufficient
        else MassCalculationStatus.AVAILABLE
    )
    return WorkMassPlan(
        status,
        totals,
        None if insufficient else _per_product_from_plan(totals, work.batch_multiplier),
        tuple(diagnostics),
    )


def _unavailable_result(
    result: NestingResult,
    status: MassCalculationStatus,
    diagnostics: tuple[MassCalculationDiagnostic, ...],
) -> NestingMassResult:
    return NestingMassResult(status, result.status, None, None, diagnostics)


def calculate_nesting_result_mass(work: Work, result: NestingResult) -> NestingMassResult:
    """Calculate consumed-stock mass without mixing in unused Work inventory."""

    if not isinstance(work, Work) or not isinstance(result, NestingResult):
        raise TypeError("calculate_nesting_result_mass requires Work and NestingResult")
    if result.work_id != work.id:
        return _unavailable_result(
            result,
            MassCalculationStatus.WORK_RESULT_MISMATCH,
            (
                MassCalculationDiagnostic(
                    MassCalculationDiagnosticCode.WORK_RESULT_MISMATCH,
                    f"Nesting result belongs to {result.work_id}, not {work.id}",
                    related_work_id=work.id,
                ),
            ),
        )
    if result.status is ResultStatus.FAILED_VALIDATION:
        messages = tuple(
            MassCalculationDiagnostic(
                MassCalculationDiagnosticCode.FAILED_NESTING_VALIDATION,
                diagnostic.message,
                related_work_id=work.id,
            )
            for diagnostic in result.diagnostics
        )
        return _unavailable_result(result, MassCalculationStatus.FAILED_VALIDATION, messages)
    classified = _classified_values(work)
    if classified is None:
        return _unavailable_result(
            result,
            MassCalculationStatus.MATERIAL_DATA_REQUIRED,
            (_material_required(work),),
        )
    if result.requested_part_count != len(work.part_instances):
        return _unavailable_result(
            result,
            MassCalculationStatus.INVALID_RESULT,
            (
                MassCalculationDiagnostic(
                    MassCalculationDiagnosticCode.RESULT_DATA_MISMATCH,
                    "Nesting result demand count does not match the Work snapshot",
                    related_work_id=work.id,
                ),
            ),
        )

    thickness_mm, density = classified
    stock_instances = {item.id: item for item in work.stock_instances}
    specifications = {item.id: item for item in work.stock_specifications}
    consumed_ids = [layout.stock_instance_id for layout in result.layouts]
    if len(consumed_ids) != len(set(consumed_ids)) or any(
        identifier not in stock_instances for identifier in consumed_ids
    ):
        return _unavailable_result(
            result,
            MassCalculationStatus.INVALID_RESULT,
            (
                MassCalculationDiagnostic(
                    MassCalculationDiagnosticCode.RESULT_DATA_MISMATCH,
                    "Nesting result references duplicate or unknown stock instances",
                    related_work_id=work.id,
                    related_stock_instance_id=next(
                        (
                            identifier
                            for identifier in consumed_ids
                            if consumed_ids.count(identifier) > 1
                            or identifier not in stock_instances
                        ),
                        None,
                    ),
                ),
            ),
        )
    consumed = tuple(stock_instances[identifier] for identifier in consumed_ids)
    physical, commercial, physical_sheets, commercial_sheets = _stock_mass_terms(
        consumed,
        specifications,
        thickness_mm=thickness_mm,
        density_g_per_cm3=density,
    )

    part_types = {item.id: item for item in work.part_types}
    part_instances = {item.id: item for item in work.part_instances}
    demand_items = {item.id: item for item in work.demand_items}
    placed_ids = [
        placement.part_instance_id
        for layout in result.layouts
        for placement in layout.placements
    ]
    if any(identifier not in part_instances for identifier in placed_ids):
        return _unavailable_result(
            result,
            MassCalculationStatus.INVALID_RESULT,
            (
                MassCalculationDiagnostic(
                    MassCalculationDiagnosticCode.RESULT_DATA_MISMATCH,
                    "Nesting result references an unknown part instance",
                    related_work_id=work.id,
                ),
            ),
        )
    placed_by_demand = {identifier: 0 for identifier in demand_items}
    for identifier in placed_ids:
        placed_by_demand[part_instances[identifier].demand_item_id] += 1
    placed_mass = fsum(
        _part_mass_kg(
            part_types[part_instances[identifier].part_type_id],
            thickness_mm=thickness_mm,
            density_g_per_cm3=density,
        )
        for identifier in sorted(placed_ids, key=str)
    )
    unplaced_terms: list[float] = []
    unplaced_by_demand: dict = {}
    for unplaced in sorted(result.unplaced_demand, key=lambda item: str(item.demand_item_id)):
        part_type = part_types.get(unplaced.part_type_id)
        demand_item = demand_items.get(unplaced.demand_item_id)
        if (
            part_type is None
            or demand_item is None
            or demand_item.part_type_id != unplaced.part_type_id
            or unplaced.work_id != work.id
        ):
            return _unavailable_result(
                result,
                MassCalculationStatus.INVALID_RESULT,
                (
                    MassCalculationDiagnostic(
                        MassCalculationDiagnosticCode.RESULT_DATA_MISMATCH,
                        "Nesting result contains unknown or cross-Work unplaced demand",
                        related_work_id=work.id,
                        related_demand_item_id=unplaced.demand_item_id,
                    ),
                ),
            )
        if unplaced.demand_item_id in unplaced_by_demand:
            return _unavailable_result(
                result,
                MassCalculationStatus.INVALID_RESULT,
                (
                    MassCalculationDiagnostic(
                        MassCalculationDiagnosticCode.RESULT_DATA_MISMATCH,
                        "Nesting result contains duplicate unplaced demand entries",
                        related_work_id=work.id,
                        related_demand_item_id=unplaced.demand_item_id,
                    ),
                ),
            )
        unplaced_by_demand[unplaced.demand_item_id] = unplaced.remaining_quantity
        unplaced_terms.append(
            _part_mass_kg(
                part_type,
                thickness_mm=thickness_mm,
                density_g_per_cm3=density,
            )
            * unplaced.remaining_quantity
        )
    for demand in sorted(work.demand_items, key=lambda item: str(item.id)):
        expected = demand.base_quantity * work.batch_multiplier
        actual = placed_by_demand[demand.id] + unplaced_by_demand.get(demand.id, 0)
        if actual != expected:
            return _unavailable_result(
                result,
                MassCalculationStatus.INVALID_RESULT,
                (
                    MassCalculationDiagnostic(
                        MassCalculationDiagnosticCode.RESULT_DATA_MISMATCH,
                        "Placed and unplaced quantities do not reconcile for demand item",
                        related_work_id=work.id,
                        related_demand_item_id=demand.id,
                    ),
                ),
            )
    unplaced_mass = fsum(unplaced_terms)
    expected_demand_mass = fsum(
        _part_mass_kg(
            part_types[demand.part_type_id],
            thickness_mm=thickness_mm,
            density_g_per_cm3=density,
        )
        * demand.base_quantity
        * work.batch_multiplier
        for demand in sorted(work.demand_items, key=lambda item: str(item.id))
    )
    if abs((placed_mass + unplaced_mass) - expected_demand_mass) > MASS_COMPARISON_EPSILON_KG:
        return _unavailable_result(
            result,
            MassCalculationStatus.INVALID_RESULT,
            (
                MassCalculationDiagnostic(
                    MassCalculationDiagnosticCode.RESULT_DATA_MISMATCH,
                    "Placed and unplaced rectangular mass does not reconcile with Work demand",
                    related_work_id=work.id,
                ),
            ),
        )
    totals = NestingMassTotals(
        placed_rectangular_part_mass_estimate_kg=placed_mass,
        unplaced_rectangular_part_mass_estimate_kg=unplaced_mass,
        gross_physical_allocation_mass_kg=physical,
        gross_commercial_allocation_mass_kg=commercial,
        physical_unused_allocation_mass_kg=physical - placed_mass,
        commercial_allocation_difference_kg=commercial - physical,
        commercial_material_allowance_kg=commercial - placed_mass,
        physical_equivalent_sheets=physical_sheets,
        commercial_equivalent_sheets=commercial_sheets,
    )
    if result.status is ResultStatus.PARTIAL:
        return NestingMassResult(
            MassCalculationStatus.PARTIAL_RESULT,
            result.status,
            totals,
            None,
            (),
        )
    if result.unplaced_demand:
        return _unavailable_result(
            result,
            MassCalculationStatus.INVALID_RESULT,
            (
                MassCalculationDiagnostic(
                    MassCalculationDiagnosticCode.RESULT_DATA_MISMATCH,
                    "Complete result contains non-zero unplaced rectangular mass",
                    related_work_id=work.id,
                ),
            ),
        )
    plan_like = WorkMassTotals(
        rectangular_part_mass_estimate_kg=placed_mass,
        gross_physical_allocation_mass_kg=physical,
        gross_commercial_allocation_mass_kg=commercial,
        physical_unused_allocation_mass_kg=physical - placed_mass,
        commercial_allocation_difference_kg=commercial - physical,
        commercial_material_allowance_kg=commercial - placed_mass,
        physical_equivalent_sheets=physical_sheets,
        commercial_equivalent_sheets=commercial_sheets,
    )
    return NestingMassResult(
        MassCalculationStatus.AVAILABLE,
        result.status,
        totals,
        _per_product_from_plan(plan_like, work.batch_multiplier),
        (),
    )
