"""Background extraction worker (QThread + pyqtSignal).

Owns the whole batch: scans the source folder, runs each archive through
:class:`ArchivePipeline`, and emits Qt signals for the GUI to render status,
progress and results. The GUI never blocks; cancellation is requested between
archives via :meth:`requestInterruption`.

The delete-confirmation dialog is shown on the GUI thread using
``QMetaObject.invokeMethod`` with a blocking queued connection so the worker
pauses until the user answers — without touching widgets directly from the
worker thread.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from ..config import Settings
from ..constants import STATUS_FAILED, STATUS_OK, STATUS_SKIPPED, STATUS_UNSOLVED
from ..models.result import ArchiveResult
from . import scanner
from .password_manager import PasswordVault
from .pipeline import ArchivePipeline, PipelineStats

log = logging.getLogger(__name__)


class ExtractionWorker(QThread):
    """Drives a full scan + extract + verify batch in the background."""

    # Signals ----------------------------------------------------------------
    scan_started = pyqtSignal()
    archive_discovered = pyqtSignal(str)                # archive path
    stage_changed = pyqtSignal(str, str, str)           # path, stage, detail
    progress = pyqtSignal(int, int)                     # current index, total
    password_try = pyqtSignal(str, int, int)           # path, attempt idx, total
    archive_result = pyqtSignal(str, str, str)          # path, status, message
    vault_committed = pyqtSignal(str)                   # commit message
    confirmation_requested = pyqtSignal(str)            # archive path (blocking)
    finished_all = pyqtSignal(int, int, int, int)        # ok, failed, skipped, unsolved
    fatal_error = pyqtSignal(str)

    def __init__(
        self,
        source_root: Path,
        settings: Settings,
        vault: PasswordVault | None,
        parent=None,
    ):
        super().__init__(parent)
        self.source_root = Path(source_root)
        self.settings = settings
        self.vault = vault
        self._confirm_delete = True   # mutated by the GUI via set_delete_decision
        self._confirm_event_set = False

    # -- public -------------------------------------------------------------
    def set_delete_decision(self, confirmed: bool) -> None:
        """Called (from the GUI thread) to answer a pending delete prompt."""
        self._confirm_delete = confirmed
        self._confirm_event_set = True

    # -- run ----------------------------------------------------------------
    def run(self) -> None:  # noqa: D401 — QThread entry point
        try:
            self._run_batch()
        except Exception as exc:  # noqa: BLE001
            log.exception("worker fatal error")
            self.fatal_error.emit(str(exc))

    def _run_batch(self) -> None:
        settings = self.settings
        if self.vault is not None:
            self.vault.open()
            self.vault_committed.emit("Vault session opened")

        self.scan_started.emit()
        out_root = settings.output_root
        archives = list(
            scanner.scan(
                self.source_root,
                output_root=out_root,
                extensions=tuple(settings.scan_extensions),
            )
        )
        total = len(archives)
        log.info("scan found %d archive(s) under %s", total, self.source_root)
        for p in archives:
            self.archive_discovered.emit(str(p))

        stats = PipelineStats()
        pipeline = ArchivePipeline(settings, self.vault)
        callbacks = _WorkerCallbacks(self)

        for idx, archive in enumerate(archives, start=1):
            if self.isInterruptionRequested():
                log.info("interrupted by user at %d/%d", idx, total)
                break
            self.progress.emit(idx, total)
            result = pipeline.process(archive, callbacks)
            self._tally(stats, result)

        if self.vault is not None:
            self.vault.close(
                stats={"tried": stats.ok + stats.unsolved, "ok": stats.ok}
            )
            self.vault_committed.emit("Vault session closed")

        self.finished_all.emit(stats.ok, stats.failed, stats.skipped, stats.unsolved)

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _tally(stats: PipelineStats, result: ArchiveResult) -> None:
        if result.status == STATUS_OK:
            stats.ok += 1
        elif result.status == STATUS_FAILED:
            stats.failed += 1
        elif result.status == STATUS_SKIPPED:
            stats.skipped += 1
        elif result.status == STATUS_UNSOLVED:
            stats.unsolved += 1


class _WorkerCallbacks:
    """Adapts the pipeline callback protocol to worker signals.

    The delete-confirmation path uses a blocking wait loop so the worker
    pauses until :meth:`ExtractionWorker.set_delete_decision` is called from
    the GUI thread (which also emits :attr:`confirmation_requested` first).
    """

    def __init__(self, worker: ExtractionWorker):
        self.worker = worker

    def on_stage(self, archive: Path, stage: str, detail: str) -> None:
        self.worker.stage_changed.emit(str(archive), stage, detail)

    def on_password_try(self, archive: Path, idx: int, total: int) -> None:
        self.worker.password_try.emit(str(archive), idx, total)
        self.worker.archive_result.emit(
            str(archive), "trying", f"尝试密码 {idx}/{total}",
        )

    def on_result(self, result: ArchiveResult) -> None:
        self.worker.archive_result.emit(
            str(result.path), result.status, result.message,
        )

    def confirm_delete(self, archive: Path) -> bool:
        """Block until the GUI answers the delete prompt.

        The GUI connects to :attr:`confirmation_requested`; its handler calls
        ``QMessageBox.question`` then :meth:`set_delete_decision`. We poll the
        flag with a short sleep to avoid a busy loop.
        """
        import time

        self.worker._confirm_event_set = False
        self.worker._confirm_delete = True
        self.worker.confirmation_requested.emit(str(archive))
        # Wait (bounded) for the GUI to answer.
        deadline = 300.0  # seconds; generous so a slow user is fine
        while not self.worker._confirm_event_set and deadline > 0:
            time.sleep(0.05)
            deadline -= 0.05
            if self.worker.isInterruptionRequested():
                return False
        return self.worker._confirm_delete
