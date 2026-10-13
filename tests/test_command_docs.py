"""Localized, deterministic command-guide generation contracts."""

import json

import pytest
from ocf_tools.cli import _build_parser
from ocf_tools.command_docs import (
    build_command_index,
    generated_command_documents,
    render_command_index,
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
