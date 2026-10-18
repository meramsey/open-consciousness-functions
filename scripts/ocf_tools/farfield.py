"""Optional Farfield background-audio synthesis integration.

OCF treats Farfield (https://github.com/txus/farfield) as an optional external
engine. This module detects it on PATH, constructs its public CLI commands, and
degrades gracefully with installation guidance when it is absent. No internal
Farfield APIs are hardcoded.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from .paths import REPO_ROOT, workspace_run

FARFIELD_REPOSITORY = "https://github.com/txus/farfield"
FARFIELD_COMPATIBLE_REVISION = "019fb804f3b274359e13e8cc9ca3b8fcaf9701f3"


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
        result = workspace_run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if result.returncode == 0:
            version = (result.stdout or result.stderr).strip() or None
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
    result = workspace_run([status.executable, *args], check=False, text=True, capture_output=True)
    # Older public CLIs print parser errors while returning zero. A package
    # version alone cannot distinguish the pre/post best-effort implementations.
    if "unknown fidelity 'best-effort'" in (result.stdout or "") + (result.stderr or ""):
        result.returncode = result.returncode or 1
        result.stderr = (result.stderr or "") + (
            "\nInstalled Farfield cannot parse best-effort presets. Install the optional "
            f"engine at {FARFIELD_REPOSITORY}@{FARFIELD_COMPATIBLE_REVISION} in a "
            "separate environment and select its CLI on PATH; see docs/BACKGROUND_AUDIO.md. "
            "Do not relabel the preset as measured-tape.\n"
        )
    return result


class OCFFarfieldMissing(RuntimeError):
    """Raised when a command requires Farfield but it is not installed."""


def farfield_preset_dirs() -> list[Path]:
    """Directories holding Farfield session YAMLs, in priority order.

     Farfield's wheel ships no presets (``RECORD`` has zero entries for them);
     they live in the source checkout that PEP 610 ``direct_url.json`` records.
     OCF therefore resolves a preset name against, in order:

    1. ``OCF_FARFIELD_PRESETS_DIR`` (``os.pathsep``-separated), when set;
    2. ``audio/background/presets/farfield/`` - the upstream-mirrored presets OCF
        commits, so a build depends on nothing outside the repository;
    3. ``audio/background/presets/`` - OCF-authored sessions composed from those
        mirrors (searched after the mirrors, so a mirror always wins a name
        clash);
    4. ``<farfield source checkout>/presets`` - an extension tier that supplies
       any name the repository does not carry.

     The committed copies are authoritative because a build must be
     reproducible from the repository alone; the checkout can differ between
     machines or Farfield versions. ``OCF_FARFIELD_PRESETS_DIR`` only *raises*
     priority - the committed tier always stays in the chain, so an override can
     shadow a preset but never make a committed one unreachable.
    """
    override = os.environ.get("OCF_FARFIELD_PRESETS_DIR", "")
    dirs = [Path(part).expanduser() for part in override.split(os.pathsep) if part.strip()]
    presets_root = REPO_ROOT / "audio" / "background" / "presets"
    dirs.append(presets_root / "farfield")
    dirs.append(presets_root)
    dirs.extend(_source_preset_dirs())
    return dirs


def _source_preset_dirs() -> list[Path]:
    """`<farfield source checkout>/presets` for the installed distribution.

    The wheel excludes presets, so they only exist in the checkout Farfield was
    installed from. ``direct_url.json`` (PEP 610) records that checkout. The
    launcher script's shebang points at the venv interpreter, whose
    ``lib/python*/site-packages`` holds the dist-info.
    """
    executable = shutil.which("farfield")
    if not executable:
        return []
    try:
        first = Path(executable).read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return []
    match = re.match(r"#!\s*(\S+)", first)
    if not match:
        return []
    interpreter = Path(match.group(1))
    # <venv>/bin/python -> <venv>
    prefixes = [interpreter.parent.parent] if interpreter.parent.name == "bin" else []
    for prefix in prefixes:
        for dist in sorted((prefix / "lib").glob("python*/site-packages/farfield-*.dist-info")):
            record = dist / "direct_url.json"
            if not record.is_file():
                continue
            try:
                metadata = json.loads(record.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(metadata, dict) or not isinstance(metadata.get("url"), str):
                continue
            try:
                url = urlparse(metadata["url"])
            except ValueError:
                continue
            if url.scheme != "file" or url.netloc not in ("", "localhost"):
                continue
            # Use url2pathname to correctly handle Windows file URIs (e.g., file:///C:/path)
            path = url2pathname(url.path)
            presets = Path(path) / "presets"
            if presets.is_dir():
                return [presets]
    return []


def resolve_preset(name: str) -> Path | None:
    """Resolve a Farfield preset name or path to a session YAML on disk.

    A value that is already a path is used as-is. Otherwise ``name`` is looked
    up by stem across :func:`farfield_preset_dirs`: explicit overrides, committed
    OCF presets, then optional source-checkout extensions.
    """
    candidate = Path(name).expanduser()
    if candidate.suffix in (".yaml", ".yml") and candidate.is_file():
        return candidate
    for directory in farfield_preset_dirs():
        for suffix in (".yaml", ".yml"):
            hit = directory / f"{name}{suffix}"
            if hit.is_file():
                return hit
    return None


def preset_search_report(name: str) -> str:
    """Human-readable account of where a preset name was looked for."""
    lines = [f"preset {name!r} was not found. Searched:"]
    for directory in farfield_preset_dirs():
        lines.append(f"  {directory}{' (exists)' if directory.is_dir() else ' (missing)'}")
    lines.append(
        "Set OCF_FARFIELD_PRESETS_DIR to a directory of Farfield session YAMLs, "
        "or add the preset under audio/background/presets/farfield/."
    )
    return "\n".join(lines)


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
