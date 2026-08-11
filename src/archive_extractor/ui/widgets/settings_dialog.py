"""Settings dialog: edit the persistent :class:`Settings` fields.

Lets the user configure the 7z path, extraction output root, delete
behaviour, password module enable, unsolved subfolder name, etc. Changes are
applied to the in-memory Settings and saved to disk on accept.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ...config import Settings, save, validate
from .folder_picker import FolderPicker


class SettingsDialog(QDialog):
    """Modal settings editor. On accept, :attr:`settings` holds the new values."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(560)
        self._settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("设置")
        title.setProperty("title", True)
        root.addWidget(title)

        # 7z path ----------------------------------------------------------
        self.seven_zip_picker = FolderPicker("7z.exe 路径", placeholder="选择 7z.exe")
        self.seven_zip_picker.set_path(settings.seven_zip_path)
        root.addWidget(self.seven_zip_picker)

        # Output root ------------------------------------------------------
        self.output_picker = FolderPicker(
            "解压输出目录", placeholder="留空 = 与压缩包同目录"
        )
        if settings.extraction_output_root:
            self.output_picker.set_path(settings.extraction_output_root)
        root.addWidget(self.output_picker)

        # Form -------------------------------------------------------------
        form = QFormLayout()
        form.setSpacing(8)

        self.same_subfolder = QCheckBox("为每个压缩包创建同名子文件夹")
        self.same_subfolder.setChecked(settings.create_same_name_subfolder)
        form.addRow(self.same_subfolder)

        self.delete_after = QCheckBox("CRC 校验通过后删除原压缩包")
        self.delete_after.setChecked(settings.delete_original_after_success)
        self.delete_after.toggled.connect(self._on_delete_toggled)
        form.addRow(self.delete_after)

        self.confirm_delete = QCheckBox("删除前弹出确认对话框")
        self.confirm_delete.setChecked(settings.confirm_before_delete)
        form.addRow(self.confirm_delete)

        self.password_enabled = QCheckBox("启用密码库（对受密码保护的压缩包尝试解密）")
        self.password_enabled.setChecked(settings.password_module_enabled)
        form.addRow(self.password_enabled)

        self.unsolved_name = QLineEdit(settings.unsolved_subfolder_name)
        form.addRow("未解决子文件夹名", self.unsolved_name)

        self.unsolved_location = QComboBox()
        self.unsolved_location.addItem("解压输出目录下", "output_root")
        self.unsolved_location.addItem("压缩包所在目录", "beside_archive")
        idx = 0 if settings.unsolved_location == "output_root" else 1
        self.unsolved_location.setCurrentIndex(idx)
        form.addRow("未解决压缩包移动位置", self.unsolved_location)

        self.ext_edit = QLineEdit(", ".join(settings.scan_extensions))
        self.ext_edit.setToolTip("逗号分隔，如 .zip, .rar, .7z")
        form.addRow("扫描扩展名", self.ext_edit)

        root.addLayout(form)

        # Validation feedback ---------------------------------------------
        self.validation = QLabel("")
        self.validation.setProperty("muted", True)
        self.validation.setWordWrap(True)
        root.addWidget(self.validation)

        # Buttons ----------------------------------------------------------
        btns = QHBoxLayout()
        self.btn_save = QPushButton("保存并关闭")
        self.btn_save.setProperty("primary", True)
        self.btn_save.clicked.connect(self._save)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_save)
        root.addLayout(btns)

        self._on_delete_toggled()

    def _on_delete_toggled(self) -> None:
        self.confirm_delete.setEnabled(self.delete_after.isChecked())

    def _collect(self) -> Settings:
        s = self._settings
        s.seven_zip_path = self.seven_zip_picker.path() or s.seven_zip_path
        s.extraction_output_root = self.output_picker.path()
        s.create_same_name_subfolder = self.same_subfolder.isChecked()
        s.delete_original_after_success = self.delete_after.isChecked()
        s.confirm_before_delete = self.confirm_delete.isChecked()
        s.password_module_enabled = self.password_enabled.isChecked()
        s.unsolved_subfolder_name = (
            self.unsolved_name.text().strip() or "password_protected_unsolved"
        )
        s.unsolved_location = self.unsolved_location.currentData()
        exts = [e.strip() for e in self.ext_edit.text().split(",") if e.strip()]
        if exts:
            s.scan_extensions = exts
        return s

    def _save(self) -> None:
        s = self._collect()
        problems = validate(s)
        if problems:
            self.validation.setText("⚠ " + "；".join(problems))
            return
        save(s)
        self._settings = s
        self.accept()

    @property
    def settings(self) -> Settings:
        return self._settings
