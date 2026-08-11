"""Module execution entry: ``python -m archive_extractor``."""
import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
