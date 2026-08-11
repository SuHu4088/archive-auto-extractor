"""Recursive folder scanner for archives.

Walks the source folder, yields archive paths (ZIP/RAR/7Z by default) while
*pruning* the extraction output root and any ``password_protected_unsolved``
folder so that already-processed archives are not re-scanned.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterator

from ..constants import SUPPORTED_EXT, UNSOLVED_SUBFOLDER
from ..utils.fs import is_hidden

log = logging.getLogger(__name__)


def _ext_match(name: str, extensions: tuple[str, ...]) -> bool:
    lower = name.lower()
    return any(lower.endswith(ext) for ext in extensions)


def scan(
    root: Path,
    output_root: Path | None = None,
    extensions: tuple[str, ...] = SUPPORTED_EXT,
    skip_hidden: bool = True,
) -> Iterator[Path]:
    """Yield archive paths under ``root`` (recursive, sorted, deterministic).

    Parameters
    ----------
    root:
        Folder to scan.
    output_root:
        Extraction output root — pruned from traversal so we never re-scan
        already-extracted contents.
    extensions:
        Archive extensions to match (case-insensitive).
    skip_hidden:
        Skip hidden / system files and directories.
    """
    root = Path(root).resolve()
    prune_dirs: set[Path] = set()
    if output_root:
        out = Path(output_root).resolve()
        if out.exists():
            prune_dirs.add(out)

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)

        # Prune output root and unsolved folder from descent.
        kept: list[str] = []
        for d in sorted(dirnames):
            full = current / d
            if full in prune_dirs:
                log.debug("prune (output root): %s", full)
                continue
            if d == UNSOLVED_SUBFOLDER:
                log.debug("prune (unsolved): %s", full)
                continue
            if skip_hidden and is_hidden(full):
                continue
            kept.append(d)
        dirnames[:] = kept  # mutate in place so os.walk skips pruned dirs

        for fname in sorted(filenames):
            if skip_hidden and is_hidden(current / fname):
                continue
            if not _ext_match(fname, extensions):
                continue
            yield current / fname
