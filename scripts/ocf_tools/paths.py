"""Repository path helpers for OCF.

All commands assume they run from any location and resolve the repository
root from the project layout itself, so the CLI works from nested directories.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SCHEMAS_DIR = REPO_ROOT / "schemas"
FUNCTIONS_DIR = REPO_ROOT / "functions"
LEGACY_DIR = REPO_ROOT / "legacy"
PROPOSALS_DIR = REPO_ROOT / "proposals"
AUDIO_DIR = REPO_ROOT / "audio"
AUDIO_BACKGROUND_DIR = AUDIO_DIR / "background"
AUDIO_IMPLEMENTATIONS_DIR = AUDIO_DIR / "implementations"
AUDIO_MANIFESTS_DIR = AUDIO_DIR / "manifests"
AUDIO_SCRIPTS_DIR = AUDIO_DIR / "scripts"
AUDIO_RENDERED_DIR = AUDIO_DIR / "rendered"
AUDIO_VOICES_DIR = AUDIO_DIR / "voices"
VOICES_PROFILES_DIR = AUDIO_VOICES_DIR / "profiles"
TEMPLATES_DIR = REPO_ROOT / "templates"
REFERENCES_DIR = REPO_ROOT / "references"
DOCS_DIR = REPO_ROOT / "docs"

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
