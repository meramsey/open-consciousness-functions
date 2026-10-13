"""Resolve structured function commands and reusable activation procedures."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import FunctionCommand, FunctionRecord
from .paths import COMMAND_PROCEDURES_FILE, schema_path
from .utils import OCFError, yaml_safe_load


class CommandMetadataError(OCFError):
    """Structured command metadata is incomplete or internally inconsistent."""


def _parallel_phrase(
    owner: FunctionRecord,
    *,
    field: str,
    id_field: str,
    command_id: str,
) -> str:
    """Resolve one stable phrase ID through a compatibility-preserving array."""
    block = owner.data.get(field) or {}
    phrases = block.get("commands", []) if field in ("legacy", "aliases") else None
    if field == "canonical":
        phrases = (block.get("command") or {}).get("modes", [])
        ids = (block.get("command") or {}).get("mode_ids", [])
    else:
        ids = block.get(id_field, [])
    if not isinstance(ids, list) or not isinstance(phrases, list) or len(ids) != len(phrases):
        raise CommandMetadataError(
            f"{owner.id}: {field}.{id_field} must align with its phrase array"
        )
    matches = [index for index, value in enumerate(ids) if value == command_id]
    if len(matches) != 1:
        raise CommandMetadataError(
            f"{owner.id}: phrase reference {command_id!r} resolves {len(matches)} times in {field}"
        )
    phrase = phrases[matches[0]]
    if not isinstance(phrase, str) or not phrase.strip():
        raise CommandMetadataError(f"{owner.id}: phrase reference {command_id!r} is empty")
    return phrase


def resolve_phrase(owner: FunctionRecord, command: FunctionCommand) -> str:
    """Resolve the one authoritative phrase named by a structured command."""
    if command.function_id != owner.id:
        raise CommandMetadataError(
            f"command {command.id} belongs to {command.function_id}, not {owner.id}"
        )
    ref = command.phrase_ref
    source = ref.get("source")
    if source == "canonical-primary":
        phrase = owner.canonical_command
    elif source == "canonical-mode":
        return _parallel_phrase(
            owner,
            field="canonical",
            id_field="mode_ids",
            command_id=str(ref.get("command_id", "")),
        )
    elif source == "lifecycle-release":
        phrase = owner.release_command
    elif source == "legacy-command":
        return _parallel_phrase(
            owner,
            field="legacy",
            id_field="command_ids",
            command_id=str(ref.get("command_id", "")),
        )
    elif source == "alias-command":
        return _parallel_phrase(
            owner,
            field="aliases",
            id_field="command_ids",
            command_id=str(ref.get("command_id", "")),
        )
    elif source == "special-phrase":
        phrase_id = ref.get("phrase_id")
        matches = [
            item for item in owner.data.get("command_phrases", []) if item.get("id") == phrase_id
        ]
        if len(matches) != 1:
            raise CommandMetadataError(
                f"{owner.id}: special phrase {phrase_id!r} resolves {len(matches)} times"
            )
        phrase = matches[0].get("phrase")
    else:
        raise CommandMetadataError(f"{owner.id}: unsupported phrase source {source!r}")
    if not isinstance(phrase, str) or not phrase.strip():
        raise CommandMetadataError(
            f"{owner.id}: command {command.id} refers to an empty {source} phrase"
        )
    return phrase


def command_view(owner: FunctionRecord, command: FunctionCommand) -> dict[str, Any]:
    """Return a rich, derived view without duplicating phrase authority in YAML."""
    result = deepcopy(command.data)
    result["phrase"] = resolve_phrase(owner, command)
    if command.data.get("effect_scope_ref") == "lifecycle.persistence":
        result["effect_scope"] = owner.persistence
    if command.procedure:
        result["resolved_procedure_steps"] = resolve_procedure(command, load_procedure_catalog())
    return result


@lru_cache(maxsize=4)
def load_procedure_catalog(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Load reusable ordered procedures, validating their schema and identities."""
    source = Path(path) if path is not None else COMMAND_PROCEDURES_FILE
    data = yaml_safe_load(source.read_text(encoding="utf-8"))
    from .validators import validate_against_schema

    errors = validate_against_schema(data, _load_command_procedure_schema())
    if errors:
        raise CommandMetadataError("invalid command procedure catalog: " + " | ".join(errors))
    procedures = data.get("procedures", [])
    by_id = {item["id"]: item for item in procedures}
    if len(by_id) != len(procedures):
        raise CommandMetadataError("command procedure catalog contains duplicate IDs")
    return by_id


def _load_command_procedure_schema() -> dict[str, Any]:
    return json.loads(schema_path("command-procedure.schema.json").read_text(encoding="utf-8"))


def resolve_procedure(
    command: FunctionCommand,
    catalog: dict[str, dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """Resolve a reusable procedure with an explicit whole-sequence override."""
    procedure = command.procedure
    if procedure is None:
        return None
    if procedure.get("status") != "documented":
        return None
    reference = procedure.get("ref")
    steps = None
    if reference:
        definition = catalog.get(str(reference))
        if definition is None:
            raise CommandMetadataError(
                f"command {command.id} refers to unknown procedure {reference!r}"
            )
        steps = list(definition["steps"])
    if "override_steps" in procedure:
        steps = list(procedure["override_steps"])
    if steps is None:
        return None
    if "override_steps" in procedure and (
        procedure.get("before_steps") or procedure.get("after_steps")
    ):
        raise CommandMetadataError(
            f"command {command.id} cannot combine override_steps with before/after steps"
        )
    return list(procedure.get("before_steps", [])) + steps + list(procedure.get("after_steps", []))


def validate_command_records(owner: FunctionRecord) -> list[str]:
    """Check local references and old-field alignment for one function."""
    records = owner.command_records
    errors: list[str] = []
    canonical_data = owner.data.get("canonical") or {}
    command_data = canonical_data.get("command") or {}
    modes = command_data.get("modes", [])
    mode_ids = command_data.get("mode_ids")
    if mode_ids is not None:
        if (
            not isinstance(mode_ids, list)
            or not isinstance(modes, list)
            or len(mode_ids) != len(modes)
        ):
            errors.append("canonical.command.mode_ids must align with canonical.command.modes")
        elif len(set(mode_ids)) != len(mode_ids):
            errors.append("canonical.command.mode_ids contains duplicate IDs")

    for block_name in ("legacy", "aliases"):
        block = owner.data.get(block_name) or {}
        ids_for_phrases = block.get("command_ids")
        if ids_for_phrases is None:
            continue
        phrases = block.get("commands", [])
        if not isinstance(ids_for_phrases, list) or not isinstance(phrases, list):
            errors.append(f"{block_name}.command_ids and {block_name}.commands must be arrays")
        elif len(ids_for_phrases) != len(phrases):
            errors.append(f"{block_name}.command_ids must align with {block_name}.commands")
        elif len(set(ids_for_phrases)) != len(ids_for_phrases):
            errors.append(f"{block_name}.command_ids contains duplicate IDs")

    if "commands" not in owner.data:
        return errors  # Old registry records remain valid until their migration phase.
    if not records:
        return errors + ["structured commands is present but empty"]
    ids = [record.id for record in records]
    if len(set(ids)) != len(ids):
        errors.append("duplicate structured command ID")
    by_id = set(ids)
    for record in records:
        if record.function_id != owner.id:
            errors.append(f"command {record.id} has a different parent function ID")
        if not record.id.startswith(f"OCF-CMD-{owner.id[4:]}-"):
            errors.append(f"command ID {record.id} is not scoped to function {owner.id}")
        try:
            resolve_phrase(owner, record)
        except CommandMetadataError as exc:
            errors.append(str(exc))
        relationships = record.relationships
        for relation in (
            "pairs_with",
            "modifies",
            "releases",
            "cancels",
            "retrieves",
            "closes",
        ):
            targets = relationships.get(relation, [])
            if not isinstance(targets, list):
                errors.append(f"command {record.id} relationship {relation} must be an array")
                continue
            if set(targets) - by_id:
                errors.append(f"command {record.id} relationship {relation} has unknown IDs")
            if record.id in targets:
                errors.append(f"command {record.id} cannot relate to itself")

    primary = owner.canonical_command
    primary_refs = [
        record for record in records if record.phrase_ref.get("source") == "canonical-primary"
    ]
    if bool(primary) != (len(primary_refs) == 1):
        errors.append("structured commands must identify exactly the declared canonical primary")
    if not primary and primary_refs:
        errors.append("a function without a canonical primary cannot declare one in commands")
    if any(
        record.designation != "primary" or record.role != "activation" for record in primary_refs
    ):
        errors.append("canonical primary command must have primary designation and activation role")
    mode_refs = {
        str(record.phrase_ref.get("command_id"))
        for record in records
        if record.phrase_ref.get("source") == "canonical-mode"
    }
    if modes and mode_ids is None:
        errors.append("structured canonical modes require stable canonical.command.mode_ids")
    if mode_ids is not None:
        if isinstance(mode_ids, list) and mode_refs != set(mode_ids):
            errors.append("structured mode commands must cover canonical.command.mode_ids exactly")
    elif mode_refs:
        errors.append("canonical-mode phrase references require canonical.command.mode_ids")

    for block_name, phrase_name in (("legacy", "commands"), ("aliases", "commands")):
        block = owner.data.get(block_name, {})
        id_field = "command_ids"
        ids_for_phrases = block.get(id_field)
        refs = {
            str(record.phrase_ref.get("command_id"))
            for record in records
            if record.phrase_ref.get("source")
            == ("legacy-command" if block_name == "legacy" else "alias-command")
        }
        if ids_for_phrases is not None:
            if isinstance(ids_for_phrases, list) and refs - set(ids_for_phrases):
                errors.append(f"{block_name} phrase references contain unknown IDs")
        elif refs:
            errors.append(f"{block_name} phrase references require {block_name}.{id_field}")

    special = owner.data.get("command_phrases", [])
    if not isinstance(special, list) or any(not isinstance(entry, dict) for entry in special):
        errors.append("command_phrases must be an array of objects")
        special = []
    special_ids = [entry.get("id") for entry in special]
    if len(set(special_ids)) != len(special_ids):
        errors.append("duplicate special command phrase ID")
    referenced_special = {
        record.phrase_ref.get("phrase_id")
        for record in records
        if record.phrase_ref.get("source") == "special-phrase"
    }
    if referenced_special - set(special_ids):
        errors.append("special command phrase reference has no phrase record")
    if set(special_ids) - referenced_special:
        errors.append("special command phrase is not referenced by a structured command")

    release = owner.data.get("lifecycle", {}).get("release", {})
    release_command_id = release.get("command_id")
    if release_command_id and release_command_id not in by_id:
        errors.append("lifecycle.release.command_id refers to an unknown command ID")
    if release.get("command"):
        if not any(record.phrase_ref.get("source") == "lifecycle-release" for record in records):
            errors.append("lifecycle.release.command must have a structured command reference")

    for command in records:
        procedure = command.procedure
        if not procedure:
            continue
        if procedure.get("ref") and procedure.get("status") == "not-specified":
            errors.append(
                f"command {command.id} cannot reference a procedure with not-specified status"
            )
        if procedure.get("status") == "not-specified" and procedure.get("override_steps"):
            errors.append(f"command {command.id} cannot override steps with not-specified status")
        if procedure.get("status") == "documented" and not (
            procedure.get("ref")
            or procedure.get("override_steps")
            or procedure.get("before_steps")
            or procedure.get("after_steps")
        ):
            errors.append(f"command {command.id} documents a procedure without steps")
        if (procedure.get("before_steps") or procedure.get("after_steps")) and not procedure.get(
            "ref"
        ):
            errors.append(f"command {command.id} procedure extensions require a reusable ref")
        if procedure.get("override_steps") and (
            procedure.get("before_steps") or procedure.get("after_steps")
        ):
            errors.append(f"command {command.id} cannot combine override_steps with extensions")
    return errors


def validate_command_collection(records: list[FunctionRecord]) -> list[str]:
    """Check global stable command IDs across all migrated functions."""
    seen: dict[str, str] = {}
    errors: list[str] = []
    for owner in records:
        for command in owner.command_records:
            previous = seen.get(command.id)
            if previous is not None:
                errors.append(f"duplicate command ID {command.id} in {previous} and {owner.id}")
            else:
                seen[command.id] = owner.id
    return errors
