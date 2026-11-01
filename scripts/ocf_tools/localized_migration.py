"""Build an exact, reviewable batch migration without mutating active locale packs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import yaml

from .artifact_names import safe_component
from .commands import localized_cue
from .guide_review import relationships
from .indexes import load_all_functions
from .locale import LocaleCatalog
from .paths import (
    REPO_ROOT,
    publish_workspace_temp_directory,
    work_root,
    workspace_temp_directory,
)
from .utils import OCFError, yaml_safe_load
from .validators import _load_schema, validate_against_schema


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _ReadableDumper(yaml.SafeDumper):
    pass


def _string(dumper, value):
    return dumper.represent_scalar(
        "tag:yaml.org,2002:str", value, style="|" if "\n" in value else None
    )


_ReadableDumper.add_representer(str, _string)


def _literal(entry) -> dict:
    if not entry.text.strip():
        raise OCFError("cannot migrate empty localized metadata")
    return {
        "text": entry.text,
        "status": entry.status or "canonical",
        "version": entry.version or "1.0.0",
    }


def build_batch(root: Path = REPO_ROOT, *, records=None, catalog=None) -> dict:
    """Prepare every function, preserving raw templates and resolved speech separately.

    Activation is intentionally separate: historical readers must be converted
    before the old runtime resource paths can be retired safely.
    """
    root = root.resolve()
    records = list(load_all_functions() if records is None else records)
    catalog = catalog or LocaleCatalog(root / "locales", function_records=lambda: records)
    if catalog.problems:
        raise OCFError("invalid source locale catalog: " + "; ".join(catalog.problems))
    schema = _load_schema("localized-function.schema.json")
    files, snapshots, mapping, filenames = {}, {}, [], set()

    def snapshot(name: str) -> str:
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise OCFError("migration source escapes repository: " + name)
        if name not in snapshots:
            text = path.read_text(encoding="utf-8")
            snapshots[name] = {"sha256": _sha(text), "text": text}
        return snapshots[name]["text"]

    def metadata(key: str) -> dict:
        entry, _ = catalog.resource(key, "en-US", domain="ui", fallback=False)
        if entry.file:
            snapshot("locales/en-US/" + entry.file)
        return _literal(entry)

    snapshot("locales/en-US/manifest.yaml")
    for owner in sorted(records, key=lambda record: record.id):
        primary = next(
            (command for command in owner.command_records if command.designation == "primary"),
            None,
        )
        if primary is None:
            raise OCFError(owner.id + ": missing primary command")
        documentation = owner.data.get("documentation") or {}
        title = metadata(documentation["title_key"])
        filename = owner.id + "-" + safe_component(title["text"]) + ".yaml"
        if filename.casefold() in filenames:
            raise OCFError("duplicate localized function filename: " + filename)
        filenames.add(filename.casefold())
        destination = "locales/en-US/" + filename
        existing = root / destination
        active_name = catalog.require("en-US").localized_function_files.get(owner.id)
        if existing.exists() and active_name != filename:
            raise OCFError("migration destination already exists: " + destination)
        entries, raw_hashes, resolved_hashes, provenance, sources = {}, {}, {}, {}, set()
        for section in owner.data["narration"]["sequence"]:
            key = section["key"]
            entry, _ = catalog.raw_resource(key, "en-US", domain="narration", fallback=False)
            name = "locales/en-US/" + entry.file
            source = yaml_safe_load(snapshot(name))["entries"][key]
            value = copy.deepcopy(source if isinstance(source, dict) else {"text": source})
            notes = value.pop("notes", None)
            if notes is not None:
                provenance[key] = notes
            entries[key] = value
            sources.add(name)
            raw_hashes[key] = _sha(entry.text)
            resolved_hashes[key] = _sha(
                catalog.resource(key, "en-US", domain="narration", fallback=False)[0].text
            )

        def cue(command) -> dict:
            resolved = localized_cue(owner, command, "en-US", catalog=catalog)
            for binding, domain in (("display_cue_key", "ui"), ("spoken_cue_key", "narration")):
                key = command.localization.get(binding)
                if key:
                    entry, _ = catalog.raw_resource(key, "en-US", domain=domain, fallback=False)
                    if entry.file:
                        snapshot("locales/en-US/" + entry.file)
            row = {
                "command_id": command.id,
                "display_cue": {
                    "text": resolved["display_cue"],
                    "status": "canonical",
                    "version": "1.0.0",
                },
            }
            if resolved["binding_status"] == "resolved":
                row["spoken_cue"] = {
                    "text": resolved["spoken_cue"],
                    "status": "reviewed",
                    "version": resolved.get("version") or "1.0.0",
                }
            return row

        activation = cue(primary)
        if "spoken_cue" not in activation:
            raise OCFError(owner.id + ": primary spoken cue is not reviewed")
        secondary = [
            {**cue(command), "role": command.role}
            for command in owner.command_records
            if command.id != primary.id
        ]
        related = [
            {"function_id": edge["related_id"], "description": metadata(edge["description_key"])}
            for edge in relationships(owner, root=root)
        ]
        data = {
            "schema_version": "1.0",
            "locale": "en-US",
            "domain": "function",
            "function_id": owner.id,
            "title": title,
            "description": metadata(documentation["short_description_key"]),
            "activation": activation,
            "secondary_commands": secondary,
            "tags": copy.deepcopy(owner.data.get("tags") or []),
            "common_uses": copy.deepcopy(owner.data.get("use_cases") or []),
            "relationships": {"related_functions": related, "complementary_functions": []},
            "changelog": [
                {
                    "version": "1.0.0",
                    "change": "Structural migration; narration and cues unchanged.",
                }
            ],
            "entries": entries,
        }
        errors = validate_against_schema(data, schema)
        if errors:
            raise OCFError(owner.id + ": " + "; ".join(errors))
        files[destination] = yaml.dump(
            data, Dumper=_ReadableDumper, allow_unicode=True, sort_keys=False, width=100
        )
        mapping.append(
            {
                "function_id": owner.id,
                "source_paths": sorted(sources),
                "destination": destination,
                "raw_template_sha256": raw_hashes,
                "resolved_text_sha256": resolved_hashes,
                "narration_notes": provenance,
            }
        )
    return {
        "schema_version": "1.0",
        "status": "preview-only; not an activated locale migration",
        "locale": "en-US",
        "count": len(mapping),
        "files": files,
        "mapping": mapping,
        "historical_source_snapshots": snapshots,
    }


def stage_batch(batch: dict, destination: Path) -> dict:
    """Publish a complete new preview directory atomically inside the private workspace."""
    destination = destination.resolve()
    if not destination.is_relative_to(work_root().resolve()) or destination == work_root():
        raise OCFError("migration preview must remain inside OCF_WORK_DIR")
    if destination.exists():
        raise OCFError("migration preview destination already exists")
    stage = workspace_temp_directory(prefix="ocf-localized-migration-")
    for name, text in batch["files"].items():
        path = stage / name
        if not path.resolve().is_relative_to(stage.resolve()):
            raise OCFError("migration preview path escapes stage")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    receipt = {key: value for key, value in batch.items() if key != "files"}
    receipt["output_sha256"] = {name: _sha(text) for name, text in batch["files"].items()}
    (stage / "migration.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    publish_workspace_temp_directory(stage, destination)
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="new private preview directory; never activates"
    )
    args = parser.parse_args(argv)
    batch = build_batch()
    if args.output:
        stage_batch(batch, args.output)
    print(
        json.dumps(
            {"status": batch["status"], "count": batch["count"], "mapping": batch["mapping"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
