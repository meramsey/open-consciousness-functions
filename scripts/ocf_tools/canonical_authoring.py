"""Build a new locale function resource from a temporary authoring record."""

from __future__ import annotations

from copy import deepcopy


def complete_resource(old, record, catalog):
    """Convert a new in-memory draft to the canonical locale contract."""
    from .commands import command_view
    from .function_catalog import contract_hash

    data = deepcopy(old)
    data.update(
        schema_version="2.0",
        slug=record.slug,
        record_metadata={
            key: deepcopy(record.data[key])
            for key in (
                "legacy",
                "aliases",
                "compatibility",
                "historical_lookup",
                "status",
                "sources",
                "claims",
                "attribution",
                "history",
                "ocf",
                "documentation",
            )
            if key in record.data
        },
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
        scope.pop("description", None)
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
    metadata = data["record_metadata"]
    metadata["commands"] = [
        {
            key: deepcopy(command[key])
            for key in ("id", "localization", "observed_phrase")
            if key in command
        }
        for command in record.data.get("commands", [])
    ]
    if record.data.get("command_phrases"):
        metadata["command_phrases"] = deepcopy(record.data["command_phrases"])
    metadata.setdefault(
        "documentation",
        {
            "title_key": f"functions.{record.id.lower()}.title",
            "short_description_key": f"functions.{record.id.lower()}.short-description",
            "purpose_key": f"functions.{record.id.lower()}.purpose",
        },
    )
    metadata.get("ocf", {}).pop("testing_status", None)
    data["content"] = deepcopy(record.data.get("content", {}))
    data["localization"] = {"status": "complete", "contract_sha256": contract_hash(data)}
    return data
