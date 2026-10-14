"""Native editor for the local Romanian-English search dictionary."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .bilingual_dictionary import (
    BilingualDictionary,
    BilingualDictionaryStore,
    new_entry,
)


def _lines(values: tuple[str, ...]) -> str:
    return "\n".join(values)


def _terms(value: str) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for line in value.replace(";", "\n").splitlines():
        term = " ".join(line.split())
        identity = term.casefold()
        if term and identity not in seen:
            seen.add(identity)
            result.append(term)
    return tuple(result)


class BilingualDictionaryEditorDialog(QDialog):
    def __init__(
        self,
        dictionary: BilingualDictionary,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = dictionary
        self._entries = list(dictionary.entries)
        self._current_index = -1
        self.setWindowTitle("Romanian-English Search Dictionary")
        self.resize(780, 620)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Terms in the same concept are treated as controlled equivalents. "
            "Enter one expression per line. Bilingual Search remains local and deterministic."
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        layout.addWidget(hint)

        picker_row = QHBoxLayout()
        self.entry_picker = QComboBox()
        self.entry_picker.currentIndexChanged.connect(self._switch_entry)
        picker_row.addWidget(self.entry_picker, 1)
        add_button = QPushButton("New Concept")
        add_button.clicked.connect(self._add_entry)
        picker_row.addWidget(add_button)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._delete_entry)
        picker_row.addWidget(self.delete_button)
        layout.addLayout(picker_row)

        form = QFormLayout()
        self.name = QLineEdit()
        form.addRow("Concept name", self.name)
        self.terms_ro = QTextEdit()
        self.terms_ro.setMaximumHeight(190)
        form.addRow("Romanian terms", self.terms_ro)
        self.terms_en = QTextEdit()
        self.terms_en.setMaximumHeight(190)
        form.addRow("English terms", self.terms_en)
        layout.addLayout(form, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save Dictionary")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_picker(0)

    def _refresh_picker(self, selected: int) -> None:
        self.entry_picker.blockSignals(True)
        self.entry_picker.clear()
        self.entry_picker.addItems(entry.name for entry in self._entries)
        self.entry_picker.setCurrentIndex(max(0, min(selected, len(self._entries) - 1)))
        self.entry_picker.blockSignals(False)
        self._current_index = self.entry_picker.currentIndex()
        self._load_current()
        self.delete_button.setEnabled(len(self._entries) > 1)

    def _capture_current(self) -> None:
        if not 0 <= self._current_index < len(self._entries):
            return
        original = self._entries[self._current_index]
        self._entries[self._current_index] = replace(
            original,
            name=self.name.text().strip(),
            terms_ro=_terms(self.terms_ro.toPlainText()),
            terms_en=_terms(self.terms_en.toPlainText()),
        )

    def _load_current(self) -> None:
        entry = self._entries[self._current_index]
        self.name.setText(entry.name)
        self.terms_ro.setPlainText(_lines(entry.terms_ro))
        self.terms_en.setPlainText(_lines(entry.terms_en))

    def _switch_entry(self, index: int) -> None:
        if index < 0 or index == self._current_index:
            return
        self._capture_current()
        previous = self._current_index
        self._current_index = index
        self._load_current()
        if 0 <= previous < self.entry_picker.count():
            self.entry_picker.setItemText(previous, self._entries[previous].name)

    def _add_entry(self) -> None:
        self._capture_current()
        self._entries.append(new_entry())
        self._refresh_picker(len(self._entries) - 1)

    def _delete_entry(self) -> None:
        if len(self._entries) <= 1:
            return
        entry = self._entries[self._current_index]
        answer = QMessageBox.question(
            self,
            "Delete concept",
            f'Delete the bilingual concept "{entry.name}"?',
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        del self._entries[self._current_index]
        self._refresh_picker(min(self._current_index, len(self._entries) - 1))

    def dictionary(self) -> BilingualDictionary:
        self._capture_current()
        return replace(self._source, entries=tuple(self._entries))

    def _accept_if_valid(self) -> None:
        dictionary = self.dictionary()
        try:
            BilingualDictionaryStore.validate(dictionary)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid dictionary", str(error))
            return
        self.accept()
