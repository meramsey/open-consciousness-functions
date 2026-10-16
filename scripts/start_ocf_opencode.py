#!/usr/bin/env python3
"""Start a new OCF OpenCode process with the native LSP tool; never restarts a backend."""

from ocf_launch import launch

if __name__ == "__main__":
    raise SystemExit(launch("opencode", __file__))
