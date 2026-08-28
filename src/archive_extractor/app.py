"""Application entry point — creates the QApplication and shows the window."""
from __future__ import annotations

import logging
import sys

from PyQt6.QtWidgets import QApplication

from .ui.main_window import MainWindow
from .ui.qt_compat import apply_compat
from .ui.theme import QSS, apply_dark_palette
from .utils.logger import setup_logging

log = logging.getLogger(__name__)


def main() -> int:
    setup_logging("INFO")
    log.info("starting Archive Auto-Extractor")

    app = QApplication(sys.argv)
    app.setApplicationName("Archive Auto-Extractor")
    # PyQt6 cross-version enum aliases — must run before any widget creation.
    apply_compat()
    apply_dark_palette(app)
    app.setStyleSheet(QSS)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
