"""Scanner tests: discovery + pruning."""
from __future__ import annotations

from pathlib import Path

from archive_extractor.core import scanner


def test_scan_finds_archives(sample_folder: Path):
    found = [p.name for p in scanner.scan(sample_folder)]
    assert "plain.zip" in found
    assert "solvable.7z" in found
    assert "locked.7z" in found


def test_scan_excludes_non_archives(sample_folder: Path):
    found = {p.name for p in scanner.scan(sample_folder)}
    assert "plain.txt" not in found  # plain file, not an archive


def test_scan_prunes_output_root(tmp_path: Path, sample_folder: Path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "decoy.zip").write_bytes(b"not real")
    found = {p.name for p in scanner.scan(sample_folder, output_root=out)}
    assert "decoy.zip" not in found


def test_scan_prunes_unsolved_subfolder(tmp_path: Path, sample_folder: Path):
    unsolved = sample_folder / "password_protected_unsolved"
    unsolved.mkdir()
    (unsolved / "skipme.zip").write_bytes(b"fake")
    found = {p.name for p in scanner.scan(sample_folder)}
    assert "skipme.zip" not in found
