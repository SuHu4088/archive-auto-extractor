"""verifier tests: CRC matching + tamper detection."""
from __future__ import annotations

from pathlib import Path

from archive_extractor.core import archive_info, extractor, verifier


def test_verify_ok(seven_zip: Path, tmp_path: Path, sample_folder: Path):
    archive = sample_folder / "plain.zip"
    info = archive_info.detect(seven_zip, archive)
    dest = tmp_path / "out" / archive.stem
    extractor.extract(seven_zip, archive, dest)
    result = verifier.verify(seven_zip, archive, dest, info=info)
    assert result.ok
    assert not result.crc_mismatches
    assert not result.size_mismatches


def test_verify_tampered_file_fails(
    seven_zip: Path, tmp_path: Path, sample_folder: Path
):
    archive = sample_folder / "plain.zip"
    info = archive_info.detect(seven_zip, archive)
    dest = tmp_path / "out" / archive.stem
    extractor.extract(seven_zip, archive, dest)
    # Corrupt the extracted file.
    (dest / "plain.txt").write_text("TAMPERED", encoding="utf-8")
    result = verifier.verify(seven_zip, archive, dest, info=info)
    assert not result.ok
    assert result.size_mismatches or result.crc_mismatches


def test_verify_encrypted_with_password(
    seven_zip: Path, tmp_path: Path, sample_folder: Path
):
    archive = sample_folder / "solvable.7z"
    dest = tmp_path / "out" / archive.stem
    extractor.extract(seven_zip, archive, dest, password="Pass111")
    result = verifier.verify(seven_zip, archive, dest, password="Pass111")
    assert result.ok
