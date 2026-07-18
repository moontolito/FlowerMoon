from dataclasses import replace

import pytest

from debbie.domain.errors import (
    ClearanceViolationError,
    OutOfBoundsError,
    OverlapError,
    OwnershipError,
    UnsupportedOrientationError,
)
from debbie.domain.geometry_values import Dimensions
from debbie.domain.identifiers import (
    DemandItemId,
    LayoutId,
    PartInstanceId,
    PartTypeId,
    StockInstanceId,
    StockSpecificationId,
    WorkId,
)
from debbie.domain.layouts import Layout, Placement
from debbie.domain.orientation import Orientation
from debbie.domain.parts import PartInstance, PartType
from debbie.domain.process import ProcessProfile
from debbie.domain.stocks import StockInstance, StockSpecification
from debbie.geometry.predicates import validate_layout_geometry


def _context(*, process: ProcessProfile = ProcessProfile()):
    work_id = WorkId("work")
    part_type = PartType(PartTypeId("part"), "Part", Dimensions(10, 10))
    stock_spec = StockSpecification(
        StockSpecificationId("stock-spec"), "Sheet", Dimensions(30, 20)
    )
    stock = StockInstance(StockInstanceId("stock"), work_id, stock_spec.id, 1)
    first = PartInstance(
        PartInstanceId("one"), work_id, DemandItemId("demand"), part_type.id, 1
    )
    second = PartInstance(
        PartInstanceId("two"), work_id, DemandItemId("demand"), part_type.id, 2
    )
    layout = Layout(LayoutId("layout"), work_id, stock.id, process)
    return layout, stock, stock_spec, {first.id: first, second.id: second}, {part_type.id: part_type}


def _validate(layout: Layout, context: tuple) -> None:
    _, stock, stock_spec, instances, part_types = context
    validate_layout_geometry(
        layout,
        stock_instance=stock,
        stock_specification=stock_spec,
        part_instances=instances,
        part_types=part_types,
    )


def test_layout_geometry_accepts_valid_placements_and_retains_process_snapshot() -> None:
    process = ProcessProfile(kerf=4, minimum_part_clearance=2)
    context = _context(process=process)
    layout = replace(
        context[0],
        placements=(Placement(PartInstanceId("one"), 0, 0), Placement(PartInstanceId("two"), 12, 0)),
    )
    _validate(layout, context)
    assert layout.process_profile == process


def test_layout_geometry_rejects_overlap() -> None:
    context = _context()
    layout = replace(
        context[0],
        placements=(Placement(PartInstanceId("one"), 0, 0), Placement(PartInstanceId("two"), 9, 0)),
    )
    with pytest.raises(OverlapError):
        _validate(layout, context)


def test_layout_geometry_rejects_clearance_violation() -> None:
    context = _context(process=ProcessProfile(minimum_part_clearance=2))
    layout = replace(
        context[0],
        placements=(Placement(PartInstanceId("one"), 0, 0), Placement(PartInstanceId("two"), 11, 0)),
    )
    with pytest.raises(ClearanceViolationError):
        _validate(layout, context)


def test_layout_geometry_rejects_out_of_bounds_placement() -> None:
    context = _context()
    layout = replace(context[0], placements=(Placement(PartInstanceId("one"), 21, 0),))
    with pytest.raises(OutOfBoundsError):
        _validate(layout, context)


def test_GEO_004_positive_boundary_clearance_is_enforced() -> None:
    context = _context(process=ProcessProfile(boundary_clearance=1))
    layout = replace(context[0], placements=(Placement(PartInstanceId("one"), 0, 1),))
    with pytest.raises(OutOfBoundsError):
        _validate(layout, context)


def test_ROT_001_layout_validation_enforces_part_orientation_policy() -> None:
    context = _context()
    part_type = next(iter(context[4].values()))
    restricted = replace(part_type, allowed_orientations=frozenset({Orientation.ZERO}))
    part_types = {restricted.id: restricted}
    changed_context = (*context[:4], part_types)
    layout = replace(
        context[0], placements=(Placement(PartInstanceId("one"), 0, 0, Orientation.DEG_90),)
    )
    with pytest.raises(UnsupportedOrientationError):
        _validate(layout, changed_context)


def test_WORK_001_layout_validation_rejects_cross_work_part() -> None:
    context = _context()
    instances = dict(context[3])
    foreign = replace(instances[PartInstanceId("one")], work_id=WorkId("other"))
    instances[foreign.id] = foreign
    changed_context = (*context[:3], instances, context[4])
    layout = replace(context[0], placements=(Placement(foreign.id, 0, 0),))
    with pytest.raises(OwnershipError):
        _validate(layout, changed_context)


def test_KERF_001_changing_kerf_alone_does_not_change_placement_validity() -> None:
    zero_context = _context(process=ProcessProfile(kerf=0, minimum_part_clearance=1))
    wide_context = _context(process=ProcessProfile(kerf=8, minimum_part_clearance=1))
    placements = (Placement(PartInstanceId("one"), 0, 0), Placement(PartInstanceId("two"), 11, 0))
    _validate(replace(zero_context[0], placements=placements), zero_context)
    _validate(replace(wide_context[0], placements=placements), wide_context)
