"""Password vault management dialog.

Lists vault entries in a table (label, masked value, enabled, use_count,
last_used). Supports add / edit / toggle-enable / delete (two-step confirm).
Passwords are masked by default with a per-row reveal toggle. The vault Git
commit log is shown in a collapsible area so the user can audit changes.

All mutations go through :class:`PasswordVault`, which commits each operation
to the vault Git repo with a descriptive message.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from ...core.password_manager import PasswordVault
from ...ui.theme import Colors


class VaultDialog(QDialog):
    """Modal vault CRUD dialog."""

    def __init__(self, vault: PasswordVault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.setWindowTitle("密码库管理")
        self.resize(720, 560)
        self._reveal = False
        self._pending_delete_id: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("密码库")
        title.setProperty("title", True)
        root.addWidget(title)

        # Add row ----------------------------------------------------------
        add_row = QHBoxLayout()
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("标签（可选）")
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("密码")
        self.value_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.add_btn = QPushButton("添加")
        self.add_btn.setProperty("primary", True)
        self.add_btn.clicked.connect(self._add)
        add_row.addWidget(QLabel("标签:"))
        add_row.addWidget(self.label_edit)
        add_row.addWidget(QLabel("密码:"))
        add_row.addWidget(self.value_edit, 1)
        add_row.addWidget(self.add_btn)
        root.addLayout(add_row)

        # Table ------------------------------------------------------------
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["标签", "密码", "启用", "使用次数", "上次使用", "操作"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for c in range(2, 6):
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        root.addWidget(self.table, stretch=1)

        # Action row -------------------------------------------------------
        actions = QHBoxLayout()
        self.reveal_check = QCheckBox("显示密码明文")
        self.reveal_check.toggled.connect(self._toggle_reveal)
        actions.addWidget(self.reveal_check)
        actions.addStretch(1)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._refresh)
        actions.addWidget(self.refresh_btn)
        root.addLayout(actions)

        # Commit log ------------------------------------------------------
        self.log_label = QLabel("最近 Git 提交记录")
        self.log_label.setProperty("muted", True)
        root.addWidget(self.log_label)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(120)
        root.addWidget(self.log_view)

        self._refresh()

    # -- table population --------------------------------------------------
    def _refresh(self) -> None:
        entries = self.vault.list_entries(enabled_only=False)
        self.table.setRowCount(len(entries))
        for r, e in enumerate(entries):
            self.table.setItem(r, 0, QTableWidgetItem(e.label))
            self.table.setItem(r, 1, QTableWidgetItem(self._mask(e.value)))
            enabled_item = QTableWidgetItem()
            enabled_item.setFlags(enabled_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            enabled_item.setCheckState(
                Qt.CheckState.Checked if e.enabled else Qt.CheckState.Unchecked
            )
            enabled_item.setData(Qt.ItemDataRole.UserRole, e.id)
            self.table.setItem(r, 2, enabled_item)
            self.table.setItem(r, 3, QTableWidgetItem(str(e.use_count)))
            self.table.setItem(r, 4, QTableWidgetItem(e.last_used or "—"))

            ops = QWidget()
            lay = QHBoxLayout(ops)
            lay.setContentsMargins(2, 2, 2, 2)
            edit_btn = QPushButton("编辑")
            edit_btn.clicked.connect(lambda _, _id=e.id: self._edit(_id))
            del_btn = QPushButton("删除")
            del_btn.setProperty("danger", True)
            del_btn.clicked.connect(lambda _, _id=e.id: self._delete(_id))
            lay.addWidget(edit_btn)
            lay.addWidget(del_btn)
            self.table.setCellWidget(r, 5, ops)

        # Refresh commit log.
        lines = self.vault.commit_log(limit=15)
        self.log_view.setText("\n".join(f"• {m}" for m in lines) or "（无提交记录）")

    def _mask(self, value: str) -> str:
        if self._reveal:
            return value
        return "•" * min(len(value), 12) if value else ""

    def _toggle_reveal(self, on: bool) -> None:
        self._reveal = on
        # Re-render password column only.
        entries = self.vault.list_entries(enabled_only=False)
        for r, e in enumerate(entries):
            item = self.table.item(r, 1)
            if item is not None:
                item.setText(self._mask(e.value))

    # -- mutations ---------------------------------------------------------
    def _add(self) -> None:
        value = self.value_edit.text()
        if not value:
            QMessageBox.warning(self, "添加", "请输入密码。")
            return
        label = self.label_edit.text().strip()
        self.vault.add_password(value, label=label)
        self.label_edit.clear()
        self.value_edit.clear()
        self._refresh()

    def _edit(self, entry_id: str) -> None:
        entries = self.vault.list_entries(enabled_only=False)
        entry = next((e for e in entries if e.id == entry_id), None)
        if entry is None:
            return
        from PyQt6.QtWidgets import QInputDialog
        new_label, ok = QInputDialog.getText(
            self, "编辑标签", "新标签:", text=entry.label
        )
        if not ok:
            return
        self.vault.update_password(entry_id, label=new_label.strip())
        self._refresh()

    def _delete(self, entry_id: str) -> None:
        """Two-step delete: prepare_delete → confirm → delete_password."""
        token = self.vault.prepare_delete(entry_id)
        if token is None:
            return
        entries = self.vault.list_entries(enabled_only=False)
        entry = next((e for e in entries if e.id == entry_id), None)
        label = entry.label if entry else ""
        btn = QMessageBox.warning(
            self,
            "确认删除",
            f"确定要删除密码 \"{label}\" 吗？\n此操作将通过 Git 提交并可在密码库历史中追溯。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if btn != QMessageBox.StandardButton.Yes:
            return
        if self.vault.delete_password(entry_id, token):
            self._refresh()
        else:
            QMessageBox.warning(self, "删除", "删除失败（令牌已失效）。")

    # -- enable toggle via checkbox ---------------------------------------
    def closeEvent(self, event):
        # Persist any checkbox toggles the user made.
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 2)
            if item is None:
                continue
            entry_id = item.data(Qt.ItemDataRole.UserRole)
            desired = item.checkState() == Qt.CheckState.Checked
            # Best-effort toggle; vault commits if state changed.
            entries = self.vault.list_entries(enabled_only=False)
            current = next((e for e in entries if e.id == entry_id), None)
            if current and current.enabled != desired:
                self.vault.set_enabled(entry_id, desired)
        super().closeEvent(event)
