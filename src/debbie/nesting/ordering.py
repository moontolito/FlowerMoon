"""Explicit business ordering; UUID values are final tie-breakers only."""

from __future__ import annotations

import unicodedata

from debbie.domain.parts import PartInstance, PartType
from debbie.domain.stocks import StockInstance, StockSpecification


def normalized_label(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def part_type_order_key(part_type: PartType) -> tuple[float | int | str, ...]:
    length = part_type.dimensions.length
    width = part_type.dimensions.width
    return (
        -(length * width),
        -max(length, width),
        -min(length, width),
        len(part_type.allowed_orientations),
        normalized_label(part_type.name),
        str(part_type.id),
    )


def part_instance_order_key(
    instance: PartInstance, part_types: dict
) -> tuple[float | int | str, ...]:
    return (
        *part_type_order_key(part_types[instance.part_type_id]),
        str(instance.demand_item_id),
        instance.sequence,
        str(instance.id),
    )


def stock_instance_order_key(
    instance: StockInstance, specifications: dict
) -> tuple[float | int | str, ...]:
    specification: StockSpecification = specifications[instance.specification_id]
    dimensions = specification.dimensions
    return (
        dimensions.length * dimensions.width,
        dimensions.length,
        dimensions.width,
        normalized_label(specification.name),
        str(specification.id),
        instance.sequence,
        str(instance.id),
    )
