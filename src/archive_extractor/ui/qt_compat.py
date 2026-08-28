"""PyQt6 cross-version compatibility layer.

PyQt6 removed the "short form" enum aliases (e.g. ``QAbstractItemView.SelectRows``)
in newer versions / newer Python builds. This module patches the missing short
aliases back at import time so the code base can use either form, keeping it
compatible with both older and newer PyQt6 releases.

This module MUST be imported BEFORE any widget or dialog constructs Qt types
that use those enum values. The import order is ensured by importing this
module first in :func:`archive_extractor.app.main`.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def _alias(target_cls: type, attr: str, value: Any) -> bool:
    """Set ``target_cls.attr = value`` if missing. Returns True if a patch was made."""
    if hasattr(target_cls, attr):
        return False
    setattr(target_cls, attr, value)
    return True


def apply_compat() -> int:
    """Patch missing enum aliases. Returns the number of patches applied.

    The approach is robust: only set the alias when it is truly missing so
    we never override an existing value supplied by Qt itself.
    """
    from PyQt6.QtWidgets import (
        QAbstractItemView,
        QComboBox,
        QFileDialog,
        QHeaderView,
        QLineEdit,
        QProgressBar,
        QScrollBar,
        QSizePolicy,
        QTableView,
        QTableWidget,
        QTreeView,
        QTreeWidget,
        QWidget,
    )

    patches = 0

    # QAbstractItemView --------------------------------------------------
    sb = QAbstractItemView
    # SelectionBehavior
    for name, enum in (
        ("SelectItems", sb.SelectionBehavior.SelectItems),
        ("SelectRows", sb.SelectionBehavior.SelectRows),
        ("SelectColumns", sb.SelectionBehavior.SelectColumns),
    ):
        if _alias(sb, name, enum.value):
            patches += 1
    # EditTrigger
    for name, enum in (
        ("NoEditTriggers", sb.EditTrigger.NoEditTriggers),
        ("CurrentChanged", sb.EditTrigger.CurrentChanged),
        ("DoubleClicked", sb.EditTrigger.DoubleClicked),
        ("SelectedClicked", sb.EditTrigger.SelectedClicked),
        ("EditKeyPressed", sb.EditTrigger.EditKeyPressed),
        ("AnyKeyPressed", sb.EditTrigger.AnyKeyPressed),
        ("AllEditTriggers", sb.EditTrigger.AllEditTriggers),
    ):
        if _alias(sb, name, enum.value):
            patches += 1
    # SelectionMode
    for name, enum in (
        ("NoSelection", sb.SelectionMode.NoSelection),
        ("SingleSelection", sb.SelectionMode.SingleSelection),
        ("MultiSelection", sb.SelectionMode.MultiSelection),
        ("ExtendedSelection", sb.SelectionMode.ExtendedSelection),
        ("ContiguousSelection", sb.SelectionMode.ContiguousSelection),
    ):
        if _alias(sb, name, enum.value):
            patches += 1
    # ScrollHint
    for name, enum in (
        ("EnsureVisible", sb.ScrollHint.EnsureVisible),
        ("PositionAtTop", sb.ScrollHint.PositionAtTop),
        ("PositionAtBottom", sb.ScrollHint.PositionAtBottom),
        ("PositionAtCenter", sb.ScrollHint.PositionAtCenter),
    ):
        if _alias(sb, name, enum.value):
            patches += 1

    # QHeaderView ----------------------------------------------------------
    hv = QHeaderView
    for name, enum in (
        ("Interactive", hv.ResizeMode.Interactive),
        ("Stretch", hv.ResizeMode.Stretch),
        ("StretchSections", hv.ResizeMode.Stretch),
        ("ResizeToContents", hv.ResizeMode.ResizeToContents),
        ("Fixed", hv.ResizeMode.Fixed),
        ("Custom", hv.ResizeMode.Custom),
    ):
        if _alias(hv, name, enum.value):
            patches += 1

    # QFileDialog ---------------------------------------------------------
    fd = QFileDialog
    # FileMode
    for name, enum in (
        ("AnyFile", fd.FileMode.AnyFile),
        ("ExistingFile", fd.FileMode.ExistingFile),
        ("Directory", fd.FileMode.Directory),
        ("ExistingFiles", fd.FileMode.ExistingFiles),
    ):
        if _alias(fd, name, enum.value):
            patches += 1
    # AcceptMode
    for name, enum in (
        ("AcceptOpen", fd.AcceptMode.AcceptOpen),
        ("AcceptSave", fd.AcceptMode.AcceptSave),
    ):
        if _alias(fd, name, enum.value):
            patches += 1
    # Option — use getattr since some flags were removed in newer PyQt6
    for name in (
        "ShowDirsOnly",
        "DontResolveSymlinks",
        "DontConfirmOverwrite",
        "DontUseNativeDialog",
        "ReadOnly",
        "HideNameFilterDetails",
    ):
        enum = getattr(fd.Option, name, None)
        if enum is not None and _alias(fd, name, enum.value):
            patches += 1

    # QComboBox -----------------------------------------------------------
    for name, enum in (
        ("InsertAtTop", QComboBox.InsertPolicy.InsertAtTop),
        ("InsertAtBottom", QComboBox.InsertPolicy.InsertAtBottom),
        ("InsertAtCurrent", QComboBox.InsertPolicy.InsertAtCurrent),
        ("InsertBeforeCurrent", QComboBox.InsertPolicy.InsertBeforeCurrent),
        ("InsertAfterCurrent", QComboBox.InsertPolicy.InsertAfterCurrent),
        ("NoInsert", QComboBox.InsertPolicy.NoInsert),
        ("InsertAlphabetically", QComboBox.InsertPolicy.InsertAlphabetically),
    ):
        if _alias(QComboBox, name, enum.value):
            patches += 1

    # QLineEdit -----------------------------------------------------------
    for name, enum in (
        ("Normal", QLineEdit.EchoMode.Normal),
        ("NoEcho", QLineEdit.EchoMode.NoEcho),
        ("Password", QLineEdit.EchoMode.Password),
        ("PasswordEchoOnEdit", QLineEdit.EchoMode.PasswordEchoOnEdit),
    ):
        if _alias(QLineEdit, name, enum.value):
            patches += 1

    # QProgressBar / QScrollBar (Orientation) -----------------------------
    # NOTE: Orientation is a top-level Qt enum (Qt.Orientation), not nested
    # under QProgressBar / QScrollBar. These classes take a Qt.Orientation
    # argument but do NOT expose a nested Orientation type, so we alias
    # Qt.Orientation.Horizontal/Vertical onto them for convenience.
    from PyQt6.QtCore import Qt as _Qt

    for cls in (QProgressBar, QScrollBar):
        for name, enum in (
            ("Horizontal", _Qt.Orientation.Horizontal),
            ("Vertical", _Qt.Orientation.Vertical),
        ):
            if _alias(cls, name, enum.value):
                patches += 1

    # QSizePolicy ---------------------------------------------------------
    sp = QSizePolicy
    for name, enum in (
        ("Fixed", sp.Policy.Fixed),
        ("Minimum", sp.Policy.Minimum),
        ("Maximum", sp.Policy.Maximum),
        ("Preferred", sp.Policy.Preferred),
        ("Expanding", sp.Policy.Expanding),
        ("MinimumExpanding", sp.Policy.MinimumExpanding),
        ("Ignored", sp.Policy.Ignored),
    ):
        if _alias(sp, name, enum.value):
            patches += 1

    if patches:
        log.info("qt_compat: applied %d PyQt6 enum short-name patches", patches)
    return patches
