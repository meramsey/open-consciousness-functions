"""Read-only discovery of OCF's project-local Python and optional render tools."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .paths import REPO_ROOT


def _user_home() -> Path:
    """Prefer the OS account home if a host harness overrides HOME for sessions."""
    try:
        import pwd

        account_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
        if account_home.is_dir():
            return account_home
    except (AttributeError, KeyError, OSError):
        pass
    return Path.home()


def _python_version(executable: Path) -> tuple[str | None, bool]:
    try:
        probe = subprocess.run(
            [str(executable), "--version"], capture_output=True, text=True, timeout=4, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, False
    match = re.search(r"Python\s+(\d+)\.(\d+)\.(\d+)", probe.stdout + probe.stderr)
    if probe.returncode or not match:
        return None, False
    version = tuple(map(int, match.groups()))
    return ".".join(map(str, version)), version >= (3, 11, 0)


def project_python(root: Path = REPO_ROOT) -> dict:
    """Report an existing project interpreter; never creates or installs one."""
    root = Path(root).resolve()
    configured = os.environ.get("OCF_PYTHON")
    candidates = []
    if configured:
        configured_path = Path(configured).expanduser()
        candidates.append(
            configured_path
            if configured_path.is_absolute() or configured_path.parent != Path(".")
            else Path(shutil.which(configured) or configured)
        )
    candidates.extend(
        [
            root / ".venv/bin/python",
            root / ".venv/bin/python3",
            root / ".venv/Scripts/python.exe",
        ]
    )
    version_file = root / ".python-version"
    if version_file.is_file():
        version = version_file.read_text(encoding="utf-8").strip()
        pyenv_root = Path(os.environ.get("PYENV_ROOT", _user_home() / ".pyenv"))
        for name in ("python", "python3"):
            candidates.append(pyenv_root / "versions" / version / "bin" / name)
    for name in ("python3", "python"):
        if located := shutil.which(name):
            candidates.append(Path(located))
    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_file() or not os.access(resolved, os.X_OK):
            continue
        seen.add(resolved)
        version, supported = _python_version(resolved)
        if supported:
            return {
                "status": "ready",
                "executable": str(resolved),
                "source": (
                    "OCF_PYTHON"
                    if configured and candidate == candidates[0]
                    else "project .venv"
                    if ".venv" in candidate.parts
                    else "pyenv .python-version"
                    if version_file.is_file() and version in version_file.read_text().strip()
                    else "PATH/active Python"
                ),
                "version": version,
            }
    if configured:
        return {
            "status": "configured-python-invalid",
            "executable": configured,
            "reason": "OCF_PYTHON is missing, cannot run, or is older than Python 3.11",
        }
    return {
        "status": "project-venv-not-found",
        "executable": str(Path(sys.executable).resolve()),
        "source": "active interpreter (not a repository .venv)",
        "version": sys.version.split()[0],
        "hint": "Use the existing project .venv/bin/python, or set OCF_PYTHON; discovery does not create environments.",
    }


def _candidate_executables(binary: str, root: Path) -> list[Path]:
    candidates = []
    located = shutil.which(binary)
    if located:
        candidates.append(Path(located))
    if binary == "piper":
        configured = os.environ.get("OCF_PIPER_EXECUTABLE")
        if configured:
            candidates.insert(0, Path(configured).expanduser())
        candidates.extend(
            [
                root / ".venv/bin/piper",
                root / ".venv/Scripts/piper.exe",
                _user_home() / ".local/bin/piper",
            ]
        )
    unique = []
    seen = set()
    for candidate in candidates:
        try:
            path = candidate.expanduser().resolve()
        except OSError:
            continue
        if path not in seen and path.is_file() and os.access(path, os.X_OK):
            seen.add(path)
            unique.append(path)
    return unique


def _piper_python_environment(executable: Path) -> dict:
    """Validate the executable's shebang interpreter and configured import paths."""
    try:
        first_line = executable.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return {"status": "unverified", "reason": "cannot read executable launcher"}
    if not first_line.startswith("#!"):
        return {"status": "unverified", "reason": "Piper launcher has no readable Python shebang"}
    words = first_line[2:].strip().split()
    if not words:
        return {"status": "unverified", "reason": "empty executable shebang"}
    if Path(words[0]).name == "env":
        if len(words) < 2:
            return {"status": "unverified", "reason": "env shebang does not name Python"}
        interpreter = shutil.which(words[-1])
    else:
        interpreter = words[0]
    if not interpreter or not Path(interpreter).is_file():
        return {"status": "broken", "reason": "Piper shebang interpreter is unavailable"}

    # Use the already-installed Python to query site paths. Import checks are
    # filesystem-only; no package installation or model download is attempted.
    probe = subprocess.run(
        [interpreter, "-c", "import site,sys; print(sys.version.split()[0]); print(site.getusersitepackages())"],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(_user_home())},
        timeout=5,
        check=False,
    )
    if probe.returncode:
        return {"status": "broken", "reason": "Piper interpreter failed a read-only version probe"}
    lines = probe.stdout.splitlines()
    version = lines[0] if lines else None
    user_site = Path(lines[1]).expanduser() if len(lines) > 1 else None
    site_paths = []
    executable_prefix = executable.parent.parent
    python_minor = ".".join(version.split(".")[:2]) if version else None
    for path in (
        user_site,
        executable_prefix / "lib" / f"python{python_minor}" / "site-packages"
        if python_minor
        else None,
    ):
        if path and (path / "piper" / "__init__.py").is_file():
            resolved_path = str(path.resolve())
            if resolved_path not in site_paths:
                site_paths.append(resolved_path)
    env = os.environ.copy()
    if site_paths:
        existing = env.get("PYTHONPATH", "")
        paths = site_paths + ([item for item in existing.split(os.pathsep) if item] if existing else [])
        env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(paths))
    check = subprocess.run(
        [interpreter, "-c", "import piper, importlib.metadata as m; print(m.version('piper-tts'))"],
        capture_output=True,
        text=True,
        env=env,
        timeout=5,
        check=False,
    )
    return {
        "status": "ready" if check.returncode == 0 else "broken",
        "interpreter": str(Path(interpreter).resolve()),
        "python_version": version,
        "package_version": check.stdout.strip() if check.returncode == 0 else None,
        "package_paths": site_paths,
        "subprocess_env": {"PYTHONPATH": env["PYTHONPATH"]} if site_paths else {},
        "reason": None if check.returncode == 0 else "Piper CLI package is not importable by its configured interpreter",
    }


def resolve_executable(binary: str, *, root: Path = REPO_ROOT) -> dict:
    """Resolve a working executable from PATH or established project/user-local paths."""
    candidates = _candidate_executables(binary, Path(root).resolve())
    if not candidates:
        return {
            "status": "not-found",
            "binary": binary,
            "executable": None,
            "reason": "not on PATH or in the project's existing local tool locations",
        }
    for executable in candidates:
        if binary != "piper":
            return {
                "status": "ready",
                "binary": binary,
                "executable": str(executable),
                "source": "PATH" if shutil.which(binary) == str(executable) else "existing local installation",
            }
        runtime = _piper_python_environment(executable)
        if runtime["status"] == "ready":
            return {
                "status": "ready",
                "binary": binary,
                "executable": str(executable),
                "source": "PATH" if shutil.which(binary) == str(executable) else "existing local installation",
                "runtime": runtime,
            }
    runtime = _piper_python_environment(candidates[0])
    return {
        "status": "broken",
        "binary": binary,
        "executable": str(candidates[0]),
        "reason": runtime.get("reason", "installed executable is unusable"),
        "runtime": runtime,
    }


def discover_environment(*, root: Path = REPO_ROOT, voice_profile: dict | None = None) -> dict:
    """Summarize resolved tools and a chosen profile's configured Amy/model assets."""
    root = Path(root).resolve()
    node_file = root / ".nvmrc"
    node_expected = node_file.read_text(encoding="utf-8").strip() if node_file.is_file() else None
    node_executable = shutil.which("node")
    node_version = None
    if node_executable:
        try:
            probe = subprocess.run(
                [node_executable, "--version"], capture_output=True, text=True, timeout=4, check=False
            )
            if probe.returncode == 0:
                node_version = probe.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    report = {
        "python": project_python(root),
        "tools": {name: resolve_executable(name, root=root) for name in ("ffmpeg", "ffprobe", "piper")},
        "node": {
            "executable": node_executable,
            "version": node_version,
            "expected_version": node_expected,
            "status": "not-installed"
            if not node_executable
            else "version-mismatch"
            if node_expected and node_version and node_version.lstrip("v") != node_expected.lstrip("v")
            else "ready",
            "version_file": str(node_file) if node_expected else None,
            "note": "Uses the active nvm/PATH selection; OCF never changes global nvm defaults.",
        },
        "model": None,
    }
    if voice_profile and voice_profile.get("backend") == "piper":
        configured = voice_profile.get("piper_model")
        if voice_profile.get("model"):
            from .custom_voices import model_path

            model = Path(model_path(voice_profile))
        else:
            model = Path(os.path.expandvars(os.path.expanduser(configured))).resolve() if configured else None
        config = Path(str(model) + ".json") if model else None
        report["model"] = {
            "status": "ready" if model and model.is_file() and config and config.is_file() else "missing",
            "model_path": str(model) if model else None,
            "config_path": str(config) if config else None,
            "model_sha256": _sha256(model) if model and model.is_file() else None,
            "config_sha256": _sha256(config) if config and config.is_file() else None,
        }
    return report


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
