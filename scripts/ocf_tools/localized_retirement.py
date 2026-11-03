"""L3 dry-run classification of L2's explicitly superseded compatibility keys.

This module never removes files or changes active packs. Applying retirement
requires the completed L2 gates and a checked historical-resource successor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .locale import normalize_tag
from .paths import REPO_ROOT
from .utils import OCFError, yaml_safe_load


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def retirement_plan(root: Path = REPO_ROOT, *, locale: str = "en-US") -> dict:
    root = root.resolve()
    tag = normalize_tag(locale)
    if not tag:
        raise OCFError("retirement requires an explicit locale")
    directory = root / "locales" / tag
    manifest_path = directory / "manifest.yaml"
    if manifest_path.is_symlink() or not manifest_path.resolve().is_relative_to(root):
        raise OCFError("unsafe retirement manifest")
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest = yaml_safe_load(manifest_text)
    if manifest.get("locale") != tag:
        raise OCFError("retirement manifest locale mismatch")
    candidates, active_functions, shared, files = [], {}, [], set()
    for declaration in manifest.get("resources", []):
        name = declaration["file"]
        path = directory / name
        if (
            Path(name).name != name
            or path.is_symlink()
            or not path.resolve().is_relative_to(directory.resolve())
        ):
            raise OCFError("unsafe retirement resource: " + name)
        if name in files:
            raise OCFError("duplicate active retirement resource: " + name)
        files.add(name)
        text = path.read_text(encoding="utf-8")
        data = yaml_safe_load(text)
        if declaration["domain"] == "function":
            identity = data.get("function_id")
            if not identity or identity in active_functions:
                raise OCFError("missing or duplicate active function identity")
            active_functions[identity] = {"file": name, "sha256": sha(text)}
        superseded = declaration.get("superseded_keys", [])
        if not superseded:
            shared.append(
                {
                    "file": name,
                    "decision": "KEEP",
                    "reason": "active function/shared or unrelated resource; no L2 supersession contract",
                }
            )
            continue
        if declaration["domain"] == "function":
            raise OCFError("active function authority cannot be a retirement candidate")
        if sha(json.dumps(data, sort_keys=True, ensure_ascii=False)) != declaration.get(
            "compatibility_sha256"
        ):
            raise OCFError("read-only compatibility resource drift: " + name)
        entries = data.get("entries") or {}
        if len(superseded) != len(set(superseded)) or not set(superseded).issubset(entries):
            raise OCFError("invalid retirement key inventory: " + name)
        remaining = {key: value for key, value in entries.items() if key not in superseded}
        candidates.append(
            {
                "file": "locales/" + tag + "/" + name,
                "decision": "ARCHIVE" if not remaining else "KEEP_SHARED_RETIRE_SUPERSEDED_KEYS",
                "prior_purpose": declaration["domain"] + " locale compatibility resource",
                "retired_key_count": len(superseded),
                "retired_keys": sorted(superseded),
                "remaining_key_count": len(remaining),
                "remaining_keys": sorted(remaining),
                "source_sha256": sha(text),
                "historical_requirement": "preserve exact original bytes outside active locale namespace and add checked logical-path resolution before removal",
                "proposed_archive": "function-content/editorial/historical-locales/"
                + tag
                + "/"
                + name,
            }
        )
    return {
        "schema_version": "1.0",
        "stage": "L3 preparation only; no transformation applied",
        "locale": tag,
        "locale_status": manifest.get("status"),
        "manifest_sha256": sha(manifest_text),
        "active_function_count": len(active_functions),
        "active_functions": active_functions,
        "retirement_candidates": candidates,
        "retired_key_count": sum(row["retired_key_count"] for row in candidates),
        "retained_resources": shared,
        "immutable_records": "KEEP existing editorial, rights and defaults locks unchanged",
        "apply_blocker": "L2 integration and historical-resource successor must be verified first",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locale", default="en-US")
    args = parser.parse_args()
    print(json.dumps(retirement_plan(locale=args.locale), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
