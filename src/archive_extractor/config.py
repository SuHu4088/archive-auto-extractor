"""Settings model and persistence.

The settings live in ``config.json`` next to ``run.py``. User-specific paths
may be stored in ``config.local.json`` (git-ignored) which overrides the
tracked defaults — this keeps secrets / machine-specific paths out of Git.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from .constants import SEVEN_ZIP_DEFAULT, SUPPORTED_EXT, UNSOLVED_SUBFOLDER

log = logging.getLogger(__name__)

# Config files ---------------------------------------------------------------
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
_LOCAL_CONFIG_PATH = _CONFIG_PATH.parent / "config.local.json"


@dataclass
class UISettings:
    """Persisted UI state (window geometry, etc.)."""
    window_geometry: str | None = None


@dataclass
class Settings:
    """Strongly-typed view of ``config.json``.

    Fields mirror the schema documented in the plan. Use ``load()`` /
    ``save()`` rather than touching the file directly.
    """
    version: int = 1
    seven_zip_path: str = SEVEN_ZIP_DEFAULT
    extraction_output_root: str = ""
    scan_extensions: list[str] = field(default_factory=lambda: list(SUPPORTED_EXT))
    create_same_name_subfolder: bool = True
    delete_original_after_success: bool = False
    confirm_before_delete: bool = True
    password_module_enabled: bool = False
    vault_path: str = "~/.archive_password_vault"
    move_unsolved_to_subfolder: bool = True
    unsolved_subfolder_name: str = UNSOLVED_SUBFOLDER
    unsolved_location: str = "output_root"  # "output_root" | "beside_archive"
    max_threads: int = 1
    theme: str = "dark"
    log_level: str = "INFO"
    ui: UISettings = field(default_factory=UISettings)

    # -- Path helpers --------------------------------------------------------
    @property
    def seven_zip(self) -> Path:
        """Resolved, expanded path to ``7z.exe``."""
        return Path(os.path.expandvars(self.seven_zip_path)).expanduser()

    @property
    def output_root(self) -> Path:
        """Resolved output root; falls back to empty Path when unset."""
        raw = self.extraction_output_root.strip()
        if not raw:
            return Path()
        return Path(os.path.expandvars(raw)).expanduser()

    @property
    def vault_dir(self) -> Path:
        return Path(os.path.expandvars(self.vault_path)).expanduser()

    # -- Serialization ------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        """Build a Settings, tolerating missing/extra keys in the file."""
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        # Nested UISettings
        if "ui" in filtered and isinstance(filtered["ui"], dict):
            filtered["ui"] = UISettings(**{
                k: v for k, v in filtered["ui"].items()
                if k in {f.name for f in fields(UISettings)}
            })
        return cls(**filtered)


def load() -> Settings:
    """Load settings from ``config.json`` with ``config.local.json`` override.

    Missing keys are filled from the dataclass defaults; a missing file
    triggers a write of defaults (so the file always exists afterwards).
    """
    data: dict[str, Any] = {}
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("config.json unreadable (%s); using defaults", exc)
    else:
        log.info("config.json missing; writing defaults")
        settings = Settings()
        save(settings)
        return settings

    # Local override (git-ignored, machine-specific).
    if _LOCAL_CONFIG_PATH.exists():
        try:
            local = json.loads(_LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
            data = {**data, **local}
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("config.local.json unreadable (%s); ignoring", exc)

    settings = Settings.from_dict(data)
    return settings


def save(settings: Settings, local: bool = False) -> None:
    """Atomically persist settings.

    ``local=True`` writes to ``config.local.json`` (git-ignored) — use this
    for machine-specific paths the user picks at runtime so the tracked
    ``config.json`` stays generic.
    """
    target = _LOCAL_CONFIG_PATH if local else _CONFIG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(settings.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, target)


def validate(settings: Settings) -> list[str]:
    """Return a list of human-readable validation problems (empty if ok)."""
    problems: list[str] = []
    sz = settings.seven_zip
    if not sz.exists():
        problems.append(f"7z.exe not found at: {sz}")
    if settings.delete_original_after_success and not settings.confirm_before_delete:
        # Allowed but risky — surface as an informational note rather than error.
        log.warning("Auto-delete is enabled with confirmation disabled.")
    if settings.max_threads < 1:
        problems.append("max_threads must be >= 1")
    return problems
