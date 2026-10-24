"""Platform-neutral, opt-in native setup; never install optional engines/models."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

from .paths import REPO_ROOT, workspace_run

CORE_REQUIREMENTS = ["PyYAML>=6.0", "jsonschema>=4.18", "referencing>=0.30"]
PIP_REQUIREMENT = "pip==26.2.0"


def setup_plan(prefix: Path, *, system: str | None = None, root: Path = REPO_ROOT) -> dict:
    prefix = prefix.expanduser().resolve()
    if prefix.exists() and not (prefix / "pyvenv.cfg").is_file():
        raise ValueError(
            "setup target already exists and is not a virtual environment; choose an unused path"
        )
    if not (root / "scripts/ocf.py").is_file():
        raise ValueError(
            "native bootstrap needs a source checkout; packaged OCF is already installed"
        )
    windows = (system or platform.system()) == "Windows"
    interpreter = prefix / ("Scripts/python.exe" if windows else "bin/python")
    return {
        "schema_version": "1.0",
        "dry_run": True,
        "venv": str(prefix),
        "reuse": prefix.exists(),
        "interpreter": str(interpreter),
        "commands": ([] if prefix.exists() else [[sys.executable, "-m", "venv", str(prefix)]])
        + [
            [
                str(interpreter),
                "-m",
                "pip",
                "install",
                "--only-binary=:all:",
                "--upgrade",
                PIP_REQUIREMENT,
            ],
            [str(interpreter), "-m", "pip", "install", *CORE_REQUIREMENTS],
            [str(interpreter), str(root / "scripts/ocf.py"), "doctor", "--json"],
        ],
        "preserved": [
            "existing configuration",
            "custom models",
            "reference material",
            "recordings",
        ],
        "optional_installs": [],
        "hint": "Use your OS/package manager for Python>=3.11; optional audio engines/models are separate explicit installs",
    }


def apply_setup(plan: dict, *, runner=None) -> dict:
    runner = runner or workspace_run
    if sys.version_info < (3, 11):  # noqa: UP036 - standalone bootstrap can start on an older interpreter
        raise ValueError("run native setup using Python>=3.11")
    commands = plan["commands"]
    for index, command in enumerate(commands):
        # Validate an existing environment before installing any dependencies.
        if index == 0 and plan["reuse"]:
            result = runner(
                [
                    plan["interpreter"],
                    "-c",
                    "import sys; print('.'.join(map(str,sys.version_info[:2])))",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode or tuple(map(int, result.stdout.strip().split("."))) < (3, 11):
                raise ValueError(
                    "existing environment is incompatible; choose another target rather than overwrite it"
                )
        result = runner(command, capture_output=True, text=True, timeout=600)
        if result.returncode:
            raise RuntimeError(f"setup step failed: {command}: {result.stderr[-1500:]}")
    return {**plan, "dry_run": False, "completed": True, "doctor": json.loads(result.stdout)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Idempotent native core setup; dry-run by default")
    parser.add_argument("--venv", type=Path, default=Path(".venv"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = setup_plan(args.venv)
        print(json.dumps(apply_setup(plan) if args.apply else plan, indent=2))
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))
    return 0
