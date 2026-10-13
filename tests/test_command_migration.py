"""Repository integration contracts for the 55 migrated function commands."""

import pytest
from ocf_tools.commands import (
    load_procedure_catalog,
    resolve_phrase,
    resolve_procedure,
    validate_command_collection,
)
from ocf_tools.indexes import load_all_functions
from ocf_tools.validators import validate_command_metadata

pytestmark = pytest.mark.integration


def test_all_55_function_commands_resolve_with_legacy_fields_unchanged():
    functions = load_all_functions()
    assert len(functions) == 55
    command_ids = []
    primary_count = mode_count = legacy_phrase_count = 0
    procedures = load_procedure_catalog()

    for function in functions:
        data = function.to_dict()
        commands = function.command_records
        assert commands
        assert all(command.function_id == function.id for command in commands)
        by_id = {command.id: command for command in commands}
        assert len(by_id) == len(commands)

        primary = [
            command for command in commands if command.phrase_ref["source"] == "canonical-primary"
        ]
        assert len(primary) == 1
        assert primary[0].designation == "primary"
        assert resolve_phrase(function, primary[0]) == function.canonical_command
        primary_count += 1

        modes = data["canonical"]["command"]["modes"]
        mode_ids = data["canonical"]["command"]["mode_ids"]
        assert len(mode_ids) == len(modes)
        for phrase, command_id in zip(modes, mode_ids, strict=True):
            command = by_id[command_id]
            assert command.phrase_ref == {"source": "canonical-mode", "command_id": command_id}
            assert resolve_phrase(function, command) == phrase
            mode_count += 1

        assert len(data["legacy"]["command_ids"]) == len(function.legacy_commands)
        assert len(data["aliases"]["command_ids"]) == len(data["aliases"]["commands"])
        for phrase, command_id in zip(
            function.legacy_commands, data["legacy"]["command_ids"], strict=True
        ):
            assert resolve_phrase(function, by_id[command_id]) == phrase
            legacy_phrase_count += 1
        for phrase, command_id in zip(
            data["aliases"]["commands"], data["aliases"]["command_ids"], strict=True
        ):
            assert resolve_phrase(function, by_id[command_id]) == phrase

        assert data["documentation"]["title_key"]
        assert data["documentation"]["short_description_key"]
        assert data["documentation"]["purpose_key"]
        assert primary[0].procedure["status"] == "documented"
        assert resolve_procedure(primary[0], procedures)
        command_ids.extend(by_id)

    assert primary_count == 55
    assert mode_count == 10
    assert legacy_phrase_count == 65
    assert len(command_ids) == len(set(command_ids)) == 98
    assert not validate_command_collection(functions)
    assert validate_command_metadata(functions).ok


def test_directional_modes_and_relationships_are_structured():
    functions = {function.id: function for function in load_all_functions()}
    expected = {
        "OCF-BOD-010": ("OCF-CMD-BOD-010-FOOD-LESS", "decrease"),
        "OCF-BOD-012": ("OCF-CMD-BOD-012-SEX-LESS", "decrease"),
        "OCF-SEN-001": ("OCF-CMD-SEN-001-HEAR-LESS", "decrease"),
        "OCF-SEN-002": ("OCF-CMD-SEN-002-SEE-LESS", "decrease"),
        "OCF-SEN-003": ("OCF-CMD-SEN-003-SMELL-LESS", "decrease"),
        "OCF-SEN-004": ("OCF-CMD-SEN-004-TASTE-LESS", "decrease"),
        "OCF-SEN-005": ("OCF-CMD-SEN-005-TOUCH-LESS", "decrease"),
    }
    for function_id, (mode_id, role) in expected.items():
        function = functions[function_id]
        commands = {command.id: command for command in function.command_records}
        assert commands[mode_id].role == role
        primary = next(c for c in commands.values() if c.designation == "primary")
        assert commands[mode_id].relationships["pairs_with"] == [primary.id]
        assert commands[mode_id].relationships["modifies"] == [primary.id]
        assert primary.id in commands[mode_id].relationships["pairs_with"]


def test_sleep_easy_and_special_release_commands_preserve_semantic_conflicts():
    functions = {function.id: function for function in load_all_functions()}

    sleep_easy = functions["OCF-SLP-005"]
    primary = next(c for c in sleep_easy.command_records if c.designation == "primary")
    assert resolve_phrase(sleep_easy, primary) == "PLUS-SLEEP EASY"
    assert primary.observed_phrase["text"] == "Plus Quiet Sleep"
    assert primary.observed_phrase["relationship"] == "conflict"
    assert sleep_easy.source_availability == "unavailable"
    assert sleep_easy.reimplementation_status == "planned"

    zoning = functions["OCF-EXP-002"]
    zoning_commands = {command.id: command for command in zoning.command_records}
    primary_id = "OCF-CMD-EXP-002-PRIMARY"
    cancel_id = "OCF-CMD-EXP-002-CANCEL"
    release_id = "OCF-CMD-EXP-002-RELEASE"
    assert zoning_commands[cancel_id].relationships["cancels"] == [primary_id]
    assert zoning_commands[release_id].relationships["releases"] == [primary_id]
    assert zoning.data["lifecycle"]["release"]["command_id"] == release_id
    assert zoning.release_command is None

    access = functions["OCF-FND-001"]
    access_close = next(c for c in access.command_records if c.role == "access-close")
    assert resolve_phrase(access, access_close) == "Plus Release Eleven Access"
    assert access_close.phrase_ref["source"] == "special-phrase"

    strong_quick = functions["OCF-PRF-006"]
    releases = [c for c in strong_quick.command_records if c.role == "release"]
    assert len(releases) == 1
    assert resolve_phrase(strong_quick, releases[0]) == "Plus Release"
    assert releases[0].id == "OCF-CMD-PRF-006-RELEASE"


def test_all_source_unavailable_functions_remain_planned():
    unavailable = [
        function
        for function in load_all_functions()
        if function.source_availability == "unavailable"
    ]
    assert len(unavailable) == 16
    assert all(function.reimplementation_status == "planned" for function in unavailable)
