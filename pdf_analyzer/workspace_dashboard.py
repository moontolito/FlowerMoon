"""Native multi-document overview dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .project_state import READING_STATUSES
from .workspace_analysis import WorkspaceSummary, update_workspace_status


class WorkspaceDashboardDialog(QDialog):
    open_document = Signal(str)
    status_changed = Signal(str, str)
    refresh_requested = Signal()
    analyze_requested = Signal()
    export_requested = Signal()
    excel_export_requested = Signal()

    def __init__(
        self,
        summary: WorkspaceSummary,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.summary = summary
        self._building = False
        self._known_paths = {item.path for item in summary.documents}
        self._included_paths = {
            item.path for item in summary.documents if item.available
        }
        self.setWindowTitle("Multi-document Analysis Dashboard")
        self.resize(1040, 690)

        layout = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setObjectName("sectionTitle")
        layout.addWidget(self.title)
        self.totals = QLabel()
        self.totals.setObjectName("muted")
        layout.addWidget(self.totals)
        self.breakdown = QLabel()
        self.breakdown.setObjectName("muted")
        self.breakdown.setWordWrap(True)
        layout.addWidget(self.breakdown)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Reading status"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(("All statuses",) + READING_STATUSES)
        self.status_filter.currentIndexChanged.connect(self._refresh_table)
        filters.addWidget(self.status_filter)
        filters.addWidget(QLabel("Tag"))
        self.tag_filter = QComboBox()
        self.tag_filter.currentIndexChanged.connect(self._refresh_table)
        filters.addWidget(self.tag_filter)
        filters.addStretch()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        filters.addWidget(self.refresh_button)
        layout.addLayout(filters)

        selection_options = QHBoxLayout()
        select_visible = QPushButton("Select Visible")
        select_visible.clicked.connect(lambda: self._set_visible_included(True))
        selection_options.addWidget(select_visible)
        clear_visible = QPushButton("Clear Visible")
        clear_visible.clicked.connect(lambda: self._set_visible_included(False))
        selection_options.addWidget(clear_visible)
        selection_options.addStretch()
        self.analyze_button = QPushButton("Analyze Selected")
        self.analyze_button.setToolTip(
            "Run Categories and Standards for every checked PDF and save all findings as tagged notes"
        )
        self.analyze_button.clicked.connect(self.analyze_requested.emit)
        selection_options.addWidget(self.analyze_button)
        layout.addLayout(selection_options)

        self.analysis_result = QLabel(
            "Batch analysis has not been run from this dashboard session."
        )
        self.analysis_result.setObjectName("muted")
        self.analysis_result.setWordWrap(True)
        layout.addWidget(self.analysis_result)

        export_options = QHBoxLayout()
        export_options.addStretch()
        export_options.addWidget(QLabel("Export mode"))
        self.export_mode = QComboBox()
        self.export_mode.addItem("Overview only", "overview")
        self.export_mode.addItem(
            "Management report",
            "management",
        )
        self.export_mode.setItemData(
            1,
            "Dashboard overview plus every Category and Standards finding; source PDFs are not appended",
            Qt.ItemDataRole.ToolTipRole,
        )
        self.export_mode.addItem("Full annotated package", "full")
        export_options.addWidget(self.export_mode)
        self.export_button = QPushButton("Export PDF")
        self.export_button.setObjectName("primaryButton")
        self.export_button.clicked.connect(self.export_requested.emit)
        export_options.addWidget(self.export_button)
        self.excel_export_button = QPushButton("Export Excel")
        self.excel_export_button.setToolTip(
            "Create an editable workbook for the selected documents and active tag filter"
        )
        self.excel_export_button.clicked.connect(self.excel_export_requested.emit)
        export_options.addWidget(self.excel_export_button)
        layout.addLayout(export_options)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ("Include", "Document", "Pages", "Reading status", "Notes", "Tags")
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self._open_row)
        layout.addWidget(self.table, 1)

        hint = QLabel(
            "Check the documents to export. The active Tag filter limits exported notes. "
            "Management report always includes all tags and findings. "
            "Double-click a document to open it. Exported status fields remain editable "
            "but do not sync back. PDF and Excel exports are separate."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        self.set_summary(summary)

    def set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        self.analyze_button.setEnabled(not busy)
        self.export_button.setEnabled(not busy)
        self.excel_export_button.setEnabled(not busy)

    def set_analysis_result(
        self,
        documents: int,
        categories: int,
        standards: int,
        notes_added: int,
        empty_pages: int,
        failed: int,
    ) -> None:
        self.analysis_result.setText(
            f"Batch analysis: {documents} documents analyzed - "
            f"{categories} category findings - {standards} standards findings - "
            f"{notes_added} new notes - {empty_pages} pages still require OCR"
            + (f" - {failed} failed documents" if failed else "")
        )

    def mark_stale(self) -> None:
        self.refresh_button.setEnabled(True)
        self.export_button.setEnabled(False)
        self.excel_export_button.setEnabled(False)
        self.breakdown.setText(
            self.breakdown.text() + "\nWorkspace data changed. Refresh before exporting."
        )

    def set_summary(self, summary: WorkspaceSummary) -> None:
        selected_status = self.status_filter.currentText()
        selected_tag = self.tag_filter.currentData()
        new_paths = {item.path for item in summary.documents}
        added_paths = new_paths - self._known_paths
        self._included_paths.intersection_update(new_paths)
        self._included_paths.update(
            item.path
            for item in summary.documents
            if item.available and item.path in added_paths
        )
        self._known_paths = new_paths
        self.summary = summary
        self.title.setText(summary.project_name)
        self.totals.setText(
            f"{len(summary.documents)} documents · {summary.total_pages} pages · "
            f"{summary.total_notes} notes · {len(summary.tag_counts)} tags"
        )
        statuses = "   |   ".join(
            f"{status}: {count}" for status, count in summary.status_counts
        ) or "No reading statuses"
        self.breakdown.setText(statuses)
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("All tags", None)
        for tag, count in summary.tag_counts:
            self.tag_filter.addItem(f"{tag} ({count})", tag)
        tag_index = self.tag_filter.findData(selected_tag)
        self.tag_filter.setCurrentIndex(max(0, tag_index))
        self.tag_filter.blockSignals(False)
        status_index = self.status_filter.findText(selected_status)
        self.status_filter.setCurrentIndex(max(0, status_index))
        self._refresh_table()

    def _visible_documents(self):
        status = self.status_filter.currentText()
        tag = self.tag_filter.currentData()
        return tuple(
            item
            for item in self.summary.documents
            if (status == "All statuses" or item.reading_status == status)
            and (
                tag is None
                or any(value.casefold() == str(tag).casefold() for value in item.tags)
            )
        )

    def _refresh_table(self, *args) -> None:
        self._building = True
        documents = self._visible_documents()
        self.table.setRowCount(len(documents))
        for row, item in enumerate(documents):
            include = QCheckBox()
            include.setChecked(item.path in self._included_paths)
            include.setEnabled(item.available)
            include.stateChanged.connect(
                lambda state, path=item.path: self._include_changed(path, bool(state))
            )
            self.table.setCellWidget(row, 0, include)
            name = item.name if item.available else f"{item.name} [missing / invalid]"
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, item.path)
            name_item.setToolTip(item.error or item.path)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, QTableWidgetItem(str(item.page_count)))
            status = QComboBox()
            status.addItems(READING_STATUSES)
            status.setCurrentText(item.reading_status)
            status.currentTextChanged.connect(
                lambda value, path=item.path: self._status_edited(path, value)
            )
            self.table.setCellWidget(row, 3, status)
            self.table.setItem(row, 4, QTableWidgetItem(str(item.note_count)))
            self.table.setItem(row, 5, QTableWidgetItem(", ".join(item.tags) or "—"))
        self._building = False

    def _include_changed(self, path: str, included: bool) -> None:
        if self._building:
            return
        if included:
            self._included_paths.add(path)
        else:
            self._included_paths.discard(path)

    def _set_visible_included(self, included: bool) -> None:
        for item in self._visible_documents():
            if not item.available:
                continue
            if included:
                self._included_paths.add(item.path)
            else:
                self._included_paths.discard(item.path)
        self._refresh_table()

    def selected_paths(self) -> tuple[str, ...]:
        return tuple(
            item.path
            for item in self.summary.documents
            if item.path in self._included_paths
        )

    def selected_tags(self) -> tuple[str, ...] | None:
        tag = self.tag_filter.currentData()
        return None if tag is None else (str(tag),)

    def export_mode_value(self) -> str:
        return str(self.export_mode.currentData())

    def _status_edited(self, path: str, status: str) -> None:
        if self._building:
            return
        self.summary = update_workspace_status(self.summary, path, status)
        self.status_changed.emit(path, status)
        self.totals.setText(
            f"{len(self.summary.documents)} documents · {self.summary.total_pages} pages · "
            f"{self.summary.total_notes} notes · {len(self.summary.tag_counts)} tags"
        )
        statuses = "   |   ".join(
            f"{value}: {count}" for value, count in self.summary.status_counts
        )
        self.breakdown.setText(statuses)

    def _open_row(self, row: int, column: int) -> None:
        item = self.table.item(row, 1)
        if item is not None:
            self.open_document.emit(str(item.data(Qt.ItemDataRole.UserRole)))
