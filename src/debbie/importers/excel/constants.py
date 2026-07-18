"""Canonical Excel schema identity, contracts, and conservative safety limits."""

from dataclasses import dataclass
from uuid import UUID

ADAPTER_ID = "canonical_excel_v1"
FORMAT_NAME = "Debbie Nesting Workbook"
SCHEMA_VERSION = "1.0"
SCHEMA_MAJOR = "1"
UNIT_SYSTEM = "mm"
REQUIRED_SHEETS = ("Debbie", "Works", "Parts", "Stocks")

METADATA_HEADERS = ("Key", "Value")
REQUIRED_METADATA = ("Format Name", "Schema Version", "Units")
KNOWN_METADATA = (*REQUIRED_METADATA, "Application Version", "Description")

WORK_HEADERS = (
    "Work Key",
    "Work Name",
    "Batch Multiplier",
    "Kerf (mm)",
    "Part Clearance (mm)",
    "Boundary Clearance (mm)",
    "Trim Left (mm)",
    "Trim Right (mm)",
    "Trim Top (mm)",
    "Trim Bottom (mm)",
)
PART_HEADERS = (
    "Work Key",
    "Part Key",
    "Part Name",
    "Length (mm)",
    "Width (mm)",
    "Quantity",
    "Allow Rotation",
)
OPTIONAL_PART_HEADERS = ("Drawing Number",)
STOCK_HEADERS = (
    "Work Key",
    "Stock Key",
    "Stock Name",
    "Length (mm)",
    "Width (mm)",
    "Quantity",
)

# A fixed application-owned namespace. Row positions, paths, and workbook metadata
# never participate in logical identity.
CANONICAL_IMPORT_NAMESPACE = UUID("d6a86f6a-52b1-5ed3-91dd-532de3b8aa4c")


@dataclass(frozen=True, slots=True)
class ImportLimits:
    max_file_bytes: int = 50 * 1024 * 1024
    max_archive_members: int = 10_000
    max_archive_uncompressed_bytes: int = 250 * 1024 * 1024
    max_archive_member_bytes: int = 100 * 1024 * 1024
    max_archive_compression_ratio: int = 250
    max_worksheets: int = 32
    max_rows_per_sheet: int = 20_000
    max_columns_per_sheet: int = 128
    max_total_data_rows: int = 50_000
    max_text_length: int = 4_096
    max_integer_value: int = 1_000_000
    max_stock_instances: int = 20_000
    max_expanded_demand_instances: int = 250_000


DEFAULT_IMPORT_LIMITS = ImportLimits()
