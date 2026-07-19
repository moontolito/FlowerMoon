"""Central visual tokens and stylesheet for the Debbie Desktop."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True, slots=True)
class ColorTokens:
    application_background: str = "#F2F3ED"
    primary_text: str = "#2F332E"
    secondary_text: str = "#6B7268"
    panel_background: str = "#FFFFFF"
    soft_panel_background: str = "#F7F8F4"
    accent: str = "#6F8F76"
    accent_hover: str = "#5F7C66"
    accent_soft: str = "#E2EBE4"
    border: str = "#D7DBD3"
    divider: str = "#E5E8E1"
    selection: str = "#DCE8DE"
    warning: str = "#8A651F"
    warning_soft: str = "#F7ECD6"
    error: str = "#943F3F"
    error_soft: str = "#F5DEDE"
    success: str = "#356844"
    success_soft: str = "#DCEBDF"
    information: str = "#466779"
    information_soft: str = "#DFE8ED"
    graphics_full_boundary: str = "#4A514A"
    graphics_allocated_fill: str = "#F7F8F4"
    graphics_usable_boundary: str = "#758078"
    graphics_part_outline: str = "#4A554B"
    graphics_part_fills: tuple[str, ...] = (
        "#AFC5B5",
        "#C7D4C2",
        "#A9BEC8",
        "#D8C59E",
        "#B9B4C8",
    )


@dataclass(frozen=True, slots=True)
class SpacingTokens:
    compact: int = 4
    control: int = 8
    panel: int = 12
    section: int = 16
    major: int = 24


@dataclass(frozen=True, slots=True)
class TypographyTokens:
    application_title_px: int = 20
    primary_section_px: int = 14
    secondary_section_px: int = 12
    content_px: int = 11
    meta_px: int = 10
    table_px: int = 10
    status_value_px: int = 13


COLORS = ColorTokens()
SPACING = SpacingTokens()
TYPOGRAPHY = TypographyTokens()


class StatusTone(StrEnum):
    NEUTRAL = "neutral"
    INFORMATION = "information"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


def contrast_ratio(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio for two hexadecimal RGB colours."""

    def luminance(value: str) -> float:
        channels = QColor(value).getRgbF()[:3]
        converted = tuple(
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        )
        return 0.2126 * converted[0] + 0.7152 * converted[1] + 0.0722 * converted[2]

    first, second = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (first + 0.05) / (second + 0.05)


def build_application_stylesheet() -> str:
    """Build the complete Debbie QSS from the immutable visual tokens."""

    c = COLORS
    t = TYPOGRAPHY
    return f"""
QWidget {{
    color: {c.primary_text};
    font-family: "Segoe UI";
    font-size: {t.content_px}px;
}}
QMainWindow, QWidget#applicationRoot {{ background: {c.application_background}; }}
QWidget#applicationHeader {{
    background: {c.primary_text};
    border: none;
}}
QLabel#applicationTitle {{
    color: #FFFFFF;
    font-size: {t.application_title_px}px;
    font-weight: 600;
}}
QLabel#applicationSubtitle {{ color: #DCE1D9; font-size: {t.meta_px}px; }}
QLabel#headerContext {{ color: #F5F7F3; font-size: {t.meta_px}px; }}
QToolBar#mainToolbar {{
    background: {c.panel_background};
    border: none;
    border-bottom: 1px solid {c.border};
    spacing: 8px;
    padding: 7px 12px;
}}
QPushButton {{
    background: {c.panel_background};
    border: 1px solid {c.border};
    border-radius: 4px;
    min-height: 30px;
    padding: 0 12px;
}}
QPushButton:hover {{ background: {c.soft_panel_background}; border-color: {c.accent}; }}
QPushButton:focus {{ border: 2px solid {c.accent}; }}
QPushButton:disabled {{ color: #9AA097; background: #ECEEE9; border-color: #DEE1DA; }}
QPushButton[primary="true"] {{
    color: #FFFFFF;
    background: {c.accent};
    border-color: {c.accent};
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{ background: {c.accent_hover}; }}
QPushButton[quiet="true"] {{ border-color: transparent; background: transparent; padding: 0 8px; }}
QPushButton[quiet="true"]:hover {{ background: {c.accent_soft}; }}
QComboBox {{
    background: {c.panel_background};
    border: 1px solid {c.border};
    border-radius: 4px;
    min-height: 30px;
    padding: 0 28px 0 8px;
}}
QComboBox:focus {{ border: 2px solid {c.accent}; }}
QComboBox QAbstractItemView {{
    background: {c.panel_background};
    border: 1px solid {c.border};
    selection-background-color: {c.selection};
    selection-color: {c.primary_text};
    padding: 4px;
}}
QScrollArea, QAbstractScrollArea {{ border: none; background: transparent; }}
QWidget#engineeringPanel {{ background: {c.panel_background}; }}
QFrame#section {{ background: transparent; border: none; }}
QLabel#sectionTitle {{
    font-size: {t.primary_section_px}px;
    font-weight: 600;
    color: {c.primary_text};
}}
QLabel#sectionDescription, QLabel#secondaryText {{ color: {c.secondary_text}; font-size: {t.meta_px}px; }}
QFrame#sectionDivider {{ background: {c.divider}; min-height: 1px; max-height: 1px; border: none; }}
QLabel[propertyLabel="true"] {{ color: {c.secondary_text}; }}
QLabel[propertyValue="true"] {{ color: {c.primary_text}; font-weight: 500; }}
QFrame#summaryCard {{
    background: {c.soft_panel_background};
    border: 1px solid {c.border};
    border-radius: 5px;
}}
QLabel#summaryCaption {{ color: {c.secondary_text}; font-size: {t.meta_px}px; font-weight: 600; }}
QLabel#summaryValue {{ color: {c.primary_text}; font-size: {t.status_value_px}px; font-weight: 600; }}
QLabel#summarySecondary {{ color: {c.secondary_text}; font-size: {t.meta_px}px; }}
QLabel#statusBadge {{ border-radius: 3px; padding: 3px 8px; font-size: {t.meta_px}px; font-weight: 600; }}
QLabel#statusBadge[tone="neutral"] {{ background: #ECEEE9; color: {c.primary_text}; }}
QLabel#statusBadge[tone="information"] {{ background: {c.information_soft}; color: {c.information}; }}
QLabel#statusBadge[tone="success"] {{ background: {c.success_soft}; color: {c.success}; }}
QLabel#statusBadge[tone="warning"] {{ background: {c.warning_soft}; color: {c.warning}; }}
QLabel#statusBadge[tone="error"] {{ background: {c.error_soft}; color: {c.error}; }}
QFrame#messagePanel {{ border: 1px solid {c.divider}; border-radius: 4px; background: {c.soft_panel_background}; }}
QFrame#messagePanel[tone="warning"] {{ border-color: #E8D1A7; background: {c.warning_soft}; }}
QFrame#messagePanel[tone="error"] {{ border-color: #E5BABA; background: {c.error_soft}; }}
QFrame#messagePanel[tone="information"] {{ border-color: #C6D7E0; background: {c.information_soft}; }}
QLabel#emptyStateTitle {{ font-size: {t.secondary_section_px}px; font-weight: 600; }}
QLabel#emptyStateText {{ color: {c.secondary_text}; }}
QTabWidget::pane {{ background: {c.panel_background}; border: 1px solid {c.border}; border-top: none; }}
QTabBar::tab {{
    background: {c.soft_panel_background};
    border: 1px solid {c.border};
    border-bottom: none;
    padding: 8px 14px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {c.panel_background}; color: {c.primary_text}; border-top: 2px solid {c.accent}; }}
QTabBar::tab:hover:!selected {{ background: {c.accent_soft}; }}
QTableView {{
    background: {c.panel_background};
    alternate-background-color: {c.soft_panel_background};
    selection-background-color: {c.selection};
    selection-color: {c.primary_text};
    border: none;
    gridline-color: {c.divider};
    font-size: {t.table_px}px;
}}
QHeaderView::section {{
    background: #E9ECE6;
    color: {c.primary_text};
    border: none;
    border-right: 1px solid {c.divider};
    border-bottom: 1px solid {c.border};
    padding: 6px 8px;
    font-weight: 600;
}}
QSplitter::handle {{ background: {c.divider}; }}
QSplitter::handle:horizontal {{ width: 4px; }}
QStatusBar {{ background: {c.panel_background}; color: {c.secondary_text}; border-top: 1px solid {c.border}; }}
QGraphicsView {{ background: {c.soft_panel_background}; border: none; }}
"""


def apply_application_theme(application: QApplication | None) -> None:
    if application is not None:
        application.setStyleSheet(build_application_stylesheet())
