#!/usr/bin/env python3
"""Launch pinned Pyright from this checkout's venv without runtime installation."""

from ocf_launch import launch

if __name__ == "__main__":
    raise SystemExit(launch("python-lsp", __file__))
