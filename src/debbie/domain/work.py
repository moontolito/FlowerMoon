"""Independent Work aggregate governed by WORK-001 and BATCH-001."""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import DomainValidationError, InvalidQuantityError, OwnershipError, UnknownReferenceError
from .identifiers import WorkId, require_identifier
from .layouts import Layout, LayoutInstance
from .material import MaterialIdentity
from .parts import DemandItem, PartInstance, PartType, expand_demand_items
from .process import ProcessProfile
from .stocks import StockInstance, StockSpecification
from .thickness import Thickness


def _assert_unique(items: tuple[object, ...], *, label: str) -> None:
    ids = [getattr(item, "id") for item in items]
    if len(ids) != len(set(ids)):
        raise DomainValidationError(f"duplicate {label} ID")


@dataclass(frozen=True, slots=True)
class Work:
    id: WorkId
    name: str
    batch_multiplier: int
    process_profile: ProcessProfile
    part_types: tuple[PartType, ...] = field(default_factory=tuple)
    demand_items: tuple[DemandItem, ...] = field(default_factory=tuple)
    part_instances: tuple[PartInstance, ...] = field(default_factory=tuple)
    stock_specifications: tuple[StockSpecification, ...] = field(default_factory=tuple)
    stock_instances: tuple[StockInstance, ...] = field(default_factory=tuple)
    layouts: tuple[Layout, ...] = field(default_factory=tuple)
    layout_instances: tuple[LayoutInstance, ...] = field(default_factory=tuple)
    material: MaterialIdentity | None = None
    thickness: Thickness | None = None

    def __post_init__(self) -> None:
        require_identifier(self.id, WorkId, field="work ID")
        name = self.name.strip()
        if not name:
            raise DomainValidationError("work name must not be empty")
        if (
            isinstance(self.batch_multiplier, bool)
            or not isinstance(self.batch_multiplier, int)
            or self.batch_multiplier <= 0
        ):
            raise InvalidQuantityError("batch multiplier must be a positive integer")
        object.__setattr__(self, "name", name)

        if (self.material is None) != (self.thickness is None):
            raise DomainValidationError(
                "material and thickness must either both be present or both be absent"
            )
        if self.material is not None:
            if not isinstance(self.material, MaterialIdentity):
                raise DomainValidationError("work material must be MaterialIdentity or None")
            if not isinstance(self.thickness, Thickness):
                raise DomainValidationError("work thickness must be Thickness or None")

        collection_fields = (
            "part_types",
            "demand_items",
            "part_instances",
            "stock_specifications",
            "stock_instances",
            "layouts",
            "layout_instances",
        )
        for field_name in collection_fields:
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))

        collections = (
            (self.part_types, "part type"),
            (self.demand_items, "demand item"),
            (self.part_instances, "part instance"),
            (self.stock_specifications, "stock specification"),
            (self.stock_instances, "stock instance"),
            (self.layouts, "layout"),
            (self.layout_instances, "layout instance"),
        )
        for items, label in collections:
            _assert_unique(items, label=label)

        if self.is_material_classified and any(
            specification.allocation is None for specification in self.stock_specifications
        ):
            raise DomainValidationError(
                "material-classified works require explicit stock allocations"
            )

        part_type_ids = {item.id for item in self.part_types}
        demands_by_id = {item.id: item for item in self.demand_items}
        part_instance_ids = {item.id for item in self.part_instances}
        stock_specification_ids = {item.id for item in self.stock_specifications}
        stock_instance_ids = {item.id for item in self.stock_instances}
        layout_ids = {item.id for item in self.layouts}

        for demand in self.demand_items:
            self._require_owner(demand.work_id, "demand item")
            if demand.part_type_id not in part_type_ids:
                raise UnknownReferenceError(f"unknown demand part type: {demand.part_type_id}")
        for instance in self.part_instances:
            self._require_owner(instance.work_id, "part instance")
            if instance.demand_item_id not in demands_by_id:
                raise UnknownReferenceError(f"unknown source demand item: {instance.demand_item_id}")
            if instance.part_type_id not in part_type_ids:
                raise UnknownReferenceError(f"unknown instance part type: {instance.part_type_id}")
            if demands_by_id[instance.demand_item_id].part_type_id != instance.part_type_id:
                raise DomainValidationError(
                    f"part instance {instance.id} type does not match its source demand item"
                )
        for stock in self.stock_instances:
            self._require_owner(stock.work_id, "stock instance")
            if stock.specification_id not in stock_specification_ids:
                raise UnknownReferenceError(f"unknown stock specification: {stock.specification_id}")
        for layout in self.layouts:
            self._require_owner(layout.work_id, "layout")
            if layout.stock_instance_id not in stock_instance_ids:
                raise UnknownReferenceError(f"unknown layout stock instance: {layout.stock_instance_id}")
            for placement in layout.placements:
                if placement.part_instance_id not in part_instance_ids:
                    raise UnknownReferenceError(
                        f"unknown or cross-work placed part instance: {placement.part_instance_id}"
                    )
        for instance in self.layout_instances:
            self._require_owner(instance.work_id, "layout instance")
            if instance.layout_id not in layout_ids:
                raise UnknownReferenceError(f"unknown layout definition: {instance.layout_id}")

    def _require_owner(self, owner: WorkId, label: str) -> None:
        if owner != self.id:
            raise OwnershipError(f"{label} belongs to work {owner}, not {self.id}")

    @property
    def is_material_classified(self) -> bool:
        return self.material is not None and self.thickness is not None

    @classmethod
    def from_inputs(
        cls,
        *,
        id: WorkId,
        name: str,
        batch_multiplier: int,
        process_profile: ProcessProfile,
        part_types: tuple[PartType, ...] = (),
        demand_items: tuple[DemandItem, ...] = (),
        stock_specifications: tuple[StockSpecification, ...] = (),
        stock_instances: tuple[StockInstance, ...] = (),
        material: MaterialIdentity | None = None,
        thickness: Thickness | None = None,
    ) -> "Work":
        """Build a work and deterministically materialize its demanded pieces."""

        return cls(
            id=id,
            name=name,
            batch_multiplier=batch_multiplier,
            process_profile=process_profile,
            part_types=part_types,
            demand_items=demand_items,
            part_instances=expand_demand_items(demand_items, batch_multiplier),
            stock_specifications=stock_specifications,
            stock_instances=stock_instances,
            material=material,
            thickness=thickness,
        )
