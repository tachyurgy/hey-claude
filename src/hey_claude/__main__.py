"""Enable ``python -m hey_claude`` as an entry point (used by the .app + launchd)."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
