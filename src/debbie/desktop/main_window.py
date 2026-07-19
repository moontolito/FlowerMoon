"""Professional read-only Debbie Desktop engineering workflow."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, QThreadPool, Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTabWidget,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from debbie.application import (
    DebbieSession,
    ImportService,
    MassService,
    NestingService,
    OperationToken,
    build_nesting_mass_summary,
    build_work_information,
    build_work_mass_summary,
)
from debbie.application.presentation import MassSummaryViewModel, UNAVAILABLE, work_key_for
from debbie.domain import Work
from debbie.nesting import NestingResult, ResultStatus

from .graphics import LayoutView
from .models import (
    DiagnosticsTableModel,
    PartsTableModel,
    StocksTableModel,
    SummaryTableModel,
    UnplacedTableModel,
)
from .theme import SPACING, StatusTone, apply_application_theme
from .widgets import EmptyState, SectionHeader, StatusBadge, SummaryCard, message_panel
from .workers import ServiceWorker

WARNING_TEXT = (
    "Non-guillotine rectangular nesting. No cutting toolpath is generated. "
    "Results are not machine-ready and are not guaranteed globally optimal."
)

PLANNING_CARD_FIELDS = (
    ("Rectangular Part Mass Estimate", "Part Mass Estimate", "Rectangular Part Mass / Product"),
    ("Gross Physical Allocation Mass", "Gross Physical", "Gross Physical Mass / Product"),
    ("Gross Commercial Allocation Mass", "Gross Commercial", "Gross Commercial Mass / Product"),
    ("Physical Equivalent Sheets", "Physical Equivalent Sheets", None),
)

RESULT_CARD_FIELDS = (
    (
        "Consumed Gross Physical Allocation Mass",
        "Consumed Physical",
        "Consumed Gross Physical Mass / Product",
    ),
    (
        "Consumed Gross Commercial Allocation Mass",
        "Consumed Commercial",
        "Consumed Gross Commercial Mass / Product",
    ),
    (
        "Placed Rectangular Part Mass Estimate",
        "Placed Part Estimate",
        "Placed Rectangular Mass / Product",
    ),
    ("Consumed Physical Equivalent Sheets", "Consumed Physical Sheets", None),
)


class DebbieMainWindow(QMainWindow):
    def __init__(
        self,
        *,
        import_service: ImportService | None = None,
        nesting_service: NestingService | None = None,
        mass_service: MassService | None = None,
    ) -> None:
        super().__init__()
        apply_application_theme(QApplication.instance())
        self.session = DebbieSession()
        self.import_service = import_service or ImportService()
        self.nesting_service = nesting_service or NestingService()
        self.mass_service = mass_service or MassService()
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(2)
        self._workers: set[ServiceWorker] = set()
        self._closing_requested = False
        self.last_development_traceback: str | None = None
        self.setWindowTitle("Debbie")
        self.setMinimumSize(960, 600)
        self.resize(1280, 720)
        self._build_ui()
        self._refresh_all()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("applicationRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_application_header())
        root_layout.addWidget(self._build_toolbar())
        root_layout.addWidget(self._build_workspace(), 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage(self.session.status_message)

    def _build_application_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("applicationHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(SPACING.section, 9, SPACING.section, 9)
        layout.setSpacing(SPACING.section)

        identity = QVBoxLayout()
        identity.setSpacing(0)
        title = QLabel("Debbie")
        title.setObjectName("applicationTitle")
        subtitle = QLabel("Sheet Nesting and Material Planning")
        subtitle.setObjectName("applicationSubtitle")
        identity.addWidget(title)
        identity.addWidget(subtitle)
        layout.addLayout(identity)
        layout.addStretch(1)

        context = QVBoxLayout()
        context.setSpacing(1)
        self.source_label = QLabel("No workbook loaded")
        self.source_label.setObjectName("headerContext")
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.current_work_header = QLabel("No Work selected")
        self.current_work_header.setObjectName("headerContext")
        self.current_work_header.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.current_work_header.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        context.addWidget(self.source_label)
        context.addWidget(self.current_work_header)
        layout.addLayout(context)
        return header

    def _build_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Main actions", self)
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(18, 18))
        style = self.style()

        self.import_button = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
            "Import Workbook",
        )
        self.import_button.setAccessibleName("Import Workbook")
        self.import_button.clicked.connect(self._choose_workbook)
        toolbar.addWidget(self.import_button)
        toolbar.addSeparator()

        work_label = QLabel("Work")
        work_label.setProperty("propertyLabel", True)
        toolbar.addWidget(work_label)
        self.work_selector = QComboBox()
        self.work_selector.setMinimumWidth(230)
        self.work_selector.setMaximumWidth(440)
        self.work_selector.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.work_selector.setAccessibleName("Selected Work")
        self.work_selector.currentIndexChanged.connect(self._work_changed)
        toolbar.addWidget(self.work_selector)

        self.run_button = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "Run Nesting"
        )
        self.run_button.setProperty("primary", True)
        self.run_button.setAccessibleName("Run Nesting")
        self.run_button.clicked.connect(self.run_nesting)
        toolbar.addWidget(self.run_button)
        toolbar.addSeparator()

        self.fit_button = self._quiet_toolbar_button(
            "Fit View", QStyle.StandardPixmap.SP_TitleBarMaxButton, self._fit_layout
        )
        self.zoom_in_button = self._quiet_toolbar_button(
            "Zoom In", QStyle.StandardPixmap.SP_ArrowUp, self.layout_zoom_in
        )
        self.zoom_out_button = self._quiet_toolbar_button(
            "Zoom Out", QStyle.StandardPixmap.SP_ArrowDown, self.layout_zoom_out
        )
        toolbar.addWidget(self.fit_button)
        toolbar.addWidget(self.zoom_in_button)
        toolbar.addWidget(self.zoom_out_button)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        self.toolbar_status = QLabel()
        self.toolbar_status.setObjectName("secondaryText")
        self.toolbar_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        toolbar.addWidget(self.toolbar_status)
        self.main_toolbar = toolbar
        return toolbar

    def _quiet_toolbar_button(self, text: str, icon, callback) -> QPushButton:
        button = QPushButton(self.style().standardIcon(icon), text)
        button.setProperty("quiet", True)
        button.setAccessibleName(text)
        button.clicked.connect(callback)
        return button

    def _build_workspace(self) -> QWidget:
        self.engineering_panel = self._build_engineering_panel()
        self.left_scroll = QScrollArea()
        self.left_scroll.setObjectName("engineeringScroll")
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setWidget(self.engineering_panel)
        self.left_scroll.setMinimumWidth(330)
        self.left_scroll.setMaximumWidth(460)

        self.tabs = self._build_tabs()
        self.main_empty_state = EmptyState(
            "Import a Debbie workbook to begin.",
            "Canonical Debbie Nesting Workbook schemas 1.0 and 1.1 are supported.",
            "Import Workbook",
        )
        self.main_empty_state.action_requested.connect(self._choose_workbook)
        self.workspace_stack = QStackedWidget()
        self.workspace_stack.addWidget(self.main_empty_state)
        self.workspace_stack.addWidget(self.tabs)

        splitter = QSplitter()
        splitter.setObjectName("mainSplitter")
        splitter.addWidget(self.left_scroll)
        splitter.addWidget(self.workspace_stack)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 900])
        self.main_splitter = splitter
        return splitter

    def _build_engineering_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("engineeringPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(
            SPACING.section, SPACING.section, SPACING.section, SPACING.section
        )
        layout.setSpacing(SPACING.section)
        self.work_info_labels: dict[str, QLabel] = {}

        work_section, work_layout = self._section("Work", "Current canonical job context")
        work_form = self._property_form()
        for key, label in (
            ("work_name", "Work Name"),
            ("work_key", "Work Key"),
            ("schema_version", "Schema Version"),
            ("batch_multiplier", "Batch Multiplier"),
        ):
            value = self._property_value()
            self.work_info_labels[key] = value
            work_form.addRow(self._property_label(label), value)
        work_layout.addLayout(work_form)
        layout.addWidget(work_section)

        material_section, material_layout = self._section(
            "Material", "Classification and mass provenance"
        )
        material_form = self._property_form()
        for key, label in (
            ("material_category", "Category"),
            ("material_grade", "Grade"),
            ("thickness", "Thickness"),
            ("density", "Density"),
            ("density_source", "Density Source"),
            ("material_description", "Description"),
        ):
            value = self._property_value()
            self.work_info_labels[key] = value
            material_form.addRow(self._property_label(label), value)
        material_layout.addLayout(material_form)
        self.material_status_panel, self.material_status = message_panel(
            "No Work selected", StatusTone.INFORMATION
        )
        material_layout.addWidget(self.material_status_panel)
        layout.addWidget(material_section)

        process_section, process_layout = self._section(
            "Process Settings", "Read-only values in millimetres"
        )
        settings_form = self._property_form()
        self.setting_labels: dict[str, QLabel] = {}
        for key, label in (
            ("batch", "Batch Multiplier"),
            ("kerf", "Kerf"),
            ("part_clearance", "Part Clearance"),
            ("boundary_clearance", "Boundary Clearance"),
            ("trim_left", "Trim Left"),
            ("trim_right", "Trim Right"),
            ("trim_top", "Trim Top"),
            ("trim_bottom", "Trim Bottom"),
        ):
            value = self._property_value()
            self.setting_labels[key] = value
            settings_form.addRow(self._property_label(label), value)
        process_layout.addLayout(settings_form)
        layout.addWidget(process_section)

        planning_section, planning_layout = self._section(
            "Planning Material Summary", "Available Work inventory"
        )
        planning_status_row = QHBoxLayout()
        self.planning_status_badge = StatusBadge()
        self.planning_status = QLabel("Mass calculations have not been run.")
        self.planning_status.setObjectName("secondaryText")
        self.planning_status.setWordWrap(True)
        self.planning_status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        planning_status_row.addWidget(self.planning_status_badge, 0)
        planning_status_row.addWidget(self.planning_status, 1)
        planning_layout.addLayout(planning_status_row)
        self.planning_cards = self._summary_cards(planning_layout, PLANNING_CARD_FIELDS)
        self.planning_mass_model = SummaryTableModel()
        self.planning_mass_table = self._table(self.planning_mass_model)
        self.planning_mass_table.setMinimumHeight(190)
        planning_layout.addWidget(self.planning_mass_table)
        layout.addWidget(planning_section)
        layout.addStretch(1)
        return panel

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        self.parts_model = PartsTableModel()
        self.stocks_model = StocksTableModel()
        self.diagnostics_model = DiagnosticsTableModel()
        self.unplaced_model = UnplacedTableModel()
        self.parts_table = self._table(self.parts_model)
        self.stocks_table = self._table(self.stocks_model)
        self.unplaced_table = self._table(self.unplaced_model)
        self.diagnostics_table = self._table(self.diagnostics_model)
        tabs.addTab(self.parts_table, "Parts")
        tabs.addTab(self.stocks_table, "Stocks")
        tabs.addTab(self._build_layout_tab(), "Layout")
        tabs.addTab(self._build_result_mass_tab(), "Result Material")

        self.unplaced_empty_state = EmptyState(
            "No unplaced demand.", "Unplaced parts and structured reasons appear here."
        )
        self.unplaced_stack = QStackedWidget()
        self.unplaced_stack.addWidget(self.unplaced_empty_state)
        self.unplaced_stack.addWidget(self.unplaced_table)
        tabs.addTab(self.unplaced_stack, "Unplaced")

        self.diagnostics_empty_state = EmptyState(
            "No diagnostics.", "Import and validation messages appear here."
        )
        self.diagnostics_stack = QStackedWidget()
        self.diagnostics_stack.addWidget(self.diagnostics_empty_state)
        self.diagnostics_stack.addWidget(self.diagnostics_table)
        tabs.addTab(self.diagnostics_stack, "Diagnostics")
        return tabs

    def _build_layout_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(SPACING.panel, SPACING.panel, SPACING.panel, SPACING.panel)
        layout.setSpacing(SPACING.control)

        status_row = QHBoxLayout()
        self.result_status = StatusBadge("NOT RUN")
        self.result_message = QLabel("Run nesting to generate a layout.")
        self.result_message.setWordWrap(True)
        self.result_message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.layout_selector = QComboBox()
        self.layout_selector.setMinimumWidth(280)
        self.layout_selector.setAccessibleName("Generated layout")
        self.layout_selector.currentIndexChanged.connect(self._layout_changed)
        status_row.addWidget(self.result_status)
        status_row.addWidget(self.result_message, 1)
        status_row.addWidget(self.layout_selector)
        layout.addLayout(status_row)

        self.result_summary_panel, self.result_summary = message_panel(
            "Nesting has not been run for this Work.", StatusTone.INFORMATION
        )
        layout.addWidget(self.result_summary_panel)

        self.layout_view = LayoutView()
        self.layout_empty_state = EmptyState(
            "Run nesting to generate layouts and result material totals.",
            "The selected Work remains available for parts, stock, and planning review.",
            "Run Nesting",
        )
        self.layout_empty_state.action_requested.connect(self.run_nesting)
        self.layout_view_stack = QStackedWidget()
        self.layout_view_stack.addWidget(self.layout_empty_state)
        self.layout_view_stack.addWidget(self.layout_view)
        layout.addWidget(self.layout_view_stack, 1)

        legend = QLabel(
            "Boundary key: full stock — solid gray · allocated region — green · "
            "usable region — dashed · effective placement region — dotted"
        )
        legend.setObjectName("secondaryText")
        legend.setWordWrap(True)
        layout.addWidget(legend)
        self.warning_panel, self.warning_label = message_panel(
            WARNING_TEXT, StatusTone.WARNING
        )
        layout.addWidget(self.warning_panel)
        return tab

    def _build_result_mass_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(SPACING.panel, SPACING.panel, SPACING.panel, SPACING.panel)
        layout.setSpacing(SPACING.panel)
        heading = SectionHeader(
            "Nesting Result Material Summary", "Consumed stock and placed/unplaced demand"
        )
        layout.addWidget(heading)
        status_row = QHBoxLayout()
        self.result_mass_badge = StatusBadge()
        self.result_mass_status = QLabel(
            "Run nesting to calculate consumed material totals."
        )
        self.result_mass_status.setWordWrap(True)
        self.result_mass_status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        status_row.addWidget(self.result_mass_badge)
        status_row.addWidget(self.result_mass_status, 1)
        layout.addLayout(status_row)
        self.result_cards = self._summary_cards(layout, RESULT_CARD_FIELDS)
        self.result_mass_model = SummaryTableModel()
        self.result_mass_table = self._table(self.result_mass_model)
        layout.addWidget(self.result_mass_table, 1)
        return tab

    @staticmethod
    def _section(title: str, description: str = "") -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("section")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.control)
        layout.addWidget(SectionHeader(title, description))
        divider = QFrame()
        divider.setObjectName("sectionDivider")
        layout.addWidget(divider)
        return frame, layout

    @staticmethod
    def _property_form() -> QFormLayout:
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(SPACING.panel)
        form.setVerticalSpacing(6)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        return form

    @staticmethod
    def _property_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("propertyLabel", True)
        return label

    @staticmethod
    def _property_value() -> QLabel:
        value = QLabel(UNAVAILABLE)
        value.setProperty("propertyValue", True)
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return value

    @staticmethod
    def _summary_cards(
        parent_layout: QVBoxLayout,
        fields: tuple[tuple[str, str, str | None], ...],
    ) -> dict[str, SummaryCard]:
        grid = QGridLayout()
        grid.setHorizontalSpacing(SPACING.control)
        grid.setVerticalSpacing(SPACING.control)
        cards = {}
        for index, (field, caption, _secondary) in enumerate(fields):
            card = SummaryCard(caption)
            cards[field] = card
            grid.addWidget(card, index // 2, index % 2)
        parent_layout.addLayout(grid)
        return cards

    @staticmethod
    def _table(model) -> QTableView:
        table = QTableView()
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(26)
        table.horizontalHeader().setMinimumHeight(30)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
            work = self.session.selected_work
            if work is not None:
                self.session.set_nesting_mass(
                    work.id, self.mass_service.for_result(work, result)
                )
            self._refresh_result()
        self._refresh_busy()

    def _unexpected_failure(
        self, token: OperationToken, title: str, message: str, detail: str
    ) -> None:
        self.last_development_traceback = detail
        if self.session.fail_operation(token, f"{title}: {message}"):
            self._refresh_all()

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

    def layout_zoom_in(self) -> None:
        self.layout_view.zoom_in()

    def layout_zoom_out(self) -> None:
        self.layout_view.zoom_out()

    def _records(self):
        return self.session.import_result.records if self.session.import_result else None

    def _refresh_all(self) -> None:
        self._refresh_work_selector()
        self.diagnostics_model.set_diagnostics(self.session.diagnostics)
        self.diagnostics_stack.setCurrentIndex(
            1 if self.diagnostics_model.rowCount() else 0
        )
        self._refresh_work()
        self._refresh_busy()

    def _refresh_work_selector(self) -> None:
        self.work_selector.blockSignals(True)
        self.work_selector.clear()
        records = self._records()
        for work in self.session.works:
            key = work_key_for(work, records)
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
            self.session.workbook_path.name
            if self.session.workbook_path
            else "No workbook loaded"
        )
        work = self.session.selected_work
        self.current_work_header.setText(
            f"Work: {work.name}" if work is not None else "No Work selected"
        )
        if not self.session.works:
            self.main_empty_state.title_label.setText("Import a Debbie workbook to begin.")
            self.main_empty_state.text_label.setText(
                "Canonical Debbie Nesting Workbook schemas 1.0 and 1.1 are supported."
            )
            self.main_empty_state.action_button.setVisible(True)
            self.workspace_stack.setCurrentIndex(0)
        elif work is None:
            self.main_empty_state.title_label.setText(
                "Select a Work to inspect parts, stock, and material planning."
            )
            self.main_empty_state.text_label.setText("")
            self.main_empty_state.action_button.setVisible(False)
            self.workspace_stack.setCurrentIndex(0)
        else:
            self.workspace_stack.setCurrentIndex(1)

    def _refresh_work(self) -> None:
        work = self.session.selected_work
        self.parts_model.set_work(work, self._records())
        self.stocks_model.set_work(work, self._records())
        if work is not None and (
            self.session.planning_mass is None
            or self.session.planning_mass_work_id != work.id
        ):
            self.session.set_planning_mass(work.id, self.mass_service.plan(work))
        self._refresh_work_information(work)
        self._refresh_planning_mass()
        self._refresh_settings(work)
        self._refresh_result()
        self._refresh_busy()

    def _refresh_settings(self, work: Work | None) -> None:
        values = {key: UNAVAILABLE for key in self.setting_labels}
        if work is not None:
            profile = work.process_profile
            values = {
                "batch": str(work.batch_multiplier),
                "kerf": f"{profile.kerf:.2f} mm",
                "part_clearance": f"{profile.minimum_part_clearance:.2f} mm",
                "boundary_clearance": f"{profile.boundary_clearance:.2f} mm",
                "trim_left": f"{profile.trim.left:.2f} mm",
                "trim_right": f"{profile.trim.right:.2f} mm",
                "trim_top": f"{profile.trim.top:.2f} mm",
                "trim_bottom": f"{profile.trim.bottom:.2f} mm",
            }
        for key, label in self.setting_labels.items():
            label.setText(values[key])

    def _refresh_work_information(self, work: Work | None) -> None:
        view = build_work_information(work, self.session.import_result)
        for key, label in self.work_info_labels.items():
            label.setText(getattr(view, key))
        self.material_status.setText(view.classification_message)
        tone = StatusTone.INFORMATION if work is None or not work.is_material_classified else StatusTone.SUCCESS
        self.material_status_panel.setProperty("tone", tone.value)
        self.material_status_panel.style().unpolish(self.material_status_panel)
        self.material_status_panel.style().polish(self.material_status_panel)

    def _refresh_planning_mass(self) -> None:
        view = build_work_mass_summary(self.session.planning_mass)
        diagnostic_text = " ".join(
            f"{item.severity} {item.code}: {item.message}" for item in view.diagnostics
        )
        status = view.status.value if view.status is not None else "UNAVAILABLE"
        display_status = status.replace("_", " ")
        self.planning_status_badge.set_status(display_status, view.status)
        self.planning_status.setText(
            view.message + (f" {diagnostic_text}" if diagnostic_text else "")
        )
        self.planning_mass_model.set_summary(view)
        self._refresh_summary_cards(
            view, self.planning_cards, PLANNING_CARD_FIELDS, self.planning_mass_table
        )

    def _refresh_result(self) -> None:
        result = self.session.visible_result
        work = self.session.selected_work
        self.layout_selector.blockSignals(True)
        self.layout_selector.clear()
        if result is None:
            self.result_status.set_status("NOT RUN", StatusTone.NEUTRAL)
            self.result_message.setText("Run nesting to generate a layout.")
            self.result_summary.setText("Nesting has not been run for this Work.")
            self.unplaced_model.set_unplaced(work, ())
            self.layout_view_stack.setCurrentIndex(0)
        else:
            status_message = {
                ResultStatus.COMPLETE: "All expanded demand was placed.",
                ResultStatus.PARTIAL: "Some expanded demand could not be placed.",
                ResultStatus.FAILED_VALIDATION: "Nesting validation failed.",
            }[result.status]
            self.result_status.set_status(result.status.value.replace("_", " "), result.status)
            self.result_message.setText(status_message)
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
                f"Engine: {result.engine_version} · Requested: {result.requested_part_count} · "
                f"Placed: {result.placed_part_count} · "
                f"Unplaced: {result.requested_part_count - result.placed_part_count} · "
                f"Sheets: {len(result.layouts)} · Full-stock area: {full_area:.2f} mm² · "
                f"Unused usable area: {unused:.2f} mm²{validation_text}"
            )
            stock_instances = {item.id: item for item in work.stock_instances} if work else {}
            stocks = {item.id: item for item in work.stock_specifications} if work else {}
            for index, item in enumerate(result.layouts):
                instance = stock_instances[item.stock_instance_id]
                stock = stocks[instance.specification_id]
                self.layout_selector.addItem(
                    f"Layout {index + 1} — {stock.name} — "
                    f"{stock.dimensions.length:.2f} × {stock.dimensions.width:.2f} mm — "
                    f"{len(item.placements)} parts",
                    str(item.id),
                )
            self.unplaced_model.set_unplaced(work, result.unplaced_demand)
            if result.layouts:
                self.layout_view_stack.setCurrentIndex(1)
            else:
                self.layout_empty_state.title_label.setText("No physical layouts were produced.")
                self.layout_empty_state.text_label.setText(
                    "Review the result status, unplaced demand, and diagnostics."
                )
                self.layout_empty_state.action_button.setVisible(False)
                self.layout_view_stack.setCurrentIndex(0)
        self.unplaced_stack.setCurrentIndex(1 if self.unplaced_model.rowCount() else 0)
        self._refresh_result_mass()
        selected = self.session.selected_layout_index
        self.layout_selector.setCurrentIndex(selected if selected is not None else -1)
        self.layout_selector.blockSignals(False)
        self._render_selected_layout()

    def _refresh_result_mass(self) -> None:
        view = build_nesting_mass_summary(self.session.nesting_mass)
        diagnostic_text = " ".join(
            f"{item.severity} {item.code}: {item.message}"
            + (f" ({item.related})" if item.related else "")
            for item in view.diagnostics
        )
        status = view.status.value if view.status is not None else "UNAVAILABLE"
        display_status = "PARTIAL" if status == "PARTIAL_RESULT" else status.replace("_", " ")
        self.result_mass_badge.set_status(display_status, view.status)
        self.result_mass_status.setText(
            view.message + (f" {diagnostic_text}" if diagnostic_text else "")
        )
        self.result_mass_model.set_summary(view)
        self._refresh_summary_cards(
            view, self.result_cards, RESULT_CARD_FIELDS, self.result_mass_table
        )

    @staticmethod
    def _refresh_summary_cards(
        view: MassSummaryViewModel,
        cards: dict[str, SummaryCard],
        fields: tuple[tuple[str, str, str | None], ...],
        table: QTableView,
    ) -> None:
        values = {item.label: item.value for item in view.items}
        has_values = bool(view.items)
        hidden_labels = set()
        for field, _caption, secondary_field in fields:
            secondary = values.get(secondary_field, "") if secondary_field else ""
            cards[field].set_values(values.get(field, UNAVAILABLE), secondary)
            cards[field].setVisible(has_values)
            hidden_labels.add(field)
            if secondary_field:
                hidden_labels.add(secondary_field)
        table.setVisible(has_values)
        model = table.model()
        for row in range(model.rowCount()):
            label = model.data(model.index(row, 0))
            table.setRowHidden(row, label in hidden_labels)

    def _render_selected_layout(self) -> None:
        result = self.session.visible_result
        work = self.session.selected_work
        index = self.layout_selector.currentIndex()
        layout = result.layouts[index] if result and 0 <= index < len(result.layouts) else None
        self.layout_view.layout_scene.render_layout(work, layout)
        if layout is not None:
            self.layout_view.fit_layout()

    def _refresh_busy(self) -> None:
        operation = self.session.busy_operation
        busy = operation is not None
        self.import_button.setText("Importing…" if operation == "import" else "Import Workbook")
        self.run_button.setText("Running nesting…" if operation == "nesting" else "Run Nesting")
        self.import_button.setEnabled(not busy)
        self.run_button.setEnabled(not busy and self.session.selected_work is not None)
        view_available = not self.layout_view.scene().itemsBoundingRect().isEmpty()
        self.fit_button.setEnabled(view_available)
        self.zoom_in_button.setEnabled(view_available)
        self.zoom_out_button.setEnabled(view_available)
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
