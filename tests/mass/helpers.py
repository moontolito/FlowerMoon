from __future__ import annotations

from debbie.domain import (
    DemandItem,
    DemandItemId,
    Density,
    DensitySource,
    Dimensions,
    MaterialCategoryKey,
    MaterialGradeKey,
    MaterialIdentity,
    PartType,
    PartTypeId,
    ProcessProfile,
    StockAllocation,
    StockInstance,
    StockInstanceId,
    StockSpecification,
    StockSpecificationId,
    Thickness,
    Work,
    WorkId,
)


def classified_work(
    *,
    work_id: str = "work",
    batch: int = 1,
    density: float = 7.9,
    thickness: float = 3.0,
    parts: tuple[tuple[str, float, float, int], ...] = (("p", 10.0, 10.0, 1),),
    stocks: tuple[tuple[str, float, float, float, float, float, int], ...] = (
        ("s", 100.0, 100.0, 100.0, 100.0, 1.0, 1),
    ),
) -> Work:
    owner = WorkId(work_id)
    part_types = tuple(
        PartType(PartTypeId(key), key, Dimensions(length, width))
        for key, length, width, _ in parts
    )
    demand_items = tuple(
        DemandItem(DemandItemId(f"d-{key}"), owner, PartTypeId(key), quantity)
        for key, _, _, quantity in parts
    )
    specifications: list[StockSpecification] = []
    instances: list[StockInstance] = []
    for key, full_l, full_w, allocated_l, allocated_w, commercial, quantity in stocks:
        specification_id = StockSpecificationId(key)
        allocated = Dimensions(allocated_l, allocated_w)
        specifications.append(
            StockSpecification(
                specification_id,
                key,
                allocated,
                StockAllocation(Dimensions(full_l, full_w), allocated, commercial),
            )
        )
        instances.extend(
            StockInstance(
                StockInstanceId(f"{key}-{sequence}"), owner, specification_id, sequence
            )
            for sequence in range(1, quantity + 1)
        )
    return Work.from_inputs(
        id=owner,
        name=f"Work {work_id}",
        batch_multiplier=batch,
        process_profile=ProcessProfile(),
        part_types=part_types,
        demand_items=demand_items,
        stock_specifications=tuple(specifications),
        stock_instances=tuple(instances),
        material=MaterialIdentity(
            MaterialCategoryKey("steel"),
            "Steel",
            MaterialGradeKey("S235"),
            "S235",
            Density(density),
            DensitySource.EXPLICIT_OVERRIDE,
        ),
        thickness=Thickness(thickness),
    )
