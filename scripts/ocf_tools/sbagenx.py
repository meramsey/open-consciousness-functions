"""Optional SBaGenX background-audio synthesis integration.

OCF treats SBaGenX (https://github.com/lm7137/SBaGenX) as an optional external
background engine alongside Farfield. This module detects the `sbagenx` CLI on
PATH, builds its public CLI commands, and degrades gracefully with install
guidance when it is absent. No internal SBaGenX libraries are hardcoded; only
the public command-line interface is used.

The `sbagenx` CLI renders brainwave-entrainment beds from `.sbg` sequence
files or built-in programs (`-p drop|slide|sigmoid|curve`). OCF presets are
authored as `.sbg` sequence files; ``render`` runs them start-to-end into a
WAV file.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .paths import REPO_ROOT

SBAGENX_REPOSITORY = "https://github.com/lm7137/SBaGenX"

# Built-in programs the CLI ships (`-p <name>`), described from the manual.
BUILTIN_PROGRAMS: dict[str, str] = {
    "drop": "scheduled carrier/beat glide; levels 00..99 and depth letters a..l",
    "slide": "long alpha slide session that drops the carrier toward zero",
    "sigmoid": "function-driven beat/pulse sigmoid curve",
    "curve": "sessions driven by a .sbgf curve function file",
}


@dataclass
class SbagenxStatus:
    available: bool
    executable: str | None = None
    version: str | None = None


def check_sbagenx() -> SbagenxStatus:
    """Detect whether the `sbagenx` CLI is available on PATH."""
    executable = shutil.which("sbagenx")
    if not executable:
        return SbagenxStatus(available=False)
    version: str | None = None
    try:
        result = subprocess.run(
            [executable, "-h"], capture_output=True, text=True, timeout=8
        )
        head = (result.stdout or result.stderr).splitlines()[:4]
        for line in head:
            match = re.search(
                r"SbaGenX\s+(?:version\s+)?v?([0-9][0-9a-zA-Z._-]*)",
                line,
                re.IGNORECASE,
            )
            if match:
                version = match.group(1)
                break
    except (OSError, subprocess.TimeoutExpired):
        pass
    return SbagenxStatus(available=True, executable=executable, version=version)


def installation_guidance() -> str:
    """Message shown when SBaGenX is not installed."""
    return (
        "sbagenx is not installed or not on PATH. OCF treats SBaGenX as an "
        "optional external background engine, so everything else keeps working.\n"
        f"  Repository: {SBAGENX_REPOSITORY}\n"
        "  Install the CLI (Ubuntu .deb or build via linux-build-all.sh) and "
        "re-run detection so it is on PATH:  sbagenx -h\n"
        "  OCF only calls the public CLI (`sbagenx -h`, `sbagenx -D FILE`, "
        "`sbagenx -SE -Wo OUT FILE`) and does not vendor its source."
    )


def run_sbagenx(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run an sbagenx CLI command, raising a clear error when it is missing."""
    status = check_sbagenx()
    if not status.available or not status.executable:
        raise OCFSbagenxMissing(installation_guidance())
    return subprocess.run(
        [status.executable, *args], check=False, text=True, capture_output=True
    )


class OCFSbagenxMissing(RuntimeError):
    """Raised when a command requires SBaGenX but it is not installed."""


def list_programs() -> str:
    """Return a description of SBaGenX generation programs (or guidance)."""
    status = check_sbagenx()
    if not status.available:
        return "  " + installation_guidance().replace("\n", "\n  ")
    lines = [f"SBaGenX built-in programs ({status.executable}):"]
    for name, note in BUILTIN_PROGRAMS.items():
        lines.append(f"  -p {name:<9} {note}")
    lines.append(
        "  sequence   .sbg session files; OCF presets live in audio/background/presets/"
    )
    return "\n".join(lines)


def describe_preset(preset: str) -> str:
    """Return `sbagenx -D <preset>` output (or guidance when absent).

    ``-D`` dumps the interpreted sequence instead of playing it.
    """
    try:
        result = run_sbagenx(["-D", preset])
    except OCFSbagenxMissing as exc:
        return str(exc)
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if result.returncode != 0:
        return f"sbagenx describe failed (exit {result.returncode}):\n{stderr or stdout}"
    return f"$ sbagenx -D {preset}\n{stdout}"


def render_preset(
    preset: str,
    *,
    output: Path | None = None,
    sample_rate: int = 44100,
) -> str:
    """Render an `.sbg` sequence start-to-end into a WAV file.

    Returns a human-readable result string. Never crashes when SBaGenX is gone.
    """
    if not output:
        stem = Path(preset).stem or preset.replace(":", "-")
        output = REPO_ROOT / "audio" / "background" / "rendered" / f"{stem}.wav"
    command = [
        "-SE",
        "-q",
        "1",
        "-r",
        str(sample_rate),
        "-Q",
        "-Wo",
        str(output),
        preset,
    ]
    try:
        result = run_sbagenx(command)
    except OCFSbagenxMissing as exc:
        return str(exc)
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if not output.exists():
        return (
            f"sbagenx render failed (exit {result.returncode}):\n"
            f"{stderr or stdout}\n$ sbagenx {' '.join(command)}"
        )
    return f"Rendered to {output}\n$ sbagenx {' '.join(command)}"