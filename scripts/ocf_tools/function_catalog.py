"""Complete locale function records; no catalog recursion or spoken inheritance."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

import yaml

from .utils import OCFError, yaml_safe_load

CANONICAL_LOCALE = "en-US"


def resources(root: Path, locale: str = CANONICAL_LOCALE, *, reader=None):
    """Discover only manifest-listed function resources, never title-derived IDs."""
    reader = reader or (lambda path: yaml_safe_load(path.read_text(encoding="utf-8")))
    if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", locale):
        raise OCFError("unsafe function catalog locale")
    directory = root / "locales" / locale
    manifest = directory / "manifest.yaml"
    if not manifest.is_file():
        return []
    if not directory.resolve().is_relative_to(root.resolve()) or any(
        node.is_symlink() for node in (root / "locales", directory, manifest)
    ):
        raise OCFError("unsafe function catalog manifest")
    result, seen, registered = [], set(), set()
    for row in reader(manifest).get("resources", []):
        if row.get("domain") != "function" or row.get("revision"):
            continue
        name = row["file"]
        registered.add(name)
        path = directory / name
        if (
            Path(name).name != name
            or "\\" in name
            or path.is_symlink()
            or not path.resolve().is_relative_to(directory.resolve())
        ):
            raise OCFError("unsafe function catalog resource: " + name)
        data = reader(path)
        identity = data.get("function_id")
        if (
            not isinstance(identity, str)
            or not re.fullmatch(r"OCF-[A-Z]{3}-[0-9]{3}", identity)
            or identity in seen
            or data.get("locale") != locale
        ):
            raise OCFError("duplicate or inconsistent function catalog identity: " + str(identity))
        seen.add(identity)
        result.append((path, data))
    # Manifest omission must never hide a second active function definition.
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in {".yaml", ".yml"} or path.name in registered:
            continue
        if path.is_symlink():
            raise OCFError("unsafe unregistered function catalog resource: " + path.name)
        try:
            candidate = reader(path)
        except (OSError, yaml.YAMLError, OCFError):
            continue  # Other resource domains are validated by their owner.
        if isinstance(candidate, dict) and (
            candidate.get("domain") == "function" or candidate.get("schema_version") == "2.0"
        ):
            raise OCFError("unregistered duplicate function definition: " + path.name)
    return sorted(result, key=lambda item: item[1]["function_id"])


def structural_contract(data):
    """Language-neutral IDs/operations/order only; localized words never inherited."""
    lifecycle = deepcopy(data["lifecycle"])
    lifecycle.pop("trigger_conditions", None)
    lifecycle.get("release", {}).pop("command", None)
    for scope in lifecycle.get("scopes", {}).values():
        scope.pop("description", None)
        scope.pop("description_key", None)
    return {
        "function_id": data["function_id"],
        "classification": data["classification"],
        "lifecycle": lifecycle,
        "trigger_count": len(data["lifecycle"].get("trigger_conditions", [])),
        "commands": [
            {
                "command_id": row["command_id"],
                "role": row.get("role", "activation"),
                "control": row["control"],
                "steps": [
                    {"id": step["id"], "operation": step["operation"]}
                    for step in row.get("procedure_steps", [])
                ],
            }
            for row in [data["activation"], *data["secondary_commands"]]
        ],
        "narration": data["narration"],
        "approved_targets": {
            key: [row["function_id"] for row in data["relationships"][key]]
            for key in ("related_functions", "complementary_functions")
        },
    }


def contract_hash(data):
    return hashlib.sha256(
        json.dumps(structural_contract(data), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def completeness(data, canonical):
    missing = []
    if data is None:
        return {"status": "missing", "missing": ["function"], "outdated_contract": False}
    for field in ("title", "description"):
        if not data.get(field, {}).get("text"):
            missing.append(field)
    for row in [canonical["activation"], *canonical["secondary_commands"]]:
        if row.get("control", {}).get("availability", "active") != "active":
            continue
        local = next(
            (
                item
                for item in [data.get("activation", {}), *data.get("secondary_commands", [])]
                if item.get("command_id") == row["command_id"]
            ),
            {},
        )
        for field in ("display_cue", "spoken_cue"):
            if row.get(field) and not local.get(field, {}).get("text"):
                missing.append(row["command_id"] + "/" + field)
    for key in canonical["entries"]:
        if not data.get("entries", {}).get(key, {}).get("text"):
            missing.append(key)
    outdated = data.get("localization", {}).get("contract_sha256") != contract_hash(canonical)
    unreviewed = any(
        entry.get("status") not in {"canonical", "reviewed"}
        for entry in data.get("entries", {}).values()
    )
    unreviewed |= any(
        row.get("spoken_cue", {}).get("status") not in {"canonical", "reviewed"}
        for row in [data.get("activation", {}), *data.get("secondary_commands", [])]
        if row.get("spoken_cue")
        and row.get("control", {}).get("availability", "active") == "active"
    )
    declared = data.get("localization", {}).get("status", "partial")
    status = (
        "needs-review"
        if outdated or unreviewed or declared == "needs-review"
        else "partial"
        if missing or declared == "partial"
        else "complete"
    )
    return {"status": status, "missing": missing, "outdated_contract": outdated}


def project(data, path, root):
    """Adapt the old Python interface, not another writable function definition.

    Every field comes from this canonical locale resource. Predecessor Git
    revisions may be inspected by audit tools, but are never function inputs.
    """
    from .models import function_from_dict

    history = data.get("record_metadata")
    if not isinstance(history, dict):
        raise OCFError("canonical function record metadata is incomplete")
    historical_fields = (
        "legacy",
        "aliases",
        "compatibility",
        "historical_lookup",
        "status",
        "sources",
        "claims",
        "attribution",
        "history",
    )
    result = {key: deepcopy(history[key]) for key in historical_fields if key in history}
    result.update(
        schema_version="1.0",
        id=data["function_id"],
        slug=data["slug"],
        classification=deepcopy(data["classification"]),
        lifecycle=deepcopy(data["lifecycle"]),
        audio=deepcopy(data["audio"]),
        safety=deepcopy(data["safety"]),
        version=deepcopy(data["function_version"]),
        narration=deepcopy(data["narration"]),
        purpose={
            "summary": data["description"]["text"],
            "source_description": None,
            "community_description": data["description"]["text"],
        },
        ocf={**deepcopy(history["ocf"]), "command_review": data["editorial"]["command_review"]},
        companions=[row["function_id"] for row in data["relationships"]["related_functions"]],
        applications=[],
        chains=[],
        incompatible_functions=[],
        use_cases=[],
    )
    for scope in result["lifecycle"].get("scopes", {}).values():
        key = scope.get("description_key")
        if key:
            scope["description"] = data["metadata_entries"][key]["text"]
    commands, modes, mode_ids, phrases = [], [], [], []
    old_commands = {row["id"]: row for row in history.get("commands", [])}
    for row in [data["activation"], *data["secondary_commands"]]:
        identity = row["command_id"]
        control = deepcopy(row["control"])
        command = {
            **control,
            "id": identity,
            "function_id": data["function_id"],
            "role": row.get("role", "activation"),
        }
        old = old_commands.get(identity, {})
        command["localization"] = deepcopy(
            old.get(
                "localization",
                {
                    field + "_key": "commands." + identity.lower() + "." + field
                    for field in ("label", "usage", "explanation")
                },
            )
        )
        command["spoken"] = row.get("spoken_cue", {}).get("text")
        command["spoken_review"] = (
            "reviewed"
            if row.get("spoken_cue", {}).get("status") in {"reviewed", "canonical"}
            else "unresolved"
        )
        if "observed_phrase" in old:
            command["observed_phrase"] = deepcopy(old["observed_phrase"])
        commands.append(command)
        source = command["phrase_ref"]["source"]
        if source == "canonical-mode":
            modes.append(row["display_cue"]["text"])
            mode_ids.append(identity)
        if source == "special-phrase":
            phrase = deepcopy(
                next(item for item in history.get("command_phrases", []) if item["id"] == identity)
            )
            phrase["phrase"] = row["display_cue"]["text"]
            phrases.append(phrase)
    result["canonical"] = {
        "name": data["title"]["text"],
        "command": {
            "primary": data["activation"]["display_cue"]["text"],
            "modes": modes,
            "mode_ids": mode_ids,
        },
    }
    result["commands"] = commands
    if phrases:
        result["command_phrases"] = phrases
    result["documentation"] = deepcopy(history["documentation"])
    result["content"] = deepcopy(data.get("content", {}))
    record = function_from_dict(result, path)
    return record


def load_functions(root, locale=CANONICAL_LOCALE):
    rows = resources(root, locale)
    if locale != CANONICAL_LOCALE:
        canonical = {data["function_id"]: data for _, data in resources(root)}
        for _, data in rows:
            reference = canonical.get(data["function_id"])
            if reference is None or contract_hash(data) != contract_hash(reference):
                raise OCFError(
                    "locale function has unknown or inconsistent canonical structural identity"
                )
    return [project(data, path, root) for path, data in rows if data.get("schema_version") == "2.0"]


def draft_resource(record, catalog):
    """An unrenderable local draft; no fabricated narration or approved speech."""
    from .canonical_authoring import complete_resource
    from .commands import resolve_phrase

    commands = []
    for command in record.command_records:
        row = {
            "command_id": command.id,
            "role": command.role,
            "display_cue": {"text": resolve_phrase(record, command), "status": "draft"},
        }
        if command.data.get("spoken"):
            row["spoken_cue"] = {"text": command.data["spoken"], "status": "draft"}
        commands.append(row)
    old = {
        "schema_version": "1.0",
        "domain": "function",
        "locale": "en-US",
        "function_id": record.id,
        "title": {"text": record.canonical_name, "status": "draft"},
        "description": {"text": record.purpose_summary, "status": "draft"},
        "activation": commands[0],
        "secondary_commands": commands[1:],
        "tags": [],
        "common_uses": [],
        "relationships": {"related_functions": [], "complementary_functions": []},
        "metadata_entries": {},
        "entries": {},
        "changelog": [],
    }
    data = complete_resource(old, record, catalog)
    data["localization"]["status"] = "partial"
    return data
