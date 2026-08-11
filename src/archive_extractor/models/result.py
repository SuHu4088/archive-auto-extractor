"""Result dataclasses for extraction, verification and the overall outcome."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractionResult:
    """Outcome of :func:`archive_extractor.core.extractor.extract`."""
    ok: bool
    dest: Path
    extracted_files: list[Path] = field(default_factory=list)
    error: str = ""


@dataclass
class VerifyResult:
    """Outcome of :func:`archive_extractor.core.verifier.verify`.

    ``ok`` is True only when *all* of: file counts match, no missing/extra,
    every size matches, every non-null CRC matches, and ``7z t`` exited 0.
    """
    ok: bool
    file_count_match: bool
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    size_mismatches: list[str] = field(default_factory=list)
    crc_mismatches: list[str] = field(default_factory=list)
    test_exit_code: int = 0
    detail: str = ""


@dataclass
class ArchiveResult:
    """Final per-archive outcome emitted through the worker signal.

    ``status`` is one of the ``STATUS_*`` constants.
    """
    path: Path
    status: str
    message: str
    extracted_count: int = 0
    password_used: str | None = None
