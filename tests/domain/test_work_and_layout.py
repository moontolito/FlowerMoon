import pytest

from debbie.domain.errors import (
    DomainValidationError,
    DuplicatePlacementError,
    InvalidQuantityError,
    OwnershipError,
    UnknownReferenceError,
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
from debbie.domain.parts import DemandItem, PartInstance, PartType
from debbie.domain.process import ProcessProfile
from debbie.domain.stocks import StockInstance, StockSpecification
from debbie.domain.work import Work


def test_WORK_001_work_rejects_cross_work_demand() -> None:
    part = PartType(PartTypeId("p"), "Part", Dimensions(10, 10))
    demand = DemandItem(DemandItemId("d"), WorkId("other"), part.id, 1)
    with pytest.raises(OwnershipError):
        Work(
            WorkId("work"),
            "Work",
            1,
            ProcessProfile(),
            part_types=(part,),
            demand_items=(demand,),
        )


def test_WORK_001_work_rejects_cross_work_stock() -> None:
    spec = StockSpecification(StockSpecificationId("s"), "Sheet", Dimensions(100, 100))
    stock = StockInstance(StockInstanceId("si"), WorkId("other"), spec.id, 1)
    with pytest.raises(OwnershipError):
        Work(
            WorkId("work"),
            "Work",
            1,
            ProcessProfile(),
            stock_specifications=(spec,),
            stock_instances=(stock,),
        )


def test_WORK_001_work_rejects_layout_with_foreign_part_reference() -> None:
    spec = StockSpecification(StockSpecificationId("s"), "Sheet", Dimensions(100, 100))
    stock = StockInstance(StockInstanceId("si"), WorkId("work"), spec.id, 1)
    layout = Layout(
        LayoutId("l"),
        WorkId("work"),
        stock.id,
        ProcessProfile(),
        (Placement(PartInstanceId("foreign"), 0, 0),),
    )
    with pytest.raises(UnknownReferenceError):
        Work(
            WorkId("work"),
            "Work",
            1,
            ProcessProfile(),
            stock_specifications=(spec,),
            stock_instances=(stock,),
            layouts=(layout,),
        )


def test_layout_rejects_duplicate_part_instance() -> None:
    placement = Placement(PartInstanceId("pi"), 0, 0)
    with pytest.raises(DuplicatePlacementError):
        Layout(
            LayoutId("l"),
            WorkId("w"),
            StockInstanceId("s"),
            ProcessProfile(),
            (placement, placement),
        )


def test_layout_copy_on_write_operation_requires_and_runs_validator() -> None:
    layout = Layout(LayoutId("l"), WorkId("w"), StockInstanceId("s"), ProcessProfile())
    calls: list[Layout] = []
    placement = Placement(PartInstanceId("pi"), 0, 0)
    changed = layout.add_placement(placement, validate=calls.append)
    assert layout.placements == ()
    assert changed.placements == (placement,)
    assert calls == [changed]


def test_layout_copies_mutable_placement_input() -> None:
    source = [Placement(PartInstanceId("pi"), 0, 0)]
    layout = Layout(
        LayoutId("l"), WorkId("w"), StockInstanceId("s"), ProcessProfile(), source  # type: ignore[arg-type]
    )
    source.clear()
    assert layout.placements == (Placement(PartInstanceId("pi"), 0, 0),)


def test_work_from_inputs_expands_demand_with_work_batch() -> None:
    work_id = WorkId("w")
    part = PartType(PartTypeId("p"), "Part", Dimensions(10, 10))
    demand = DemandItem(DemandItemId("d"), work_id, part.id, 2)
    work = Work.from_inputs(
        id=work_id,
        name="Work",
        batch_multiplier=3,
        process_profile=ProcessProfile(),
        part_types=(part,),
        demand_items=(demand,),
    )
    assert len(work.part_instances) == 6


def test_work_copies_mutable_collection_inputs() -> None:
    source: list[PartType] = []
    work = Work(
        WorkId("w"), "Work", 1, ProcessProfile(), part_types=source  # type: ignore[arg-type]
    )
    source.append(PartType(PartTypeId("p"), "Part", Dimensions(1, 1)))
    assert work.part_types == ()


def test_WORK_001_part_instance_type_must_match_source_demand() -> None:
    work_id = WorkId("w")
    first_type = PartType(PartTypeId("first"), "First", Dimensions(1, 1))
    second_type = PartType(PartTypeId("second"), "Second", Dimensions(1, 1))
    demand = DemandItem(DemandItemId("d"), work_id, first_type.id, 1)
    instance = PartInstance(
        PartInstanceId("i"), work_id, demand.id, second_type.id, 1
    )
    with pytest.raises(DomainValidationError):
        Work(
            work_id,
            "Work",
            1,
            ProcessProfile(),
            part_types=(first_type, second_type),
            demand_items=(demand,),
            part_instances=(instance,),
        )


def test_work_rejects_fractional_batch_multiplier() -> None:
    with pytest.raises(InvalidQuantityError):
        Work(WorkId("w"), "Work", 1.5, ProcessProfile())  # type: ignore[arg-type]
