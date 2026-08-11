"""Logging configuration.

Sets up a console + rotating-file logger under ``./logs/``. The GUI also
subscribes a :class:`logging.Handler` that forwards records to the status
panel via a Qt signal (see :mod:`archive_extractor.ui.widgets.status_panel`).
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
_LOG_FORMAT = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure root logging once. Safe to call multiple times."""
    global _configured
    if _configured:
        # Allow level updates between runs.
        logging.getLogger().setLevel(getattr(logging, level.upper(), logging.INFO))
        return logging.getLogger()

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler.
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # Rotating file handler (5 x 1 MB).
    file_handler = RotatingFileHandler(
        _LOG_DIR / "app.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _configured = True
    return root


def add_handler(handler: logging.Handler) -> None:
    """Attach an extra handler (used by the GUI status panel)."""
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(handler)


def remove_handler(handler: logging.Handler) -> None:
    """Detach a previously-attached handler."""
    try:
        logging.getLogger().removeHandler(handler)
    except Exception:  # noqa: BLE001
        pass
