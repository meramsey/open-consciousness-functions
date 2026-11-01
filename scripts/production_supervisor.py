#!/usr/bin/env python3
"""CLI entry point outside the package, avoiding stdlib locale shadowing."""

from ocf_tools.production_supervisor import main

if __name__ == "__main__":
    raise SystemExit(main())
