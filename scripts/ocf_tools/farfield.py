"""Optional Farfield background-audio synthesis integration.

OCF treats Farfield (https://github.com/txus/farfield) as an optional external
engine. This module detects it on PATH, constructs its public CLI commands, and
degrades gracefully with installation guidance when it is absent. No internal
Farfield APIs are hardcoded.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .paths import REPO_ROOT

FARFIELD_REPOSITORY = "https://github.com/txus/farfield"


@dataclass
class FarfieldStatus:
    available: bool
    executable: str | None = None
    version: str | None = None


def check_farfield() -> FarfieldStatus:
    """Detect whether the `farfield` CLI is available on PATH."""
    executable = shutil.which("farfield")
    if not executable:
        return FarfieldStatus(available=False)
    version: str | None = None
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if result.returncode == 0:
            version = (result.stdout or result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return FarfieldStatus(available=True, executable=executable, version=version)


def installation_guidance() -> str:
    """Message shown when Farfield is not installed."""
    return (
        "farfield is not installed or not on PATH. OCF treats Farfield as an "
        "optional external engine, so everything else keeps working.\n"
        f"  Repository: {FARFIELD_REPOSITORY}\n"
        "  If you have a package manager install, run:  farfield --help\n"
        "  Once installed and on PATH, retry the command. OCF only calls the "
        "public CLI (`farfield list|describe|render`) and does not vendor its source."
    )


def run_farfield(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a Farfield CLI command, raising a clear error when it is missing."""
    status = check_farfield()
    if not status.available or not status.executable:
        raise OCFFarfieldMissing(installation_guidance())
    return subprocess.run(
        [status.executable, *args], check=False, text=True, capture_output=True
    )


class OCFFarfieldMissing(RuntimeError):
    """Raised when a command requires Farfield but it is not installed."""


def describe_preset(preset: str) -> str:
    """Return `farfield describe <preset>` output (or guidance when absent)."""
    try:
        result = run_farfield(["describe", preset])
    except OCFFarfieldMissing as exc:
        return str(exc)
    return f"$ farfield describe {preset}\n" + (result.stdout or result.stderr)


def render_preset(
    preset: str,
    *,
    output: Path | None = None,
    seed: int | None = None,
) -> str:
    """Render `farfield render <preset>` with optional --output and --seed.

    Returns a human-readable result string. Never crashes when Farfield is gone.
    """
    if not output:
        output = REPO_ROOT / "audio" / "background" / "rendered" / f"{preset.replace(':', '-')}.wav"
    command = ["render", preset, "--output", str(output)]
    if seed is not None:
        command.extend(["--seed", str(seed)])
    try:
        result = run_farfield(command)
    except OCFFarfieldMissing as exc:
        return str(exc)
    if result.returncode != 0:
        return f"farfield render failed (exit {result.returncode}):\n{result.stderr}"
    return f"Rendered to {output}\n$ farfield {' '.join(command)}"


def list_background_presets() -> str:
    """Return `farfield list` output (or guidance when absent)."""
    try:
        result = run_farfield(["list"])
    except OCFFarfieldMissing as exc:
        return str(exc)
    return (result.stdout or result.stderr) + "\n(OCF presets live in audio/background/presets/)"
