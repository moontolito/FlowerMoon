"""Read-only Qt table models over immutable Debbie backend data."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from debbie.domain import Orientation, Work
from debbie.application.presentation import (
    MassSummaryViewModel,
    build_stock_allocation_rows,
    format_dimension_value,
    format_fraction,
    work_record_for,
)
from debbie.importers.excel import (
    CanonicalWorkbookRecords,
    CanonicalWorkbookV11Records,
    ImportDiagnostic,
)
from debbie.importers.excel.identifiers import part_type_id
from debbie.nesting import UnplacedDemand


def _mm(value: float) -> str:
    return format_dimension_value(value)


def _short(value: object) -> str:
    return str(value)[:8]


class ReadOnlyTableModel(QAbstractTableModel):
    headers: tuple[str, ...] = ()
    numeric_columns: frozenset[int] = frozenset()

    def __init__(self, rows: Sequence[Sequence[Any]] = ()) -> None:
        super().__init__()
        self._rows = tuple(tuple(row) for row in rows)

    def set_rows(self, rows: Sequence[Sequence[Any]]) -> None:
        self.beginResetModel()
        self._rows = tuple(tuple(row) for row in rows)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or role not in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.TextAlignmentRole,
        ):
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            horizontal = (
                Qt.AlignmentFlag.AlignRight
                if index.column() in self.numeric_columns
                else Qt.AlignmentFlag.AlignLeft
            )
            return int(Qt.AlignmentFlag.AlignVCenter | horizontal)
        return self._rows[index.row()][index.column()]

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.headers):
            return self.headers[section]
        return section + 1

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class PartsTableModel(ReadOnlyTableModel):
    headers = (
        "Part Name",
        "Part Key / ID",
        "Drawing Number",
        "Length (mm)",
        "Width (mm)",
        "Base Quantity",
        "Expanded Quantity",
        "Rotation Allowed",
    )
    numeric_columns = frozenset({3, 4, 5, 6})

    def set_work(
        self,
        work: Work | None,
        records: CanonicalWorkbookRecords | CanonicalWorkbookV11Records | None,
    ) -> None:
        if work is None:
            self.set_rows(())
            return
        imported = {}
        drawings = {}
        if records is not None:
            work_record = work_record_for(work, records)
            if work_record is not None:
                for item in records.parts:
                    if item.work_key == work_record.work_key:
                        identifier = part_type_id(work.id, item.part_key)
                        imported[identifier] = item.part_key
                        drawings[identifier] = item.drawing_number or ""
        demand_by_type = {item.part_type_id: item for item in work.demand_items}
        rows = []
        for part in sorted(work.part_types, key=lambda item: (item.name.casefold(), str(item.id))):
            demand = demand_by_type[part.id]
            rotation = "0° / 90°" if Orientation.DEG_90 in part.allowed_orientations else "0°"
            rows.append(
                (
                    part.name,
                    imported.get(part.id, _short(part.id)),
                    drawings.get(part.id, ""),
                    _mm(part.dimensions.length),
                    _mm(part.dimensions.width),
                    demand.base_quantity,
                    demand.base_quantity * work.batch_multiplier,
                    rotation,
                )
            )
        self.set_rows(rows)


class StocksTableModel(ReadOnlyTableModel):
    headers = (
        "Stock Name",
        "Stock Key / ID",
        "Quantity",
        "Full Length (mm)",
        "Full Width (mm)",
        "Allocated Length (mm)",
        "Allocated Width (mm)",
        "Physical Allocation",
        "Commercial Allocation",
        "Usable Length (mm)",
        "Usable Width (mm)",
        "Effective Length (mm)",
        "Effective Width (mm)",
    )
    numeric_columns = frozenset(range(2, 13))

    def set_work(
        self,
        work: Work | None,
        records: CanonicalWorkbookRecords | CanonicalWorkbookV11Records | None,
    ) -> None:
        if work is None:
            self.set_rows(())
            return
        self.set_rows(
            (
                row.stock_name,
                row.stock_key,
                row.quantity,
                _mm(row.full_length_mm),
                _mm(row.full_width_mm),
                _mm(row.allocated_length_mm),
                _mm(row.allocated_width_mm),
                format_fraction(row.physical_allocation_fraction),
                format_fraction(row.commercial_allocation_fraction),
                _mm(row.usable_length_mm),
                _mm(row.usable_width_mm),
                _mm(row.effective_length_mm),
                _mm(row.effective_width_mm),
            )
            for row in build_stock_allocation_rows(work, records)
        )


class DiagnosticsTableModel(ReadOnlyTableModel):
    headers = (
        "Severity", "Code", "Worksheet", "Row", "Header", "Work", "Part", "Stock", "Message"
    )
    numeric_columns = frozenset({3})

    def set_diagnostics(self, diagnostics: Sequence[ImportDiagnostic]) -> None:
        self.set_rows(
            (
                item.severity.value.title(),
                item.code.value,
                item.worksheet or "",
                item.row if item.row is not None else "",
                item.header or "",
                item.related_work_key or "",
                item.related_part_key or "",
                item.related_stock_key or "",
                item.message,
            )
            for item in diagnostics
        )


class SummaryTableModel(ReadOnlyTableModel):
    headers = ("Measure", "Value")
    numeric_columns = frozenset({1})

    def set_summary(self, summary: MassSummaryViewModel) -> None:
        self.set_rows((item.label, item.value) for item in summary.items)


class UnplacedTableModel(ReadOnlyTableModel):
    headers = ("Part Name", "Demand Key", "Remaining Quantity", "Reason Code", "Details")
    numeric_columns = frozenset({2})

    def set_unplaced(self, work: Work | None, items: Sequence[UnplacedDemand]) -> None:
        names = {part.id: part.name for part in work.part_types} if work else {}
        rows = sorted(
            items,
            key=lambda item: (names.get(item.part_type_id, ""), str(item.demand_item_id)),
        )
        self.set_rows(
            (
                names.get(item.part_type_id, _short(item.part_type_id)),
                _short(item.demand_item_id),
                item.remaining_quantity,
                item.reason_code.value,
                "; ".join(f"{key}: {value}" for key, value in item.diagnostic_details),
            )
            for item in rows
        )
