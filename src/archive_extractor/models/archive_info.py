"""Dataclasses describing an archive's structure and encryption state."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ManifestEntry:
    """One file inside an archive, as reported by ``7z l -slt``.

    ``crc`` is the CRC32 stored in the archive (8 hex chars) or ``None`` when
    the archive does not store one (e.g. solid RAR4 entries).
    """
    path: str          # archive-relative path with forward slashes
    size: int          # uncompressed size in bytes
    crc: str | None    # stored CRC32 hex, or None


@dataclass
class ArchiveInfo:
    """Result of :func:`archive_extractor.core.archive_info.detect`."""
    path: Path
    format: str                       # "zip" | "7z" | "rar" | ...
    is_password_protected: bool
    header_encrypted: bool            # True => can't even list without password
    manifest: list[ManifestEntry] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.manifest)
