"""Git automation for the password vault.

The vault lives OUTSIDE the project folder (requirement 11) as its own Git
repository. :class:`VaultGit` initializes it on first use and commits with a
descriptive message after every mutating operation. Git failures are logged
but never block the vault write — vault integrity outranks the git snapshot.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from ..constants import VAULT_FILENAME, VAULT_README_FILENAME
from ..models.vault_entry import VaultEntry

log = logging.getLogger(__name__)

_CREATE_NO_WINDOW = 0x08000000 if __import__("os").name == "nt" else 0

_VAULT_README = """# Password Vault

This directory is an automatically-managed password vault for the
Archive Auto-Extractor application.

## Properties

- It lives OUTSIDE the project folder by design.
- It is its own Git repository; every add / update / toggle / delete /
  record-success / record-failure / session-open / session-close operation
  produces a descriptive commit so changes are traceable and reversible.
- The application never deletes this file directly; removals go through
  the two-step confirm flow and are still committed.

## Files

- `passwords.json` — the vault data (versioned).
"""


class VaultGitError(RuntimeError):
    """Raised when a vault git operation that *must* succeed fails."""


class VaultGit:
    """Local Git wrapper for the vault directory."""

    def __init__(self, vault_dir: Path):
        self.vault_dir = Path(vault_dir)

    # -- low-level git ------------------------------------------------------
    def _git(self, args: list[str], check: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.vault_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            creationflags=_CREATE_NO_WINDOW,
            check=check,
        )

    # -- lifecycle ----------------------------------------------------------
    def ensure_repo(self) -> None:
        """Initialize the vault repo on first use.

        Idempotent: if ``.git`` already exists, does nothing.
        """
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        if (self.vault_dir / ".git").exists():
            return

        log.info("initializing vault git repo at %s", self.vault_dir)
        # init
        self._git(["init"]).check_returncode()
        # local identity (only if not inherited from global).
        if not self._git(["config", "user.name"]).stdout.strip():
            self._git(["config", "user.name", "Archive Extractor Vault"])
        if not self._git(["config", "user.email"]).stdout.strip():
            self._git(["config", "user.email", "vault@archive-extractor.local"])

        # Seed files.
        (self.vault_dir / VAULT_README_FILENAME).write_text(_VAULT_README, encoding="utf-8")
        vault_file = self.vault_dir / VAULT_FILENAME
        if not vault_file.exists():
            vault_file.write_text(
                '{"version": 1, "metadata": {}, "passwords": [], "audit": []}',
                encoding="utf-8",
            )

        self._git(["add", VAULT_FILENAME, VAULT_README_FILENAME])
        # Commit may fail if identity still missing — try, log on failure.
        r = self._git(["commit", "-m", "Initialize password vault"])
        if r.returncode != 0:
            log.warning("vault initial commit failed: %s", (r.stderr or "").strip())

    # -- commit -------------------------------------------------------------
    def commit(self, message: str, allow_empty: bool = False) -> bool:
        """Stage the vault files and commit with ``message``.

        Returns True if a commit was created, False if there was nothing to
        commit (or git failed — failure is logged, not raised).

        ``allow_empty=True`` forces a commit even when the vault file did not
        change — used for session open/close audit markers (requirement 11).
        """
        self._git(["add", VAULT_FILENAME, VAULT_README_FILENAME])
        cmd = ["commit", "-m", message]
        if allow_empty:
            cmd.append("--allow-empty")
        r = self._git(cmd)
        if r.returncode == 0:
            log.info("vault commit: %s", message)
            return True
        # "nothing to commit" exits 1 — that's fine, just no new commit.
        low = (r.stdout + r.stderr).lower()
        if "nothing to commit" in low or "no changes" in low:
            return False
        log.warning("vault commit failed (%s): %s", message, (r.stderr or r.stdout).strip())
        return False

    # -- inspection ---------------------------------------------------------
    def log(self, limit: int = 20) -> list[str]:
        """Return recent commit subject lines."""
        r = self._git(["log", f"-{limit}", "--pretty=%s"])
        if r.returncode != 0:
            return []
        return [line for line in r.stdout.splitlines() if line.strip()]
