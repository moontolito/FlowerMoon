from pathlib import Path

from debbie.application import DebbieSession
from debbie.importers.excel import (
    CanonicalWorkbookImportResult,
    ImportDiagnostic,
    ImportDiagnosticCode,
    ImportSeverity,
)
from debbie.nesting import nest_work

from .conftest import make_import_result, make_work


def failed_result(message: str = "bad workbook") -> CanonicalWorkbookImportResult:
    return CanonicalWorkbookImportResult(
        diagnostics=(
            ImportDiagnostic(
                ImportSeverity.ERROR, ImportDiagnosticCode.INVALID_METADATA, message
            ),
        )
    )


def test_initial_empty_state() -> None:
    session = DebbieSession()
    assert session.works == ()
    assert session.selected_work is None
    assert session.visible_result is None
    assert session.status_message == "No workbook loaded"


def test_successful_import_selects_stable_work_and_clears_old_result() -> None:
    first = make_work()
    second = make_work("W2", "Another")
    session = DebbieSession()
    token = session.begin_import()
    assert session.finish_import(token, "one.xlsx", make_import_result(first))
    solve_token, work = session.begin_nesting()
    assert session.finish_nesting(solve_token, nest_work(work))
    token = session.begin_import()
    assert session.finish_import(token, "two.xlsx", make_import_result(second))
    assert session.selected_work_id == second.id
    assert session.nesting_result is None
    assert session.workbook_path == Path("two.xlsx")


def test_failed_import_preserves_project_and_shows_new_diagnostics() -> None:
    work = make_work()
    session = DebbieSession()
    token = session.begin_import()
    session.finish_import(token, "good.xlsx", make_import_result(work))
    token = session.begin_import()
    session.finish_import(token, "bad.xlsx", failed_result("new failure"))
    assert session.works == (work,)
    assert session.workbook_path == Path("good.xlsx")
    assert session.diagnostics[0].message == "new failure"
    assert "preserved" in session.status_message


def test_invalid_then_valid_has_no_diagnostic_leakage() -> None:
    session = DebbieSession()
    token = session.begin_import()
    session.finish_import(token, "bad.xlsx", failed_result())
    token = session.begin_import()
    session.finish_import(token, "good.xlsx", make_import_result(make_work()))
    assert session.diagnostics == ()
    assert session.selected_work is not None


def test_work_switch_hides_result_for_another_work() -> None:
    work_a = make_work("A", "A")
    work_b = make_work("B", "B")
    session = DebbieSession()
    token = session.begin_import()
    session.finish_import(token, "both.xlsx", make_import_result(work_a, work_b))
    session.select_work(work_a.id)
    solve_token, work = session.begin_nesting()
    session.finish_nesting(solve_token, nest_work(work))
    assert session.visible_result is not None
    session.select_work(work_b.id)
    assert session.visible_result is None


def test_stale_solver_result_is_rejected_after_project_change() -> None:
    original = make_work("A", "A")
    replacement = make_work("B", "B")
    session = DebbieSession()
    token = session.begin_import()
    session.finish_import(token, "a.xlsx", make_import_result(original))
    solve_token, work = session.begin_nesting()
    session.invalidate_running_operation()
    import_token = session.begin_import()
    session.finish_import(import_token, "b.xlsx", make_import_result(replacement))
    assert not session.finish_nesting(solve_token, nest_work(work))
    assert session.visible_result is None


def test_duplicate_run_is_blocked() -> None:
    session = DebbieSession()
    token = session.begin_import()
    session.finish_import(token, "a.xlsx", make_import_result(make_work()))
    session.begin_nesting()
    try:
        session.begin_nesting()
    except RuntimeError:
        pass
    else:
        raise AssertionError("duplicate nesting run was not blocked")


def test_import_cannot_replace_an_active_operation_token() -> None:
    session = DebbieSession()
    session.begin_import()
    try:
        session.begin_import()
    except RuntimeError:
        pass
    else:
        raise AssertionError("concurrent import was not blocked")


def test_new_run_clears_previous_result_before_worker_boundary() -> None:
    session = DebbieSession()
    token = session.begin_import()
    session.finish_import(token, "a.xlsx", make_import_result(make_work()))
    token, work = session.begin_nesting()
    session.finish_nesting(token, nest_work(work))
    assert session.visible_result is not None
    session.begin_nesting()
    assert session.visible_result is None


def test_result_for_wrong_work_clears_busy_state_and_is_rejected() -> None:
    first = make_work("A", "A")
    second = make_work("B", "B")
    session = DebbieSession()
    token = session.begin_import()
    session.finish_import(token, "both.xlsx", make_import_result(first, second))
    session.select_work(first.id)
    solve_token, _ = session.begin_nesting()
    assert not session.finish_nesting(solve_token, nest_work(second))
    assert session.busy_operation is None
    assert session.visible_result is None
    assert "different work" in session.status_message
