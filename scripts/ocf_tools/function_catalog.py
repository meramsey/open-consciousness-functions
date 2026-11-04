"""Complete locale function records; no catalog recursion or spoken inheritance."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from .utils import OCFError, yaml_safe_load

CANONICAL_LOCALE = "en-US"


def resources(root: Path, locale: str = CANONICAL_LOCALE, *, reader=None):
    """Discover only manifest-listed function resources, never title-derived IDs."""
    reader = reader or (lambda path: yaml_safe_load(path.read_text(encoding="utf-8")))
    directory = root / "locales" / locale
    manifest = directory / "manifest.yaml"
    if not manifest.is_file():
        return []
    result, seen = [], set()
    for row in reader(manifest).get("resources", []):
        if row.get("domain") != "function" or row.get("revision"):
            continue
        name = row["file"]
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
        if not identity or identity in seen or data.get("locale") != locale:
            raise OCFError("duplicate or inconsistent function catalog identity: " + str(identity))
        seen.add(identity)
        result.append((path, data))
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

    Only explicitly historical/provenance fields are obtained from the exact
    archive. Every active behavior and every current spoken word comes from
    this locale's complete resource.
    """
    from .locale_history import read_logical
    from .models import function_from_dict

    history = (
        yaml_safe_load(read_logical(root, data["historical_record"]))
        if data.get("historical_record")
        else {
            "legacy": {
                "source_system": None,
                "name": "",
                "commands": [],
                "command_status": "proposed",
                "source_availability": "pending-source-review",
            },
            "aliases": {"names": [], "commands": []},
            "compatibility": {"state": "none"},
            "status": {
                "maturity": "community-proposed",
                "implementation": "specification-only",
                "evidence": "unverified",
            },
            "sources": [],
            "claims": {"intended_effects": [], "prohibited_claims": []},
            "attribution": {"original_authors": [], "ocf_contributors": []},
            "ocf": {"reimplementation_status": "draft", "command_review": "pending"},
            "commands": [],
            "documentation": {
                "title_key": f"functions.{data['function_id'].lower()}.title",
                "short_description_key": f"functions.{data['function_id'].lower()}.short-description",
                "purpose_key": f"functions.{data['function_id'].lower()}.purpose",
            },
        }
    )
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
    old_commands = {row["id"]: row for row in history["commands"]}
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
                next(item for item in history["command_phrases"] if item["id"] == identity)
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
    record = function_from_dict(result, path)
    return record


def load_functions(root, locale=CANONICAL_LOCALE):
    rows = resources(root, locale)
    return [project(data, path, root) for path, data in rows if data.get("schema_version") == "2.0"]


def draft_resource(record, catalog):
    """An unrenderable local draft; no fabricated narration or approved speech."""
    from .commands import resolve_phrase
    from .function_authority_migration import complete_resource

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
    data.pop("historical_record")
    data["localization"]["status"] = "partial"
    return data
