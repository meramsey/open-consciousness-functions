#!/usr/bin/env python3
"""Launch the existing OCF stdio server using this checkout's optional LSP extra."""

from ocf_launch import launch

if __name__ == "__main__":
    raise SystemExit(launch("lsp", __file__))
