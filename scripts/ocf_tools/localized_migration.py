"""Build an exact, reviewable batch migration and activate it in place.

Stage L1 keeps the existing function resource filenames: consolidated metadata
is staged in the current narration file and exact predecessor bytes are
recorded in an editorial ledger. Consumer activation and redundant source
retirement are separate stages; this stage removes no resource files or keys.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import yaml

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

LEDGER = "function-content/editorial/localized-consolidation-002.json"
SUPERSEDED_PILOT = "OCF-EMO-003-Empathize.yaml"


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
    """Prepare every function in place, preserving raw templates and resolved speech.

    Activation is intentionally separate: historical readers must be converted
    before the old runtime resource keys can be retired safely.
    """
    root = root.resolve()
    records = list(load_all_functions() if records is None else records)
    if len({record.id for record in records}) != len(records):
        raise OCFError("duplicate localized function identity")
    catalog = catalog or LocaleCatalog(root / "locales", function_records=lambda: records)
    if catalog.problems:
        raise OCFError("invalid source locale catalog: " + "; ".join(catalog.problems))
    schema = _load_schema("localized-function.schema.json")
    files, snapshots, mapping = {}, {}, []

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
        entries, raw_hashes, resolved_hashes, provenance, sources = {}, {}, {}, {}, set()
        narration_file = None
        for section in owner.data["narration"]["sequence"]:
            key = section["key"]
            entry, _ = catalog.raw_resource(key, "en-US", domain="narration", fallback=False)
            name = "locales/en-US/" + entry.file
            if narration_file is None:
                narration_file = entry.file
            elif narration_file != entry.file:
                raise OCFError(owner.id + ": narration spans multiple resource files")
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
        # The playback sequence is not the full resource inventory. Historical
        # and optional sections (for example Access to Energy's access-close)
        # remain canonical even when absent from the current three-slot plan.
        resource_entries = yaml_safe_load(snapshot("locales/en-US/" + narration_file))["entries"]
        for key, source in resource_entries.items():
            if key in entries:
                continue
            value = copy.deepcopy(source if isinstance(source, dict) else {"text": source})
            notes = value.pop("notes", None)
            if notes is not None:
                provenance[key] = notes
            entries[key] = value
            raw = catalog.raw_resource(key, "en-US", domain="narration", fallback=False)[0]
            resolved = catalog.resource(key, "en-US", domain="narration", fallback=False)[0]
            raw_hashes[key] = _sha(raw.text)
            resolved_hashes[key] = _sha(resolved.text)
        active_name = catalog.require("en-US").localized_function_files.get(owner.id)
        filename = narration_file
        if filename == SUPERSEDED_PILOT:
            # A branch-local pilot renamed one function; stage L1 restores the
            # stable pre-pilot path as the single in-place authority.
            filename = "hplus-" + owner.id + ".yaml"
        destination = "locales/en-US/" + filename
        if active_name not in (None, filename, SUPERSEDED_PILOT):
            raise OCFError(owner.id + ": localized function already active as " + str(active_name))
        if not (root / destination).is_file():
            raise OCFError(owner.id + ": no existing localized file to consolidate: " + destination)

        def cue(command) -> dict:
            resolved = localized_cue(owner, command, "en-US", catalog=catalog)
            bound = {}
            for binding, domain in (("display_cue_key", "ui"), ("spoken_cue_key", "narration")):
                key = command.localization.get(binding)
                if key:
                    entry, _ = catalog.raw_resource(key, "en-US", domain=domain, fallback=False)
                    bound[binding] = _literal(entry)
                    if entry.file:
                        snapshot("locales/en-US/" + entry.file)
            row = {
                "command_id": command.id,
                "display_cue": bound.get("display_cue_key")
                or {
                    "text": resolved["display_cue"],
                    "status": "canonical",
                    "version": "1.0.0",
                },
            }
            if resolved["binding_status"] == "resolved":
                row["spoken_cue"] = bound.get("spoken_cue_key") or {
                    "text": resolved["spoken_cue"],
                    "status": "reviewed",
                    "version": resolved.get("version") or "1.0.0",
                }
            for field in ("label", "explanation", "usage"):
                key = command.localization.get(field + "_key")
                if key:
                    row[field] = metadata(key)
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


def activate_batch(batch: dict, root: Path = REPO_ROOT, *, records=None) -> dict:
    """Consolidate L1 metadata without activating or removing competing sources.

    L2 is deliberately separate. Narration remains active through the existing
    key-based reader; first-class metadata is schema-checked, staged data until
    every consumer is migrated. The immutable pilot ledger is never rewritten.
    """
    root = root.resolve()
    locale_dir = root / "locales/en-US"
    outputs = {}
    for name, text in batch["files"].items():
        data = yaml_safe_load(text)
        data["domain"] = "narration"
        outputs[name] = yaml.dump(
            data, Dumper=_ReadableDumper, allow_unicode=True, sort_keys=False, width=100
        )
    ledger_path = root / LEDGER
    if ledger_path.is_file():
        # A finished consolidation is a no-op, not an opportunity to replace
        # predecessor evidence or silently absorb subsequent human edits.
        prior = json.loads(ledger_path.read_text(encoding="utf-8"))
        pending = []
        for name, row in prior["files"].items():
            path = root / name
            if path.is_symlink() or not path.resolve().is_relative_to(locale_dir.resolve()):
                raise OCFError("unsafe consolidation target: " + name)
            if (
                _sha(row["before"]) != row["before_sha256"]
                or _sha(row["after"]) != row["after_sha256"]
            ):
                raise OCFError("consolidation evidence drift: " + name)
            actual = _sha(path.read_text(encoding="utf-8"))
            if actual not in {row["before_sha256"], row["after_sha256"]}:
                raise OCFError("consolidated resource drift: " + name)
            if actual != row["after_sha256"]:
                pending.append((path, row["after"]))
        for path, text in pending:
            path.write_text(text, encoding="utf-8", newline="\n")
        return {
            "status": "resumed" if pending else "already-consolidated",
            "count": prior["count"],
            "ledger": LEDGER,
        }
    before_blobs = {name: (root / name).read_text(encoding="utf-8") for name in outputs}
    for name, text in outputs.items():
        target = (root / name).resolve()
        if not target.is_relative_to(locale_dir.resolve()) or (root / name).is_symlink():
            raise OCFError("unsafe consolidation target: " + name)
        errors = validate_against_schema(
            yaml_safe_load(text),
            _load_schema(
                "locale-manifest.schema.json"
                if name.endswith("manifest.yaml")
                else "locale-resource.schema.json"
            ),
        )
        if errors:
            raise OCFError(name + ": " + "; ".join(errors))
    ledger = {
        "schema_version": "1.0",
        "purpose": "Stage L1 only: explicit metadata, exact narration and predecessor provenance; no source retirement.",
        "count": batch["count"],
        "mapping": batch["mapping"],
        "files": {
            name: {
                "before": before_blobs[name],
                "before_sha256": _sha(before_blobs[name]),
                "after": text,
                "after_sha256": _sha(text),
            }
            for name, text in outputs.items()
        },
    }
    # Preserve all preimages before the first resource write. On interruption
    # each target is still either the recorded preimage or the staged output.
    (root / LEDGER).write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    for name, text in outputs.items():
        (root / name).write_text(text, encoding="utf-8", newline="\n")
    return {
        "status": "consolidated; consumers unchanged until L2",
        "count": len(batch["files"]),
        "ledger": LEDGER,
        "ledger_sha256": _sha(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n"),
        "source_files_removed": [],
        "at_existing_filenames": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="new private preview directory; never activates"
    )
    parser.add_argument(
        "--activate", action="store_true", help="activate in place under existing filenames"
    )
    args = parser.parse_args(argv)
    batch = build_batch()
    if args.output:
        stage_batch(batch, args.output)
    if args.activate:
        print(json.dumps(activate_batch(batch)))
        return 0
    print(
        json.dumps(
            {"status": batch["status"], "count": batch["count"], "mapping": batch["mapping"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
