"""Entry point for the Archive Auto-Extractor application.

Run with:  python run.py
"""
import sys
from pathlib import Path

# Make the local ``archive_extractor`` package importable when running the
# script directly (no install step required).
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from archive_extractor.app import main

if __name__ == "__main__":
    sys.exit(main())
