"""Deterministic public documentation projection; published narration is excluded."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from .command_docs import build_command_index
from .function_catalog import resources
from .indexes import load_all_functions
from .locale import LocaleCatalog
from .paths import REPO_ROOT
from .utils import OCFError, write_text_atomic
from .validators import _load_schema, validate_against_schema

SOURCE_REPOSITORY = "https://github.com/ocfproject-org/open-consciousness-functions"
EXPORTER = "ocf.public-site-guides/1"
PUBLIC_VALUE_STATUSES = {"canonical", "reviewed"}


def _digest(value: object) -> str:
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OCFError(message)


def _approved_value(value, *, label: str) -> dict:
    if not isinstance(value, dict) or value.get("status") not in PUBLIC_VALUE_STATUSES:
        raise OCFError(f"public guide export requires reviewed {label}")
    text = value.get("text")
    if not isinstance(text, str) or not text.strip():
        raise OCFError(f"public guide export requires nonempty {label}")
    return {"text": text, "status": value["status"]}


def _command(row: dict, local: dict, *, historical: bool = False) -> dict:
    presentation = row["cue_presentation"]
    display = presentation.get("display_cue") or row.get("phrase")
    if not isinstance(display, str) or not display.strip():
        raise OCFError(f"public guide export requires a display cue for {row['id']}")
    display_status = presentation.get("resource_status")
    if display_status not in PUBLIC_VALUE_STATUSES:
        local_display = local.get("display_cue")
        display_status = local_display.get("status") if isinstance(local_display, dict) else None
    if historical and display_status is None:
        display_status = "historical"
    if display_status not in PUBLIC_VALUE_STATUSES | ({"historical"} if historical else set()):
        raise OCFError(f"public guide export requires reviewed display cue {row['id']}")
    spoken = None
    if row.get("spoken_review") == "reviewed" and presentation.get("binding_status") == "resolved":
        value = local.get("spoken_cue")
        spoken = _approved_value(value, label=f"spoken cue {row['id']}") if value else None

    steps = []
    step_statuses = []
    for step in row.get("procedure_steps", []):
        instruction = step.get("instruction", {})
        step_statuses.append(instruction.get("status"))
    procedure_status = row.get("procedure_status", "not-specified")
    if (
        procedure_status == "documented"
        and step_statuses
        and all(status in PUBLIC_VALUE_STATUSES for status in step_statuses)
    ):
        for step in row["procedure_steps"]:
            instruction = _approved_value(
                step["instruction"], label=f"procedure instruction {row['id']}"
            )
            steps.append(
                {
                    "id": step["id"],
                    "operation": step["operation"],
                    "instruction": instruction["text"],
                }
            )
        public_procedure_status = "documented"
    elif procedure_status == "documented":
        # Fail closed: do not publish a partially reviewed procedure.
        public_procedure_status = "review-pending"
    else:
        public_procedure_status = "not-specified"

    def localized_text(name):
        value = local.get(name)
        return _approved_value(value, label=f"{name} {row['id']}") if value else None

    invocation = row.get("invocation_scope")
    public_invocation = None
    if invocation:
        public_invocation = {
            key: invocation[key]
            for key in ("activation", "persistence")
            if invocation.get(key) is not None
        }
    return {
        "command_id": row["id"],
        "command_status": "historical-inactive" if historical else "active",
        "role": row["role"],
        "designation": row["designation"],
        "display_cue": {"text": display, "status": display_status},
        "spoken_cue": spoken["text"] if spoken else None,
        "spoken_status": spoken["status"] if spoken else "not-reviewed-or-unbound",
        "label": localized_text("label"),
        "usage": localized_text("usage"),
        "explanation": localized_text("explanation"),
        "procedure_status": public_procedure_status,
        "procedure_steps": steps,
        "effect_scope": row.get("effect_scope"),
        "invocation_scope": public_invocation,
    }


def _function(
    record,
    document,
    metadata,
    resource_path: Path,
    relation_titles: dict,
    *,
    locale: str,
) -> dict:
    identity = record.id
    title = _approved_value(metadata.get("title"), label=f"title {identity}")
    description = _approved_value(metadata.get("description"), label=f"description {identity}")
    if record.data.get("audio", {}).get("script_status") != "approved":
        raise OCFError(f"public guide export requires approved function script status: {identity}")

    local_commands = {
        row["command_id"]: row
        for row in [metadata["activation"], *metadata.get("secondary_commands", [])]
    }
    all_commands = [
        _command(
            row,
            local_commands[row["id"]],
            historical=row.get("role") == "legacy-alias",
        )
        for row in document["commands"]
        if row.get("role") not in {"access-close"}
    ]
    commands = [row for row in all_commands if row["command_status"] == "active"]
    historical_commands = [
        row for row in all_commands if row["command_status"] == "historical-inactive"
    ]

    categories = []
    for key in [record.primary_domain, *record.secondary_domains]:
        value = metadata.get("category_labels", {}).get(key)
        label = _approved_value(value, label=f"category label {identity}/{key}")
        categories.append({"id": key, "label": label["text"], "status": label["status"]})

    def discovery(values):
        return [
            {"text": item["text"], "status": item.get("status", "unspecified")}
            for item in values
            if isinstance(item.get("text"), str) and item["text"].strip()
        ]

    relationships = []
    for relation in document.get("related_functions", []):
        relation_id = relation.get("relationship_id")
        function_id = relation.get("function_id")
        _require(
            isinstance(relation_id, str) and relation_id,
            f"approved relationship projection lacks a stable ID: {identity}",
        )
        _require(
            function_id in relation_titles,
            f"approved relationship projection has an unknown function: {identity}/{function_id}",
        )
        _require(
            relation.get("relationship_type") in {"related", "complementary"}
            and relation.get("dependency") == "optional",
            f"approved relationship projection has an invalid type/scope: {identity}/{relation_id}",
        )
        localized_description = relation.get("description", {})
        _require(
            localized_description.get("requested_locale") == locale
            and localized_description.get("resolved_locale") == locale
            and localized_description.get("fallback") is False,
            f"approved relationship description is not resolved for {locale}: {identity}/{relation_id}",
        )
        relation_description = localized_description.get("text")
        _require(
            isinstance(relation_description, str) and relation_description.strip(),
            f"approved relationship description is empty: {identity}/{relation_id}",
        )
        relationships.append(
            {
                "relationship_id": relation_id,
                "function_id": function_id,
                "title": relation_titles[function_id],
                "description": relation_description,
                "relationship_type": relation["relationship_type"],
                "direction": "outgoing",
                "dependency": relation["dependency"],
            }
        )

    lifecycle = record.data.get("lifecycle", {})
    scopes = []
    raw_scopes = lifecycle.get("scopes", {})
    metadata_entries = metadata.get("metadata_entries", {})
    for scope in document.get("lifecycle_scopes", []):
        raw_scope = raw_scopes.get(scope["kind"], {})
        description_key = raw_scope.get("description_key")
        description_value = metadata_entries.get(description_key) if description_key else None
        description_status = (
            description_value.get("status")
            if isinstance(description_value, dict)
            and description_value.get("status") in PUBLIC_VALUE_STATUSES
            else "unspecified"
            if isinstance(description_value, dict)
            and not description_value.get("status")
            and isinstance(description_value.get("text"), str)
            else "unreviewed"
        )
        scopes.append(
            {
                "kind": scope["kind"],
                "label": scope["label"]["text"],
                "persistence": scope["persistence"],
                "activation": scope.get("activation"),
                "description": description_value["text"]
                if description_status in PUBLIC_VALUE_STATUSES | {"unspecified"}
                else None,
                "description_status": description_status,
            }
        )

    return {
        "function_id": identity,
        "slug": record.slug,
        "canonical_resource": "locales/en-US/" + resource_path.name,
        "title": title,
        "description": description,
        "primary_category": record.primary_domain,
        "categories": categories,
        "tags": discovery(metadata.get("tags", [])),
        "common_uses": discovery(metadata.get("common_uses", [])),
        "commands": commands,
        "historical_commands": historical_commands,
        "lifecycle": {
            "activation": lifecycle.get("activation"),
            "persistence": lifecycle.get("persistence"),
            "trigger_conditions": list(lifecycle.get("trigger_conditions", [])),
            "release_command": (lifecycle.get("release") or {}).get("command"),
            "scopes": scopes,
        },
        "safety_notes": list(record.safety_notes),
        "related_functions": relationships,
        "documentation_status": "canonical-function-resource",
        "canonical_resource_sha256": hashlib.sha256(resource_path.read_bytes()).hexdigest(),
    }


def export_data(*, source_commit: str, root: Path = REPO_ROOT, locale: str = "en-US") -> dict:
    """Create a deterministic allowlisted export with no canonical narration or source evidence."""
    if locale != "en-US":
        raise OCFError("public website function guides require a complete reviewed locale")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise OCFError("public website export requires an exact 40-character source commit")

    catalog = LocaleCatalog(root / "locales")
    if catalog.problems:
        raise OCFError("public website export locale catalog: " + " | ".join(catalog.problems))
    records = load_all_functions(root=root)
    docs = build_command_index(locale, catalog)
    by_id = {row["function_id"]: row for row in docs["functions"]}
    canonical = catalog.require(locale)
    relation_titles = {
        identity: _approved_value(data.get("title"), label=f"title {identity}")["text"]
        for identity, data in canonical.localized_functions.items()
    }
    resource_paths = {data["function_id"]: path for path, data in resources(root, locale)}
    if len(records) != 58 or set(by_id) != {row.id for row in records}:
        raise OCFError("public website export requires exactly 58 canonical function records")

    functions = []
    for record in records:
        metadata = canonical.localized_functions[record.id]
        functions.append(
            _function(
                record,
                by_id[record.id],
                metadata,
                resource_paths[record.id],
                relation_titles,
                locale=locale,
            )
        )

    listening_path = root / "docs" / "LISTENING_GUIDE.md"
    listening_markdown = listening_path.read_text(encoding="utf-8")
    payload = {
        "schema_version": 1,
        "exporter": EXPORTER,
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": source_commit,
        "locale": locale,
        "functions": functions,
        "listening_guide": {
            "markdown": listening_markdown,
            "source_sha256": hashlib.sha256(listening_markdown.encode("utf-8")).hexdigest(),
        },
    }
    payload["build_receipt"] = {
        "function_count": len(functions),
        "approved_relationship_count": sum(len(row["related_functions"]) for row in functions),
        "functions_sha256": _digest(functions),
        "export_content_sha256": _digest(payload),
        "narration_text_included": False,
        "source_evidence_paths_included": False,
        "draft_procedures_included": False,
        "relationship_proposals_included": False,
    }
    errors = validate_against_schema(payload, _load_schema("public-site-guide-export.schema.json"))
    if errors:
        raise OCFError("invalid public website guide export: " + " | ".join(errors))
    return payload


def write_export(output: Path, *, source_commit: str, root: Path = REPO_ROOT) -> dict:
    payload = export_data(source_commit=source_commit, root=root)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    write_text_atomic(output, text, overwrite=False)
    return payload["build_receipt"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = write_export(args.output, source_commit=args.source_commit)
    except (OCFError, OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
