"""Provenance errors must not be masked by good OCF implementation quality."""

from copy import deepcopy

from ocf_tools.content import discover, validate_layers, validate_library
from ocf_tools.indexes import load_function_by_id
from tools.extract_function_content import initialize


def layers():
    record = load_function_by_id("OCF-FND-004")
    inventory = {
        "files": [
            {
                "function_id": record.id,
                "sha256": "a" * 64,
                "path": "mockup.txt",
                "evidence_class": "reconstructed_mockup",
                "completeness": "not applicable",
                "candidate_locators": {"main": [3]},
                "source_type": "txt",
            }
        ]
    }
    return initialize(inventory, record, [])


def test_mockup_cannot_be_authenticated_or_historical_evidence():
    data = layers()
    assert validate_layers(data, "OCF-FND-004") == []
    bad = deepcopy(data)
    bad["evidence"]["sources"][0]["authentication"] = "authenticated"
    assert validate_layers(bad, "OCF-FND-004")
    bad = deepcopy(data)
    bad["evidence"]["observations"][0]["scope"] = "historical"
    assert any("historical assertion" in error for error in validate_layers(bad, "OCF-FND-004"))


def test_locale_binding_cannot_redefine_provenance_and_decisions_cannot_be_facts():
    data = layers()
    data["bindings"]["evidence_class"] = "source_transcript"
    assert validate_layers(data, "OCF-FND-004")
    data = layers()
    data["decisions"]["decisions"] = [
        {
            "id": "test",
            "kind": "source-fact",
            "description": "Choice",
            "status": "provisional",
            "material_change": True,
            "human_review": "required",
        }
    ]
    assert validate_layers(data, "OCF-FND-004")


def test_references_unknown_blocks_and_review_promotion_rejected():
    data = layers()
    data["specifications"]["blocks"]["main"]["evidence_refs"] = ["invented"]
    assert "specification references unknown evidence observation" in validate_layers(
        data, "OCF-FND-004"
    )
    data = layers()
    data["specifications"]["human_review"] = "approved"
    assert validate_layers(data, "OCF-FND-004")


def test_library_and_rich_discovery_keep_unknown_requirements_explicit():
    assert validate_library() == []
    data = discover(load_function_by_id("OCF-FND-004"))
    assert data["activation"]["primary"] == "PLUS-RELAX"
    assert data["duration"] is None
    assert data["human_review"] in ("unknown", "required")


def test_rich_cli_schema_and_pilot_freeze(capsys):
    import json

    from ocf_tools.cli import main
    from ocf_tools.validators import _load_schema, validate_against_schema

    assert main(["functions", "describe", "relax", "--rich", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert validate_against_schema(data, _load_schema("function-discovery.schema.json")) == []
    row = data["functions"][0]
    assert row["content_maturity"] == "pilot" and row["human_review"] == "required"
    assert row["states"]["status"] == "unknown"
    assert row["locales"] == ["en-US"]
