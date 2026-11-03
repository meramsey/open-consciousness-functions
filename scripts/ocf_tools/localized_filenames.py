"""Read-only L4 rename planning through existing stable-ID locale resources.

No file is renamed here. L3 must first resolve historical destination collisions;
activation needs a checked logical-path successor and atomic manifest switch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import unicodedata
from copy import deepcopy

import yaml

from .artifact_names import safe_component
from .locale import LocaleCatalog
from .paths import REPO_ROOT
from .utils import OCFError, write_bytes_atomic, write_text_atomic, yaml_safe_load

LEDGER = "function-content/editorial/localized-filenames-005.json"


def readable_filename(function_id: str, title: str) -> str:
    if not re.fullmatch(r"OCF-[A-Z]{3}-[0-9]{3}", function_id):
        raise OCFError("localized filename requires a stable function ID")
    if any(
        unicodedata.category(char) == "Cs"
        or unicodedata.bidirectional(char)
        in {"LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI"}
        for char in title
    ):
        raise OCFError("localized filename title contains unsafe Unicode controls")
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
    physical = {}
    for path in pack.path.iterdir():
        key = collision_key(path.name)
        if key in physical:
            raise OCFError("case-insensitive existing locale path collision: " + path.name)
        physical[key] = path
    owned = {collision_key(name): owner for owner, name in pack.localized_function_files.items()}
    destinations = set()
    mapping, blockers, historical_reuse = [], [], []
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
        target = physical.get(key, pack.path / new)
        if target.exists() and new != old:
            from .locale_history import before_structural
            from .utils import yaml_safe_load

            stub = yaml_safe_load(target.read_text(encoding="utf-8"))
            logical = "locales/" + pack.locale + "/" + new
            if (
                isinstance(stub, dict)
                and stub.get("kind") == "immutable-historical-locale-reference"
                and stub.get("logical_path") == logical
            ):
                predecessor = before_structural(root, logical, target.read_text(encoding="utf-8"))
                if hashlib.sha256(predecessor.encode("utf-8")).hexdigest() != stub["sha256"]:
                    raise OCFError("historical destination identity drift: " + new)
                historical_reuse.append(
                    {"function_id": identity, "path": new, "archive": stub["archive"]}
                )
            else:
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
        "verified_historical_destination_reuse": historical_reuse,
        "required_before_apply": "L3 verified; exact historical logical-path resolver; staged target files and atomic manifest switch; Git rename detection and final gates",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locale", default="en-US")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            apply_filenames(locale=args.locale)
            if args.apply
            else filename_plan(locale=args.locale),
            indent=2,
            ensure_ascii=False,
        )
    )


def apply_filenames(root=REPO_ROOT, *, locale="en-US"):
    from .dev_jobs import lock

    with lock("localized-source-migration", wait=False) as acquired:
        if not acquired:
            raise OCFError("another localized source migration owns the lease")
        return _apply_filenames(root.resolve(), locale=locale)


def _apply_filenames(root, *, locale):
    from .locale_history import FILENAMES_SHA256
    from .localized_retirement import historical_stub

    ledger_path = root / LEDGER
    if ledger_path.exists():
        if hashlib.sha256(ledger_path.read_bytes()).hexdigest() != FILENAMES_SHA256:
            raise OCFError("immutable filename ledger drift")
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
        for name, row in data["files"].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != row["after_sha256"]:
                raise OCFError("filename migration already exists with changed source: " + name)
            if (
                hashlib.sha256((root / row["archive"]).read_bytes()).hexdigest()
                != row["before_sha256"]
            ):
                raise OCFError("filename archive drift: " + name)
        for name, checksum in data["created_resources"].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != checksum:
                raise OCFError("renamed localized resource changed; preserve edits: " + name)
        return {"status": "already-renamed; no writes", "count": data["count"]}
    plan = filename_plan(root, locale=locale)
    if plan["blockers"]:
        raise OCFError(
            "filename destinations require reconciliation: " + json.dumps(plan["blockers"])
        )
    rows = [row for row in plan["mapping"] if row["old_path"] != row["new_path"]]
    if not rows:
        return {"status": "no implemented resources require renaming", "count": 0}
    tag = plan["locale"]
    manifest_name = "locales/" + tag + "/manifest.yaml"
    manifest = yaml_safe_load((root / manifest_name).read_text(encoding="utf-8"))
    successor = deepcopy(manifest)
    path_map = {row["old_path"]: row["new_path"] for row in rows}
    for resource in successor["resources"]:
        logical = "locales/" + tag + "/" + resource["file"]
        if logical in path_map:
            resource["file"] = path_map[logical].rsplit("/", 1)[-1]
    new_files, outputs, originals = {}, {}, {}
    for row in rows:
        old, new = root / row["old_path"], root / row["new_path"]
        if (
            old.is_symlink()
            or not old.resolve().is_relative_to(root)
            or not new.resolve().is_relative_to(root)
        ):
            raise OCFError("unsafe localized rename path")
        raw = old.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["source_sha256"]:
            raise OCFError("localized source changed before rename: " + row["old_path"])
        originals[row["old_path"]] = raw
        new_files[row["new_path"]] = raw
        archive = "function-content/editorial/historical-locales/005/" + tag + "/" + old.name
        outputs[row["old_path"]] = historical_stub(
            row["old_path"], archive, row["source_sha256"]
        ).encode("utf-8")
        if new.exists():
            # Only the separately verified historical stub may be replaced.
            allowed = {entry["path"] for entry in plan["verified_historical_destination_reuse"]}
            if new.name not in allowed or new.is_symlink():
                raise OCFError("refusing to overwrite rename destination: " + row["new_path"])
            originals[row["new_path"]] = new.read_bytes()
            outputs[row["new_path"]] = raw
    originals[manifest_name] = (root / manifest_name).read_bytes()
    outputs[manifest_name] = yaml.safe_dump(
        successor, sort_keys=False, allow_unicode=True, width=100
    ).encode("utf-8")
    files = {}
    for name, raw in originals.items():
        archive = (
            "function-content/editorial/historical-locales/005/"
            + tag
            + "/"
            + name.rsplit("/", 1)[-1]
        )
        destination = root / archive
        if (
            destination.exists()
            or destination.is_symlink()
            or not destination.resolve().is_relative_to(root)
        ):
            raise OCFError("refusing unsafe/existing filename archive: " + archive)
        files[name] = {
            "archive": archive,
            "before_sha256": hashlib.sha256(raw).hexdigest(),
            "after_sha256": hashlib.sha256(outputs[name]).hexdigest(),
        }
    ledger = {
        "schema_version": "1.0",
        "stage": "L4",
        "locale": tag,
        "count": len(rows),
        "files": files,
        "mapping": rows,
        "created_resources": {
            name: hashlib.sha256(raw).hexdigest() for name, raw in new_files.items()
        },
    }
    for name, raw in originals.items():
        archive = root / files[name]["archive"]
        archive.parent.mkdir(parents=True, exist_ok=True)
        with archive.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    # Write the replay record before publishing any new active resource. All
    # ordinary destinations use exclusive publication; only verified history
    # stubs are replaceable. The manifest switches only after targets exist.
    write_text_atomic(
        ledger_path, json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", overwrite=False
    )
    for name, raw in new_files.items():
        write_bytes_atomic(root / name, raw, overwrite=name in originals)
    write_bytes_atomic(root / manifest_name, outputs[manifest_name])
    for row in rows:
        write_bytes_atomic(root / row["old_path"], outputs[row["old_path"]])
    return {
        "status": "renamed",
        "count": len(rows),
        "locale": tag,
        "historical_destinations_reused": len(plan["verified_historical_destination_reuse"]),
        "ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    main()
