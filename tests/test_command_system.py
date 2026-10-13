"""Unit contracts for structured command references and procedures."""

from pathlib import Path

import pytest
import yaml
from ocf_tools.commands import (
    CommandMetadataError,
    load_procedure_catalog,
    resolve_phrase,
    resolve_procedure,
    validate_command_collection,
    validate_command_records,
)
from ocf_tools.models import FunctionCommand, FunctionRecord
from ocf_tools.paths import REPO_ROOT, schema_path
from ocf_tools.validators import validate_against_schema, validate_command_metadata

pytestmark = pytest.mark.unit

FUNCTION_ID = "OCF-COG-999"
PRIMARY_ID = "OCF-CMD-COG-999-ACTIVATE"
MODE_ID = "OCF-CMD-COG-999-CLOSE"
RELEASE_ID = "OCF-CMD-COG-999-RELEASE"
LEGACY_ID = "OCF-CMD-COG-999-LEGACY-01"
ALIAS_ID = "OCF-CMD-COG-999-ALIAS-01"
SPECIAL_ID = "OCF-CMD-COG-999-ACCESS-CLOSE"


def command_record(command_id, phrase_ref, role, designation="secondary", **extras):
    return {
        "id": command_id,
        "function_id": FUNCTION_ID,
        "phrase_ref": phrase_ref,
        "role": role,
        "designation": designation,
        **extras,
    }


def structured_owner_data():
    return {
        "id": FUNCTION_ID,
        "slug": "command-fixture",
        "canonical": {
            "name": "Command fixture",
            "command": {
                "primary": "PLUS-OPEN",
                "modes": ["PLUS-CLOSED"],
                "mode_ids": [MODE_ID],
            },
        },
        "legacy": {"commands": ["PLUS-OLD"], "command_ids": [LEGACY_ID]},
        "aliases": {"commands": ["PLUS-ALIAS"], "command_ids": [ALIAS_ID]},
        "lifecycle": {
            "persistence": "temporary",
            "release": {"required": False, "command": "PLUS-END", "command_id": RELEASE_ID},
        },
        "command_phrases": [
            {
                "id": SPECIAL_ID,
                "phrase": "Plus Close Access",
                "source_narration_key": "hplus.function.ocf-cog-999.access-close",
                "status": "observed",
            }
        ],
        "commands": [
            command_record(
                PRIMARY_ID,
                {"source": "canonical-primary"},
                "activation",
                designation="primary",
            ),
            command_record(
                MODE_ID,
                {"source": "canonical-mode", "command_id": MODE_ID},
                "close",
                relationships={"closes": [PRIMARY_ID]},
            ),
            command_record(
                RELEASE_ID,
                {"source": "lifecycle-release"},
                "release",
                relationships={"releases": [PRIMARY_ID]},
            ),
            command_record(
                LEGACY_ID,
                {"source": "legacy-command", "command_id": LEGACY_ID},
                "auxiliary",
            ),
            command_record(
                ALIAS_ID,
                {"source": "alias-command", "command_id": ALIAS_ID},
                "auxiliary",
            ),
            command_record(
                SPECIAL_ID,
                {"source": "special-phrase", "phrase_id": SPECIAL_ID},
                "access-close",
            ),
        ],
    }


def test_command_records_resolve_existing_phrase_sources_without_copying_phrases():
    record = FunctionRecord(
        FUNCTION_ID, "command-fixture", Path("fixture.yaml"), structured_owner_data()
    )
    commands = {command.id: command for command in record.command_records}

    assert resolve_phrase(record, commands[PRIMARY_ID]) == "PLUS-OPEN"
    assert resolve_phrase(record, commands[MODE_ID]) == "PLUS-CLOSED"
    assert resolve_phrase(record, commands[RELEASE_ID]) == "PLUS-END"
    assert resolve_phrase(record, commands[LEGACY_ID]) == "PLUS-OLD"
    assert resolve_phrase(record, commands[ALIAS_ID]) == "PLUS-ALIAS"
    assert resolve_phrase(record, commands[SPECIAL_ID]) == "Plus Close Access"
    assert validate_command_records(record) == []


@pytest.mark.parametrize(
    "phrase_ref",
    [
        {"source": "canonical-mode", "command_id": "OCF-CMD-COG-999-MISSING"},
        {"source": "legacy-command", "command_id": "OCF-CMD-COG-999-MISSING"},
        {"source": "alias-command", "command_id": "OCF-CMD-COG-999-MISSING"},
        {"source": "special-phrase", "phrase_id": "OCF-CMD-COG-999-MISSING"},
    ],
)
def test_missing_phrase_references_fail_closed(phrase_ref):
    data = structured_owner_data()
    command = data["commands"][0]
    command["phrase_ref"] = phrase_ref
    record = FunctionRecord(FUNCTION_ID, "command-fixture", Path("fixture.yaml"), data)

    with pytest.raises(CommandMetadataError):
        resolve_phrase(record, record.command_records[0])


def test_command_parent_and_mode_alignment_are_validated():
    data = structured_owner_data()
    data["commands"][0]["function_id"] = "OCF-BOD-999"
    data["canonical"]["command"]["mode_ids"] = []
    record = FunctionRecord(FUNCTION_ID, "command-fixture", Path("fixture.yaml"), data)

    errors = validate_command_records(record)
    assert any("different parent function ID" in error for error in errors)
    assert any("mode_ids must align" in error for error in errors)


def test_command_relationships_reject_unknown_or_self_targets():
    data = structured_owner_data()
    data["commands"][0]["relationships"] = {"releases": [PRIMARY_ID, "OCF-CMD-COG-999-MISSING"]}
    record = FunctionRecord(FUNCTION_ID, "command-fixture", Path("fixture.yaml"), data)

    errors = validate_command_records(record)
    assert any("unknown IDs" in error for error in errors)
    assert any("cannot relate to itself" in error for error in errors)


def test_procedure_catalog_is_valid_and_command_override_is_explicit(tmp_path):
    catalog_path = tmp_path / "command-procedures.yaml"
    catalog_path.write_text(
        """schema_version: '1.0'
procedures:
  - id: OCF-PROC-INHALE-HOLD-EXHALE
    source_narration_keys: [hplus.function.ocf-cog-999.function-body]
    steps:
      - {id: inhale, operation: inhale}
      - {id: hold, operation: hold-breath}
      - {id: exhale, operation: exhale}
""",
        encoding="utf-8",
    )
    catalog = load_procedure_catalog(catalog_path)
    command = {
        "procedure": {
            "ref": "OCF-PROC-INHALE-HOLD-EXHALE",
            "status": "documented",
            "override_steps": [{"id": "breathe", "operation": "breathe-normally"}],
        }
    }

    steps = resolve_procedure(
        FunctionCommand.from_dict(
            {
                **command_record(
                    PRIMARY_ID, {"source": "canonical-primary"}, "activation", "primary"
                ),
                **command,
            }
        ),
        catalog,
    )
    assert [step["operation"] for step in steps] == ["breathe-normally"]

    extended = FunctionCommand.from_dict(
        {
            **command_record(PRIMARY_ID, {"source": "canonical-primary"}, "activation", "primary"),
            "procedure": {
                "ref": "OCF-PROC-INHALE-HOLD-EXHALE",
                "status": "documented",
                "before_steps": [{"id": "purpose", "operation": "select-purpose"}],
                "after_steps": [{"id": "release", "operation": "release-temporary-application"}],
            },
        }
    )
    steps = resolve_procedure(extended, catalog)
    assert [step["operation"] for step in steps] == [
        "select-purpose",
        "inhale",
        "hold-breath",
        "exhale",
        "release-temporary-application",
    ]


def test_legacy_function_records_still_expose_existing_command_accessors():
    data = {
        "id": FUNCTION_ID,
        "slug": "legacy-command-fixture",
        "canonical": {"command": {"primary": "PLUS-THINK", "modes": ["PLUS-THINK MORE"]}},
        "legacy": {"commands": ["PLUS-OLD"]},
    }
    record = FunctionRecord(FUNCTION_ID, "legacy-command-fixture", Path("fixture.yaml"), data)

    assert record.canonical_command == "PLUS-THINK"
    assert record.command_modes == ["PLUS-THINK MORE"]
    assert record.legacy_commands == ["PLUS-OLD"]
    assert record.command_records == []


def test_function_schema_accepts_optional_structured_commands():
    path = REPO_ROOT / "functions/foundation/attention.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["commands"] = [
        {
            "id": "OCF-CMD-FND-002-ACTIVATE",
            "function_id": "OCF-FND-002",
            "phrase_ref": {"source": "canonical-primary"},
            "role": "activation",
            "designation": "primary",
            "effect_scope_ref": "lifecycle.persistence",
            "localization": {
                "label_key": "commands.ocf-fnd-002.activate.label",
                "explanation_key": "commands.ocf-fnd-002.activate.explanation",
            },
            "documentation": {"visible": True, "order": 1},
        }
    ]
    schema = yaml.safe_load(schema_path("function.schema.json").read_text())
    assert validate_against_schema(data, schema) == []
    invalid = {**data, "commands": [{**data["commands"][0], "designation": "tertiary"}]}
    assert validate_against_schema(invalid, schema)


def test_command_collection_rejects_duplicate_ids_across_functions():
    first_data = structured_owner_data()
    second_data = structured_owner_data()
    second_data["id"] = "OCF-BOD-999"
    second_data["slug"] = "another-function"
    for command in second_data["commands"]:
        command["function_id"] = second_data["id"]
    records = [
        FunctionRecord(FUNCTION_ID, "command-fixture", Path("first.yaml"), first_data),
        FunctionRecord("OCF-BOD-999", "another-function", Path("second.yaml"), second_data),
    ]

    errors = validate_command_collection(records)
    assert any(f"duplicate command ID {PRIMARY_ID}" in error for error in errors)


def test_unknown_procedure_reference_is_reported_by_command_validation():
    data = structured_owner_data()
    data["commands"][0]["procedure"] = {
        "ref": "OCF-PROC-MISSING",
        "status": "documented",
    }
    record = FunctionRecord(FUNCTION_ID, "command-fixture", Path("fixture.yaml"), data)

    result = validate_command_metadata([record])
    assert any(issue.code == "command-procedure-reference" for issue in result.errors)
