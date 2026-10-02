"""Metadata-only voice packs, separate from external TTS profiles and assets."""

from __future__ import annotations

from pathlib import Path

from .indexes import load_yaml_file
from .paths import REPO_ROOT
from .utils import OCFError
from .validators import _load_schema, validate_against_schema

REGISTRY = REPO_ROOT / "audio/voices/registry"


def load_registry(root: Path | None = None) -> list[dict]:
    entries = []
    identifiers = set()
    for path in sorted((root or REGISTRY).glob("*.yaml")):
        data = load_yaml_file(path)
        errors = validate_against_schema(data, _load_schema("community-voice.schema.json"))
        if errors:
            raise OCFError("community voice metadata: " + " | ".join(errors))
        if data["id"] in identifiers:
            raise OCFError(f"duplicate community voice identity: {data['id']}")
        identifiers.add(data["id"])
        entries.append(data)
    return entries
