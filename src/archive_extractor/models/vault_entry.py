"""Password vault entry model.

A :class:`VaultEntry` is one stored password. ``enabled`` allows the user to
keep a password on file without it being tried (requirement 10 toggle).
``use_count`` / ``last_used`` drive the try-order: enabled entries are tried
first, sorted by descending success count then recency.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


@dataclass
class VaultEntry:
    """A single password record in the vault."""
    id: str
    value: str
    label: str = ""
    enabled: bool = True
    use_count: int = 0
    created_at: str = ""
    last_used: str | None = None
    notes: str = ""

    @staticmethod
    def new(value: str, label: str = "", notes: str = "") -> "VaultEntry":
        return VaultEntry(
            id=str(uuid.uuid4()),
            value=value,
            label=label or value[:3] + "***",
            enabled=True,
            use_count=0,
            created_at=_now(),
            last_used=None,
            notes=notes,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "VaultEntry":
        return VaultEntry(
            id=data.get("id", str(uuid.uuid4())),
            value=data.get("value", ""),
            label=data.get("label", ""),
            enabled=bool(data.get("enabled", True)),
            use_count=int(data.get("use_count", 0)),
            created_at=data.get("created_at", ""),
            last_used=data.get("last_used"),
            notes=data.get("notes", ""),
        )

    def mark_used(self) -> None:
        self.use_count += 1
        self.last_used = _now()
