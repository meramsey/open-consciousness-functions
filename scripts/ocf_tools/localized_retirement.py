"""L3 dry-run classification of L2's explicitly superseded compatibility keys.

This module never removes files or changes active packs. Applying retirement
requires the completed L2 gates and a checked historical-resource successor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

import yaml

from .locale import normalize_tag
from .paths import REPO_ROOT
from .utils import OCFError, write_text_atomic, yaml_safe_load

LEDGER = "function-content/editorial/localized-retirement-004.json"


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
            active_functions[identity] = {
                "file": name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
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
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "historical_requirement": "preserve exact original bytes outside active locale namespace and add checked logical-path resolution before removal",
                "proposed_archive": "function-content/editorial/historical-locales/"
                + tag
                + "/"
                + name,
            }
        )
    historical = []
    pilot_ledger = root / "function-content/editorial/localized-resource-migration-001.json"
    if pilot_ledger.is_file():
        for logical_path, expected in (
            json.loads(pilot_ledger.read_text(encoding="utf-8")).get("active_resources", {}).items()
        ):
            source = root / logical_path
            if source.parent != directory or source.name in files:
                continue
            if source.is_symlink() or not source.is_file():
                raise OCFError(
                    "missing historical pilot resource requires reconciliation: " + logical_path
                )
            from .locale_history import before_structural

            actual = sha(before_structural(root, logical_path, source.read_text(encoding="utf-8")))
            if actual != expected:
                raise OCFError("historical pilot resource drift: " + logical_path)
            historical.append(
                {
                    "file": logical_path,
                    "decision": "ARCHIVE_WITH_LOGICAL_PATH_RESOLVER",
                    "source_sha256": actual,
                    "consumer": "immutable localized-resource-migration-001 active_resources",
                    "reason": "unlisted predecessor, not an editable active authority; preserve exact bytes before moving outside locale namespace",
                }
            )
    return {
        "schema_version": "1.0",
        "stage": "L3 preparation only; no transformation applied",
        "locale": tag,
        "locale_status": manifest.get("status"),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "active_function_count": len(active_functions),
        "active_functions": active_functions,
        "retirement_candidates": candidates,
        "unlisted_historical_resources": historical,
        "retired_key_count": sum(row["retired_key_count"] for row in candidates),
        "retained_resources": shared,
        "immutable_records": "KEEP existing editorial, rights and defaults locks unchanged",
        "apply_blocker": "L2 integration and historical-resource successor must be verified first",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locale", default="en-US")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="retire declared keys after L2 integration; retain checked history",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            apply_retirement(locale=args.locale)
            if args.apply
            else retirement_plan(locale=args.locale),
            indent=2,
            ensure_ascii=False,
        )
    )


def historical_stub(logical, archive, checksum):
    return yaml.safe_dump(
        {
            "schema_version": "1.0",
            "kind": "immutable-historical-locale-reference",
            "logical_path": logical,
            "archive": archive,
            "sha256": checksum,
        },
        sort_keys=False,
        allow_unicode=True,
    )


def apply_retirement(root=REPO_ROOT, *, locale="en-US"):
    from .dev_jobs import lock

    with lock("localized-source-migration", wait=False) as acquired:
        if not acquired:
            raise OCFError("another localized source migration owns the lease")
        return _apply_retirement(root, locale=locale)


def _apply_retirement(root=REPO_ROOT, *, locale="en-US"):
    """Retire words, not history: prepare shared resources before manifest switch.

    Original logical paths retain tiny unlisted, word-free compatibility stubs.
    The existing historical readers project checked archives before older locks;
    no active locale entry can be loaded from a stub.
    """
    root = root.resolve()
    ledger_path = root / LEDGER
    if ledger_path.exists():
        from .locale_history import RETIREMENT_SHA256

        if sha(ledger_path.read_text(encoding="utf-8")) != RETIREMENT_SHA256:
            raise OCFError("immutable retirement ledger drift")
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
        for name, row in data["files"].items():
            if not (root / name).resolve().is_relative_to(root) or not (
                root / row["archive"]
            ).resolve().is_relative_to(root):
                raise OCFError("retirement evidence escapes source root")
            if sha((root / name).read_text(encoding="utf-8")) != row["after_sha256"]:
                raise OCFError("retirement already exists with changed source: " + name)
            if (
                hashlib.sha256((root / row["archive"]).read_bytes()).hexdigest()
                != row["before_sha256"]
            ):
                raise OCFError("retirement archive drift: " + name)
        for name, checksum in data.get("created_resources", {}).items():
            if sha((root / name).read_text(encoding="utf-8")) != checksum:
                raise OCFError("retained shared resource changed; preserve overrides: " + name)
        return {"status": "already-retired; no writes", "keys": data["retired_key_count"]}
    plan = retirement_plan(root, locale=locale)
    manifest_name = "locales/" + plan["locale"] + "/manifest.yaml"
    manifest = yaml_safe_load((root / manifest_name).read_text(encoding="utf-8"))
    new_manifest = deepcopy(manifest)
    candidates = {Path(row["file"]).name: row for row in plan["retirement_candidates"]}
    declarations, created, outputs, archives = [], {}, {}, {}
    for resource in new_manifest["resources"]:
        row = candidates.get(resource["file"])
        if row is None:
            declarations.append(resource)
            continue
        name = row["file"]
        source = root / name
        if hashlib.sha256(source.read_bytes()).hexdigest() != row["source_sha256"]:
            raise OCFError("retirement source changed: " + name)
        data = yaml_safe_load(source.read_text(encoding="utf-8"))
        remaining = {
            key: value for key, value in data["entries"].items() if key not in row["retired_keys"]
        }
        if remaining:
            shared_name = "shared-" + source.name
            destination = "locales/" + plan["locale"] + "/" + shared_name
            if (root / destination).exists():
                raise OCFError("refusing to overwrite shared resource: " + destination)
            data["entries"] = remaining
            created[destination] = yaml.safe_dump(
                data, sort_keys=False, allow_unicode=True, width=100
            )
            declarations.append(
                {
                    "file": shared_name,
                    "domain": resource["domain"],
                    "description": "Shared locale labels retained after function metadata retirement.",
                }
            )
        archive = (
            "function-content/editorial/historical-locales/004/"
            + plan["locale"]
            + "/"
            + source.name
        )
        archives[name] = archive
        outputs[name] = historical_stub(name, archive, row["source_sha256"])
    for row in plan.get("unlisted_historical_resources", []):
        name = row["file"]
        archive = (
            "function-content/editorial/historical-locales/004/"
            + plan["locale"]
            + "/"
            + Path(name).name
        )
        archives[name] = archive
        outputs[name] = historical_stub(name, archive, row["source_sha256"])
    new_manifest["resources"] = declarations
    archives[manifest_name] = (
        "function-content/editorial/historical-locales/004/" + plan["locale"] + "/manifest.yaml"
    )
    outputs[manifest_name] = yaml.safe_dump(
        new_manifest, sort_keys=False, allow_unicode=True, width=100
    )
    files = {}
    for name, archive in archives.items():
        destination = root / archive
        if not destination.resolve().is_relative_to(root) or destination.is_symlink():
            raise OCFError("historical archive escapes source root: " + archive)
        if destination.exists():
            raise OCFError("refusing to replace historical archive: " + archive)
        raw = (root / name).read_bytes()
        files[name] = {
            "archive": archive,
            "before_sha256": hashlib.sha256(raw).hexdigest(),
            "after_sha256": sha(outputs[name]),
        }
    ledger = {
        "schema_version": "1.0",
        "stage": "L3",
        "locale": plan["locale"],
        "retired_key_count": plan["retired_key_count"],
        "files": files,
        "created_resources": {name: sha(text) for name, text in created.items()},
        "active_function_count": plan["active_function_count"],
    }
    # Prepare all new resources and exact archives first. Existing active files
    # remain untouched until their replacement resources are complete.
    for name, archive in archives.items():
        destination = root / archive
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write((root / name).read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
    for name, text in created.items():
        write_text_atomic(root / name, text, overwrite=False)
    write_text_atomic(
        ledger_path, json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", overwrite=False
    )
    write_text_atomic(root / manifest_name, outputs[manifest_name])
    for name, text in outputs.items():
        if name != manifest_name:
            write_text_atomic(root / name, text)
    return {
        "status": "retired",
        "functions": plan["active_function_count"],
        "keys": plan["retired_key_count"],
        "compatibility_stubs": len(outputs) - 1,
        "shared_resources": len(created),
        "ledger_sha256": sha(ledger_path.read_text(encoding="utf-8")),
    }


if __name__ == "__main__":
    main()
