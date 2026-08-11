"""Pytest fixtures: build a temp dir with sample archives via 7z.exe."""
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

from archive_extractor.config import Settings
from archive_extractor.constants import EXIT_OK

_CREATE_NO_WINDOW = 0x08000000


def _run_7z(args: list[str]) -> None:
    subprocess.run(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_CREATE_NO_WINDOW,
        check=True,
    )


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def seven_zip(settings: Settings) -> Path:
    sz = settings.seven_zip
    assert sz.exists(), f"7z.exe not found at {sz}; install 7-Zip to run tests"
    return sz


@pytest.fixture
def sample_folder(tmp_path: Path, seven_zip: Path) -> Path:
    """A temp folder with plain + encrypted archives under ``src``."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "plain.txt").write_text("plain content", encoding="utf-8")
    (src / "secret.txt").write_text("top secret", encoding="utf-8")
    (src / "other.txt").write_text("other secret", encoding="utf-8")

    # Plain ZIP.
    zp = src / "plain.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(src / "plain.txt", "plain.txt")

    # Encrypted 7z (header-encrypted), password "Pass111".
    enc1 = src / "solvable.7z"
    _run_7z(
        [str(seven_zip), "a", str(enc1), str(src / "secret.txt"),
         "-pPass111", "-y", "-mhe=on"]
    )

    # Encrypted 7z, password "Unknown999" (not in any test vault).
    enc2 = src / "locked.7z"
    _run_7z(
        [str(seven_zip), "a", str(enc2), str(src / "other.txt"),
         "-pUnknown999", "-y", "-mhe=on"]
    )
    return src


@pytest.fixture
def vault(tmp_path: Path):
    from archive_extractor.core.password_manager import PasswordVault

    vault = PasswordVault(tmp_path / "vault")
    vault.open()
    return vault
