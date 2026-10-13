"""Provenance errors must not be masked by good OCF implementation quality."""

import json
from copy import deepcopy

import pytest
from ocf_tools.content import discover, validate_layers, validate_library
from ocf_tools.indexes import load_function_by_id
from ocf_tools.utils import OCFError
from tools import extract_function_content
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


def test_initialize_deduplicates_evidence_and_selects_only_matching_template_resources():
    record = load_function_by_id("OCF-FND-004")
    digest = "a" * 64
    inventory = {
        "files": [
            {
                "function_id": record.id,
                "sha256": digest,
                "path": "source.txt",
                "evidence_class": "partial_source_transcript",
                "completeness": "explicit gaps",
                "candidate_locators": {"opener": [1], "main": [2], "unknown-category": [3]},
                "source_type": "txt",
            },
            {
                "function_id": record.id,
                "sha256": digest,
                "path": "same-source.txt",
                "evidence_class": "source_transcript",
                "completeness": "review pending",
                "candidate_locators": {"opener": [1]},
                "source_type": "pdf",
            },
            {
                "function_id": "OCF-XXX-001",
                "sha256": "b" * 64,
                "path": "other.txt",
                "evidence_class": "source_transcript",
                "completeness": "review pending",
                "candidate_locators": {"main": [1]},
                "source_type": "txt",
            },
        ]
    }
    templates = [
        {
            "id": "OCF-TPL-PILOT-001",
            "function_id": record.id,
            "sections": [
                {
                    "narration": {
                        "en": {"narration_key": "shared.key"},
                        "es": {"narration_key": "es.key"},
                    }
                }
            ],
        },
        {"id": "other", "function_id": "OCF-XXX-001", "sections": []},
    ]
    data = initialize(inventory, record, templates)
    assert len(data["evidence"]["sources"]) == 1
    assert len(data["evidence"]["observations"]) == 3
    assert data["specifications"]["blocks"]["opener"]["status"] == "inferred"
    assert data["specifications"]["blocks"]["main"]["status"] == "inferred"
    assert data["specifications"]["maturity"] == "pilot"
    assert data["bindings"]["narration_resources"] == [
        {"locale": "en-US", "key": "es.key"},
        {"locale": "en-US", "key": "shared.key"},
    ]


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


def test_content_validation_stops_after_unknown_layer_or_identity_failure():
    data = layers()
    assert "unknown content layer: transcript" in validate_layers(
        {**data, "transcript": {}}, "OCF-FND-004"
    )
    wrong = deepcopy(data)
    wrong["evidence"]["function_id"] = "OCF-TST-001"
    assert "evidence: function identity mismatch" in validate_layers(wrong, "OCF-FND-004")


def test_evidence_observation_identity_and_source_references_are_unique():
    data = layers()
    observation = deepcopy(data["evidence"]["observations"][0])
    data["evidence"]["observations"].append(observation)
    assert "duplicate observation identity" in validate_layers(data, "OCF-FND-004")

    data = layers()
    data["evidence"]["observations"][0]["source_sha256"] = "f" * 64
    assert "observation refers to unknown source fingerprint" in validate_layers(
        data, "OCF-FND-004"
    )


def test_validation_checks_explicit_source_review_and_runtime_bindings(monkeypatch):
    from ocf_tools import session
    from ocf_tools.indexes import load_yaml_file
    from ocf_tools.paths import REPO_ROOT

    data = layers()
    spec = data["specifications"]
    review = load_yaml_file(REPO_ROOT / "function-content/specifications/OCF-FND-004.yaml")[
        "analysis_review"
    ]
    review["source_extent"].update(file="mockup.txt", source_sha256="a" * 64, start_line=2)
    for answer in review["sections"].values():
        for locator in answer["locators"]:
            locator.update(file="mockup.txt", source_sha256="a" * 64)
    locator = review["sections"]["main"]["locators"][0]
    locator.update(file="unknown.txt", source_sha256="b" * 64, start_line=7, end_line=6)
    spec["analysis_review"] = review
    errors = validate_layers(data, "OCF-FND-004")
    assert "review locator references unknown/mismatched source identity" in errors
    assert "review locator has invalid/incomplete source range" in errors
    assert "completed review must inspect the full available source from line1" in errors

    data = layers()
    data["bindings"]["session_templates"] = ["missing-template"]
    monkeypatch.setattr(
        session, "load_template", lambda _reference: (_ for _ in ()).throw(OCFError("not found"))
    )
    assert "not found" in validate_layers(data, "OCF-FND-004")
    monkeypatch.setattr(session, "load_template", lambda _reference: {"function_id": "OCF-XXX-999"})
    assert "template binding has a different function identity" in validate_layers(
        data, "OCF-FND-004"
    )

    data = layers()
    data["bindings"]["narration_resources"] = [{"locale": "zz-ZZ", "key": "absent.key"}]
    assert "binding refers to an unavailable locale resource" in validate_layers(
        data, "OCF-FND-004"
    )


def test_library_reports_unknown_records_and_bad_layers(monkeypatch, tmp_path):
    from ocf_tools import content

    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "OCF-XXX-999.yaml").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(content, "CONTENT_DIR", tmp_path)
    assert content.validate_library() == ["unknown function content: OCF-XXX-999"]


def test_layer_loader_and_library_report_invalid_content(monkeypatch, tmp_path):
    from ocf_tools import content

    monkeypatch.setattr(content, "validate_layers", lambda *_args: ["invalid synthetic layer"])
    with pytest.raises(OCFError, match="function content: invalid synthetic layer"):
        content.load_layers("OCF-FND-004", tmp_path)

    monkeypatch.setattr(content, "CONTENT_DIR", tmp_path)
    monkeypatch.setattr(content, "load_all_functions", lambda: [load_function_by_id("OCF-FND-004")])
    errors = content.validate_library()
    assert errors == ["function content: invalid synthetic layer"]


def test_extract_driver_preflights_and_persists_idempotent_partial_layers(
    monkeypatch, tmp_path, capsys
):
    record = load_function_by_id("OCF-FND-004")
    inventory = tmp_path / "inventory.json"
    inventory.write_text('{"files": []}', encoding="utf-8")
    output = tmp_path / "partial-content"
    (tmp_path / "audio/templates/sessions").mkdir(parents=True)
    monkeypatch.setattr(extract_function_content, "ROOT", tmp_path)
    monkeypatch.setattr(extract_function_content, "load_all_functions", lambda: [record])
    monkeypatch.setattr(extract_function_content, "validate_layers", lambda *_args: [])
    monkeypatch.setattr(
        extract_function_content.sys,
        "argv",
        ["extract_function_content", "--inventory", str(inventory), "--output", str(output)],
    )

    extract_function_content.main()
    assert "Initialized 1 partial research records" in capsys.readouterr().out
    for layer in ("evidence", "specifications", "decisions", "bindings"):
        assert (output / layer / f"{record.id}.yaml").is_file()
    before = {path: path.read_bytes() for path in output.rglob("*.yaml")}
    extract_function_content.main()
    assert before == {path: path.read_bytes() for path in output.rglob("*.yaml")}

    conflict = output / "evidence" / f"{record.id}.yaml"
    conflict.write_text("customized: true\n", encoding="utf-8")
    with pytest.raises(OCFError, match="refusing to overwrite reviewed/customized"):
        extract_function_content.main()


def test_extract_driver_validation_failure_writes_no_partial_layers(monkeypatch, tmp_path):
    record = load_function_by_id("OCF-FND-004")
    inventory = tmp_path / "inventory.json"
    inventory.write_text('{"files": []}', encoding="utf-8")
    output = tmp_path / "partial-content"
    (tmp_path / "audio/templates/sessions").mkdir(parents=True)
    monkeypatch.setattr(extract_function_content, "ROOT", tmp_path)
    monkeypatch.setattr(extract_function_content, "load_all_functions", lambda: [record])
    monkeypatch.setattr(extract_function_content, "validate_layers", lambda *_args: ["bad layer"])
    monkeypatch.setattr(
        extract_function_content.sys,
        "argv",
        ["extract_function_content", "--inventory", str(inventory), "--output", str(output)],
    )
    with pytest.raises(OCFError, match="bad layer"):
        extract_function_content.main()
    assert not output.exists()


def test_extract_driver_script_entrypoint_runs_main(monkeypatch, tmp_path, capsys):
    import runpy
    import sys
    from pathlib import Path

    from ocf_tools import content, indexes

    record = load_function_by_id("OCF-FND-004")
    inventory = tmp_path / "inventory.json"
    inventory.write_text('{"files": []}', encoding="utf-8")
    output = tmp_path / "entrypoint-output"
    original_glob = Path.glob

    def no_committed_templates(path, pattern):
        if path == extract_function_content.ROOT / "audio/templates/sessions":
            return iter(())
        return original_glob(path, pattern)

    monkeypatch.setattr(Path, "glob", no_committed_templates)
    monkeypatch.setattr(indexes, "load_all_functions", lambda: [record])
    monkeypatch.setattr(content, "validate_layers", lambda *_args: [])
    monkeypatch.setattr(
        sys,
        "argv",
        ["extract_function_content.py", "--inventory", str(inventory), "--output", str(output)],
    )
    runpy.run_path(str(Path(extract_function_content.__file__)), run_name="__main__")
    assert "Initialized 1 partial research records" in capsys.readouterr().out
    assert (output / "evidence" / f"{record.id}.yaml").is_file()


def test_library_and_rich_discovery_keep_unknown_requirements_explicit():
    assert validate_library() == []
    data = discover(load_function_by_id("OCF-FND-004"))
    assert data["activation"]["primary"] == "PLUS-RELAX"
    assert {command["phrase"] for command in data["commands"]} >= {"PLUS-RELAX"}
    assert data["commands"]
    assert data["duration"] is None
    assert data["human_review"] in ("unknown", "required")


def test_rich_cli_schema_and_pilot_freeze(capsys):

    from ocf_tools.cli import main
    from ocf_tools.validators import _load_schema, validate_against_schema

    assert main(["functions", "describe", "relax", "--rich", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert validate_against_schema(data, _load_schema("function-discovery.schema.json")) == []
    row = data["functions"][0]
    assert row["content_maturity"] == "pilot" and row["human_review"] == "required"
    assert row["states"]["status"] == "unknown"
    assert row["locales"] == ["en-US"]
