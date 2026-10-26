"""Optional Farfield background-audio synthesis integration.

OCF treats Farfield (https://github.com/txus/farfield) as an optional external
engine. This module detects it on PATH, constructs its public CLI commands, and
degrades gracefully with installation guidance when it is absent. No internal
Farfield APIs are hardcoded.
"""

from __future__ import annotations

import inspect
import json
import os
import re
import shlex
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


def _runtime_fingerprint() -> dict:
    """Run in the launcher's interpreter; hash installed and actually resolved code."""
    import ast
    import csv
    import hashlib
    import importlib.metadata as metadata
    import importlib.util
    import json
    import sys
    import sysconfig
    from io import StringIO
    from pathlib import Path

    from packaging.requirements import Requirement

    launcher = Path(sys.argv[1])
    sys.path[0] = str(launcher.parent)  # Match console-script imports, not OCF.
    hashes, signatures = {}, {}

    def fingerprint(path):
        path = Path(path).resolve()
        if not path.is_file():
            return
        if path.suffix == ".pyc":
            raise ValueError("bytecode-only implementation cannot authorize verified reuse")
        before = path.stat()
        signature = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        if signatures.get(str(path)) == signature:
            return
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.stat()
        if signature != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ValueError("engine input changed while fingerprinting")
        hashes[str(path)] = digest.hexdigest()
        signatures[str(path)] = signature

    engine = metadata.distribution("farfield")
    entry = next(
        e for e in engine.entry_points if e.group == "console_scripts" and e.name == "farfield"
    )
    # Only standard console stubs can be probed without executing custom setup.
    tree = ast.parse(launcher.read_text(encoding="utf-8-sig"))
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    if (
        len(imports) != 1
        or imports[0].module != entry.module
        or [(item.name, item.asname) for item in imports[0].names] != [(entry.attr, None)]
    ):
        raise ValueError("unverified console entry point")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            (item.name not in {"sys", "re"} or item.asname) for item in node.names
        ):
            raise ValueError("custom launcher imports")
        if isinstance(node, ast.Call) and ast.unparse(node.func) not in {
            entry.attr,
            "sys.exit",
            "re.sub",
            "sys.argv[0].endswith",
        }:
            raise ValueError("custom launcher calls")
        if isinstance(node, ast.Assign) and any(
            ast.unparse(target) != "sys.argv[0]" for target in node.targets
        ):
            raise ValueError("custom launcher assignment")
        if isinstance(
            node,
            (
                ast.AugAssign,
                ast.AnnAssign,
                ast.NamedExpr,
                ast.Delete,
                ast.FunctionDef,
                ast.ClassDef,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.With,
                ast.AsyncWith,
                ast.Try,
                ast.comprehension,
            ),
        ):
            raise ValueError("custom launcher setup")
    pending, seen, packages = [("farfield", frozenset())], set(), {}
    while pending:
        name, extras = pending.pop()
        normalized = name.lower().replace("_", "-").replace(".", "-")
        if (normalized, extras) in seen:
            continue
        seen.add((normalized, extras))
        distribution = metadata.distribution(name)
        files = distribution.files
        # Python 3.12's files property omits missing RECORD entries.
        record = distribution.read_text("RECORD")
        if record is not None:
            files = [metadata.PackagePath(row[0]) for row in csv.reader(StringIO(record)) if row]
        if files is None:
            raise ValueError("installed distribution has no file inventory")
        packages[normalized] = distribution.version
        roots = {entry.module.split(".")[0]} if normalized == "farfield" else set()
        for file in files:
            if "__pycache__" in file.parts:
                continue
            path = Path(distribution.locate_file(file))
            if not path.is_file():
                raise ValueError("installed engine/dependency file is missing")
            fingerprint(path)
            root = file.parts[0].removesuffix(".py")
            if root.isidentifier():
                roots.add(root)
        for root in roots:
            spec = importlib.util.find_spec(root)
            if spec is None:
                raise ValueError("engine/dependency import cannot be resolved")
            if spec.origin and spec.origin.endswith(".pyc"):
                raise ValueError("bytecode-only import cannot authorize verified reuse")
            if spec.origin not in (None, "built-in", "frozen"):
                fingerprint(spec.origin)
            for directory in spec.submodule_search_locations or ():
                for path in sorted(Path(directory).rglob("*")):
                    if "__pycache__" not in path.parts:
                        fingerprint(path)
        for requirement in distribution.requires or ():
            requirement = Requirement(requirement)
            if requirement.marker is None or any(
                requirement.marker.evaluate({"extra": extra}) for extra in (extras or {""})
            ):
                pending.append((requirement.name, frozenset(requirement.extras)))
    fingerprint(sys.executable)
    library = Path(sysconfig.get_config_var("LIBDIR") or "") / (
        sysconfig.get_config_var("LDLIBRARY") or ""
    )
    fingerprint(library)
    return {
        "python": sys.version,
        "platform": sys.platform,
        "packages": packages,
        "implementation_sha256": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
    }


def engine_identity() -> dict | None:
    """Unknown launchers/runtimes disable verified reuse, never guess from presets."""
    from .utils import sha256_of_file

    status = check_farfield()
    if not status.available or not status.executable:
        return None
    executable = Path(status.executable).resolve()
    try:
        with executable.open("rb") as stream:
            header = stream.read(4096).split(b"\n", 1)[0].decode("utf-8")
        if not header.startswith("#!"):
            return None
        command = shlex.split(header[2:].strip(), posix=os.name != "nt")
        interpreter = Path(command[0].strip('"'))
        if not interpreter.is_absolute() or not interpreter.is_file():
            return None
        # env/shell launchers cannot prove which Python imports the engine.
        if not interpreter.name.lower().startswith("python"):
            return None
        probe = inspect.getsource(_runtime_fingerprint)
        result = workspace_run(
            [
                str(interpreter),
                *command[1:],
                "-c",
                "import json\n" + probe + "\nprint(json.dumps(_runtime_fingerprint()))",
                str(executable),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode:
            return None
        runtime = json.loads(result.stdout)
        if not isinstance(runtime, dict) or not re.fullmatch(
            r"[a-f0-9]{64}", runtime.get("implementation_sha256", "")
        ):
            return None
        return {
            "version": status.version,
            "executable": sha256_of_file(executable),
            "runtime": runtime,
        }
    except (OSError, ValueError, TypeError, IndexError, subprocess.SubprocessError):
        return None


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


class OCFFarfieldFailed(RuntimeError):
    """A public engine command failed; callers must propagate a failure status."""


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
    diagnostic = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise OCFFarfieldFailed(
            f"farfield describe failed (exit {result.returncode}):\n{diagnostic}"
        )
    return f"$ farfield describe {preset}\n" + diagnostic


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
        raise OCFFarfieldFailed(
            f"farfield render failed (exit {result.returncode}):\n"
            + (result.stdout or "")
            + (result.stderr or "")
        )
    return f"Rendered to {output}\n$ farfield {' '.join(command)}"


def list_background_presets() -> str:
    """Return `farfield list` output (or guidance when absent)."""
    try:
        result = run_farfield(["list"])
    except OCFFarfieldMissing as exc:
        return str(exc)
    return (result.stdout or result.stderr) + "\n(OCF presets live in audio/background/presets/)"
