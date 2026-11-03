"""Read-only L4 rename planning through existing stable-ID locale resources.

No file is renamed here. L3 must first resolve historical destination collisions;
activation needs a checked logical-path successor and atomic manifest switch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata

from .artifact_names import safe_component
from .locale import LocaleCatalog
from .paths import REPO_ROOT
from .utils import OCFError


def readable_filename(function_id: str, title: str) -> str:
    if not re.fullmatch(r"OCF-[A-Z]{3}-[0-9]{3}", function_id):
        raise OCFError("localized filename requires a stable function ID")
    suffix = safe_component(title, max_length=72)
    while len(suffix.encode("utf-8")) > 128:
        suffix = suffix[:-1].rstrip(" .-")
    if not suffix:
        raise OCFError("localized filename title is empty after length limiting")
    return function_id + "-" + suffix + ".yaml"


def collision_key(filename: str) -> str:
    return unicodedata.normalize("NFC", filename).casefold()


def filename_plan(root=REPO_ROOT, *, locale="en-US", catalog=None):
    root = root.resolve()
    catalog = catalog or LocaleCatalog(root / "locales")
    if catalog.problems:
        raise OCFError("invalid locale catalog: " + "; ".join(catalog.problems))
    pack = catalog.require(locale)
    owned = {collision_key(name): owner for owner, name in pack.localized_function_files.items()}
    destinations = set()
    mapping, blockers = [], []
    for identity, data in sorted(pack.localized_functions.items()):
        value = data.get("title") or {}
        if not isinstance(value.get("text"), str):
            raise OCFError(
                identity + ": consolidate literal localized title before filename migration"
            )
        old = pack.localized_function_files[identity]
        new = readable_filename(identity, value["text"])
        key = collision_key(new)
        if key in destinations:
            raise OCFError("case-insensitive localized filename collision: " + new)
        destinations.add(key)
        if key in owned and owned[key] != identity:
            raise OCFError("localized filename belongs to another active function: " + new)
        source = pack.path / old
        if source.is_symlink() or not source.resolve().is_relative_to(pack.path.resolve()):
            raise OCFError("unsafe localized rename source: " + old)
        target = pack.path / new
        if target.exists() and new != old:
            blockers.append(
                {
                    "function_id": identity,
                    "path": new,
                    "reason": "existing destination retained; resolve historical ownership before rename",
                }
            )
        mapping.append(
            {
                "function_id": identity,
                "locale": pack.locale,
                "old_path": "locales/" + pack.locale + "/" + old,
                "new_path": "locales/" + pack.locale + "/" + new,
                "original_logical_path": "locales/" + pack.locale + "/" + old,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        )
    return {
        "stage": "L4 dry-run only; no renames applied",
        "locale": pack.locale,
        "locale_status": pack.manifest.get("status"),
        "count": len(mapping),
        "filename_policy": "stable ID from YAML; NFC readable suffix; casefold collision key; 72characters/128UTF8bytes maximum suffix; Windows reserved/path characters sanitized by existing safe_component",
        "mapping": mapping,
        "blockers": blockers,
        "required_before_apply": "L3 verified; exact historical logical-path resolver; staged target files and atomic manifest switch; Git rename detection and final gates",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locale", default="en-US")
    args = parser.parse_args()
    print(json.dumps(filename_plan(locale=args.locale), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
