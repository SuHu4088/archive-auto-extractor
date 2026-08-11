"""archive_info tests: format / encryption / manifest detection."""
from __future__ import annotations

from pathlib import Path

from archive_extractor.core import archive_info


def test_detect_plain_zip(seven_zip: Path, sample_folder: Path):
    info = archive_info.detect(seven_zip, sample_folder / "plain.zip")
    assert info.format == "zip"
    assert not info.is_password_protected
    assert not info.header_encrypted
    assert info.file_count == 1


def test_detect_header_encrypted_7z(seven_zip: Path, sample_folder: Path):
    info = archive_info.detect(seven_zip, sample_folder / "solvable.7z")
    assert info.is_password_protected
    assert info.header_encrypted
    assert info.file_count == 0  # cannot list without password


def test_list_with_password(seven_zip: Path, sample_folder: Path):
    info = archive_info.list_with_password(
        seven_zip, sample_folder / "solvable.7z", "Pass111"
    )
    assert info.file_count == 1
    entry = info.manifest[0]
    assert entry.path == "secret.txt"
    assert entry.crc is not None and len(entry.crc) == 8


def test_detect_not_counting_header_block(seven_zip: Path, sample_folder: Path):
    """Regression: the SLT header block (Type=zip, Path=<archive>) must not
    be counted as a file entry."""
    info = archive_info.detect(seven_zip, sample_folder / "plain.zip")
    assert info.file_count == 1, "header block was counted as a file"
