"""Native editor for bilingual category profiles."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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

from .categories import CategoryDefinition, CategoryProfile, CategoryProfileStore, new_category


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


class CategoryEditorDialog(QDialog):
    def __init__(self, profile: CategoryProfile, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source_profile = profile
        self._categories = list(profile.categories)
        self._current_index = -1
        self.setWindowTitle("Search Category Editor")
        self.resize(760, 700)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Subject terms produce matches. Context terms increase relevance when they appear "
            "in the same paragraph or nearby. Enter one term per line."
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        layout.addWidget(hint)

        picker_row = QHBoxLayout()
        self.category_picker = QComboBox()
        self.category_picker.currentIndexChanged.connect(self._switch_category)
        picker_row.addWidget(self.category_picker, 1)
        add_button = QPushButton("New Category")
        add_button.clicked.connect(self._add_category)
        picker_row.addWidget(add_button)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._delete_category)
        picker_row.addWidget(self.delete_button)
        layout.addLayout(picker_row)

        form = QFormLayout()
        self.enabled = QCheckBox("Category enabled")
        form.addRow("Status", self.enabled)
        self.group = QLineEdit()
        form.addRow("Group", self.group)
        self.name_ro = QLineEdit()
        form.addRow("Romanian name", self.name_ro)
        self.name_en = QLineEdit()
        form.addRow("English name", self.name_en)
        self.description = QLineEdit()
        form.addRow("Description", self.description)
        self.terms_ro = QTextEdit()
        self.terms_ro.setMaximumHeight(120)
        form.addRow("Romanian terms", self.terms_ro)
        self.terms_en = QTextEdit()
        self.terms_en.setMaximumHeight(120)
        form.addRow("English terms", self.terms_en)
        self.context_ro = QTextEdit()
        self.context_ro.setMaximumHeight(90)
        form.addRow("Romanian context", self.context_ro)
        self.context_en = QTextEdit()
        self.context_en.setMaximumHeight(90)
        form.addRow("English context", self.context_en)
        layout.addLayout(form, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save Profile")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_picker(0)

    def _refresh_picker(self, selected: int) -> None:
        self.category_picker.blockSignals(True)
        self.category_picker.clear()
        self.category_picker.addItems(category.display_name for category in self._categories)
        self.category_picker.setCurrentIndex(max(0, min(selected, len(self._categories) - 1)))
        self.category_picker.blockSignals(False)
        self._current_index = self.category_picker.currentIndex()
        self._load_current()
        self.delete_button.setEnabled(len(self._categories) > 1)

    def _capture_current(self) -> None:
        if self._current_index < 0 or self._current_index >= len(self._categories):
            return
        original = self._categories[self._current_index]
        self._categories[self._current_index] = replace(
            original,
            enabled=self.enabled.isChecked(),
            group=self.group.text().strip(),
            name_ro=self.name_ro.text().strip(),
            name_en=self.name_en.text().strip(),
            description=self.description.text().strip(),
            terms_ro=_terms(self.terms_ro.toPlainText()),
            terms_en=_terms(self.terms_en.toPlainText()),
            context_ro=_terms(self.context_ro.toPlainText()),
            context_en=_terms(self.context_en.toPlainText()),
        )

    def _load_current(self) -> None:
        category = self._categories[self._current_index]
        self.enabled.setChecked(category.enabled)
        self.group.setText(category.group)
        self.name_ro.setText(category.name_ro)
        self.name_en.setText(category.name_en)
        self.description.setText(category.description)
        self.terms_ro.setPlainText(_lines(category.terms_ro))
        self.terms_en.setPlainText(_lines(category.terms_en))
        self.context_ro.setPlainText(_lines(category.context_ro))
        self.context_en.setPlainText(_lines(category.context_en))

    def _switch_category(self, index: int) -> None:
        if index < 0 or index == self._current_index:
            return
        self._capture_current()
        previous = self._current_index
        self._current_index = index
        self._load_current()
        if 0 <= previous < self.category_picker.count():
            self.category_picker.setItemText(previous, self._categories[previous].display_name)

    def _add_category(self) -> None:
        self._capture_current()
        self._categories.append(new_category())
        self._refresh_picker(len(self._categories) - 1)

    def _delete_category(self) -> None:
        if len(self._categories) <= 1:
            return
        category = self._categories[self._current_index]
        answer = QMessageBox.question(
            self,
            "Delete category",
            f'Delete the category "{category.display_name}"?',
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        del self._categories[self._current_index]
        self._refresh_picker(min(self._current_index, len(self._categories) - 1))

    def profile(self) -> CategoryProfile:
        self._capture_current()
        return replace(self._source_profile, categories=tuple(self._categories))

    def _accept_if_valid(self) -> None:
        profile = self.profile()
        try:
            CategoryProfileStore.validate(profile)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid profile", str(error))
            return
        self.accept()
