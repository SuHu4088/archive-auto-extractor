"""Password vault manager — the *single* accessor for the vault file.

Design (requirement 11):

* The vault JSON lives at ``~/.archive_password_vault/passwords.json`` (outside
  the project folder).
* :class:`PasswordVault` is the ONLY object that reads/writes it. Reads return
  copies of entries (never the live list); writes go through atomic
  ``os.replace`` and then ``VaultGit.commit``.
* Deletes require a two-step confirm token (``prepare_delete`` →
  ``delete_password``) so no code path can "directly delete".
* Every mutation produces a descriptive Git commit; session open/close also
  commit.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import threading
from pathlib import Path
from typing import Iterator

from ..constants import VAULT_FILENAME
from ..models.vault_entry import VaultEntry
from .vault_git import VaultGit

log = logging.getLogger(__name__)


def _empty_vault() -> dict:
    return {"version": 1, "metadata": {}, "passwords": [], "audit": []}


class PasswordVault:
    """Thread-safe, Git-tracked password vault."""

    def __init__(self, vault_dir: Path, git: VaultGit | None = None):
        self.vault_dir = Path(vault_dir)
        self.vault_file = self.vault_dir / VAULT_FILENAME
        self._git = git or VaultGit(self.vault_dir)
        self._lock = threading.Lock()
        self._pending_delete_tokens: dict[str, str] = {}
        self._session_open = False

    # -- bootstrap ----------------------------------------------------------
    def open(self) -> None:
        """Ensure the repo + file exist and log a session-open commit."""
        with self._lock:
            self._git.ensure_repo()
            if not self.vault_file.exists():
                self._write_locked(_empty_vault(), commit_msg="Vault session opened")
            self._session_open = True
            # Session-open commit (descriptive, per requirement 11).
            self._git.commit("Vault session opened", allow_empty=True)

    def close(self, stats: dict[str, int] | None = None) -> None:
        """Log a session-close commit with usage stats."""
        with self._lock:
            if stats:
                msg = f"Vault session closed (tried={stats.get('tried', 0)} ok={stats.get('ok', 0)})"
            else:
                msg = "Vault session closed"
        self._git.commit(msg, allow_empty=True)
        self._session_open = False

    # -- read ---------------------------------------------------------------
    def _read_locked(self) -> dict:
        if not self.vault_file.exists():
            return _empty_vault()
        try:
            return json.loads(self.vault_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.error("vault unreadable (%s); treating as empty", exc)
            return _empty_vault()

    def list_entries(self, enabled_only: bool = False) -> list[VaultEntry]:
        """Return copies of all entries (optionally enabled only)."""
        with self._lock:
            data = self._read_locked()
        entries = [VaultEntry.from_dict(d) for d in data.get("passwords", [])]
        if enabled_only:
            entries = [e for e in entries if e.enabled]
        return entries

    def iter_passwords_for(self, archive_name: str) -> Iterator[tuple[VaultEntry, str]]:
        """Yield ``(entry_copy, password)`` in try-order.

        Order: enabled first, then by descending ``use_count``, then by
        descending ``last_used`` (most-recently-successful first).
        """
        entries = self.list_entries(enabled_only=True)
        entries.sort(
            key=lambda e: (-e.use_count, e.last_used or "", e.label),
            reverse=False,
        )
        # We want descending use_count and descending last_used.
        entries.sort(key=lambda e: (e.last_used or ""), reverse=True)
        entries.sort(key=lambda e: e.use_count, reverse=True)
        for entry in entries:
            yield entry, entry.value

    # -- write helpers ------------------------------------------------------
    def _write_locked(self, data: dict, commit_msg: str) -> None:
        """Atomically write the vault file then commit. Caller holds the lock."""
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.vault_file.with_suffix(self.vault_file.suffix + ".tmp")
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, self.vault_file)
        self._git.commit(commit_msg)

    # -- mutations ----------------------------------------------------------
    def add_password(self, value: str, label: str = "", notes: str = "") -> VaultEntry:
        with self._lock:
            data = self._read_locked()
            entry = VaultEntry.new(value=value, label=label, notes=notes)
            data.setdefault("passwords", []).append(entry.to_dict())
            self._write_locked(data, f"Add password '{entry.label}'")
        log.info("added password '%s'", entry.label)
        return entry

    def update_password(
        self, entry_id: str, value: str | None = None, label: str | None = None
    ) -> VaultEntry | None:
        with self._lock:
            data = self._read_locked()
            for d in data.get("passwords", []):
                if d.get("id") == entry_id:
                    if value is not None:
                        d["value"] = value
                    if label is not None:
                        d["label"] = label
                    updated = VaultEntry.from_dict(d)
                    self._write_locked(data, f"Update password '{updated.label}'")
                    log.info("updated password '%s'", updated.label)
                    return updated
        return None

    def set_enabled(self, entry_id: str, enabled: bool) -> bool:
        with self._lock:
            data = self._read_locked()
            for d in data.get("passwords", []):
                if d.get("id") == entry_id:
                    d["enabled"] = enabled
                    label = d.get("label", "")
                    state = "enabled" if enabled else "disabled"
                    self._write_locked(data, f"Toggle password '{label}' -> {state}")
                    log.info("password '%s' %s", label, state)
                    return True
        return False

    # -- delete (two-step) --------------------------------------------------
    def prepare_delete(self, entry_id: str) -> str | None:
        """Return a one-time confirm token required by :meth:`delete_password`.

        The token is ephemeral (in-memory only) so a stray commit of vault data
        can never silently include a deletion.
        """
        with self._lock:
            data = self._read_locked()
            if not any(d.get("id") == entry_id for d in data.get("passwords", [])):
                return None
            token = secrets.token_urlsafe(8)
            self._pending_delete_tokens[entry_id] = token
            return token

    def delete_password(self, entry_id: str, token: str) -> bool:
        """Delete the entry, but only if ``token`` matches the prepared one.

        A wrong token does NOT consume the prepared token, so the caller may
        retry with the correct one.
        """
        with self._lock:
            expected = self._pending_delete_tokens.get(entry_id)
            if not expected or not secrets.compare_digest(expected, token):
                log.warning("delete denied for %s (bad/expired token)", entry_id)
                return False
            data = self._read_locked()
            label = "unknown"
            for d in data.get("passwords", []):
                if d.get("id") == entry_id:
                    label = d.get("label", "unknown")
                    break
            before = len(data.get("passwords", []))
            data["passwords"] = [
                d for d in data.get("passwords", []) if d.get("id") != entry_id
            ]
            if len(data["passwords"]) == before:
                self._pending_delete_tokens.pop(entry_id, None)
                return False
            self._write_locked(data, f"Delete password '{label}'")
            self._pending_delete_tokens.pop(entry_id, None)
            log.info("deleted password '%s' (%s)", label, entry_id)
            return True

    # -- usage tracking -----------------------------------------------------
    def record_success(self, entry_id: str, archive_name: str) -> None:
        with self._lock:
            data = self._read_locked()
            label = "unknown"
            for d in data.get("passwords", []):
                if d.get("id") == entry_id:
                    d["use_count"] = int(d.get("use_count", 0)) + 1
                    import time as _t

                    d["last_used"] = _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime())
                    label = d.get("label", "unknown")
                    break
            data.setdefault("audit", []).append(
                {"action": "success", "entry": label, "archive": archive_name}
            )
            self._write_locked(
                data, f"Record success for '{label}' on {archive_name}"
            )

    def record_failure_all(self, archive_name: str) -> None:
        with self._lock:
            data = self._read_locked()
            data.setdefault("audit", []).append(
                {"action": "all_failed", "archive": archive_name}
            )
            self._write_locked(data, f"All passwords failed for {archive_name}")

    # -- inspection ---------------------------------------------------------
    def commit_log(self, limit: int = 20) -> list[str]:
        """Return recent vault git commit subjects."""
        return self._git.log(limit)
