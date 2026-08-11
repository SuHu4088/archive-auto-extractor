"""Real-time status log panel.

A :class:`QListWidget` that appends colour-coded lines. Each line shows the
current operation: the archive path, the stage (scan / detect / extract /
verify / finalize) and the success / failure / skip status. Also acts as a
:class:`logging.Handler` so log records appear in the same panel.
"""
from __future__ import annotations

import logging
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...ui.theme import Colors


class StatusPanel(QWidget):
    """Colour-coded real-time status log."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.title = QLabel("状态日志")
        self.title.setProperty("title", True)

        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.setWordWrap(True)
        self.list.setUniformItemSizes(False)

        layout.addWidget(self.title)
        layout.addWidget(self.list, stretch=1)

    # -- public API --------------------------------------------------------
    def append(self, text: str, color: str = Colors.TEXT) -> None:
        item = QListWidgetItem(text)
        item.setForeground(QColor(color))
        ts = datetime.now().strftime("%H:%M:%S")
        item.setText(f"[{ts}] {text}")
        self.list.addItem(item)
        self.list.scrollToBottom()

    def append_status(self, path: str, status: str, message: str) -> None:
        color = {
            "ok": Colors.STATUS_OK,
            "skipped": Colors.STATUS_SKIPPED,
            "failed": Colors.STATUS_FAILED,
            "unsolved": Colors.STATUS_UNSOLVED,
            "trying": Colors.STATUS_TRYING,
        }.get(status, Colors.STATUS_INFO)
        name = path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        self.append(f"{status.upper():<8} {name} — {message}", color)

    def append_stage(self, path: str, stage: str, detail: str) -> None:
        name = path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        self.append(f"… {stage:<7} {name} — {detail}", Colors.STATUS_INFO)

    def clear_log(self) -> None:
        self.list.clear()


class StatusLogHandler(logging.Handler):
    """Bridges :mod:`logging` records to :class:`StatusPanel`."""

    def __init__(self, panel: StatusPanel):
        super().__init__()
        self._panel = panel

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = record.levelname
            color = {
                "ERROR": Colors.ERROR,
                "WARNING": Colors.WARN,
                "INFO": Colors.MUTED,
                "DEBUG": Colors.MUTED,
            }.get(level, Colors.MUTED)
            self._panel.append(f"({level}) {record.getMessage()}", color)
        except Exception:  # noqa: BLE001
            pass
