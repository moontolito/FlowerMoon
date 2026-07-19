from __future__ import annotations

from pathlib import Path
from time import monotonic
from dataclasses import replace
from threading import Event

from PySide6.QtCore import QEventLoop, QTimer

from debbie.application import ImportService, NestingService
from debbie.desktop import DebbieMainWindow
from debbie.desktop.graphics import PartGraphicsItem, StockBoundaryItem
from debbie.desktop.workers import ServiceWorker
from debbie.nesting import ResultStatus

from .conftest import make_import_result, make_work


class BlockingNestingService:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def run(self, work):
        self.started.set()
        if not self.release.wait(5):
            raise TimeoutError("test did not release nesting worker")
        return NestingService().run(work)


class BlockingImportService:
    def __init__(self, result) -> None:
        self.result = result
        self.started = Event()
        self.release = Event()

    def import_workbook(self, path):
        self.started.set()
        if not self.release.wait(5):
            raise TimeoutError("test did not release import worker")
        return self.result


def wait_until(qt_app, predicate, timeout_ms: int = 5000) -> None:
    deadline = monotonic() + timeout_ms / 1000
    while not predicate() and monotonic() < deadline:
        qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    assert predicate(), "Qt condition timed out"


def test_worker_success_and_unexpected_exception(qt_app) -> None:
    successes = []
    failures = []
    success = ServiceWorker(lambda: 42)
    success.signals.succeeded.connect(successes.append)
    success.run()
    failure = ServiceWorker(lambda: 1 / 0)
    failure.signals.failed.connect(lambda message, detail: failures.append((message, detail)))
    failure.run()
    assert successes == [42]
    assert "division by zero" in failures[0][0]
    assert "Traceback" in failures[0][1]


def test_window_constructs_empty_with_required_actions_and_warnings(qt_app) -> None:
    window = DebbieMainWindow()
    assert window.windowTitle() == "Debbie"
    assert window.import_button.text() == "Import Workbook"
    assert not window.run_button.isEnabled()
    assert window.work_selector.count() == 0
    assert window.workspace_stack.currentWidget() is window.main_empty_state
    assert "Import a Debbie workbook" in window.main_empty_state.title_label.text()
    assert "Non-guillotine" in window.warning_label.text()
    assert "not machine-ready" in window.warning_label.text()
    window.layout_view.fit_layout()
    window.close()


def test_window_state_updates_and_work_switch_hides_result(qt_app) -> None:
    work_a = make_work("A", "Alpha")
    work_b = make_work("B", "Beta")
    window = DebbieMainWindow()
    token = window.session.begin_import()
    window.session.finish_import(token, "works.xlsx", make_import_result(work_a, work_b))
    window._refresh_all()
    assert window.work_selector.count() == 2
    assert window.parts_model.rowCount() == 1
    assert window.stocks_model.rowCount() == 1
    assert window.setting_labels["kerf"].text() == "0.20 mm"
    assert window.run_button.isEnabled()
    assert window.run_nesting()
    wait_until(qt_app, lambda: window.session.busy_operation is None)
    assert window.layout_selector.count() >= 1
    window.work_selector.setCurrentIndex(1)
    assert window.session.visible_result is None
    assert window.layout_selector.count() == 0
    assert not window.fit_button.isEnabled()
    window.close()


def test_partial_result_is_visible_with_reason_code(qt_app) -> None:
    work = make_work(stock_quantity=0)
    window = DebbieMainWindow()
    token = window.session.begin_import()
    window.session.finish_import(token, "partial.xlsx", make_import_result(work))
    window._refresh_all()
    window.run_nesting()
    wait_until(qt_app, lambda: window.session.busy_operation is None)
    assert "PARTIAL" in window.result_status.text()
    assert window.unplaced_model.rowCount() == 1
    assert "INSUFFICIENT_STOCK_QUANTITY" == window.unplaced_model.data(
        window.unplaced_model.index(0, 3)
    )
    window.close()


def test_failed_validation_status_and_diagnostic_are_visible(qt_app) -> None:
    work = make_work()
    prior = NestingService().run(work)
    invalid_solver_input = replace(work, layouts=prior.layouts)
    failed = NestingService().run(invalid_solver_input)
    assert failed.status is ResultStatus.FAILED_VALIDATION
    window = DebbieMainWindow()
    token = window.session.begin_import()
    window.session.finish_import(token, "failed.xlsx", make_import_result(work))
    solve_token, _ = window.session.begin_nesting()
    window.session.finish_nesting(solve_token, failed)
    window._refresh_all()
    assert window.result_status.text() == "FAILED VALIDATION"
    assert "INVALID_INPUT_REJECTED_BEFORE_RUN" in window.result_summary.text()
    window.close()


def test_end_to_end_canonical_import_solver_and_scene(
    qt_app, canonical_workbook: Path
) -> None:
    window = DebbieMainWindow()
    assert window.import_workbook(canonical_workbook)
    wait_until(qt_app, lambda: window.session.busy_operation is None)
    assert window.work_selector.count() == 1
    assert window.session.selected_work is not None
    assert window.run_nesting()
    wait_until(qt_app, lambda: window.session.busy_operation is None)
    assert window.session.visible_result.status is ResultStatus.COMPLETE
    assert window.layout_selector.count() == 1
    items = window.layout_view.scene().items()
    assert any(isinstance(item, StockBoundaryItem) for item in items)
    assert sum(isinstance(item, PartGraphicsItem) for item in items) == 2
    renamed = canonical_workbook.with_name("released.xlsx")
    canonical_workbook.rename(renamed)
    renamed.unlink()
    window.close()
    assert window.thread_pool.activeThreadCount() == 0


def test_failed_import_preserves_visible_project_and_updates_diagnostics(
    qt_app, tmp_path: Path
) -> None:
    work = make_work()
    window = DebbieMainWindow()
    token = window.session.begin_import()
    window.session.finish_import(token, "good.xlsx", make_import_result(work))
    window._refresh_all()
    invalid = tmp_path / "bad.xlsx"
    invalid.write_bytes(b"not a workbook")
    window.import_workbook(invalid)
    wait_until(qt_app, lambda: window.session.busy_operation is None)
    assert window.session.selected_work == work
    assert window.diagnostics_model.rowCount() >= 1
    assert "preserved" in window.session.status_message
    window.close()


def test_cancellation_boundary_is_service_extension_point() -> None:
    work = make_work()
    called = []
    result = NestingService().run(work, cancellation_check=lambda: called.append(True))
    assert result.status is ResultStatus.COMPLETE
    assert called


def test_concurrent_work_change_rejects_result_and_new_import_is_blocked(qt_app) -> None:
    first = make_work("A", "Alpha")
    second = make_work("B", "Beta")
    service = BlockingNestingService()
    window = DebbieMainWindow(nesting_service=service)
    token = window.session.begin_import()
    window.session.finish_import(token, "both.xlsx", make_import_result(first, second))
    window._refresh_all()
    assert window.run_nesting()
    wait_until(qt_app, service.started.is_set)
    window.session.select_work(second.id)
    window._refresh_work()
    assert not window.import_workbook("new.xlsx")
    service.release.set()
    wait_until(qt_app, lambda: window.session.busy_operation is None)
    assert window.session.selected_work_id == second.id
    assert window.session.visible_result is None
    assert "stale" in window.session.status_message.lower()
    window.close()


def test_close_during_import_waits_responsively_then_closes(qt_app) -> None:
    service = BlockingImportService(make_import_result(make_work()))
    window = DebbieMainWindow(import_service=service)
    window.show()
    assert window.import_workbook("blocked.xlsx")
    wait_until(qt_app, service.started.is_set)
    window.close()
    assert window.isVisible()
    assert not window.isEnabled()
    service.release.set()
    wait_until(qt_app, lambda: not window.isVisible())
    assert window.thread_pool.activeThreadCount() == 0


def test_close_during_solver_waits_responsively_then_closes(qt_app) -> None:
    work = make_work()
    service = BlockingNestingService()
    window = DebbieMainWindow(nesting_service=service)
    token = window.session.begin_import()
    window.session.finish_import(token, "work.xlsx", make_import_result(work))
    window._refresh_all()
    window.show()
    assert window.run_nesting()
    wait_until(qt_app, service.started.is_set)
    window.close()
    assert window.isVisible()
    service.release.set()
    wait_until(qt_app, lambda: not window.isVisible())
    assert window.thread_pool.activeThreadCount() == 0


def test_multiple_layout_selector_tracks_deterministic_physical_sheets(qt_app) -> None:
    base = make_work(stock_quantity=2)
    expanded_demand = replace(base.demand_items[0], base_quantity=3)
    work = replace(base, demand_items=(expanded_demand,), part_instances=())
    window = DebbieMainWindow()
    token = window.session.begin_import()
    window.session.finish_import(token, "multiple.xlsx", make_import_result(work))
    window._refresh_all()
    assert window.run_nesting()
    wait_until(qt_app, lambda: window.session.busy_operation is None)
    assert window.layout_selector.count() == 2
    first_layout_id = window.layout_selector.itemData(0)
    window.layout_selector.setCurrentIndex(1)
    assert window.layout_selector.currentData() != first_layout_id
    assert window.session.selected_layout_index == 1
    window.close()


def test_new_nesting_run_after_completion_replaces_result(qt_app) -> None:
    work = make_work()
    window = DebbieMainWindow()
    token = window.session.begin_import()
    window.session.finish_import(token, "work.xlsx", make_import_result(work))
    window._refresh_all()
    assert window.run_nesting()
    wait_until(qt_app, lambda: window.session.busy_operation is None)
    first_result = window.session.visible_result
    assert first_result is not None
    assert window.run_nesting()
    assert window.session.visible_result is None
    wait_until(qt_app, lambda: window.session.busy_operation is None)
    assert window.session.visible_result == first_result
    window.close()
