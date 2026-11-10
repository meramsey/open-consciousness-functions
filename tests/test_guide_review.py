"""Canonical optional relationship decisions feed read-only guide projections."""

from pathlib import Path
from urllib.parse import quote

import pytest
from ocf_tools import guide_review as review
from ocf_tools import listening_guides as guides
from ocf_tools.command_docs import _function_document
from ocf_tools.indexes import load_all_functions, load_function_by_id
from ocf_tools.locale import LocaleCatalog
from ocf_tools.models import FunctionRecord


@pytest.mark.integration
def test_owner_approved_relationships_are_hash_provenance_and_canonical_text():
    assert review.verify() == []
    rows = review.record()["decisions"]
    assert len(rows) == 33
    for row in rows:
        owner = load_function_by_id(row["source_id"])
        projection = next(
            item
            for item in review.relationships(owner)
            if item["relationship_id"] == row["relationship_id"]
        )
        assert projection["approved_explanation"]
        assert projection["dependency"] == "optional"
        assert len(projection["source_row_sha256"]) == 64
        assert "before" not in projection


@pytest.mark.integration
def test_all_canonical_guides_render_the_existing_commands_and_scopes():
    documents = guides.markdown_documents()
    catalog = LocaleCatalog()
    count = 0
    for owner in load_all_functions():
        text = documents["functions/" + guides.function_guide_stem(owner, catalog=catalog) + ".md"]
        document = _function_document(owner, "en-US", catalog)
        for command in document["commands"]:
            if command["role"] in {"legacy-alias", "access-close"}:
                continue
            count += 1
            for i, step in enumerate(command["procedure_steps"], 1):
                assert f"{i}. {step['instruction']['text']}" in text
        for scope in document["lifecycle_scopes"]:
            assert scope["description"]["text"] in text
    assert count == 72


@pytest.mark.unit
def test_companion_validation_rejects_self_and_unknown(monkeypatch):
    from ocf_tools import validators

    record = FunctionRecord(
        "OCF-TST-001", "test", Path("test.yaml"), {"companions": ["OCF-TST-001", "OCF-TST-999"]}
    )
    monkeypatch.setattr(validators, "load_all_functions", lambda: [record])
    result = validators.validate_collection()
    assert len([issue for issue in result.issues if issue.code == "invalid-companion"]) == 2
    record.data["companions"] = [{}]
    assert validators.validate_collection().issues[0].code == "invalid-companion"
    record.data["companions"] = None
    assert not validators.validate_collection().issues


@pytest.mark.integration
def test_reader_guides_adopt_relationships_and_separate_historical_lookup():
    records = load_all_functions()
    refs = guides.reference_documents(records)
    assert "Legacy alias" not in refs["cue-reference.md"]
    assert "PLUS-TOUCH GREATER" in refs["historical-lookup.md"]
    legacy = [record for record in records if record.data.get("legacy", {}).get("name")]
    assert len(legacy) == 55
    for record in legacy:
        assert record.data["legacy"]["name"] in refs["historical-lookup.md"]
        assert (
            quote("functions/" + guides.function_guide_stem(record) + ".md")
            in refs["historical-lookup.md"]
        )
    assert "DRAFT" not in refs["relationship-map.md"]
    assert "OCF-BOD-003" in refs["complementary-map.md"]
    assert "(draft)" not in refs["tag-discovery.md"]
    for record in records:
        text = guides.function_guide_markdown(record)
        assert "(draft)" not in text and "Draft optional suggestions" not in text
        assert "## Access Close" not in text and "### Access channel closure" not in text
