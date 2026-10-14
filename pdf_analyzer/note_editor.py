"""Dialog for creating a comment and Zotero-style tags from selected PDF text."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .evidence import EvidenceStore


def parse_tags(raw_text: str) -> tuple[str, ...]:
    return EvidenceStore.normalize_tags(
        tuple(part for part in re.split(r"[,;\n]+", raw_text) if part.strip())
    )


class NoteDialog(QDialog):
    def __init__(
        self,
        selected_text: str,
        existing_tags: tuple[str, ...] = (),
        default_tags: tuple[str, ...] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._note_result: tuple[str, tuple[str, ...]] | None = None
        self.setWindowTitle("PDF Note")
        self.resize(620, 520)
        layout = QVBoxLayout(self)

        selected_label = QLabel("SELECTED TEXT")
        selected_label.setObjectName("sectionTitle")
        layout.addWidget(selected_label)
        self.selected_text = QTextEdit()
        self.selected_text.setReadOnly(True)
        self.selected_text.setPlainText(selected_text)
        self.selected_text.setMaximumHeight(145)
        layout.addWidget(self.selected_text)

        comment_label = QLabel("PERSONAL COMMENT")
        comment_label.setObjectName("sectionTitle")
        layout.addWidget(comment_label)
        self.comment_input = QTextEdit()
        self.comment_input.setPlaceholderText("Add an observation, risk or required action...")
        layout.addWidget(self.comment_input, 1)

        tags_label = QLabel("TAGS")
        tags_label.setObjectName("sectionTitle")
        layout.addWidget(tags_label)
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Contract, Delivery, FAT — separated by commas")
        self.tags_input.setText(", ".join(default_tags))
        completer = QCompleter(sorted(existing_tags, key=str.casefold), self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.tags_input.setCompleter(completer)
        layout.addWidget(self.tags_input)

        hint = QLabel("Add multiple tags separated by commas, semicolons or new lines.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save Note")
        buttons.accepted.connect(self._accept_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.comment_input.setFocus()

    def note(self) -> tuple[str, tuple[str, ...]]:
        return self._note_result or (
            self.comment_input.toPlainText().strip(),
            parse_tags(self.tags_input.text()),
        )

    def _accept_valid(self) -> None:
        try:
            self._note_result = (
                self.comment_input.toPlainText().strip(),
                parse_tags(self.tags_input.text()),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid tags", str(error))
            return
        self.accept()

    @classmethod
    def get_note(
        cls,
        parent: QWidget,
        selected_text: str,
        existing_tags: tuple[str, ...] = (),
        default_tags: tuple[str, ...] = (),
    ) -> tuple[str, tuple[str, ...]] | None:
        dialog = cls(selected_text, existing_tags, default_tags, parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.note()
