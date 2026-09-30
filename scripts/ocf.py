#!/usr/bin/env python3
"""OCF CLI — use as `python3 scripts/ocf.py` or via the `ocf` console script."""

import sys
from pathlib import Path

# Ensure the tools package is importable regardless of how this is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ocf_tools.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
