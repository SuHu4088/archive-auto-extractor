"""Archive extraction via ``7z x``.

The caller computes the destination (same-name subfolder under the output
root, per requirement 9); this module just runs the extraction and reports
the files that landed in ``dest``.
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..models.result import ExtractionResult
from ..utils.fs import ensure_dir, is_hidden
from ..utils.seven_zip import run_7z

log = logging.getLogger(__name__)


def extract(
    seven_zip: Path,
    archive: Path,
    dest: Path,
    password: str | None = None,
) -> ExtractionResult:
    """Extract ``archive`` into ``dest`` (created if needed).

    Refuses to overwrite a non-empty ``dest`` to avoid mixing extractions.
    Returns the list of extracted files (recursively walked).
    """
    ensure_dir(dest)
    existing = [p for p in dest.iterdir() if not is_hidden(p)]
    if existing:
        return ExtractionResult(
            ok=False,
            dest=dest,
            error=f"destination not empty: {dest}",
        )

    # 7z x extracts preserving paths. -o<dest> has no space (7z syntax).
    result = run_7z(
        seven_zip,
        archive,
        ["x", f"-o{dest}"],
        password=password,
    )

    if not result.ok:
        return ExtractionResult(
            ok=False,
            dest=dest,
            error=(result.stderr or f"7z exit code {result.returncode}").strip(),
        )

    extracted = sorted(p for p in dest.rglob("*") if p.is_file())
    log.info("extracted %d file(s) from %s into %s", len(extracted), archive.name, dest)
    return ExtractionResult(ok=True, dest=dest, extracted_files=extracted)
