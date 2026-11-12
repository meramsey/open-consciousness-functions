"""Public website export is a deterministic, narration-free canonical projection."""

from copy import deepcopy

import pytest
from ocf_tools import public_site_export as export
from ocf_tools.utils import OCFError, OCFFileExistsError

pytestmark = pytest.mark.unit
SOURCE_COMMIT = "a" * 40


def test_export_is_deterministic_and_contains_only_allowlisted_public_fields():
    first = export.export_data(source_commit=SOURCE_COMMIT)
    second = export.export_data(source_commit=SOURCE_COMMIT)

    assert first == second
    assert len(first["functions"]) == first["build_receipt"]["function_count"] == 58
    assert len({row["function_id"] for row in first["functions"]}) == 58
    assert first["build_receipt"]["approved_relationship_count"] == 33
    assert first["source_commit"] == SOURCE_COMMIT
    assert first["build_receipt"]["narration_text_included"] is False
    assert first["build_receipt"]["source_evidence_paths_included"] is False
    assert first["build_receipt"]["draft_procedures_included"] is False
    assert first["build_receipt"]["relationship_proposals_included"] is False
    assert all(
        row["documentation_status"] == "canonical-function-resource" for row in first["functions"]
    )
    assert all(
        row["canonical_resource"].startswith("locales/en-US/OCF-") for row in first["functions"]
    )
    assert all(
        command["command_status"] == "active"
        for row in first["functions"]
        for command in row["commands"]
    )
    assert sum(len(row["historical_commands"]) for row in first["functions"]) == 10
    assert all(
        command["command_status"] == "historical-inactive"
        for row in first["functions"]
        for command in row["historical_commands"]
    )
    assert all(
        step["instruction"]
        for row in first["functions"]
        for command in row["commands"]
        for step in command["procedure_steps"]
    )

    def nested_keys(value):
        if isinstance(value, dict):
            yield from value.keys()
            for child in value.values():
                yield from nested_keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from nested_keys(child)

    keys = set(nested_keys(first["functions"]))
    assert not keys & {
        "entries",
        "narration",
        "narration_text",
        "source_path",
        "source_sha256",
        "evidence",
        "bindings",
        "editorial_decisions",
        "historical_lookup",
    }
    encoded = str(first)
    assert "HumanPlusTranscripts" not in encoded
    assert "F11 V4.flac" not in encoded


def test_export_requires_exact_source_commit_and_approved_function_fields(monkeypatch):
    with pytest.raises(OCFError, match="exact 40-character source commit"):
        export.export_data(source_commit="not-a-commit")

    catalog = export.LocaleCatalog()
    first = next(iter(catalog.canonical.localized_functions))
    catalog.canonical.localized_functions[first] = deepcopy(
        catalog.canonical.localized_functions[first]
    )
    catalog.canonical.localized_functions[first]["title"]["status"] = "draft"
    monkeypatch.setattr(export, "LocaleCatalog", lambda *_args, **_kwargs: catalog)
    with pytest.raises(OCFError, match="requires reviewed title"):
        export.export_data(source_commit=SOURCE_COMMIT)


def test_export_uses_only_approved_relationship_projection(monkeypatch):
    catalog = export.LocaleCatalog()
    approved_index = export.build_command_index("en-US", catalog)
    source = next(row for row in approved_index["functions"] if row["related_functions"])
    identity = source["function_id"]
    metadata = deepcopy(catalog.canonical.localized_functions[identity])
    metadata.setdefault("relationships", {}).setdefault("related_functions", []).append(
        {
            "function_id": "OCF-FND-002",
            "description": {
                "text": "Unapproved keyless description must not be published.",
                "status": "reviewed",
            },
            "relationship_type": "related",
        }
    )
    catalog.canonical.localized_functions[identity] = metadata
    monkeypatch.setattr(export, "LocaleCatalog", lambda *_args, **_kwargs: catalog)

    result = export.export_data(source_commit=SOURCE_COMMIT)
    exported = next(row for row in result["functions"] if row["function_id"] == identity)
    assert result["build_receipt"]["approved_relationship_count"] == 33
    assert len(exported["related_functions"]) == len(source["related_functions"])
    assert "Unapproved keyless description must not be published." not in str(result)
    approved_count = 0
    exported_by_function = {row["function_id"]: row for row in result["functions"]}
    for source_function in approved_index["functions"]:
        relations = source_function["related_functions"]
        approved_count += len(relations)
        projected = exported_by_function[source_function["function_id"]]["related_functions"]
        assert len(projected) == len(relations)
        by_id = {row["function_id"]: row for row in projected}
        for relation in relations:
            item = by_id[relation["function_id"]]
            assert item["relationship_id"] == relation["relationship_id"]
            assert item["title"] == relation["title"]["text"]
            assert item["description"] == relation["description"]["text"]
            assert item["relationship_type"] == relation["relationship_type"]
            assert item["direction"] == "outgoing"
            assert item["dependency"] == relation["dependency"] == "optional"
    assert approved_count == 33


def test_draft_procedure_is_excluded_as_a_whole(monkeypatch):
    original = export.build_command_index

    def draft_one_step(locale, catalog):
        rows = deepcopy(original(locale, catalog))
        command = rows["functions"][0]["commands"][0]
        command["procedure_steps"][0]["instruction"]["status"] = "draft"
        return rows

    monkeypatch.setattr(export, "build_command_index", draft_one_step)
    result = export.export_data(source_commit=SOURCE_COMMIT)
    function = next(row for row in result["functions"] if row["function_id"] == "OCF-AUT-001")
    command = function["commands"][0]
    assert command["procedure_status"] == "review-pending"
    assert command["procedure_steps"] == []
    assert result["build_receipt"]["draft_procedures_included"] is False


def test_export_file_uses_exclusive_atomic_publication(tmp_path):
    output = tmp_path / "website-guides.json"
    receipt = export.write_export(output, source_commit=SOURCE_COMMIT)
    assert receipt["function_count"] == 58
    original = output.read_bytes()
    with pytest.raises(OCFFileExistsError):
        export.write_export(output, source_commit=SOURCE_COMMIT)
    assert output.read_bytes() == original
