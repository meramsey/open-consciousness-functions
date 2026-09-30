"""Indexing: discover and load all function, proposal, and audio records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import FunctionRecord, function_from_dict
from .paths import (
    AUDIO_IMPLEMENTATIONS_DIR,
    AUDIO_MANIFESTS_DIR,
    AUDIO_SCRIPTS_DIR,
    FUNCTIONS_DIR,
    REPO_ROOT,
    VOICES_PROFILES_DIR,
)
from .utils import OCFError, read_text, yaml_safe_load

PROPOSAL_STATUSES = (
    "draft",
    "review",
    "experimental",
    "accepted",
    "deprecated",
    "superseded",
    "rejected",
    "withdrawn",
)

PROPOSAL_DIR_STATE_MAP = {
    "draft": "draft",
    "review": "review",
    "accepted": "accepted",
    "rejected": "rejected",
    "withdrawn": "withdrawn",
}


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Parse a YAML file into a dict, raising a helpful error on failure."""
    try:
        data = yaml_safe_load(read_text(path))
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise OCFError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise OCFError(f"{path} does not contain a mapping at top level")
    return data


def discover_function_files() -> list[Path]:
    """Return every *.yaml/*.yml function record under functions/."""
    if not FUNCTIONS_DIR.is_dir():
        return []
    files: list[Path] = []
    for path in FUNCTIONS_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in (".yaml", ".yml"):
            files.append(path)
    return sorted(files)


def load_all_functions() -> list[FunctionRecord]:
    """Load and parse every function record, sorted by OCF id."""
    records: list[FunctionRecord] = []
    for path in discover_function_files():
        data = load_yaml_file(path)
        try:
            records.append(function_from_dict(data, path))
        except ValueError as exc:
            raise OCFError(str(exc)) from exc
    return sorted(records, key=lambda r: r.id)


def load_function_by_id(function_id: str) -> FunctionRecord | None:
    """Return the record with the given OCF id, or None."""
    for record in load_all_functions():
        if record.id == function_id:
            return record
    return None


def load_function_by_slug_or_id(query: str) -> FunctionRecord | None:
    """Match a record by slug or OCF id."""
    for record in load_all_functions():
        if record.id == query or record.slug == query:
            return record
    return None


def discover_proposal_files() -> list[Path]:
    """Return proposal markdown/yaml files under proposals/."""
    files: list[Path] = []
    for path in (REPO_ROOT / "proposals").rglob("*"):
        if path.is_file() and path.suffix.lower() in (".md", ".yaml", ".yml"):
            files.append(path)
    return sorted(files)


def count_proposals() -> int:
    """Number of proposal files (excluding README)."""
    return sum(1 for p in discover_proposal_files() if p.name.lower() != "readme.md")


def discover_audio_manifests() -> list[Path]:
    """Return audio implementation manifests (audio/manifests/*.yaml)."""
    if not AUDIO_MANIFESTS_DIR.is_dir():
        return []
    files = [p for p in AUDIO_MANIFESTS_DIR.rglob("*") if p.suffix.lower() in (".yaml", ".yml")]
    # Fall back to a companion directory if present
    if not files and AUDIO_IMPLEMENTATIONS_DIR.is_dir():
        files = [
            p for p in AUDIO_IMPLEMENTATIONS_DIR.rglob("*") if p.suffix.lower() in (".yaml", ".yml")
        ]
    return sorted(files)


def discover_background_manifests() -> list[Path]:
    """Return background-audio manifests (audio/background/manifests/*.yaml)."""
    base = REPO_ROOT / "audio" / "background" / "manifests"
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*") if p.suffix.lower() in (".yaml", ".yml"))


def discover_timed_transcripts() -> list[Path]:
    """Return OCF timed-transcript documents (audio/scripts/*.yaml)."""
    if not AUDIO_SCRIPTS_DIR.is_dir():
        return []
    return sorted(p for p in AUDIO_SCRIPTS_DIR.rglob("*") if p.suffix.lower() in (".yaml", ".yml"))


def discover_voice_profiles() -> list[Path]:
    """Return voice profiles (audio/voices/profiles/*.yaml)."""
    if not VOICES_PROFILES_DIR.is_dir():
        return []
    return sorted(
        p for p in VOICES_PROFILES_DIR.rglob("*") if p.suffix.lower() in (".yaml", ".yml")
    )


def load_audio_manifests() -> list[dict[str, Any]]:
    """Load audio-implementation manifests keyed by their id."""
    out = []
    for path in discover_audio_manifests():
        data = load_yaml_file(path)
        out.append(data)
    return out


def load_background_manifests() -> list[dict[str, Any]]:
    """Load background-audio manifests keyed by their id."""
    out = []
    for path in discover_background_manifests():
        data = load_yaml_file(path)
        out.append(data)
    return out


def load_voice_profiles() -> list[dict[str, Any]]:
    """Load all voice profiles from audio/voices/profiles/*.yaml."""
    out = []
    for path in discover_voice_profiles():
        data = load_yaml_file(path)
        out.append(data)
    return out


def find_audio_manifest(query: str) -> dict[str, Any] | None:
    """Find an audio-implementation manifest by exact id or path."""
    if "/" in query or query.endswith(".yaml"):
        candidate = REPO_ROOT / query if not Path(query).is_absolute() else Path(query)
        if candidate.is_file():
            return load_yaml_file(candidate)
    for manifest in load_audio_manifests():
        if manifest.get("id") == query.split(".")[0]:
            return manifest
    return None


def audio_implementations_for(function_id: str) -> list[dict[str, Any]]:
    """Return audio manifests that reference the given function id."""
    return [m for m in load_audio_manifests() if m.get("function_id") == function_id]


def background_presets_for(function_id: str, field: str = "functions") -> list[dict[str, Any]]:
    """Return background manifests that list the function under the given usage field."""
    return [
        m for m in load_background_manifests() if function_id in m.get("usage", {}).get(field, [])
    ]


def json_dump(data: Any) -> str:
    """Deterministic JSON serialization."""
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
