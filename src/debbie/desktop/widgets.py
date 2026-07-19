"""Small reusable visual widgets for the read-only Debbie Desktop."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from debbie.application.presentation import UNAVAILABLE

from .theme import SPACING, StatusTone


def status_tone_for(status: object | None) -> StatusTone:
    """Map a typed backend status to a presentation-only tone."""

    value = getattr(status, "value", status)
    if value in {"COMPLETE", "AVAILABLE"}:
        return StatusTone.SUCCESS
    if value in {"PARTIAL", "PARTIAL_RESULT", "INSUFFICIENT_AVAILABLE_STOCK"}:
        return StatusTone.WARNING
    if value in {"FAILED_VALIDATION", "INVALID_RESULT", "WORK_RESULT_MISMATCH"}:
        return StatusTone.ERROR
    if value in {"MATERIAL_DATA_REQUIRED"}:
        return StatusTone.INFORMATION
    return StatusTone.NEUTRAL


class SectionHeader(QWidget):
    def __init__(self, title: str, description: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.compact)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("sectionTitle")
        layout.addWidget(self.title_label)
        self.description_label = QLabel(description)
        self.description_label.setObjectName("sectionDescription")
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(bool(description))
        layout.addWidget(self.description_label)


class StatusBadge(QLabel):
    def __init__(self, text: str = "NOT AVAILABLE", tone: StatusTone = StatusTone.NEUTRAL) -> None:
        super().__init__(text)
        self.setObjectName("statusBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_status(text, tone)

    def set_status(self, text: str, status_or_tone: object | None = None) -> None:
        tone = (
            status_or_tone
            if isinstance(status_or_tone, StatusTone)
            else status_tone_for(status_or_tone)
        )
        self.setText(text)
        self.setProperty("tone", tone.value)
        self.style().unpolish(self)
        self.style().polish(self)


class SummaryCard(QFrame):
    def __init__(self, caption: str, value: str = UNAVAILABLE, secondary: str = "") -> None:
        super().__init__()
        self.setObjectName("summaryCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.control, SPACING.control, SPACING.control, SPACING.control)
        layout.setSpacing(2)
        self.caption_label = QLabel(caption.upper())
        self.caption_label.setObjectName("summaryCaption")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("summaryValue")
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.secondary_label = QLabel(secondary)
        self.secondary_label.setObjectName("summarySecondary")
        self.secondary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.secondary_label.setVisible(bool(secondary))
        layout.addWidget(self.caption_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.secondary_label)

    def set_values(self, value: str, secondary: str = "") -> None:
        self.value_label.setText(value)
        self.secondary_label.setText(secondary)
        self.secondary_label.setVisible(bool(secondary))


class EmptyState(QFrame):
    action_requested = Signal()

    def __init__(self, title: str, text: str = "", action_text: str = "") -> None:
        super().__init__()
        self.setObjectName("messagePanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.major, SPACING.major, SPACING.major, SPACING.major)
        layout.setSpacing(SPACING.control)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("emptyStateTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label = QLabel(text)
        self.text_label.setObjectName("emptyStateText")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setWordWrap(True)
        self.action_button = QPushButton(action_text)
        self.action_button.setVisible(bool(action_text))
        self.action_button.clicked.connect(self.action_requested)
        layout.addWidget(self.title_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignHCenter)


def message_panel(text: str, tone: StatusTone = StatusTone.INFORMATION) -> tuple[QFrame, QLabel]:
    panel = QFrame()
    panel.setObjectName("messagePanel")
    panel.setProperty("tone", tone.value)
    layout = QHBoxLayout(panel)
    layout.setContentsMargins(SPACING.control, SPACING.control, SPACING.control, SPACING.control)
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(label)
    return panel, label
