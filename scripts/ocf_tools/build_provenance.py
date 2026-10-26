"""Attach a portable, checksummed build receipt to a private listening export."""

from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath

from .audition_exports import _artifact
from .utils import OCFError, read_json_object, sha256_of_file, write_text_atomic


def _portable(value):
    if isinstance(value, dict):
        for child in value.values():
            _portable(child)
    elif isinstance(value, list):
        for child in value:
            _portable(child)
    elif isinstance(value, str) and (
        Path(value).is_absolute() or PureWindowsPath(value).drive or PureWindowsPath(value).root
    ):
        raise OCFError("absolute filesystem path in portable build provenance")


def attach_build_provenance(export: str | Path, provenance: dict) -> dict:
    root = Path(export).expanduser().resolve()
    manifest_path = root / "manifest.json"
    manifest = read_json_object(manifest_path)
    if manifest.get("kind") != "private-audition-export":
        raise OCFError("build provenance attaches only to private audition exports")
    _portable(provenance)
    text = json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path = root / "build-provenance.json"
    if path.exists() and path.read_text(encoding="utf-8") != text:
        raise OCFError("refusing to replace different build provenance")
    if not path.exists():
        write_text_atomic(path, text, overwrite=False)
    artifact = {**_artifact(path), "path": path.name}
    existing = manifest.get("artifacts", {}).get("build_provenance")
    if existing and existing != artifact:
        raise OCFError("export manifest already refers to different build provenance")
    manifest.setdefault("artifacts", {})["build_provenance"] = artifact
    manifest["build_provenance"] = {
        "path": path.name,
        "size_bytes": artifact["size_bytes"],
        "sha256": artifact["sha256"],
    }
    write_text_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    if sha256_of_file(path) != artifact["sha256"]:
        raise OCFError("build provenance checksum read-back failed")
    return artifact


def attach_audio_quality(export: str | Path, quality: dict) -> dict:
    """Attach read-only measurements without assigning a mastering target."""
    root = Path(export).expanduser().resolve()
    manifest_path = root / "manifest.json"
    manifest = read_json_object(manifest_path)
    if manifest.get("kind") != "private-audition-export":
        raise OCFError("audio quality attaches only to private audition exports")
    _portable(quality)
    text = json.dumps(quality, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path = root / "audio-quality.json"
    if path.exists() and path.read_text(encoding="utf-8") != text:
        raise OCFError("refusing to replace different audio quality evidence")
    if not path.exists():
        write_text_atomic(path, text, overwrite=False)
    artifact = {**_artifact(path), "path": path.name}
    existing = manifest.get("artifacts", {}).get("audio_quality")
    if existing and existing != artifact:
        raise OCFError("export manifest already refers to different audio quality evidence")
    manifest.setdefault("artifacts", {})["audio_quality"] = artifact
    manifest["audio_quality"] = {
        "path": path.name,
        "size_bytes": artifact["size_bytes"],
        "sha256": artifact["sha256"],
    }
    write_text_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    if sha256_of_file(path) != artifact["sha256"]:
        raise OCFError("audio quality checksum read-back failed")
    return artifact
