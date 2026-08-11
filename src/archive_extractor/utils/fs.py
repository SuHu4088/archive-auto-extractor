"""Filesystem helpers: safe moves, same-name subfolders, deletion.

Deletion prefers the Recycle Bin (via :mod:`send2trash`) so that an accidental
delete can be undone; it falls back to ``Path.unlink`` when send2trash is not
installed.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

log = logging.getLogger(__name__)


def ensure_dir(path: Path) -> Path:
    """Create ``path`` (and parents) if missing; return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def same_name_subfolder(output_root: Path, archive: Path) -> Path:
    """Return ``output_root / archive.stem`` (the same-name subfolder)."""
    return output_root / archive.stem


def safe_move(src: Path, dest_dir: Path, *, overwrite: bool = False) -> Path:
    """Move ``src`` into ``dest_dir`` (created if needed).

    On a name clash, appends a numeric suffix unless ``overwrite`` is True.
    Returns the final destination path.
    """
    ensure_dir(dest_dir)
    target = dest_dir / src.name
    if target.exists():
        if overwrite:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        else:
            stem, ext = target.stem, target.suffix
            i = 1
            while target.exists():
                target = dest_dir / f"{stem} ({i}){ext}"
                i += 1
    shutil.move(str(src), str(target))
    log.debug("moved %s -> %s", src, target)
    return target


def safe_delete(path: Path) -> bool:
    """Delete a file, preferring the Recycle Bin.

    Returns True on success. Never raises — failures are logged so a single
    bad delete does not abort a batch.
    """
    try:
        if not path.exists():
            log.warning("delete target does not exist: %s", path)
            return False
        try:
            from send2trash import send2trash  # type: ignore[import-not-found]

            send2trash(str(path))
            log.info("sent to recycle bin: %s", path)
            return True
        except ImportError:
            path.unlink()
            log.info("deleted (permanent): %s", path)
            return True
    except Exception as exc:  # noqa: BLE001 — best-effort delete in a batch
        log.error("failed to delete %s: %s", path, exc)
        return False


def is_hidden(path: Path) -> bool:
    """Heuristic for hidden / system files on Windows & dotfiles on POSIX."""
    name = path.name
    if name.startswith("."):
        return True
    if os.name == "nt":
        try:
            import ctypes

            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            if attrs != -1 and (attrs & 0x2):  # FILE_ATTRIBUTE_HIDDEN
                return True
        except Exception:  # noqa: BLE001
            pass
    return False
