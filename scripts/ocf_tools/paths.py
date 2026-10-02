"""Repository path helpers for OCF.

All commands assume they run from any location and resolve the repository
root from the project layout itself, so the CLI works from nested directories.
"""

from __future__ import annotations

import os
from importlib.resources import files
from pathlib import Path


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

SCHEMAS_DIR = REPO_ROOT / "schemas"
FUNCTIONS_DIR = REPO_ROOT / "functions"
LEGACY_DIR = REPO_ROOT / "legacy"
PROPOSALS_DIR = REPO_ROOT / "proposals"
AUDIO_DIR = REPO_ROOT / "audio"
AUDIO_BACKGROUND_DIR = AUDIO_DIR / "background"
AUDIO_IMPLEMENTATIONS_DIR = AUDIO_DIR / "implementations"
AUDIO_MANIFESTS_DIR = AUDIO_DIR / "manifests"
AUDIO_SCRIPTS_DIR = AUDIO_DIR / "scripts"
AUDIO_RENDERED_DIR = (
    AUDIO_DIR / "rendered" if (REPO_ROOT / "scripts").is_dir() else Path.home() / ".ocf/rendered"
)
AUDIO_VOICES_DIR = AUDIO_DIR / "voices"
VOICES_PROFILES_DIR = AUDIO_VOICES_DIR / "profiles"
TEMPLATES_DIR = REPO_ROOT / "templates"
REFERENCES_DIR = REPO_ROOT / "references"
DOCS_DIR = REPO_ROOT / "docs"
LOCALES_DIR = REPO_ROOT / "locales"

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
