"""Per-archive processing state machine.

Pure logic — no Qt dependency — so it is unit-testable. The
:class:`PipelineCallbacks` protocol lets the worker thread report progress
without importing QtWidgets.

Flow (see plan §"单压缩包端到端流程"):

    SCAN → DETECT → DECIDE → EXTRACT → VERIFY → FINALIZE

Decision branches:
* plain archive           → extract → verify → (optional delete)
* encrypted, module off   → SKIP (leave in place)
* encrypted, module on    → try each password; on success extract+verify;
  on total failure move to ``password_protected_unsolved/`` and emit
  ``已尝试所有密码仍无法打开``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..config import Settings
from ..constants import STATUS_FAILED, STATUS_OK, STATUS_SKIPPED, STATUS_UNSOLVED
from ..models.result import ArchiveResult
from ..utils.fs import ensure_dir, same_name_subfolder, safe_move
from ..utils.seven_zip import run_7z
from . import archive_info, extractor, verifier
from .password_manager import PasswordVault

log = logging.getLogger(__name__)


class PipelineCallbacks(Protocol):
    """Progress-reporting hooks implemented by the worker."""

    def on_stage(self, archive: Path, stage: str, detail: str) -> None: ...

    def on_password_try(self, archive: Path, idx: int, total: int) -> None: ...

    def on_result(self, result: ArchiveResult) -> None: ...

    def confirm_delete(self, archive: Path) -> bool: ...


@dataclass
class PipelineStats:
    """Counters accumulated across one batch."""
    ok: int = 0
    failed: int = 0
    skipped: int = 0
    unsolved: int = 0


class ArchivePipeline:
    """Processes a single archive through detect → extract → verify → finalize."""

    def __init__(self, settings: Settings, vault: PasswordVault | None):
        self.settings = settings
        self.vault = vault

    # -- helpers ------------------------------------------------------------
    def _output_root(self, archive: Path) -> Path:
        root = self.settings.output_root
        if str(root):
            return root
        # Default to the archive's own folder when no output root configured.
        return archive.parent

    def _unsolved_dir(self, archive: Path) -> Path:
        base = self._output_root(archive)
        if self.settings.unsolved_location == "beside_archive":
            base = archive.parent
        return base / self.settings.unsolved_subfolder_name

    # -- main entry ---------------------------------------------------------
    def process(
        self, archive: Path, callbacks: PipelineCallbacks
    ) -> ArchiveResult:
        """Run the full pipeline for ``archive``; return the outcome."""
        try:
            return self._run(archive, callbacks)
        except Exception as exc:  # noqa: BLE001 — never let one archive abort the batch
            log.exception("pipeline error on %s", archive)
            result = ArchiveResult(
                path=archive, status=STATUS_FAILED, message=f"内部错误: {exc}"
            )
            callbacks.on_result(result)
            return result

    def _run(self, archive: Path, cb: PipelineCallbacks) -> ArchiveResult:
        sz = self.settings.seven_zip

        # 1. Detect ----------------------------------------------------------
        cb.on_stage(archive, "detect", "检测压缩包…")
        info = archive_info.detect(sz, archive, password=None)

        # 2. Decide ---------------------------------------------------------
        if not info.is_password_protected:
            return self._extract_and_verify(archive, None, info, cb)

        # Encrypted.
        if not self.settings.password_module_enabled or self.vault is None:
            result = ArchiveResult(
                path=archive,
                status=STATUS_SKIPPED,
                message="受密码保护，已跳过（密码模块未启用）",
            )
            cb.on_result(result)
            return result

        # 3. Try passwords --------------------------------------------------
        return self._try_passwords(archive, info, cb)

    # -- branches -----------------------------------------------------------
    def _extract_and_verify(
        self,
        archive: Path,
        password: str | None,
        info,
        cb: PipelineCallbacks,
    ) -> ArchiveResult:
        sz = self.settings.seven_zip
        out_root = self._output_root(archive)
        ensure_dir(out_root)
        dest = same_name_subfolder(out_root, archive)

        cb.on_stage(archive, "extract", "解压中…")
        ex = extractor.extract(sz, archive, dest, password=password)
        if not ex.ok:
            result = ArchiveResult(
                path=archive, status=STATUS_FAILED,
                message=f"解压失败: {ex.error}",
            )
            cb.on_result(result)
            return result

        cb.on_stage(archive, "verify", "CRC 校验中…")
        vr = verifier.verify(sz, archive, dest, password=password, info=info)
        if not vr.ok:
            result = ArchiveResult(
                path=archive, status=STATUS_FAILED,
                message=f"CRC 校验失败: {vr.detail}",
                extracted_count=len(ex.extracted_files),
                password_used=password,
            )
            cb.on_result(result)
            return result

        # 4. Finalize ------------------------------------------------------
        cb.on_stage(archive, "finalize", "完成")
        deleted = False
        if self.settings.delete_original_after_success:
            if self.settings.confirm_before_delete:
                cb.on_stage(archive, "finalize", "等待删除确认…")
                if not cb.confirm_delete(archive):
                    msg = f"已解压 {len(ex.extracted_files)} 个文件，CRC 校验通过（未删除原文件）"
                    result = ArchiveResult(
                        path=archive, status=STATUS_OK, message=msg,
                        extracted_count=len(ex.extracted_files), password_used=password,
                    )
                    cb.on_result(result)
                    return result
            deleted = self._delete_original(archive)

        verb = "已删除原文件" if deleted else "保留原文件"
        result = ArchiveResult(
            path=archive, status=STATUS_OK,
            message=f"已解压 {len(ex.extracted_files)} 个文件，CRC 校验通过，{verb}",
            extracted_count=len(ex.extracted_files), password_used=password,
        )
        cb.on_result(result)
        return result

    def _try_passwords(self, archive, info, cb: PipelineCallbacks) -> ArchiveResult:
        sz = self.settings.seven_zip
        candidates = list(self.vault.iter_passwords_for(archive.name))
        total = len(candidates)
        if total == 0:
            return self._all_passwords_failed(archive, cb, "密码库为空")

        for idx, (entry, password) in enumerate(candidates, start=1):
            cb.on_password_try(archive, idx, total)
            test = run_7z(sz, archive, ["t"], password=password)
            if test.ok:
                # Found it. Re-list (for header-encrypted) then extract+verify.
                if info.header_encrypted:
                    info = archive_info.list_with_password(sz, archive, password)
                self.vault.record_success(entry.id, archive.name)
                return self._extract_and_verify(archive, password, info, cb)
            if test.corrupt:
                result = ArchiveResult(
                    path=archive, status=STATUS_FAILED,
                    message="压缩包已损坏，无法解压",
                )
                cb.on_result(result)
                return result
            # wrong_password (or other non-ok) => try next candidate.

        return self._all_passwords_failed(archive, cb)

    def _all_passwords_failed(
        self, archive: Path, cb: PipelineCallbacks, reason: str = ""
    ) -> ArchiveResult:
        self.vault.record_failure_all(archive.name)
        moved = ""
        if self.settings.move_unsolved_to_subfolder:
            unsolved = self._unsolved_dir(archive)
            try:
                safe_move(archive, unsolved)
                moved = f"（已移至 {self.settings.unsolved_subfolder_name}/）"
            except Exception as exc:  # noqa: BLE001
                log.warning("could not move unsolved archive %s: %s", archive, exc)
        msg = "已尝试所有密码仍无法打开" + moved
        if reason:
            msg = f"{reason}。" + msg
        result = ArchiveResult(
            path=archive, status=STATUS_UNSOLVED, message=msg,
        )
        cb.on_result(result)
        return result

    # -- delete -------------------------------------------------------------
    def _delete_original(self, archive: Path) -> bool:
        from ..utils.fs import safe_delete

        return safe_delete(archive)
