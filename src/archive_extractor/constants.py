"""Application-wide constants.

Only constants live here — no runtime state, no I/O. This is the single
source of truth for default paths, supported extensions and fixed folder
names so that scanner / extractor / pipeline stay consistent.
"""
from __future__ import annotations

# Application identity --------------------------------------------------------
APP_NAME = "Archive Auto-Extractor"
APP_VERSION = "1.0.0"

# 7-Zip -----------------------------------------------------------------------
# Standard Windows install location; user may override in settings.
SEVEN_ZIP_DEFAULT = r"C:\Program Files\7-Zip\7z.exe"

# Password vault -------------------------------------------------------------
# Stored OUTSIDE the project folder (requirement 11) in the user's home dir.
VAULT_DIRNAME = ".archive_password_vault"
VAULT_FILENAME = "passwords.json"
VAULT_README_FILENAME = "README.md"

# Subfolder for archives whose password could not be cracked ----------------
UNSOLVED_SUBFOLDER = "password_protected_unsolved"

# Supported archive extensions (case-insensitive match) ----------------------
SUPPORTED_EXT = (".zip", ".rar", ".7z")

# 7-Zip exit codes (the subset we care about) --------------------------------
# Reference: 7-Zip docs. 0 = ok, 1 = warning, 2 = fatal error,
# 7 = command-line error, 255 = user stop / wrong password (context dependent).
EXIT_OK = 0
EXIT_WARNING = 1
EXIT_FATAL = 2
EXIT_CMDLINE_ERROR = 7
EXIT_WRONG_PASSWORD = 255

# Status strings emitted through the worker signals --------------------------
STATUS_OK = "ok"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"
STATUS_UNSOLVED = "unsolved"

# Stage labels for the status panel ------------------------------------------
STAGE_SCAN = "scan"
STAGE_DETECT = "detect"
STAGE_EXTRACT = "extract"
STAGE_VERIFY = "verify"
STAGE_FINALIZE = "finalize"
