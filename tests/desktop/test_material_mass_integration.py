from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from time import monotonic

from PySide6.QtCore import QEventLoop, Qt

from debbie.desktop import DebbieMainWindow
from debbie.application import MassService
from debbie.nesting import ResultStatus, nest_work


def _wait(qt_app, predicate, timeout_ms: int = 5000) -> None:
    deadline = monotonic() + timeout_ms / 1000
    while not predicate() and monotonic() < deadline:
        qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    assert predicate(), "Qt condition timed out"


def _displayed(model, row: int, column: int):
    return model.data(model.index(row, column), Qt.ItemDataRole.DisplayRole)


def _summary_values(model) -> dict[str, str]:
    return {
        _displayed(model, row, 0): _displayed(model, row, 1)
        for row in range(model.rowCount())
    }


def _import(window: DebbieMainWindow, qt_app, path: Path) -> None:
    assert window.import_workbook(path)
    _wait(qt_app, lambda: window.session.busy_operation is None)
    assert window.session.selected_work is not None


def _nest(window: DebbieMainWindow, qt_app) -> None:
    assert window.run_nesting()
    _wait(qt_app, lambda: window.session.busy_operation is None)


class CountingMassService(MassService):
    def __init__(self) -> None:
        self.plan_calls = 0

    def plan(self, work):
        self.plan_calls += 1
        return super().plan(work)


def test_schema_1_0_shows_unavailable_material_without_blocking_nesting(
    qt_app, canonical_workbook: Path
) -> None:
    window = DebbieMainWindow()
    _import(window, qt_app, canonical_workbook)
    assert window.work_info_labels["schema_version"].text() == "1.0"
    assert window.work_info_labels["material_category"].text() == "—"
    assert "Not available in schema 1.0" in window.material_status.text()
    assert "MATERIAL_DATA_REQUIRED" in window.planning_status.text()
    assert window.planning_mass_model.rowCount() == 0
    assert window.planning_mass_table.isHidden()
    assert all(card.isHidden() for card in window.planning_cards.values())
    _nest(window, qt_app)
    assert window.session.visible_result.status is ResultStatus.COMPLETE
    assert "MATERIAL_DATA_REQUIRED" in window.result_mass_status.text()
    assert window.result_mass_model.rowCount() == 0
    assert window.result_mass_table.isHidden()
    assert all(card.isHidden() for card in window.result_cards.values())
    window.close()


def test_schema_1_1_full_allocation_material_planning_and_complete_result(
    qt_app, canonical_workbook_v11_factory
) -> None:
    window = DebbieMainWindow()
    _import(window, qt_app, canonical_workbook_v11_factory())
    assert window.work_info_labels["work_key"].text() == "W-1"
    assert window.work_info_labels["schema_version"].text() == "1.1"
    assert window.work_info_labels["material_category"].text() == "Stainless Steel"
    assert window.work_info_labels["material_grade"].text() == "AISI 304"
    assert window.work_info_labels["thickness"].text() == "3.00 mm"
    assert window.work_info_labels["density"].text() == "7.900 g/cm³"
    assert window.work_info_labels["density_source"].text() == "Explicit override"
    assert _displayed(window.stocks_model, 0, 1) == "S-1"
    assert _displayed(window.stocks_model, 0, 7) == "100.00%"
    assert _displayed(window.stocks_model, 0, 8) == "100.00%"
    assert window.planning_status_badge.text() == "AVAILABLE"
    _nest(window, qt_app)
    values = _summary_values(window.result_mass_model)
    assert "COMPLETE" in window.result_status.text()
    assert "All expanded demand was placed" in window.result_mass_status.text()
    assert values["Unplaced Rectangular Part Mass Estimate"] == "0.00 kg"
    assert "Consumed Gross Physical Mass / Product" in values
    window.close()


def test_planning_mass_is_calculated_once_for_an_unchanged_selected_work(
    qt_app, canonical_workbook_v11_factory
) -> None:
    mass_service = CountingMassService()
    window = DebbieMainWindow(mass_service=mass_service)
    _import(window, qt_app, canonical_workbook_v11_factory())
    assert mass_service.plan_calls == 1
    window._refresh_all()
    window._refresh_work()
    assert mass_service.plan_calls == 1
    window.close()


def test_schema_1_1_partial_allocation_is_visible_and_used_by_result_mass(
    qt_app, canonical_workbook_v11_factory
) -> None:
    path = canonical_workbook_v11_factory(
        parts=[["W-1", "P-1", "Panel", 100, 100, 1, "No", None]],
        stocks=[["W-1", "HALF", "Half", 200, 100, 100, 100, 1, 1]],
    )
    window = DebbieMainWindow()
    _import(window, qt_app, path)
    assert _displayed(window.stocks_model, 0, 3) == "200.00"
    assert _displayed(window.stocks_model, 0, 5) == "100.00"
    assert _displayed(window.stocks_model, 0, 7) == "50.00%"
    assert _displayed(window.stocks_model, 0, 8) == "100.00%"
    _nest(window, qt_app)
    result = window.session.visible_result
    assert result.status is ResultStatus.COMPLETE
    assert result.layouts[0].process_profile.trim.left == 0
    values = _summary_values(window.result_mass_model)
    assert values["Consumed Physical Equivalent Sheets"] == "0.500 sheets"
    assert values["Consumed Commercial Equivalent Sheets"] == "1.000 sheets"
    window.close()


def test_worked_four_and_half_sheet_values_are_displayed_semantically(
    qt_app, canonical_workbook_v11_factory
) -> None:
    work = [
        "W-1", "Worked example", "stainless-steel", "Stainless Steel",
        "aisi-304", "AISI 304", 3, 7.9, "explicit_override", 10,
        0, 0, 0, 0, 0, 0, 0, None,
    ]
    path = canonical_workbook_v11_factory(
        work=work,
        parts=[],
        stocks=[
            ["W-1", "FULL", "Full", 2500, 1250, 2500, 1250, 1, 4],
            ["W-1", "HALF", "Half", 2500, 1250, 1250, 1250, 1, 1],
        ],
    )
    window = DebbieMainWindow()
    _import(window, qt_app, path)
    values = _summary_values(window.planning_mass_model)
    assert values["Physical Equivalent Sheets"] == "4.500 sheets"
    assert values["Commercial Equivalent Sheets"] == "5.000 sheets"
    assert values["Gross Physical Allocation Mass"] == "333.28 kg"
    assert values["Gross Commercial Allocation Mass"] == "370.31 kg"
    assert values["Commercial Allocation Difference"] == "37.03 kg"
    assert values["Gross Physical Mass / Product"] == "33.33 kg"
    window.close()


def test_partial_result_withholds_completed_product_values_and_shows_reason(
    qt_app, canonical_workbook_v11_factory
) -> None:
    path = canonical_workbook_v11_factory(
        parts=[["W-1", "P-1", "Large", 60, 60, 2, "No", None]],
        stocks=[["W-1", "S-1", "Sheet", 100, 100, 100, 100, 1, 1]],
    )
    window = DebbieMainWindow()
    _import(window, qt_app, path)
    _nest(window, qt_app)
    values = _summary_values(window.result_mass_model)
    assert "PARTIAL" in window.result_status.text()
    assert "Completed-product gross mass is unavailable" in window.result_mass_status.text()
    assert float(values["Placed Rectangular Part Mass Estimate"].split()[0]) > 0
    assert float(values["Unplaced Rectangular Part Mass Estimate"].split()[0]) > 0
    assert not any("/ Product" in label for label in values)
    assert _displayed(window.unplaced_model, 0, 3) == "NO_VALID_PLACEMENT_FOUND"
    window.close()


def test_insufficient_planning_keeps_negative_unused_mass_and_withholds_per_product(
    qt_app, canonical_workbook_v11_factory
) -> None:
    path = canonical_workbook_v11_factory(
        parts=[["W-1", "P-1", "Oversized", 200, 200, 1, "No", None]],
        stocks=[["W-1", "S-1", "Sheet", 100, 100, 100, 100, 1, 1]],
    )
    window = DebbieMainWindow()
    _import(window, qt_app, path)
    values = _summary_values(window.planning_mass_model)
    assert "INSUFFICIENT_AVAILABLE_STOCK" in window.planning_status.text()
    assert "insufficient" in window.planning_status.text().lower()
    assert values["Physical Unused Allocation Mass"].startswith("-")
    assert not any("/ Product" in label for label in values)
    window.close()


def test_failed_validation_clears_values_and_exposes_diagnostic(
    qt_app, canonical_workbook_v11_factory
) -> None:
    window = DebbieMainWindow()
    _import(window, qt_app, canonical_workbook_v11_factory())
    work = window.session.selected_work
    _nest(window, qt_app)
    assert window.result_mass_model.rowCount() > 0
    complete = window.session.visible_result
    invalid = replace(work, layouts=complete.layouts)
    failed = nest_work(invalid)
    assert failed.status is ResultStatus.FAILED_VALIDATION
    token, _ = window.session.begin_nesting()
    window._nesting_succeeded(token, failed)
    assert window.result_mass_model.rowCount() == 0
    assert window.result_mass_badge.text() == "FAILED VALIDATION"
    assert "FAILED_NESTING_VALIDATION" in window.result_mass_status.text()
    assert "INVALID_INPUT_REJECTED_BEFORE_RUN" in window.result_summary.text()
    window.close()


def test_invalid_result_reconciliation_is_structured_and_does_not_crash(
    qt_app, canonical_workbook_v11_factory
) -> None:
    window = DebbieMainWindow()
    _import(window, qt_app, canonical_workbook_v11_factory())
    work = window.session.selected_work
    changed_demand = replace(work.demand_items[0], base_quantity=1)
    stale_snapshot = replace(work, demand_items=(changed_demand,), part_instances=())
    malformed = nest_work(stale_snapshot)
    token, _ = window.session.begin_nesting()
    window._nesting_succeeded(token, malformed)
    assert window.result_mass_model.rowCount() == 0
    assert window.result_mass_badge.text() == "INVALID RESULT"
    assert "RESULT_DATA_MISMATCH" in window.result_mass_status.text()
    window.close()


def test_new_import_and_work_change_clear_prior_result_mass(
    qt_app, canonical_workbook_v11_factory, canonical_workbook: Path
) -> None:
    window = DebbieMainWindow()
    _import(window, qt_app, canonical_workbook_v11_factory())
    _nest(window, qt_app)
    assert window.result_mass_model.rowCount() > 0
    _import(window, qt_app, canonical_workbook)
    assert window.session.nesting_mass is None
    assert window.result_mass_model.rowCount() == 0
    assert "MATERIAL_DATA_REQUIRED" in window.planning_status.text()
    window.close()


def test_failed_import_preserves_prior_classified_planning_and_result_state(
    qt_app, canonical_workbook_v11_factory, canonical_workbook: Path, tmp_path: Path
) -> None:
    window = DebbieMainWindow()
    _import(window, qt_app, canonical_workbook_v11_factory())
    _nest(window, qt_app)
    selected = window.session.selected_work
    planning = window.session.planning_mass
    nesting = window.session.visible_result
    result_mass = window.session.nesting_mass

    invalid = tmp_path / "invalid-attempt.xlsx"
    invalid.write_bytes(b"not an xlsx package")
    assert window.import_workbook(invalid)
    _wait(qt_app, lambda: window.session.busy_operation is None)
    assert window.session.selected_work is selected
    assert window.session.planning_mass is planning
    assert window.session.visible_result is nesting
    assert window.session.nesting_mass is result_mass
    assert window.diagnostics_model.rowCount() > 0
    assert "preserved" in window.session.status_message

    _import(window, qt_app, canonical_workbook)
    assert window.session.selected_work is not selected
    assert window.session.nesting_mass is None
    assert "MATERIAL_DATA_REQUIRED" in window.planning_status.text()
    window.close()


def test_schema_1_0_to_1_1_replaces_unavailable_state_with_classified_values(
    qt_app, canonical_workbook_v11_factory, canonical_workbook: Path
) -> None:
    window = DebbieMainWindow()
    _import(window, qt_app, canonical_workbook)
    assert "MATERIAL_DATA_REQUIRED" in window.planning_status.text()
    _import(window, qt_app, canonical_workbook_v11_factory())
    assert window.planning_status_badge.text() == "AVAILABLE"
    assert window.work_info_labels["material_grade"].text() == "AISI 304"
    assert window.planning_mass_model.rowCount() > 0
    window.close()


def test_complete_and_partial_reimports_do_not_leak_result_presentation(
    qt_app, canonical_workbook_v11_factory
) -> None:
    complete_path = canonical_workbook_v11_factory()
    partial_path = canonical_workbook_v11_factory(
        parts=[["W-1", "P-1", "Large", 60, 60, 2, "No", None]],
        stocks=[["W-1", "S-1", "Sheet", 100, 100, 100, 100, 1, 1]],
    )
    window = DebbieMainWindow()
    _import(window, qt_app, complete_path)
    _nest(window, qt_app)
    assert any("/ Product" in key for key in _summary_values(window.result_mass_model))
    _import(window, qt_app, partial_path)
    assert window.result_mass_model.rowCount() == 0
    _nest(window, qt_app)
    assert "PARTIAL" in window.result_status.text()
    assert not any("/ Product" in key for key in _summary_values(window.result_mass_model))
    _import(window, qt_app, complete_path)
    _nest(window, qt_app)
    assert "COMPLETE" in window.result_status.text()
    assert "partial" not in window.result_mass_status.text().lower()
    assert any("/ Product" in key for key in _summary_values(window.result_mass_model))
    window.close()


def test_functional_layout_remains_scrollable_at_supported_window_sizes(
    qt_app, canonical_workbook_v11_factory
) -> None:
    window = DebbieMainWindow()
    _import(window, qt_app, canonical_workbook_v11_factory())
    for width, height in ((1280, 720), (1920, 1080)):
        window.resize(width, height)
        window.show()
        qt_app.processEvents()
        assert window.centralWidget().size().width() > 0
        assert window.planning_mass_table.verticalScrollBar() is not None
        assert window.work_info_labels["density"].text().endswith("g/cm³")
    window.close()
