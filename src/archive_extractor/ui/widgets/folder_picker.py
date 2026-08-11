"""Folder selection row: a label, read-only line edit and browse button."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


class FolderPicker(QWidget):
    """A folder picker row that emits ``folder_changed(path_str)``."""

    folder_changed = pyqtSignal(str)

    def __init__(self, title: str, placeholder: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(title)
        self.label.setMinimumWidth(90)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setReadOnly(True)

        self.button = QPushButton("浏览…")
        self.button.clicked.connect(self._browse)

        layout.addWidget(self.label)
        layout.addWidget(self.edit, stretch=1)
        layout.addWidget(self.button)

    def _browse(self) -> None:
        start = self.edit.text() or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, self._title, start)
        if path:
            self.set_path(path)

    def set_path(self, path: str) -> None:
        self.edit.setText(path)
        self.folder_changed.emit(path)

    def path(self) -> str:
        return self.edit.text().strip()
