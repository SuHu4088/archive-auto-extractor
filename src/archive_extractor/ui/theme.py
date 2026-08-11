"""Dark theme for the application.

The QSS string here is the *single* place where colours live, so the whole
palette can be tuned in one spot. The palette is tuned for high contrast and
readability in dark mode (requirement 1).

Status colour constants are exposed for the status panel so per-row colours
match the theme.
"""
from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette


class Colors:
    """Central palette (also used for per-row status colours)."""
    BG = "#1e1f22"
    PANEL = "#2b2d31"
    PANEL_ALT = "#313338"
    BORDER = "#3f4147"
    TEXT = "#e6e6e6"
    SUBTEXT = "#b5b6b8"
    MUTED = "#80848e"
    ACCENT = "#7c9cff"
    ACCENT_STRONG = "#5b7cff"
    SUCCESS = "#46c46e"
    WARN = "#e0a832"
    ERROR = "#e5534b"

    # Per-status text colours for the status log.
    STATUS_OK = "#46c46e"
    STATUS_SKIPPED = "#e0a832"
    STATUS_FAILED = "#e5534b"
    STATUS_UNSOLVED = "#e0a832"
    STATUS_INFO = "#7c9cff"
    STATUS_TRYING = "#b5b6b8"


QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
    font-size: 13px;
    color: {Colors.TEXT};
}}
QMainWindow, QDialog {{
    background-color: {Colors.BG};
}}
QWidget {{
    background-color: transparent;
}}
QGroupBox {{
    background-color: {Colors.PANEL};
    border: 1px solid {Colors.BORDER};
    border-radius: 10px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {Colors.SUBTEXT};
}}
QPushButton {{
    background-color: {Colors.PANEL_ALT};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    padding: 7px 16px;
    color: {Colors.TEXT};
}}
QPushButton:hover {{
    background-color: {Colors.ACCENT_STRONG};
    border-color: {Colors.ACCENT};
    color: #ffffff;
}}
QPushButton:pressed {{
    background-color: {Colors.ACCENT};
}}
QPushButton:disabled {{
    background-color: {Colors.PANEL};
    color: {Colors.MUTED};
    border-color: {Colors.BORDER};
}}
QPushButton[primary="true"] {{
    background-color: {Colors.ACCENT_STRONG};
    border-color: {Colors.ACCENT};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{
    background-color: {Colors.ACCENT};
}}
QPushButton[danger="true"] {{
    background-color: #3a2326;
    border-color: {Colors.ERROR};
    color: {Colors.ERROR};
}}
QPushButton[danger="true"]:hover {{
    background-color: {Colors.ERROR};
    color: #ffffff;
}}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {Colors.PANEL_ALT};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {Colors.ACCENT_STRONG};
    selection-color: #ffffff;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {Colors.ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {Colors.PANEL_ALT};
    border: 1px solid {Colors.BORDER};
    selection-background-color: {Colors.ACCENT_STRONG};
}}
QListWidget, QTreeWidget, QTableWidget {{
    background-color: {Colors.PANEL};
    alternate-background-color: {Colors.PANEL_ALT};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    outline: 0;
}}
QListWidget::item, QTreeWidget::item {{
    padding: 4px 6px;
    border-radius: 4px;
}}
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{
    background-color: {Colors.ACCENT_STRONG};
    color: #ffffff;
}}
QHeaderView::section {{
    background-color: {Colors.PANEL_ALT};
    color: {Colors.SUBTEXT};
    border: none;
    border-right: 1px solid {Colors.BORDER};
    border-bottom: 1px solid {Colors.BORDER};
    padding: 6px 8px;
    font-weight: 600;
}}
QProgressBar {{
    background-color: {Colors.PANEL_ALT};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    text-align: center;
    color: {Colors.TEXT};
    height: 18px;
}}
QProgressBar::chunk {{
    background-color: {Colors.ACCENT};
    border-radius: 5px;
}}
QLabel {{
    color: {Colors.TEXT};
    background: transparent;
}}
QLabel[muted="true"] {{
    color: {Colors.MUTED};
}}
QLabel[title="true"] {{
    font-size: 15px;
    font-weight: 600;
}}
QMenuBar {{
    background-color: {Colors.BG};
    border-bottom: 1px solid {Colors.BORDER};
    color: {Colors.TEXT};
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 12px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {Colors.PANEL_ALT};
}}
QMenu {{
    background-color: {Colors.PANEL_ALT};
    border: 1px solid {Colors.BORDER};
}}
QMenu::item {{
    padding: 6px 24px 6px 18px;
}}
QMenu::item:selected {{
    background-color: {Colors.ACCENT_STRONG};
    color: #ffffff;
}}
QScrollBar:vertical {{
    background: {Colors.PANEL};
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {Colors.BORDER};
    min-height: 30px;
    border-radius: 5px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {Colors.MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {Colors.PANEL};
    height: 12px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {Colors.BORDER};
    min-width: 30px;
    border-radius: 5px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {Colors.MUTED};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QCheckBox, QRadioButton {{
    color: {Colors.TEXT};
    spacing: 8px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {Colors.BORDER};
    border-radius: 3px;
    background: {Colors.PANEL_ALT};
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {Colors.ACCENT_STRONG};
    border-color: {Colors.ACCENT};
}}
QToolTip {{
    background-color: {Colors.PANEL_ALT};
    color: {Colors.TEXT};
    border: 1px solid {Colors.BORDER};
    padding: 4px 6px;
}}
QStatusBar {{
    background-color: {Colors.BG};
    border-top: 1px solid {Colors.BORDER};
    color: {Colors.SUBTEXT};
}}
"""


def apply_dark_palette(app) -> None:
    """Apply the QPalette so native widgets (e.g. dialogs) match the theme."""
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(Colors.BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(Colors.TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(Colors.PANEL_ALT))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(Colors.PANEL))
    pal.setColor(QPalette.ColorRole.Text, QColor(Colors.TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor(Colors.PANEL_ALT))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(Colors.TEXT))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(Colors.ACCENT_STRONG))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(Colors.PANEL_ALT))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(Colors.TEXT))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(Colors.MUTED))
    app.setPalette(pal)
