"""First read-only Debbie Desktop engineering workflow."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from debbie.application import DebbieSession, ImportService, NestingService, OperationToken
from debbie.domain import Work
from debbie.nesting import NestingResult, ResultStatus
from debbie.importers.excel.identifiers import work_id

from .graphics import LayoutView
from .models import DiagnosticsTableModel, PartsTableModel, StocksTableModel, UnplacedTableModel
from .workers import ServiceWorker

WARNING_TEXT = (
    "Non-guillotine rectangular nesting.\n"
    "No cutting toolpath is generated.\n"
    "The result is not machine-ready and is not guaranteed globally optimal."
)


class DebbieMainWindow(QMainWindow):
    def __init__(
        self,
        *,
        import_service: ImportService | None = None,
        nesting_service: NestingService | None = None,
    ) -> None:
        super().__init__()
        self.session = DebbieSession()
        self.import_service = import_service or ImportService()
        self.nesting_service = nesting_service or NestingService()
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(2)
        self._workers: set[ServiceWorker] = set()
        self._closing_requested = False
        self.last_development_traceback: str | None = None
        self.setWindowTitle("Debbie Desktop MVP")
        self.resize(1280, 720)
        self._build_ui()
        self._refresh_all()

    def _build_ui(self) -> None:
        toolbar = QToolBar("Main", self)
        self.addToolBar(toolbar)
        self.import_button = QPushButton("Import Excel")
        self.run_button = QPushButton("Run Nesting")
        self.fit_button = QPushButton("Fit Layout")
        toolbar.addWidget(self.import_button)
        toolbar.addWidget(self.run_button)
        toolbar.addWidget(self.fit_button)
        self.toolbar_status = QLabel()
        toolbar.addSeparator()
        toolbar.addWidget(self.toolbar_status)
        self.import_button.clicked.connect(self._choose_workbook)
        self.run_button.clicked.connect(self.run_nesting)
        self.fit_button.clicked.connect(self._fit_layout)

        project_box = QGroupBox("Current work")
        project_form = QFormLayout(project_box)
        self.work_selector = QComboBox()
        self.source_label = QLabel("No workbook loaded")
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        project_form.addRow("Work", self.work_selector)
        project_form.addRow("Source", self.source_label)
        self.work_selector.currentIndexChanged.connect(self._work_changed)

        settings_box = QGroupBox("Process settings (mm)")
        settings_form = QFormLayout(settings_box)
        self.setting_labels = {}
        for key, label in (
            ("batch", "Batch multiplier"),
            ("kerf", "Kerf"),
            ("part_clearance", "Part clearance"),
            ("boundary_clearance", "Boundary clearance"),
            ("trim_left", "Trim left"),
            ("trim_right", "Trim right"),
            ("trim_top", "Trim top"),
            ("trim_bottom", "Trim bottom"),
        ):
            value = QLabel("—")
            self.setting_labels[key] = value
            settings_form.addRow(label, value)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(project_box)
        left_layout.addWidget(settings_box)
        left_layout.addStretch(1)

        self.tabs = QTabWidget()
        self.parts_model = PartsTableModel()
        self.stocks_model = StocksTableModel()
        self.diagnostics_model = DiagnosticsTableModel()
        self.unplaced_model = UnplacedTableModel()
        self.parts_table = self._table(self.parts_model)
        self.stocks_table = self._table(self.stocks_model)
        self.unplaced_table = self._table(self.unplaced_model)
        self.diagnostics_table = self._table(self.diagnostics_model)
        self.tabs.addTab(self.parts_table, "Parts")
        self.tabs.addTab(self.stocks_table, "Stocks")

        layout_tab = QWidget()
        layout_grid = QGridLayout(layout_tab)
        self.result_status = QLabel("Nesting has not been run")
        self.result_status.setWordWrap(True)
        self.result_status.setStyleSheet("font-size: 14px; font-weight: 700;")
        self.result_summary = QLabel("—")
        self.result_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.result_summary.setWordWrap(True)
        self.layout_selector = QComboBox()
        self.layout_selector.currentIndexChanged.connect(self._layout_changed)
        self.layout_view = LayoutView()
        self.warning_label = QLabel(WARNING_TEXT)
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("font-weight: 600; color: #7a3e00; padding: 6px;")
        layout_grid.addWidget(self.result_status, 0, 0)
        layout_grid.addWidget(self.layout_selector, 0, 1)
        layout_grid.addWidget(self.result_summary, 1, 0, 1, 2)
        layout_grid.addWidget(self.layout_view, 2, 0, 1, 2)
        layout_grid.addWidget(self.warning_label, 3, 0, 1, 2)
        layout_grid.setRowStretch(2, 1)
        self.tabs.addTab(layout_tab, "Layout")
        self.tabs.addTab(self.unplaced_table, "Unplaced")
        self.tabs.addTab(self.diagnostics_table, "Diagnostics")

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.tabs)
        splitter.setSizes([300, 980])
        self.setCentralWidget(splitter)
        self.statusBar().showMessage(self.session.status_message)

    @staticmethod
    def _table(model) -> QTableView:
        table = QTableView()
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _choose_workbook(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Debbie Nesting Workbook", "", "Excel workbooks (*.xlsx)"
        )
        if path:
            self.import_workbook(path)

    def import_workbook(self, path: str | Path) -> bool:
        if self.session.busy_operation is not None:
            return False
        token = self.session.begin_import()
        self._refresh_busy()
        worker = ServiceWorker(lambda: self.import_service.import_workbook(path))
        worker.signals.succeeded.connect(
            lambda result: self._import_succeeded(token, Path(path), result)
        )
        worker.signals.failed.connect(
            lambda message, detail: self._unexpected_failure(
                token, "Import failed", message, detail
            )
        )
        self._start_worker(worker)
        return True

    def _import_succeeded(self, token: OperationToken, path: Path, result) -> None:
        if self.session.finish_import(token, path, result):
            self._refresh_all()

    def run_nesting(self) -> bool:
        try:
            token, work = self.session.begin_nesting()
        except (ValueError, RuntimeError):
            return False
        self._refresh_busy()
        worker = ServiceWorker(lambda: self.nesting_service.run(work))
        worker.signals.succeeded.connect(lambda result: self._nesting_succeeded(token, result))
        worker.signals.failed.connect(
            lambda message, detail: self._unexpected_failure(
                token, "Nesting failed", message, detail
            )
        )
        self._start_worker(worker)
        return True

    def _nesting_succeeded(self, token: OperationToken, result: NestingResult) -> None:
        if self.session.finish_nesting(token, result):
            self._refresh_result()
        self._refresh_busy()

    def _unexpected_failure(
        self, token: OperationToken, title: str, message: str, detail: str
    ) -> None:
        self.last_development_traceback = detail
        if self.session.fail_operation(token, f"{title}: {message}"):
            self._refresh_all()
            QMessageBox.critical(self, title, message)

    def _start_worker(self, worker: ServiceWorker) -> None:
        self._workers.add(worker)
        worker.signals.finished.connect(lambda: self._worker_finished(worker))
        self.thread_pool.start(worker)

    def _worker_finished(self, worker: ServiceWorker) -> None:
        self._workers.discard(worker)
        if self._closing_requested and not self._workers:
            self.setEnabled(True)
            self.close()

    def _work_changed(self, index: int) -> None:
        work_id = self.work_selector.itemData(index) if index >= 0 else None
        if work_id != self.session.selected_work_id:
            self.session.select_work(work_id)
            self._refresh_work()

    def _layout_changed(self, index: int) -> None:
        self.session.selected_layout_index = index if index >= 0 else None
        self._render_selected_layout()

    def _fit_layout(self) -> None:
        self.layout_view.fit_layout()

    def _records(self):
        return self.session.import_result.records if self.session.import_result else None

    def _refresh_all(self) -> None:
        self._refresh_work_selector()
        self.diagnostics_model.set_diagnostics(self.session.diagnostics)
        self._refresh_work()
        self._refresh_busy()

    def _refresh_work_selector(self) -> None:
        self.work_selector.blockSignals(True)
        self.work_selector.clear()
        records = self._records()
        key_by_id = (
            {work_id(item.work_key): item.work_key for item in records.works}
            if records
            else {}
        )
        for work in self.session.works:
            key = key_by_id.get(work.id, str(work.id)[:8])
            self.work_selector.addItem(f"{work.name} — {key}", work.id)
        selected = next(
            (
                index
                for index in range(self.work_selector.count())
                if self.work_selector.itemData(index) == self.session.selected_work_id
            ),
            -1,
        )
        self.work_selector.setCurrentIndex(selected)
        self.work_selector.blockSignals(False)
        self.source_label.setText(
            self.session.workbook_path.name if self.session.workbook_path else "No workbook loaded"
        )

    def _refresh_work(self) -> None:
        work = self.session.selected_work
        self.parts_model.set_work(work, self._records())
        self.stocks_model.set_work(work, self._records())
        self._refresh_settings(work)
        self._refresh_result()
        self._refresh_busy()

    def _refresh_settings(self, work: Work | None) -> None:
        values = {key: "—" for key in self.setting_labels}
        if work is not None:
            profile = work.process_profile
            values = {
                "batch": str(work.batch_multiplier),
                "kerf": f"{profile.kerf:.2f}",
                "part_clearance": f"{profile.minimum_part_clearance:.2f}",
                "boundary_clearance": f"{profile.boundary_clearance:.2f}",
                "trim_left": f"{profile.trim.left:.2f}",
                "trim_right": f"{profile.trim.right:.2f}",
                "trim_top": f"{profile.trim.top:.2f}",
                "trim_bottom": f"{profile.trim.bottom:.2f}",
            }
        for key, label in self.setting_labels.items():
            label.setText(values[key])

    def _refresh_result(self) -> None:
        result = self.session.visible_result
        work = self.session.selected_work
        self.layout_selector.blockSignals(True)
        self.layout_selector.clear()
        if result is None:
            self.result_status.setText("Nesting has not been run for this work")
            self.result_summary.setText("—")
            self.unplaced_model.set_unplaced(work, ())
        else:
            self.result_status.setText(f"Result status: {result.status.value}")
            unused = result.objective.unused_usable_area
            full_area = result.objective.nominal_full_stock_area_consumed
            validation_text = ""
            if result.diagnostics:
                validation_text = "\nValidation: " + "; ".join(
                    f"{item.reason_code.value}: {item.message}" for item in result.diagnostics
                )
            self.result_summary.setText(
                f"Strategy: {result.strategy_display_name}\n"
                f"Feasibility: {result.feasibility.classification}\n"
                f"Engine: {result.engine_version} | Requested: {result.requested_part_count} | "
                f"Placed: {result.placed_part_count} | "
                f"Unplaced: {result.requested_part_count - result.placed_part_count} | "
                f"Sheets: {len(result.layouts)} | Full-stock area: {full_area:.2f} mm² | "
                f"Unused usable area: {unused:.2f} mm²{validation_text}"
            )
            stock_instances = {item.id: item for item in work.stock_instances} if work else {}
            stocks = {item.id: item for item in work.stock_specifications} if work else {}
            for index, layout in enumerate(result.layouts):
                instance = stock_instances[layout.stock_instance_id]
                stock = stocks[instance.specification_id]
                self.layout_selector.addItem(
                    f"Layout {index + 1} — {stock.name} — "
                    f"{stock.dimensions.length:.2f} × {stock.dimensions.width:.2f} mm — "
                    f"{len(layout.placements)} parts",
                    str(layout.id),
                )
            self.unplaced_model.set_unplaced(work, result.unplaced_demand)
        selected = self.session.selected_layout_index
        self.layout_selector.setCurrentIndex(selected if selected is not None else -1)
        self.layout_selector.blockSignals(False)
        self._render_selected_layout()

    def _render_selected_layout(self) -> None:
        result = self.session.visible_result
        work = self.session.selected_work
        index = self.layout_selector.currentIndex()
        layout = result.layouts[index] if result and 0 <= index < len(result.layouts) else None
        self.layout_view.layout_scene.render_layout(work, layout)
        if layout is not None:
            self.layout_view.fit_layout()

    def _refresh_busy(self) -> None:
        busy = self.session.busy_operation is not None
        self.import_button.setEnabled(not busy)
        self.run_button.setEnabled(not busy and self.session.selected_work is not None)
        self.fit_button.setEnabled(not self.layout_view.scene().itemsBoundingRect().isEmpty())
        self.work_selector.setEnabled(not busy and bool(self.session.works))
        self.toolbar_status.setText(self.session.status_message)
        self.statusBar().showMessage(self.session.status_message)

    def closeEvent(self, event) -> None:
        if not self._workers:
            event.accept()
            return
        if not self._closing_requested:
            self._closing_requested = True
            self.session.invalidate_running_operation()
            self.thread_pool.clear()
            self.setEnabled(False)
            self.statusBar().showMessage("Finishing background work before closing…")
        event.ignore()
