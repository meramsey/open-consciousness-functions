"""Localized, deterministic command-guide generation contracts."""

import json

import pytest
from ocf_tools.cli import _build_parser
from ocf_tools.command_docs import (
    build_command_index,
    generated_command_documents,
    render_command_index,
    render_function_sheet,
    render_quick_reference,
)

pytestmark = pytest.mark.unit


def test_localized_command_data_preserves_canonical_phrases_and_fallback_provenance():
    index = build_command_index("es")

    assert index["locale"] == "es"
    assert index["function_count"] > 0
    assert index["command_count"] > index["function_count"]
    assert index["fallback_count"] > 0
    assert all(row["locale"] == "en-US" for row in index["fallbacks"])

    sleep = next(item for item in index["functions"] if item["function_id"] == "OCF-SLP-005")
    activation = next(item for item in sleep["commands"] if item["designation"] == "primary")
    assert activation["phrase"] == "PLUS-SLEEP EASY"
    assert activation["observed_phrase"]["text"] == "Plus Quiet Sleep"

    rendered = render_command_index(index)
    assert "locale fallback chain" in rendered
    assert "PLUS-SLEEP EASY" in rendered


def test_generated_command_documents_are_deterministic_and_include_function_sheets():
    first = generated_command_documents()
    second = generated_command_documents()

    assert first == second
    paths = {path for path, _ in first}
    assert "docs/COMMAND_INDEX.md" in paths
    assert "docs/COMMAND_QUICK_REFERENCE.md" in paths
    assert "function-command-index.json" in paths
    assert "docs/functions/OCF-SLP-005.md" in paths
    export = next(content for path, content in first if path == "function-command-index.json")
    payload = export.split("\n\n", 1)[1]
    assert json.loads(payload)["command_count"] > 0


def test_reference_renders_scope_secondary_roles_and_role_specific_procedures():
    index = build_command_index("en-US")
    functions = {item["function_id"]: item for item in index["functions"]}

    zoning = render_function_sheet(functions["OCF-EXP-002"], index)
    assert "Function persistence**: Temporary" in zoning
    assert "Cancellation sequence" in zoning
    assert "Release sequence" in zoning
    assert "**Activation procedure**" not in zoning

    short_fix = render_function_sheet(functions["OCF-BOD-015"], index)
    release_section = short_fix.split("## PLUS-RELEASE", 1)[1]
    assert "Release sequence" in release_section
    assert "Close your eyes" not in release_section

    access = render_function_sheet(functions["OCF-FND-001"], index)
    assert "Access-channel close cue" in access
    assert "Access channel (separate from function persistence)" in render_command_index(index)

    quick_reference = render_quick_reference(index)
    assert "Release command: Plus Release" in quick_reference
    assert "Function persistence" in quick_reference
    assert "Permanent" in quick_reference


def test_commands_cli_parser_keeps_list_describe_and_export_interfaces():
    parser = _build_parser()

    assert (
        parser.parse_args(["commands", "list", "--locale", "es", "--json"]).command_kind == "list"
    )
    describe = parser.parse_args(["commands", "describe", "OCF-SLP-005"])
    assert describe.function == "OCF-SLP-005"
    export = parser.parse_args(["commands", "export", "--format", "md", "--force"])
    assert export.format == "md"
    assert export.force
