"""UUID5 identity policy for canonical Excel schemas 1.0 and 1.1."""

from debbie.domain import (
    DemandItemId,
    PartTypeId,
    StockInstanceId,
    StockSpecificationId,
    WorkId,
)

from .constants import (
    CANONICAL_IMPORT_NAMESPACE,
    FORMAT_NAME,
    SCHEMA_MAJOR,
    SCHEMA_VERSION_V11,
)


def work_id(work_key: str) -> WorkId:
    return WorkId.deterministic(
        CANONICAL_IMPORT_NAMESPACE,
        f"{FORMAT_NAME}|schema-major:{SCHEMA_MAJOR}|work:{work_key}",
    )


def work_id_v11(work_key: str) -> WorkId:
    """Schema 1.1 identity is deliberately distinct from unclassified 1.0."""

    return WorkId.deterministic(
        CANONICAL_IMPORT_NAMESPACE,
        f"{FORMAT_NAME}|schema:{SCHEMA_VERSION_V11}|work:{work_key}",
    )


def part_type_id(owner: WorkId, part_key: str) -> PartTypeId:
    return PartTypeId.deterministic(
        CANONICAL_IMPORT_NAMESPACE, f"work:{owner}|part-type:{part_key}"
    )


def demand_item_id(owner: WorkId, part_key: str) -> DemandItemId:
    return DemandItemId.deterministic(
        CANONICAL_IMPORT_NAMESPACE,
        f"work:{owner}|part:{part_key}|role:canonical-demand-v1",
    )


def stock_specification_id(owner: WorkId, stock_key: str) -> StockSpecificationId:
    return StockSpecificationId.deterministic(
        CANONICAL_IMPORT_NAMESPACE, f"work:{owner}|stock-specification:{stock_key}"
    )


def stock_instance_id(specification: StockSpecificationId, sequence: int) -> StockInstanceId:
    return StockInstanceId.deterministic(
        CANONICAL_IMPORT_NAMESPACE,
        f"stock-specification:{specification}|physical-sequence:{sequence}",
    )
