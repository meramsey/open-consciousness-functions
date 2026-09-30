"""Generated index tests: contents, determinism, and freshness."""

from __future__ import annotations

import csv
import io
import json

from ocf_tools.generators import (
    availability_matrix_markdown,
    command_review_markdown,
    function_index_csv,
    function_index_json,
    function_index_markdown,
    generate_all_content,
    hplus_command_map_csv,
    hplus_command_map_json,
    indexes_are_fresh,
    reimplementation_roadmap_markdown,
    safety_matrix_markdown,
)

GENERATED_HEADER = "GENERATED FILE — DO NOT EDIT DIRECTLY"


def _csv_rows(text: str) -> list[dict]:
    """Parse a generated CSV, skipping the mandatory banner + blank line."""
    body = "\n".join(text.splitlines()[2:])
    if not body.strip():
        raise AssertionError("generated CSV body is empty")
    return list(csv.DictReader(io.StringIO(body)))


def test_function_index_markdown_has_rows():
    text = function_index_markdown()
    assert text.startswith(GENERATED_HEADER)
    assert "OCF-FND-001" in text
    assert "PLUS-THINK" in text  # canonical invariant surfaces in the index
    assert "PLUS-FOCUS" in text


def test_function_index_csv_has_55_rows():
    text = function_index_csv()
    assert text.startswith(GENERATED_HEADER)
    rows = _csv_rows(text)
    assert len(rows) == 55
    assert rows[0]["ocf_id"].startswith("OCF-")


def test_function_index_json_has_55():
    payload = json.loads(function_index_json().split("\n\n", 1)[1])
    assert payload["count"] == 55
    assert len(payload["functions"]) == 55


def test_command_map_json_round_trips():
    payload = json.loads(hplus_command_map_json().split("\n\n", 1)[1])
    assert payload["count"] == 55
    think = next(m for m in payload["mappings"] if m["legacy_name"] == "THINK FAST")
    assert think["canonical_commands"] == ["PLUS-THINK"]


def test_command_map_csv_has_55():
    rows = _csv_rows(hplus_command_map_csv())
    assert len(rows) == 55


def test_command_review_report_groups():
    text = command_review_markdown()
    assert "Commands retained unchanged" in text
    assert "Commands still requiring review" in text
    assert "Commands normalized" in text


def test_matrices_render():
    assert "39" in availability_matrix_markdown()
    assert "16" in availability_matrix_markdown()
    assert "OCF-FND-001" in reimplementation_roadmap_markdown()
    assert "emergency" in safety_matrix_markdown()


def test_all_generated_content_is_deterministic():
    first = generate_all_content()
    second = generate_all_content()
    assert [(rel, content) for rel, content in first] == [(rel, content) for rel, content in second]


def test_indexes_are_fresh_in_repository():
    assert indexes_are_fresh()


def test_generated_files_carry_header(repo_root):
    for relative, _ in generate_all_content():
        text = (repo_root / relative).read_text(encoding="utf-8")
        assert text.startswith(GENERATED_HEADER), relative
