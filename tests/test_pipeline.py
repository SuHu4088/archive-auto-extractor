"""pipeline tests: end-to-end scenarios per archive."""
from __future__ import annotations

from pathlib import Path

from archive_extractor.config import Settings
from archive_extractor.constants import (
    STATUS_FAILED,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_UNSOLVED,
)
from archive_extractor.core.password_manager import PasswordVault
from archive_extractor.core.pipeline import ArchivePipeline


class _Cb:
    def __init__(self, confirm: bool = True):
        self.results = []
        self.tries = 0
        self._confirm = confirm

    def on_stage(self, a, stage, detail): ...
    def on_password_try(self, a, idx, total): self.tries += 1
    def on_result(self, r): self.results.append(r)
    def confirm_delete(self, a): return self._confirm


def _settings(tmp_path: Path, module_on: bool) -> Settings:
    s = Settings()
    s.extraction_output_root = str(tmp_path / "out")
    s.password_module_enabled = module_on
    s.delete_original_after_success = False
    return s


def test_plain_archive_ok(seven_zip, tmp_path, sample_folder, settings):
    s = _settings(tmp_path, module_on=False)
    pipe = ArchivePipeline(s, vault=None)
    r = pipe.process(sample_folder / "plain.zip", _Cb())
    assert r.status == STATUS_OK


def test_encrypted_skipped_when_module_off(
    seven_zip, tmp_path, sample_folder, settings, vault
):
    s = _settings(tmp_path, module_on=False)
    pipe = ArchivePipeline(s, vault)
    r = pipe.process(sample_folder / "solvable.7z", _Cb())
    assert r.status == STATUS_SKIPPED


def test_encrypted_solved_with_password(
    seven_zip, tmp_path, sample_folder, settings, vault
):
    s = _settings(tmp_path, module_on=True)
    vault.add_password("Pass111", label="common")
    pipe = ArchivePipeline(s, vault)
    cb = _Cb()
    r = pipe.process(sample_folder / "solvable.7z", cb)
    assert r.status == STATUS_OK
    assert r.password_used == "Pass111"
    assert cb.tries == 1


def test_encrypted_unsolved_moved(
    seven_zip, tmp_path, sample_folder, settings, vault
):
    s = _settings(tmp_path, module_on=True)
    vault.add_password("Pass111", label="common")  # not the right password
    pipe = ArchivePipeline(s, vault)
    r = pipe.process(sample_folder / "locked.7z", _Cb())
    assert r.status == STATUS_UNSOLVED
    assert "已尝试所有密码仍无法打开" in r.message
    assert not (sample_folder / "locked.7z").exists()
    unsolved = Path(s.extraction_output_root) / s.unsolved_subfolder_name
    assert (unsolved / "locked.7z").exists()
