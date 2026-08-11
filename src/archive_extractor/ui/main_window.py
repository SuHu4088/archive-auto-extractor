"""Main application window.

Lays out the folder pickers, start/stop controls, status log and progress
bar, then wires :class:`ExtractionWorker` signals to the UI. Handles the
delete-confirmation prompt (shown on the GUI thread when the worker emits
``confirmation_requested``).

Window geometry is persisted to ``config.local.json`` (git-ignored) so the
tracked ``config.json`` stays generic.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QAction, QCloseEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..config import Settings, load, save
from ..core.password_manager import PasswordVault
from ..core.worker import ExtractionWorker
from ..utils.logger import setup_logging
from .theme import QSS, apply_dark_palette
from .widgets.folder_picker import FolderPicker
from .widgets.progress_panel import ProgressPanel
from .widgets.settings_dialog import SettingsDialog
from .widgets.status_panel import StatusPanel
from .widgets.vault_dialog import VaultDialog

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load()
        setup_logging(self.settings.log_level)

        self.setWindowTitle("密码识别并自动解压缩 · Archive Auto-Extractor")
        self.resize(900, 640)
        self._restore_geometry()

        self.vault: PasswordVault | None = None
        if self.settings.password_module_enabled:
            self._open_vault()
        self.worker: ExtractionWorker | None = None

        self._build_ui()
        self._build_menu()
        self._build_statusbar()

    # -- UI construction ----------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Source folder picker.
        self.source_picker = FolderPicker("源文件夹", placeholder="选择待扫描的文件夹")
        if Path.cwd().exists():
            pass
        self.source_picker.folder_changed.connect(self._on_source_changed)
        root.addWidget(self.source_picker)

        # Output folder picker (optional override).
        self.output_picker = FolderPicker(
            "解压输出目录", placeholder="留空 = 使用设置中的默认"
        )
        if self.settings.extraction_output_root:
            self.output_picker.set_path(self.settings.extraction_output_root)
        self.output_picker.folder_changed.connect(self._on_output_changed)
        root.addWidget(self.output_picker)

        # Action row.
        actions = QHBoxLayout()
        self.start_btn = QPushButton("▶ 开始")
        self.start_btn.setProperty("primary", True)
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("■ 停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.clicked.connect(self._clear_log)
        actions.addWidget(self.start_btn)
        actions.addWidget(self.stop_btn)
        actions.addStretch(1)
        actions.addWidget(self.clear_btn)
        root.addLayout(actions)

        # Status + progress.
        self.status_panel = StatusPanel()
        root.addWidget(self.status_panel, stretch=1)

        self.progress_panel = ProgressPanel()
        root.addWidget(self.progress_panel)

        self.setCentralWidget(central)

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        m_file = menubar.addMenu("文件(&F)")
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_tools = menubar.addMenu("工具(&T)")
        act_settings = QAction("设置…", self)
        act_settings.triggered.connect(self._open_settings)
        m_tools.addAction(act_settings)
        act_vault = QAction("密码库…", self)
        act_vault.triggered.connect(self._open_vault_dialog)
        m_tools.addAction(act_vault)

        m_help = menubar.addMenu("帮助(&H)")
        act_about = QAction("关于", self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

    def _build_statusbar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        self.module_label = QLabel("密码模块：未启用")
        bar.addPermanentWidget(self.module_label)
        self._refresh_module_label()

    # -- slots --------------------------------------------------------------
    def _on_source_changed(self, path: str) -> None:
        self.status_panel.append(f"已选择源文件夹：{path}")

    def _on_output_changed(self, path: str) -> None:
        self.settings.extraction_output_root = path
        save(self.settings, local=True)
        self.status_panel.append(f"解压输出目录设为：{path}")

    def _start(self) -> None:
        source = self.source_picker.path()
        if not source or not Path(source).exists():
            QMessageBox.warning(self, "开始", "请先选择有效的源文件夹。")
            return
        # Sync output picker into settings.
        out = self.output_picker.path()
        if out:
            self.settings.extraction_output_root = out
            save(self.settings, local=True)

        # Open the vault lazily when the module is enabled but not yet open.
        if self.settings.password_module_enabled and self.vault is None:
            self._open_vault()

        self.worker = ExtractionWorker(
            Path(source), self.settings, self.vault, parent=self
        )
        self._wire_worker(self.worker)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_panel.append("开始处理…", "#7c9cff")
        self.progress_panel.reset()
        self.worker.start()

    def _stop(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.status_panel.append("正在停止（将在当前文件处理完后中止）…", "#e0a832")

    def _clear_log(self) -> None:
        self.status_panel.clear_log()

    # -- worker wiring -----------------------------------------------------
    def _wire_worker(self, w: ExtractionWorker) -> None:
        w.scan_started.connect(lambda: self.status_panel.append("扫描文件夹…", "#7c9cff"))
        w.archive_discovered.connect(self._on_discovered)
        w.stage_changed.connect(self._on_stage)
        w.progress.connect(self._on_progress)
        w.password_try.connect(self._on_password_try)
        w.archive_result.connect(self._on_result)
        w.vault_committed.connect(self._on_vault_committed)
        w.confirmation_requested.connect(self._on_confirmation)
        w.finished_all.connect(self._on_finished)
        w.fatal_error.connect(self._on_fatal)

    def _on_discovered(self, path: str) -> None:
        self.status_panel.append(f"发现压缩包：{Path(path).name}")
        self.progress_panel.set_current(f"扫描中… {Path(path).name}")

    def _on_stage(self, path: str, stage: str, detail: str) -> None:
        self.status_panel.append_stage(path, stage, detail)
        self.progress_panel.set_current(f"{stage} · {Path(path).name}")

    def _on_progress(self, current: int, total: int) -> None:
        self.progress_panel.set_progress(current, total)

    def _on_password_try(self, path: str, idx: int, total: int) -> None:
        self.status_panel.append_status(path, "trying", f"尝试密码 {idx}/{total}")

    def _on_result(self, path: str, status: str, message: str) -> None:
        self.status_panel.append_status(path, status, message)

    def _on_vault_committed(self, message: str) -> None:
        self.status_panel.append(f"密码库提交：{message}", "#b5b6b8")

    def _on_confirmation(self, path: str) -> None:
        name = Path(path).name
        btn = QMessageBox.question(
            self,
            "确认删除",
            f"压缩包 \"{name}\" 已解压并通过 CRC 校验。\n是否删除原始压缩包？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        confirmed = btn == QMessageBox.StandardButton.Yes
        if self.worker:
            self.worker.set_delete_decision(confirmed)

    def _on_finished(self, ok: int, failed: int, skipped: int, unsolved: int) -> None:
        self.progress_panel.set_current(
            f"完成：成功 {ok} · 失败 {failed} · 跳过 {skipped} · 未解决 {unsolved}"
        )
        self.status_panel.append(
            f"批次完成：成功 {ok} · 失败 {failed} · 跳过 {skipped} · 未解决 {unsolved}",
            "#46c46e" if failed == 0 else "#e0a832",
        )
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_fatal(self, message: str) -> None:
        self.status_panel.append(f"致命错误：{message}", "#e5534b")
        QMessageBox.critical(self, "致命错误", message)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    # -- dialogs ------------------------------------------------------------
    def _open_settings(self) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "设置", "请先停止当前任务再修改设置。")
            return
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self.settings = dlg.settings
            if self.settings.password_module_enabled and self.vault is None:
                self._open_vault()
            elif not self.settings.password_module_enabled and self.vault is not None:
                self.vault.close()
                self.vault = None
            self._refresh_module_label()
            self.status_panel.append("设置已保存。")

    def _open_vault_dialog(self) -> None:
        if self.vault is None:
            self._open_vault()
        if self.vault is None:
            return
        dlg = VaultDialog(self.vault, self)
        dlg.exec()

    def _open_vault(self) -> None:
        try:
            self.vault = PasswordVault(self.settings.vault_dir)
            self.vault.open()
            self.status_panel.append(
                f"已打开密码库：{self.settings.vault_dir}", "#7c9cff"
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("vault open failed")
            QMessageBox.warning(self, "密码库", f"打开密码库失败：{exc}")
            self.vault = None

    def _refresh_module_label(self) -> None:
        state = "已启用" if self.settings.password_module_enabled else "未启用"
        self.module_label.setText(f"密码模块：{state}")

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "关于",
            "<b>密码识别并自动解压缩</b><br>"
            "递归扫描文件夹，自动解压 ZIP/RAR/7Z 压缩包，"
            "CRC 校验完整性，支持密码库自动尝试解密。<br><br>"
            "深色模式 · PyQt6 · 7-Zip",
        )

    # -- persistence -------------------------------------------------------
    def _restore_geometry(self) -> None:
        geo = self.settings.ui.window_geometry
        if geo:
            try:
                self.restoreGeometry(QByteArray(bytes.fromhex(geo)))
            except Exception:  # noqa: BLE001
                pass
        else:
            # Center on screen (user preference).
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                avail = screen.availableGeometry()
                self.move(
                    avail.center().x() - self.width() // 2,
                    avail.center().y() - self.height() // 2,
                )

    def _save_geometry(self) -> None:
        self.settings.ui.window_geometry = self.saveGeometry().toHex().data().decode()
        save(self.settings, local=True)

    # -- close -------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker and self.worker.isRunning():
            btn = QMessageBox.question(
                self,
                "退出",
                "任务正在运行，确定退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if btn != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.worker.requestInterruption()
            self.worker.wait(5000)
        self._save_geometry()
        if self.vault is not None:
            try:
                self.vault.close()
            except Exception:  # noqa: BLE001
                pass
        event.accept()
