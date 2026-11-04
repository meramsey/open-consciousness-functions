"""Deterministic, resumable Option A structural migration (no speech generation)."""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy

import yaml

from .function_catalog import contract_hash, project, resources
from .paths import REPO_ROOT
from .utils import OCFError, write_bytes_atomic, write_text_atomic, yaml_safe_load

LEDGER = "function-content/editorial/function-authority-migration-007.json"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def complete_resource(old, record, catalog):
    from .commands import command_view

    data = deepcopy(old)
    data.update(
        schema_version="2.0",
        slug=record.slug,
        historical_record=record.path.relative_to(REPO_ROOT).as_posix(),
        classification=deepcopy(record.data["classification"]),
        category_labels={
            name: {"text": name, "status": "canonical"}
            for name in [record.primary_domain, *record.secondary_domains]
        },
        lifecycle=deepcopy(record.data["lifecycle"]),
        audio=deepcopy(record.data["audio"]),
        safety=deepcopy(record.data["safety"]),
        function_version=deepcopy(record.data["version"]),
        narration=deepcopy(record.data["narration"]),
        editorial={"command_review": record.command_review},
    )
    for scope in data["lifecycle"].get("scopes", {}).values():
        scope.pop("description", None)  # Existing metadata_entries already owns these exact words.
    commands = {command.id: command for command in record.command_records}
    control_fields = (
        "designation",
        "phrase_ref",
        "availability",
        "documentation",
        "effect_scope_ref",
        "invocation_scope_ref",
        "procedure",
        "relationships",
    )
    for row in [data["activation"], *data["secondary_commands"]]:
        command = commands[row["command_id"]]
        row["role"] = command.role
        row["control"] = {
            field: deepcopy(command.data[field])
            for field in control_fields
            if field in command.data
        }
        view = command_view(record, command, catalog=catalog)
        row["procedure_steps"] = []
        for step in view.get("resolved_procedure_steps") or []:
            key = step.get("localization_key") or "command.procedure." + step["operation"]
            entry, _ = catalog.raw_resource(key, "en-US", domain="ui", fallback=False)
            value = {"text": entry.text}
            for attr in ("status", "version"):
                if getattr(entry, attr) is not None:
                    value[attr] = getattr(entry, attr)
            row["procedure_steps"].append(
                {"id": step["id"], "operation": step["operation"], "instruction": value}
            )
    for value in data["tags"]:
        value["semantic_id"] = value["text"]
    data["localization"] = {"status": "complete", "contract_sha256": contract_hash(data)}
    return data


def build(root=REPO_ROOT):
    from .locale import LocaleCatalog
    from .models import function_from_dict

    if (root / LEDGER).exists():
        ledger = json.loads((root / LEDGER).read_text())
        verify(root, ledger)
        return ledger, {}
    if root.resolve() != REPO_ROOT.resolve():
        raise OCFError("migration uses the selected OCF_DATA_ROOT; do not mix checkout identities")
    catalog = LocaleCatalog()
    records = {}
    for source in sorted((root / "functions").rglob("*.yaml")):
        record = function_from_dict(yaml_safe_load(source.read_text(encoding="utf-8")), source)
        if record.id in records:
            raise OCFError("duplicate structural migration identity: " + record.id)
        records[record.id] = record
    rows = resources(root)
    if len(rows) != len(records) or len(rows) != 58:
        raise OCFError("Option A requires the exact complete 58-function baseline")
    ledger = {
        "schema_version": "1.0",
        "id": "OCF-FUNCTION-AUTHORITY-007",
        "source_commit": "6e3929db4dce126521572fc5b1911da170714171",
        "scope": "Approved Option A; structural relocation only, no narration/cue/lifecycle change.",
        "files": {},
        "locale_files": {},
    }
    writes = {}
    for path, old in rows:
        record = records[old["function_id"]]
        source = record.path.relative_to(root).as_posix()
        archive = "function-content/editorial/historical-functions/007/" + source.removeprefix(
            "functions/"
        )
        source_raw = record.path.read_bytes()
        locale_name = path.relative_to(root).as_posix()
        locale_archive = (
            "function-content/editorial/historical-locales/007/"
            + locale_name.removeprefix("locales/")
        )
        archive_path = root / locale_archive
        before = archive_path.read_bytes() if archive_path.is_file() else path.read_bytes()
        old = yaml_safe_load(before.decode("utf-8"))
        new = complete_resource(old, record, catalog)
        after = yaml.safe_dump(new, sort_keys=False, allow_unicode=True, width=100).encode()
        if path.read_bytes() not in (before, after):
            raise OCFError("migration resume refuses an edited locale successor: " + locale_name)
        if after.startswith(b"\n") or new["entries"] != old["entries"]:
            raise OCFError("migration changed canonical narration")
        projected = project(new, path, root)
        for field in (
            "id",
            "slug",
            "classification",
            "lifecycle",
            "audio",
            "safety",
            "version",
            "narration",
            "commands",
            "canonical",
        ):
            if projected.data[field] != record.data[field]:
                raise OCFError(f"{record.id}: migration changed {field}")
        ledger["files"][source] = {
            "function_id": record.id,
            "archive": archive,
            "sha256": sha(source_raw),
            "text_sha256": sha(record.path.read_text(encoding="utf-8").encode()),
        }
        ledger["locale_files"][locale_name] = {
            "function_id": record.id,
            "archive": locale_archive,
            "before_sha256": sha(before),
            "after_sha256": sha(after),
        }
        writes[archive] = source_raw
        writes[locale_archive] = before
        writes[locale_name] = after
    return ledger, writes


def verify(root, ledger):
    from .locale_history import read_logical

    for name, row in ledger["files"].items():
        archive = root / row["archive"]
        if sha(archive.read_bytes()) != row["sha256"]:
            raise OCFError("historical function archive drift: " + name)
        path = root / name
        if path.exists() and sha(path.read_bytes()) != row["sha256"]:
            raise OCFError("old function source drift: " + name)
    for name, row in ledger["locale_files"].items():
        if (
            sha((root / name).read_bytes()) != row["after_sha256"]
            or sha((root / row["archive"]).read_bytes()) != row["before_sha256"]
        ):
            raise OCFError("complete function migration source drift: " + name)
        data = yaml_safe_load((root / name).read_text())
        record = project(data, root / name, root)
        old = yaml_safe_load(read_logical(root, data["historical_record"]))
        for field in (
            "id",
            "slug",
            "classification",
            "lifecycle",
            "audio",
            "safety",
            "version",
            "narration",
            "commands",
            "canonical",
        ):
            if record.data[field] != old[field]:
                raise OCFError("complete function equivalence failure: " + field)
    return {"functions": len(ledger["files"]), "speech_unchanged": True, "behavior_unchanged": True}


def apply(root=REPO_ROOT):
    from .dev_jobs import lock

    with lock("complete-function-authority-migration", wait=False) as acquired:
        if not acquired:
            raise OCFError("another function authority migration owns the lease")
        ledger, writes = build(root)
        if not writes:
            return {"status": "already-migrated; no writes", **verify(root, ledger)}
        for name, raw in writes.items():
            target = root / name
            if name.startswith("function-content/"):
                if target.exists():
                    if target.read_bytes() != raw:
                        raise OCFError("preserve conflicting migration archive: " + name)
                else:
                    write_bytes_atomic(target, raw, overwrite=False)
        # Archives are all verified before any active publication. The existing
        # loader remains on old structure until the complete batch is committed.
        for name, raw in writes.items():
            if name.startswith("locales/"):
                write_bytes_atomic(root / name, raw)
        text = json.dumps(ledger, indent=2, ensure_ascii=False) + "\n"
        write_text_atomic(root / LEDGER, text, overwrite=False)
        return {
            "status": "migrated",
            "functions": 58,
            "ledger_sha256": sha(text.encode()),
            **verify(root, ledger),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        result = apply()
    else:
        ledger, writes = build()
        result = {"status": "dry-run", "functions": len(ledger["files"]), "writes": len(writes)}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
