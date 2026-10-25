"""Approved guide projection and unchanged-behavior regression contracts."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from ocf_tools import guide_review as review
from ocf_tools import listening_guides as guides
from ocf_tools.command_docs import _function_document
from ocf_tools.indexes import load_all_functions
from ocf_tools.locale import LocaleCatalog
from ocf_tools.models import FunctionRecord
from ocf_tools.utils import OCFError


@pytest.mark.unit
def test_metadata_scope_does_not_authorize_behavior_or_speech():
    before = {
        "id": "OCF-FND-002",
        "purpose": {"summary": "Focus.", "community_description": "Focus."},
        "companions": [],
        "commands": [{"spoken": "Plus Focus"}],
        "lifecycle": {"persistence": "temporary"},
        "narration": {"sequence": ["unchanged"]},
    }
    after = deepcopy(before)
    after["companions"] = ["OCF-COG-007"]
    review.check_function_scope(before, after)
    for field, value in (
        ("commands", [{"spoken": "Different"}]),
        ("lifecycle", {"persistence": "permanent"}),
        ("narration", {"sequence": ["changed"]}),
        ("companions", ["OCF-COG-006"]),
    ):
        changed = deepcopy(after)
        changed[field] = value
        with pytest.raises(OCFError, match="metadata-only scope"):
            review.check_function_scope(before, changed)


@pytest.mark.unit
def test_unapproved_relationships_are_not_published(tmp_path):
    owner = FunctionRecord(
        "OCF-TST-001", "test", Path("test.yaml"), {"companions": ["OCF-TST-002"]}
    )
    with pytest.raises(OCFError, match="matching guide approval"):
        review.relationships(owner, root=tmp_path)
    owner.data["companions"] = []
    assert review.relationships(owner, root=tmp_path) == []


@pytest.mark.unit
def test_ordered_html_instructions_are_semantic_and_escaped():
    html = guides.html_bytes("# Café\n\n1. Inhale.\n2. Think `<unsafe>`.\n3. Exhale.\n").decode()
    assert "<ol><li>Inhale.</li><li>Think &lt;unsafe&gt;.</li><li>Exhale.</li></ol>" in html


@pytest.mark.unit
def test_companion_validation_rejects_self_and_unknown(monkeypatch):
    from ocf_tools import validators

    record = FunctionRecord(
        "OCF-TST-001", "test", Path("test.yaml"), {"companions": ["OCF-TST-001", "OCF-TST-999"]}
    )
    monkeypatch.setattr(validators, "load_all_functions", lambda: [record])
    result = validators.validate_collection()
    assert len([x for x in result.issues if x.code == "invalid-companion"]) == 2
    record.data["companions"] = [{}]
    assert validators.validate_collection().issues[0].code == "invalid-companion"
    record.data["companions"] = None
    assert not validators.validate_collection().issues


@pytest.mark.integration
def test_all58_guides_project_existing73_procedures_and_scopes():
    documents = guides.markdown_documents()
    catalog = LocaleCatalog()
    count = 0
    for owner in load_all_functions():
        text = documents[f"functions/{owner.id}.md"]
        document = _function_document(owner, "en-US", catalog)
        for command in document["commands"]:
            if command["role"] == "legacy-alias":
                continue
            count += 1
            for i, step in enumerate(command["procedure_steps"], 1):
                assert f"{i}. {step['instruction']['text']}" in text
        for scope in document["lifecycle_scopes"]:
            assert scope["description"]["text"] in text
            if scope.get("activation"):
                assert f"activation: {scope['activation']}" in text
        for condition in owner.data["lifecycle"].get("trigger_conditions", []):
            assert condition in text
    assert count == 73
    intuition = documents["functions/OCF-EXP-006.md"]
    assert "Allow a quiet moment to notice what arises." in intuition
    assert "Follow the function-specific instruction recorded for this step" not in intuition
    assert "Hold your breath" not in intuition
    assert "PLUS-FOOD MORE" not in documents["functions/OCF-BOD-005.md"]
    assert "activation: automatic" in documents["functions/OCF-BOD-005.md"]
    assert "PLUS-FOOD MORE" in documents["functions/OCF-BOD-010.md"]
    assert (
        "outside this function's bound narration sequence" in documents["functions/OCF-FND-001.md"]
    )
    with pytest.raises(OCFError, match="en-US only"):
        guides.function_guide_markdown(None, locale="es")


@pytest.mark.integration
def test_six_directional_relationships_are_approved_not_prerequisites():
    assert review.verify() == []
    catalog = LocaleCatalog()
    actual = {}
    for owner in load_all_functions():
        relations = _function_document(owner, "en-US", catalog)["related_functions"]
        if relations:
            actual[owner.id] = [r["function_id"] for r in relations]
            assert all(
                r["dependency"] == "optional" and r["approval"] == "OCF-GUIDE-REVIEW-001"
                for r in relations
            )
    assert actual == review.EDGES
    assert sum(map(len, actual.values())) == 6
    assert "OCF-EXP-006" not in actual


@pytest.mark.unit
def test_immutable_approval_and_malformed_scope_fail_closed(tmp_path, monkeypatch):
    path = tmp_path / review.LEDGER
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(OCFError, match="immutable"):
        review.record(tmp_path)
    decisions = [
        {"source_id": s, "related_id": t, "response": "1", "dependency": "optional"}
        for s, targets in review.EDGES.items()
        for t in targets
    ]
    original = {"confirmation": "Yes", "decisions": decisions, "files": {}}
    for mutation, match in (
        ("confirmation", "confirmation"),
        ("response", "approval drift"),
        ("dependency", "approval drift"),
        ("target", "scope drift"),
    ):
        data = deepcopy(original)
        if mutation == "confirmation":
            data["confirmation"] = "No"
        elif mutation == "target":
            data["decisions"][0]["related_id"] = "OCF-TST-999"
        else:
            data["decisions"][0][mutation] = "not approved"
        text = json.dumps(data)
        path.write_text(text, encoding="utf-8")
        monkeypatch.setattr(review, "LEDGER_SHA256", review.sha(text))
        with pytest.raises(OCFError, match=match):
            review.record(tmp_path)


@pytest.mark.unit
def test_confirmed_creator_is_metadata_only_and_refuses_overwrite(tmp_path, monkeypatch):
    import yaml
    from tools import create_guide_review as creator

    originals = {}
    for name in ("locales/en-US/commands.yaml", "locales/en-US/ui.yaml"):
        originals[name] = (
            "schema_version: '1.0'\nlocale: en-US\ndomain: ui\nentries:\n  # retained comment\n  unchanged: Original\n"
        )
    records = []
    for fid in ("OCF-COG-004", "OCF-FND-002", "OCF-EXP-006", "OCF-PRF-004"):
        purpose = (
            "Practice; proposed concise cue PLUS-LIGHT." if fid == "OCF-PRF-004" else "Practice."
        )
        data = {
            "id": fid,
            "purpose": {"summary": purpose, "community_description": purpose},
            "companions": [],
            "commands": [],
            "narration": {"sequence": ["unchanged"]},
            "documentation": {
                "purpose_key": f"functions.{fid.lower()}.purpose",
                "short_description_key": f"functions.{fid.lower()}.purpose",
            },
        }
        if fid == "OCF-EXP-006":
            data["commands"] = [
                {
                    "procedure": {
                        "override_steps": [
                            {"id": key, "operation": "other"} for key in review.STEP_TEXT
                        ]
                    }
                }
            ]
        name = f"functions/{fid}.yaml"
        text = yaml.safe_dump(data, sort_keys=False)
        originals[name] = text
        records.append(FunctionRecord(fid, "test", tmp_path / name, data))
    for name, text in originals.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    queue = [
        {
            "decision_status": "approved",
            "exact_user_responses": ["1"],
            "current_source_evidence": {
                "relationship_id": f"test-{source}-{target}",
                "source_id": source,
                "related_id": target,
            },
        }
        for source, targets in review.EDGES.items()
        for target in targets
    ]
    local = tmp_path / "review.json"
    local.write_text(
        json.dumps(
            {
                "source_commit": creator.SOURCE,
                "implementation_confirmation": {"exact_user_response": "Yes"},
                "queue": queue,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(creator, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(creator, "load_all_functions", lambda: records)
    monkeypatch.setattr(
        creator.subprocess,
        "check_output",
        lambda args, **kw: originals[args[-1].split(":", 1)[1]].encode(),
    )
    monkeypatch.setattr("sys.argv", ["create_guide_review", str(local)])
    creator.main()
    ledger = json.loads((tmp_path / creator.LEDGER).read_text(encoding="utf-8"))
    assert len(ledger["decisions"]) == 6 and ledger["confirmation"] == "Yes"
    for record in records:
        current = yaml.safe_load(record.path.read_text(encoding="utf-8"))
        review.check_function_scope(record.data, current)
        assert current["narration"] == record.data["narration"]
    assert "# retained comment" in (tmp_path / "locales/en-US/ui.yaml").read_text(encoding="utf-8")
    with pytest.raises(OCFError, match="already exists"):
        creator.main()


@pytest.mark.integration
def test_rich_discovery_and_agent_api_share_companion_identity():
    from ocf_tools.agent_api import get_function
    from ocf_tools.content import discover
    from ocf_tools.indexes import load_function_by_id
    from ocf_tools.validators import _load_schema, validate_against_schema

    for fid, targets in review.EDGES.items():
        function = discover(load_function_by_id(fid))
        assert function["companions"] == targets
        assert (
            validate_against_schema(
                {"schema_version": "1.0", "functions": [function]},
                _load_schema("function-discovery.schema.json"),
            )
            == []
        )
        invalid = deepcopy(function)
        invalid["companions"] = [targets[0], targets[0]]
        assert validate_against_schema(
            {"schema_version": "1.0", "functions": [invalid]},
            _load_schema("function-discovery.schema.json"),
        )
        assert get_function(fid, fields=["companions"])["data"]["companions"] == targets


@pytest.mark.unit
def test_predecessor_requires_hashes_and_unchanged_behavior(monkeypatch, tmp_path):
    before = {
        "id": "OCF-FND-002",
        "purpose": {"summary": "Focus.", "community_description": "Focus."},
        "companions": [],
        "lifecycle": {"persistence": "temporary"},
    }
    after = deepcopy(before)
    after["companions"] = ["OCF-COG-007"]
    old, current = json.dumps(before), json.dumps(after)
    name = "functions/focus.yaml"
    row = {"before": old, "before_sha256": review.sha(old), "after_sha256": review.sha(current)}
    monkeypatch.setattr(review, "record", lambda root: {"files": {name: row}})
    assert review.predecessor(tmp_path, name, current) == old
    with pytest.raises(OCFError, match="fingerprint drift"):
        review.predecessor(tmp_path, name, current + " ")
    row["before_sha256"] = "0" * 64
    with pytest.raises(OCFError, match="fingerprint drift"):
        review.predecessor(tmp_path, name, current)
    row["before_sha256"] = review.sha(old)
    after["lifecycle"]["persistence"] = "permanent"
    current = json.dumps(after)
    row["after_sha256"] = review.sha(current)
    with pytest.raises(OCFError, match="metadata-only scope"):
        review.predecessor(tmp_path, name, current)


@pytest.mark.integration
def test_companion_schema_requires_unique_function_id_references():
    from jsonschema import Draft7Validator
    from ocf_tools.validators import _load_schema

    validator = Draft7Validator(_load_schema("function.schema.json")["properties"]["companions"])
    assert not list(validator.iter_errors(["OCF-COG-007"]))
    assert list(validator.iter_errors(["not-a-function"]))
    assert list(validator.iter_errors(["OCF-COG-007", "OCF-COG-007"]))
    assert list(validator.iter_errors(None))
