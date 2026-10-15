"""Project-local MCP launcher; selects .venv on POSIX or Windows without a global install."""

import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
interpreter = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not interpreter.is_file():
    raise SystemExit("Create .venv and install -e '.[mcp]' before enabling the OCF MCP server.")
os.execv(str(interpreter), [str(interpreter), str(root / "scripts/ocf.py"), "mcp"])
