"""CRC / consistency verification.

Three independent checks must all pass before an original archive may be
deleted (requirement 4 & 5):

1. **Manifest match** — the stored CRCs (from ``7z l -slt``) are compared
   against CRC32 of the extracted files computed with :func:`zlib.crc32`.
2. **Consistency** — file count, paths and sizes all match between the
   archive manifest and the extracted folder.
3. **7z self-test** — ``7z t <archive> -p<pw>`` exits 0 (7z's own
   post-decompress CRC test, independent of our parser).

For entries whose stored CRC is blank (rare; solid RAR4), the CRC check is
downgraded to a size-only comparison for that entry.
"""
from __future__ import annotations

import logging
import zlib
from pathlib import Path

from ..models.archive_info import ArchiveInfo, ManifestEntry
from ..models.result import VerifyResult
from ..utils.seven_zip import run_7z
from . import archive_info as archive_info_mod

log = logging.getLogger(__name__)

_CHUNK = 64 * 1024  # 64 KiB read chunk for CRC computation.


def _crc32_of_file(path: Path) -> str:
    """Compute CRC32 (8 lowercase hex chars) of ``path``."""
    crc = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
    return f"{crc & 0xFFFFFFFF:08x}"


def _normalize(rel_path: str) -> str:
    """Normalize a path for comparison (forward slashes, lowercase on
    case-insensitive systems)."""
    return rel_path.replace("\\", "/")


def compute_extracted(dest: Path) -> dict[str, tuple[int, str]]:
    """Return ``{relpath: (size, crc32_hex)}`` for every file under ``dest``."""
    out: dict[str, tuple[int, str]] = {}
    for p in dest.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(dest).as_posix()
        out[_normalize(rel)] = (p.stat().st_size, _crc32_of_file(p))
    return out


def verify(
    seven_zip: Path,
    archive: Path,
    dest: Path,
    password: str | None = None,
    info: ArchiveInfo | None = None,
) -> VerifyResult:
    """Verify extracted files against the archive.

    Parameters
    ----------
    info:
        Optional pre-computed :class:`ArchiveInfo` (with manifest). When
        omitted, :func:`archive_info.detect` is called (re-listing the
        archive). For header-encrypted archives the caller MUST pass a
        password so the manifest can be read.
    """
    if info is None or not info.manifest:
        if password is not None:
            info = archive_info_mod.list_with_password(seven_zip, archive, password)
        else:
            info = archive_info_mod.detect(seven_zip, archive, password=None)
        if not info.manifest:
            # Cannot build a manifest (e.g. still encrypted) — fail safe.
            return VerifyResult(
                ok=False,
                file_count_match=False,
                detail="cannot read archive manifest for verification",
            )

    manifest: list[ManifestEntry] = info.manifest
    extracted = compute_extracted(dest)

    manifest_paths = {_normalize(m.path): m for m in manifest}
    extracted_paths = set(extracted.keys())

    missing = sorted(set(manifest_paths) - extracted_paths)
    extra = sorted(extracted_paths - set(manifest_paths))

    size_mismatches: list[str] = []
    crc_mismatches: list[str] = []
    for rel, entry in manifest_paths.items():
        if rel not in extracted:
            continue  # already counted as missing
        ex_size, ex_crc = extracted[rel]
        if ex_size != entry.size:
            size_mismatches.append(rel)
            continue
        if entry.crc is None:
            # No stored CRC for this entry — size match is the best we can do.
            continue
        if ex_crc.lower() != entry.crc.lower():
            crc_mismatches.append(rel)

    file_count_match = (len(manifest_paths) == len(extracted_paths))

    # 7z self-test cross-check.
    test = run_7z(seven_zip, archive, ["t"], password=password)
    test_ok = test.ok

    ok = (
        file_count_match
        and not missing
        and not extra
        and not size_mismatches
        and not crc_mismatches
        and test_ok
    )

    detail_parts: list[str] = []
    if missing:
        detail_parts.append(f"missing {len(missing)}")
    if extra:
        detail_parts.append(f"extra {len(extra)}")
    if size_mismatches:
        detail_parts.append(f"size-mismatch {len(size_mismatches)}")
    if crc_mismatches:
        detail_parts.append(f"crc-mismatch {len(crc_mismatches)}")
    if not test_ok:
        detail_parts.append(f"7z-t exit={test.returncode}")
    detail = "; ".join(detail_parts) if detail_parts else "all checks passed"

    log.info("verify %s: ok=%s (%s)", archive.name, ok, detail)
    return VerifyResult(
        ok=ok,
        file_count_match=file_count_match,
        missing=missing,
        extra=extra,
        size_mismatches=size_mismatches,
        crc_mismatches=crc_mismatches,
        test_exit_code=test.returncode,
        detail=detail,
    )
