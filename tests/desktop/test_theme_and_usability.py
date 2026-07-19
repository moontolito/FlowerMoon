from __future__ import annotations

from pathlib import Path

import pytest

from debbie.application.presentation import UNAVAILABLE
from debbie.desktop import DebbieMainWindow
from debbie.desktop.theme import (
    COLORS,
    StatusTone,
    build_application_stylesheet,
    contrast_ratio,
)
from debbie.desktop.widgets import EmptyState, StatusBadge, SummaryCard, status_tone_for
from debbie.mass import MassCalculationStatus
from debbie.nesting import ResultStatus


def test_theme_builds_from_tokens_and_key_contrast_is_readable() -> None:
    stylesheet = build_application_stylesheet()
    assert COLORS.application_background in stylesheet
    assert COLORS.accent in stylesheet
    for tone in StatusTone:
        assert f'tone="{tone.value}"' in stylesheet
    assert contrast_ratio(COLORS.primary_text, COLORS.panel_background) >= 7
    assert contrast_ratio(COLORS.success, COLORS.success_soft) >= 4.5
    assert contrast_ratio(COLORS.error, COLORS.error_soft) >= 4.5


@pytest.mark.parametrize(
    ("status", "tone"),
    (
        (ResultStatus.COMPLETE, StatusTone.SUCCESS),
        (ResultStatus.PARTIAL, StatusTone.WARNING),
        (ResultStatus.FAILED_VALIDATION, StatusTone.ERROR),
        (MassCalculationStatus.MATERIAL_DATA_REQUIRED, StatusTone.INFORMATION),
    ),
)
def test_status_badge_maps_typed_statuses(status, tone, qt_app) -> None:
    badge = StatusBadge()
    badge.set_status(status.value.replace("_", " "), status)
    assert badge.property("tone") == tone.value
    assert badge.text()


def test_summary_card_and_empty_state_expose_semantic_content(qt_app) -> None:
    unavailable = SummaryCard("Unavailable")
    assert unavailable.value_label.text() == "—" == UNAVAILABLE
    assert unavailable.value_label.text() != "\u00e2\u20ac\u201d"

    card = SummaryCard("Gross Physical", "333.28 kg", "33.33 kg / product")
    assert card.caption_label.text() == "GROSS PHYSICAL"
    assert card.value_label.text() == "333.28 kg"
    assert card.secondary_label.text() == "33.33 kg / product"

    state = EmptyState("Import a Debbie workbook to begin.", action_text="Import Workbook")
    triggered = []
    state.action_requested.connect(lambda: triggered.append(True))
    state.action_button.click()
    assert triggered == [True]


def test_changed_text_sources_are_utf8_and_contain_no_mojibake() -> None:
    root = Path(__file__).resolve().parents[2]
    sources = (
        root / "README.md",
        root / "docs" / "MATERIAL_AND_WEIGHT_MODEL.md",
        root / "docs" / "MIGRATION_PLAN.md",
        root / "docs" / "DESKTOP_UI_BASELINE.md",
        root / "src" / "debbie" / "application" / "presentation.py",
        root / "src" / "debbie" / "desktop" / "app.py",
        root / "src" / "debbie" / "desktop" / "graphics.py",
        root / "src" / "debbie" / "desktop" / "main_window.py",
        root / "src" / "debbie" / "desktop" / "models.py",
        root / "src" / "debbie" / "desktop" / "theme.py",
        root / "src" / "debbie" / "desktop" / "widgets.py",
        root / "tests" / "desktop" / "test_material_mass_integration.py",
        root / "tests" / "desktop" / "test_models_and_graphics.py",
        root / "tests" / "desktop" / "test_presentation.py",
        root / "tests" / "desktop" / "test_theme_and_usability.py",
        root / "tests" / "desktop" / "test_workers_and_window.py",
        root / "Launch Debbie.bat",
    )
    mojibake = tuple(
        "".join(chr(codepoint) for codepoint in codepoints)
        for codepoints in (
            (0xE2, 0x20AC, 0x201D),
            (0xE2, 0x20AC, 0x2013),
            (0xE2, 0x20AC, 0xA6),
            (0xE2, 0x20AC, 0x2122),
            (0xE2, 0x2020, 0x2019),
        )
    ) + (chr(0xC2), chr(0xC3))
    for source in sources:
        text = source.read_text(encoding="utf-8", errors="strict")
        assert not any(sequence in text for sequence in mojibake), source


def test_window_hierarchy_actions_empty_state_and_busy_text(qt_app) -> None:
    window = DebbieMainWindow()
    assert window.windowTitle() == "Debbie"
    assert window.main_toolbar.objectName() == "mainToolbar"
    assert window.import_button.isVisible() or not window.isVisible()
    assert window.import_button.accessibleName() == "Import Workbook"
    assert window.run_button.accessibleName() == "Run Nesting"
    assert window.workspace_stack.currentWidget() is window.main_empty_state
    assert window.diagnostics_stack.currentWidget() is window.diagnostics_empty_state
    assert window.left_scroll.widgetResizable()

    token = window.session.begin_import()
    window._refresh_busy()
    assert window.import_button.text() == "Importing…"
    assert not window.import_button.isEnabled()
    window.session.fail_operation(token, "Import failed")
    window._refresh_busy()
    assert window.import_button.text() == "Import Workbook"
    window.close()


def test_window_remains_operational_at_supported_logical_sizes(qt_app) -> None:
    window = DebbieMainWindow()
    for size in ((1280, 720), (1920, 1080)):
        window.resize(*size)
        window.show()
        qt_app.processEvents()
        assert window.main_splitter.sizes()[0] >= 330
        assert window.main_empty_state.action_button.isVisible()
        assert window.main_toolbar.height() > 0
    window.close()


def test_development_launcher_is_relative_quoted_and_safe() -> None:
    root = Path(__file__).resolve().parents[2]
    launcher = root / "Launch Debbie.bat"
    text = launcher.read_text(encoding="utf-8")
    assert launcher.is_file()
    assert "%~dp0" in text
    assert '"%DEBBIE_PYTHON%" -m debbie.desktop %*' in text
    assert 'if not exist "%DEBBIE_PYTHON%"' in text
    assert "could not find the repository-local Python environment" in text
    assert "D:\\Software" not in text
    assert "http://" not in text and "https://" not in text
