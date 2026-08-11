"""Archive Auto-Extractor package.

A desktop application that recursively scans a folder for archives
(ZIP / RAR / 7Z), extracts them, verifies integrity via CRC, and optionally
deletes the originals only after verification succeeds. Password-protected
archives are skipped by default until the user enables the password vault.
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
