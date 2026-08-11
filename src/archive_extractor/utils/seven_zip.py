"""7-Zip command-line wrapper.

All 7z invocations go through :func:`run_7z` so that we *always* pass the
password flag (empty string if none), assume-yes, suppress prompts and hide
the console window. This is the single guard against 7z hanging on stdin.
"""
from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..constants import (
    EXIT_FATAL,
    EXIT_OK,
    EXIT_WRONG_PASSWORD,
)

log = logging.getLogger(__name__)

# Hide the flickering console window on Windows.
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class SevenZipError(RuntimeError):
    """Raised when 7z fails with a non-recoverable error."""

    def __init__(self, returncode: int, stderr: str, command: list[str]):
        self.returncode = returncode
        self.stderr = stderr
        self.command = command
        super().__init__(
            f"7z exited {returncode}: {stderr.strip()[:200]} "
            f"(cmd: {' '.join(command[:3])} ...)"
        )


@dataclass
class SevenZipResult:
    """Structured result of a 7z invocation."""
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == EXIT_OK

    @property
    def wrong_password(self) -> bool:
        """True when 7z reports the password is incorrect.

        For encrypted archives, wrong password yields exit code 2 (fatal) in
        modern 7z versions; historically 255 was used. We check both the code
        and the stderr text to be robust across versions.
        """
        if self.returncode == EXIT_WRONG_PASSWORD:
            return True
        if self.returncode == EXIT_FATAL:
            low = (self.stderr or "").lower()
            if "wrong password" in low or "cannot open encrypted" in low:
                return True
        return False

    @property
    def corrupt(self) -> bool:
        """True when the archive itself is damaged (CRC/test failure).

        Excludes the wrong-password case so the two properties are mutually
        exclusive (a wrong-password probe is never misread as corruption).
        """
        if self.wrong_password:
            return False
        if self.returncode == EXIT_FATAL:
            low = (self.stderr or "").lower()
            if "crc failed" in low or "data error" in low or "cannot open" in low:
                return True
        return False


def build_command(archive: Path, args: list[str], password: str | None) -> list[str]:
    """Build the full 7z argv with password / assume-yes always present."""
    cmd: list[str] = []
    # archive and operation args provided by caller; we wrap them so the
    # password flag is always present (empty when no password) to suppress
    # interactive prompts.
    pw = password if password is not None else ""
    cmd.extend(args)  # e.g. ["7z.exe", "x", archive, "-odest"]
    cmd.append(f"-p{pw}")
    cmd.append("-y")  # assume yes to all queries
    cmd.append("-bb1")  # output progress lines
    cmd.append("-bso0")  # suppress normal stdout
    cmd.append("-bse2")  # send errors to stderr
    return cmd


def run_7z(
    seven_zip: Path,
    archive: Path,
    args: list[str],
    password: str | None = None,
    timeout: int | None = None,
) -> SevenZipResult:
    """Run a 7z command and capture output.

    Parameters
    ----------
    seven_zip:
        Path to ``7z.exe``.
    archive:
        The archive being operated on (used to build the command and for error
        messages).
    args:
        Operation-specific args *excluding* the password/yes flags, e.g.
        ``["x", "-odest"]``. The archive path and password flag are appended
        automatically.
    password:
        Password to try; ``None`` means "no password" (still passes ``-p`` with
        an empty value to suppress prompts).
    timeout:
        Optional per-call timeout in seconds.
    """
    if not seven_zip.exists():
        raise SevenZipError(-1, f"7z.exe not found: {seven_zip}", [])

    cmd = [str(seven_zip), *args, str(archive), f"-p{password if password is not None else ''}",
           "-y", "-bb1", "-bso0", "-bse2"]

    log.debug("7z cmd: %s", " ".join(cmd[:3]) + " ... -p*** -y")

    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise SevenZipError(-1, f"7z timed out after {timeout}s", cmd) from exc

    return SevenZipResult(
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )
