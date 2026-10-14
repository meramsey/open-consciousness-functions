"""Repository path helpers for OCF.

All commands assume they run from any location and resolve the repository
root from the project layout itself, so the CLI works from nested directories.
"""

from __future__ import annotations

import errno
import math
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any


def resolve_data_root(
    module_file: Path, override: str | None = None, bundled: Path | None = None
) -> Path:
    if override:
        path = Path(override).expanduser().resolve()
        if not (path / "schemas").is_dir() or not (path / "functions").is_dir():
            raise RuntimeError(
                "OCF_DATA_ROOT must contain schemas/ and functions/; use a complete writable OCF checkout"
            )
        return path
    source = module_file.resolve().parent.parent.parent
    if (source / "schemas").is_dir() and (source / "functions").is_dir():
        return source
    packaged = bundled if bundled is not None else Path(str(files("ocf_tools").joinpath("data")))
    if (packaged / "schemas").is_dir() and (packaged / "functions").is_dir():
        return packaged
    raise RuntimeError(
        "OCF runtime data unavailable; reinstall the wheel or set OCF_DATA_ROOT to a complete checkout"
    )


REPO_ROOT = resolve_data_root(Path(__file__), os.environ.get("OCF_DATA_ROOT"))


def work_root() -> Path:
    """Resolve OCF's private working root, relative overrides from the repository."""
    override = os.environ.get("OCF_WORK_DIR")
    if override:
        configured = Path(override).expanduser()
        candidate = (configured if configured.is_absolute() else REPO_ROOT / configured).resolve()
    else:
        candidate = (REPO_ROOT / ".ocf-work").resolve()
    if candidate == Path(candidate.anchor) or candidate == REPO_ROOT:
        raise RuntimeError(
            "OCF_WORK_DIR must be a dedicated directory, not a filesystem or repository root"
        )
    if candidate.exists() and not candidate.is_dir():
        raise RuntimeError(f"OCF working path is not a directory: {candidate}")
    if not override and not candidate.is_relative_to(REPO_ROOT):
        raise RuntimeError("the default OCF working directory must remain inside the repository")
    return candidate


def work_path(area: str, *parts: str) -> Path:
    """Return a contained path in one of OCF's standard local work areas."""
    if area not in {"tmp", "cache", "renders", "logs"}:
        raise ValueError(f"unknown OCF work area: {area}")
    root = work_root()
    result = root.joinpath(area, *parts).resolve()
    if not result.is_relative_to(root):
        raise ValueError("OCF workspace path escapes its configured root")
    return result


def ensure_workspace() -> dict[str, Path]:
    """Create the private workspace layout and verify it is writable."""
    layout = {area: work_path(area) for area in ("tmp", "cache", "renders", "logs")}
    for path in layout.values():
        path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise OSError(f"OCF workspace location is not a directory: {path}")
    if not os.access(layout["tmp"], os.W_OK | os.X_OK):
        raise OSError(f"OCF temporary workspace is not writable: {layout['tmp']}")
    return layout


def workspace_temp_directory(prefix: str = "ocf-") -> Path:
    """Create a marked temporary directory owned by OCF under ``.ocf-work/tmp``."""
    layout = ensure_workspace()
    safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "-", prefix)
    if not safe_prefix.startswith("ocf-"):
        safe_prefix = "ocf-" + safe_prefix
    path = Path(tempfile.mkdtemp(prefix=safe_prefix, dir=layout["tmp"]))
    (path / ".ocf-owned").write_text(uuid.uuid4().hex + "\n", encoding="ascii")
    return path


def workspace_temp_file(prefix: str = "ocf-", suffix: str = "") -> tuple[int, Path]:
    """Allocate an OCF scratch file under the private workspace."""
    directory = workspace_temp_directory(prefix="ocf-temp-file-")
    safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "-", prefix)
    if not safe_prefix.startswith("ocf-"):
        safe_prefix = "ocf-" + safe_prefix
    descriptor, filename = tempfile.mkstemp(prefix=safe_prefix, suffix=suffix, dir=directory)
    return descriptor, Path(filename)


def cleanup_workspace_temp(path: str | Path, *, force: bool = False) -> bool:
    """Remove only a marked OCF temp directory; successful scratch can be retained."""
    target = Path(path).resolve()
    temporary_root = work_path("tmp").resolve()
    if target.parent != temporary_root or not target.name.startswith("ocf-"):
        raise ValueError(f"refusing to clean outside OCF temporary workspace: {target}")
    marker = target / ".ocf-owned"
    if not marker.is_file():
        raise ValueError(f"refusing to clean an unmarked OCF temporary directory: {target}")
    retain = os.environ.get("OCF_KEEP_WORK", "").strip().lower() in {"1", "true", "yes", "on"}
    if retain and not force:
        return False
    shutil.rmtree(target)
    return True


def cleanup_workspace(
    older_than_seconds: float = 24 * 60 * 60, *, dry_run: bool = False
) -> list[Path]:
    """Clean only stale, directly-owned OCF temp directories; preserve logs/renders/cache."""
    if not math.isfinite(older_than_seconds) or older_than_seconds < 0:
        raise ValueError("older_than_seconds must be nonnegative")
    temporary_root = work_path("tmp").resolve()
    if not temporary_root.is_dir():
        return []
    cutoff = datetime.now(UTC).timestamp() - older_than_seconds
    removed = []
    for child in temporary_root.iterdir():
        resolved = child.resolve()
        if (
            resolved.parent != temporary_root
            or not resolved.is_dir()
            or not resolved.name.startswith("ocf-")
            or not (resolved / ".ocf-owned").is_file()
            or resolved.stat().st_mtime > cutoff
        ):
            continue
        if not dry_run:
            cleanup_workspace_temp(resolved, force=True)
        removed.append(resolved)
    return removed


def publish_workspace_temp_directory(source: str | Path, destination: str | Path) -> Path:
    """Publish a verified temp directory, supporting cross-filesystem outputs safely."""
    source_path = Path(source).resolve()
    destination_path = Path(destination).expanduser().resolve()
    temporary_root = work_path("tmp").resolve()
    marker = source_path / ".ocf-owned"
    if (
        source_path.parent != temporary_root
        or not source_path.name.startswith("ocf-")
        or not marker.is_file()
    ):
        raise ValueError("publish source is not an OCF-owned temporary directory")
    if destination_path.exists():
        raise FileExistsError(f"refusing to replace existing OCF output: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        try:
            os.replace(source_path, destination_path)
        except OSError as exc:
            if exc.errno != errno.EXDEV:
                raise
            try:
                shutil.copytree(source_path, destination_path)
            except BaseException:
                if (destination_path / ".ocf-owned").is_file():
                    shutil.rmtree(destination_path, ignore_errors=True)
                raise
            (destination_path / ".ocf-owned").unlink(missing_ok=True)
            cleanup_workspace_temp(source_path)
        else:
            (destination_path / ".ocf-owned").unlink(missing_ok=True)
    except BaseException:
        raise
    return destination_path


def workspace_environment(
    extra: dict[str, str] | None = None, *, temporary_directory: Path | None = None
) -> dict[str, str]:
    """Build subprocess-only temp/cache settings without changing OCF's environment."""
    layout = ensure_workspace()
    env = os.environ.copy()
    if extra:
        env.update(extra)
    temp = str(temporary_directory or layout["tmp"])
    env.update({"TMPDIR": temp, "TMP": temp, "TEMP": temp, "XDG_CACHE_HOME": str(layout["cache"])})
    return env


def workspace_run(command: Any, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
    """Run an external process with the OCF-local temp/cache environment."""
    scratch = workspace_temp_directory(prefix="ocf-subprocess-")
    run_id = scratch.name
    kwargs["env"] = workspace_environment(kwargs.get("env"), temporary_directory=scratch)
    try:
        result = subprocess.run(command, *args, **kwargs)
    except BaseException as exc:
        record_workspace_failure(
            run_id, f"subprocess failed: {type(exc).__name__}: {exc}; retained scratch: {scratch}"
        )
        raise
    if result.returncode == 0:
        cleanup_workspace_temp(scratch)
    else:
        detail = getattr(result, "stderr", b"") or getattr(result, "stdout", b"") or b""
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", "replace")
        record_workspace_failure(
            run_id,
            f"subprocess exited {result.returncode}: {str(detail)[-2000:]}; retained scratch: {scratch}",
        )
    return result


def record_workspace_failure(run_id: str, details: str) -> Path:
    """Retain a diagnostic log for a failed or interrupted OCF render."""
    log_path = work_path("logs", f"{run_id}.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat()
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(f"[{timestamp}] {details.rstrip()}\n")
    return log_path


def unique_run_id(label: str) -> str:
    """Return a path-safe run label for collision-resistant retained outputs."""
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip(".-") or "render"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return f"{stem}-{stamp}-{uuid.uuid4().hex[:8]}"


SCHEMAS_DIR = REPO_ROOT / "schemas"
FUNCTIONS_DIR = REPO_ROOT / "functions"
LEGACY_DIR = REPO_ROOT / "legacy"
PROPOSALS_DIR = REPO_ROOT / "proposals"
FUNCTION_CONTENT_DIR = REPO_ROOT / "function-content"
COMMAND_PROCEDURES_FILE = FUNCTION_CONTENT_DIR / "command-procedures.yaml"
AUDIO_DIR = REPO_ROOT / "audio"
AUDIO_BACKGROUND_DIR = AUDIO_DIR / "background"
AUDIO_IMPLEMENTATIONS_DIR = AUDIO_DIR / "implementations"
AUDIO_MANIFESTS_DIR = AUDIO_DIR / "manifests"
AUDIO_SCRIPTS_DIR = AUDIO_DIR / "scripts"
AUDIO_RENDERED_DIR = work_path("renders")
AUDIO_VOICES_DIR = AUDIO_DIR / "voices"
VOICES_PROFILES_DIR = AUDIO_VOICES_DIR / "profiles"
TEMPLATES_DIR = REPO_ROOT / "templates"
REFERENCES_DIR = REPO_ROOT / "references"
DOCS_DIR = REPO_ROOT / "docs"
LOCALES_DIR = REPO_ROOT / "locales"
COMMAND_PROCEDURES_FILE = REPO_ROOT / "function-content" / "command-procedures.yaml"

GENERATED_FILES = (
    "FUNCTION_INDEX.md",
    "function-index.json",
    "function-index.csv",
    "legacy/hplus-command-map.json",
    "legacy/hplus-command-map.csv",
    "docs/COMMAND_REVIEW.md",
    "docs/AVAILABILITY_MATRIX.md",
    "docs/REIMPLEMENTATION_ROADMAP.md",
    "docs/SAFETY_MATRIX.md",
    "docs/AUDIO_IMPLEMENTATION_INDEX.md",
    "docs/BACKGROUND_AUDIO_INDEX.md",
    "docs/FUNCTION_EXTRACTION_REVIEW.md",
)

GENERATED_HEADER = "GENERATED FILE — DO NOT EDIT DIRECTLY"


def schema_path(name: str) -> Path:
    """Return the path to a schema by base name (e.g. 'function.schema.json')."""
    return SCHEMAS_DIR / name


def domain_path(domain: str) -> Path:
    """Return the function directory for a primary domain."""
    return FUNCTIONS_DIR / domain


def all_function_dirs() -> list[Path]:
    """Return every domain directory that may hold function records."""
    if not FUNCTIONS_DIR.is_dir():
        return []
    return sorted(d for d in FUNCTIONS_DIR.iterdir() if d.is_dir())


def ensure_dir(path: Path) -> Path:
    """Create a directory (and parents) if missing; return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path
