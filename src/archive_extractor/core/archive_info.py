"""Detect an archive's format, encryption state and build its manifest.

Uses ``7z l -slt`` (list with technical fields). This works uniformly across
ZIP / RAR / 7Z and distinguishes:

* **header-encrypted** archives (e.g. RAR5 with encrypted filenames): ``7z l``
  fails outright with "Wrong password" / "Cannot open encrypted archive" —
  we can list nothing without the password.
* **data-encrypted** archives: ``7z l`` succeeds, entries carry
  ``Encrypted = +`` — we can read filenames/sizes/CRCs without the password.
* **plain** archives: ``7z l`` succeeds, entries have ``Encrypted = -``.
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..models.archive_info import ArchiveInfo, ManifestEntry
from ..utils.seven_zip import run_7z

log = logging.getLogger(__name__)

# Marker phrases that 7z emits when an encrypted header blocks listing.
_ENCRYPTED_MARKERS = ("wrong password", "cannot open encrypted", "enter password")


def _parse_slt(stdout: str) -> tuple[list[ManifestEntry], str, bool]:
    """Parse ``7z l -slt`` output.

    Returns ``(manifest, archive_format, encrypted_seen)``. ``encrypted_seen``
    is True when any entry carries ``Encrypted = +``.

    The output has a *header block* (``Path = <archive>``, ``Type = zip`` …)
    that must NOT be counted as a file. The reliable distinguisher is the
    ``Type`` key: the header block carries it, file/dir entries do not. (7z
    entries omit the ``Folder`` field that ZIP entries include, so relying on
    ``Folder`` alone misses 7z files.)
    """
    manifest: list[ManifestEntry] = []
    archive_format = "unknown"
    encrypted_seen = False

    # Entries are separated by blank lines; each entry is a list of
    # "Key = Value" lines.
    blocks = stdout.split("\n\n")
    current: dict[str, str] = {}
    for block in blocks:
        for line in block.splitlines():
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            current[key.strip()] = value.strip()

        # Header block: carries "Type = <format>" alongside "Path = <archive>".
        if "Type" in current and archive_format == "unknown":
            archive_format = current["Type"].strip().lower()

        # File / directory entries: have "Path" but NO "Type" key.
        if "Path" in current and "Type" not in current:
            entry_path = current["Path"].strip()
            if entry_path:
                # Skip directory entries (Folder = +, when present).
                if current.get("Folder", "-").strip() != "+":
                    encrypted = current.get("Encrypted", "-").strip() == "+"
                    if encrypted:
                        encrypted_seen = True
                    size_raw = current.get("Size", "0").strip()
                    try:
                        size = int(size_raw) if size_raw else 0
                    except ValueError:
                        size = 0
                    crc_raw = current.get("CRC", "").strip()
                    crc = crc_raw if crc_raw else None
                    manifest.append(ManifestEntry(path=entry_path, size=size, crc=crc))
        current = {}

    return manifest, archive_format, encrypted_seen


def detect(seven_zip: Path, archive: Path, password: str | None = None) -> ArchiveInfo:
    """Probe ``archive`` and return its :class:`ArchiveInfo`.

    A single ``7z l -slt -p""`` call tells us everything: format, encryption,
    and (when not header-encrypted) the full manifest with stored CRCs.
    """
    result = run_7z(seven_zip, archive, ["l", "-slt"], password=password)

    if result.ok:
        manifest, fmt, encrypted = _parse_slt(result.stdout)
        return ArchiveInfo(
            path=archive,
            format=fmt or Path(archive).suffix.lstrip(".").lower(),
            is_password_protected=encrypted,
            header_encrypted=False,
            manifest=manifest,
        )

    # Non-zero exit: header-encrypted archives fail here.
    low = (result.stderr or "").lower()
    if any(marker in low for marker in _ENCRYPTED_MARKERS) or result.wrong_password:
        log.info("archive %s is header-encrypted (cannot list without password)", archive.name)
        return ArchiveInfo(
            path=archive,
            format=Path(archive).suffix.lstrip(".").lower(),
            is_password_protected=True,
            header_encrypted=True,
            manifest=[],  # unknown until unlocked
        )

    # Genuinely unreadable / corrupt.
    log.warning("archive %s unreadable: %s", archive.name, (result.stderr or "").strip())
    return ArchiveInfo(
        path=archive,
        format=Path(archive).suffix.lstrip(".").lower(),
        is_password_protected=False,
        header_encrypted=False,
        manifest=[],
    )


def list_with_password(seven_zip: Path, archive: Path, password: str) -> ArchiveInfo:
    """Re-list an archive once the correct password is known.

    Used to populate the manifest for verification of header-encrypted archives
    after the password has been found.
    """
    result = run_7z(seven_zip, archive, ["l", "-slt"], password=password)
    if result.ok:
        manifest, fmt, encrypted = _parse_slt(result.stdout)
        return ArchiveInfo(
            path=archive,
            format=fmt or Path(archive).suffix.lstrip(".").lower(),
            is_password_protected=encrypted,
            header_encrypted=False,
            manifest=manifest,
        )
    log.warning("list_with_password failed for %s: %s", archive.name, (result.stderr or "").strip())
    return ArchiveInfo(
        path=archive,
        format=Path(archive).suffix.lstrip(".").lower(),
        is_password_protected=True,
        header_encrypted=True,
        manifest=[],
    )
