"""Progress bar + current-file label shown at the bottom of the window."""
from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget


class ProgressPanel(QWidget):
    """Indicates the overall batch progress and the file being processed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.current_label = QLabel("就绪")
        self.current_label.setProperty("muted", True)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setFormat("")

        layout.addWidget(self.current_label)
        layout.addWidget(self.bar)

    def set_current(self, text: str) -> None:
        self.current_label.setText(text)

    def set_progress(self, current: int, total: int) -> None:
        if total <= 0:
            self.bar.setValue(0)
            self.bar.setFormat("")
            return
        pct = int(current * 100 / total)
        self.bar.setValue(pct)
        self.bar.setFormat(f"{current}/{total}  ({pct}%)")

    def reset(self) -> None:
        self.bar.setValue(0)
        self.bar.setFormat("")
        self.current_label.setText("就绪")
