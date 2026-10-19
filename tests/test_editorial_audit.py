"""Editorial output is complete evidence/recommendations, never a mutation engine."""

import hashlib
import json
from collections import Counter

import pytest
from ocf_tools.commands import resolve_phrase
from ocf_tools.indexes import load_all_functions
from ocf_tools.models import FunctionRecord
from ocf_tools.utils import OCFError
from tools import editorial_audit as audit


def historical_data():
    return json.loads(
        (audit.REPO_ROOT / "docs/releases/OCF_COMMAND_NAMING_RECOMMENDATIONS.json").read_text(
            encoding="utf-8"
        )
    )


def test_complete_function_command_audit_preserves_every_authoritative_phrase():
    records = [
        row
        for row in load_all_functions()
        if row.data["legacy"]["source_system"] == "Monroe H-PLUS"
    ]
    data = historical_data()
    from ocf_tools.cue_migration import decision_record
    from ocf_tools.editorial_successors import records as successor_records

    migrated = {
        row["primary_command_id"]: row["previous"]["display_cue"]
        for row in decision_record()["decisions"]
    }
    for successor in successor_records():
        for decision in successor["decisions"]:
            if "primary_command_id" not in decision:
                continue
            migrated.setdefault(decision["primary_command_id"], decision["previous"]["display_cue"])
    actual = {row["id"]: row["phrase"] for row in data["commands"]}
    expected = {
        command.id: migrated.get(command.id, resolve_phrase(record, command))
        for record in records
        for command in record.command_records
    }
    assert actual == expected and len(actual) == 97
    assert {row["function_id"] for row in data["functions"]} == {record.id for record in records}
    assert data["counts"]["functions"] == 55 and data["counts"]["protected_entries"] == 177
    assert not data["implemented"]
    assert all(row["status"] == audit.PROPOSAL for row in data["functions"])
    assert all(row["audit_status"] == audit.PROPOSAL for row in data["commands"])
    snapshot = dict(audit.tracked_snapshot())
    for name, checksum in data["source_sha256"].items():
        assert hashlib.sha256(snapshot[name].encode()).hexdigest() == checksum


def test_special_cases_and_shared_roles_are_not_silently_canonicalized():
    data = historical_data()
    by_id = {row["function_id"]: row for row in data["functions"]}
    mobius, sleep = by_id["OCF-EXP-001"], by_id["OCF-SLP-005"]
    assert mobius["current_command"] == "PLUS-PROGRAM"
    assert mobius["proposed_command"] == "PLUS-MANIFEST"
    assert {"PLUS-CREATE", "PLUS-CHANGE"} <= set(mobius["alternatives"])
    assert sleep["current_command"] == "PLUS-SLEEP EASY"
    assert "PLUS-QUIET SLEEP" in sleep["alternatives"]
    assert any(
        "Plus Quiet Sleep" in row["exact_activation_fragments"]
        for row in sleep["observed_narration"]
    )
    commands = {row["id"]: row for row in data["commands"]}
    assert commands["OCF-CMD-COG-003-CLOSED"]["phrase"] == "PLUS-CLOSED"
    assert commands["OCF-CMD-COG-004-RECALL"]["role"] == "retrieval"
    assert commands["OCF-CMD-BOD-015-LEGACY-02"]["role"] == "release"
    assert commands["OCF-CMD-EXP-002-CANCEL"]["role"] == "cancel"
    assert commands["OCF-CMD-FND-001-ACCESS-CLOSE"]["role"] == "access-close"


def test_identifier_inventory_counts_complete_occurrences_and_proposes_only():
    data = audit.identifier_audit()
    assert data["text_occurrences"] == len(data["occurrences"]) == sum(data["categories"].values())
    assert len(data["files"]) == data["files_affected"]
    assert Counter(row["path"] for row in data["occurrences"]) == {
        row["path"]: row["occurrences"] for row in data["files"]
    }
    assert not any(
        row["path"].startswith(("ReusablePrompts/", "references/HumanPlusTranscripts/"))
        for row in data["occurrences"]
    )
    assert all(
        not row["implemented"] and row["status"] == audit.PROPOSAL for row in data["mappings"]
    )
    defined = [row for row in data["mappings"] if row["defined_in_snapshot"]]
    assert not any(row["target_collision"] for row in defined)
    assert len({row["proposed"] for row in defined}) == len(defined)
    mappings = {row["old"]: row for row in data["mappings"]}
    assert mappings["OCF-AUDIO-DEFAULTS-HPLUS-001"]["risk"] == "critical"
    assert mappings["hplus.function.ocf-fnd-001.access-close"]["proposed"].endswith("access-close")
    assert all(row["old"] != row["proposed"] for row in data["path_mappings"])


@pytest.mark.unit
@pytest.mark.parametrize(
    "path,line,token,expected",
    [
        (
            "locales/en-US/entry.yaml",
            "hplus.shared.body:",
            "hplus.shared.body",
            "protected resource key",
        ),
        (
            "audio/templates/x.yaml",
            "id: OCF-TPL-SESSION-HPLUS-LOCKED-001",
            "OCF-TPL-SESSION-HPLUS-LOCKED-001",
            "active implementation identifier",
        ),
        ("functions/x.yaml", "source_system: Monroe H-Plus", "H-Plus", "external attribution"),
        ("docs/releases/x.md", "Historical Human Plus", "Human Plus", "historical provenance"),
        ("tests/test_x.py", 'assert title == "HPLUS"', "HPLUS", "compatibility reference"),
        (
            "audio/templates/x.yaml",
            "name: HPLUS reference shell",
            "HPLUS",
            "human-readable active label",
        ),
        ("references/README.md", "Human Plus", "Human Plus", "user-supplied reference"),
    ],
)
def test_occurrence_classification_is_explicit(path, line, token, expected):
    assert audit.category(path, line, token) == expected


@pytest.mark.unit
def test_incomplete_decision_set_fails_before_any_generation(monkeypatch):
    monkeypatch.setattr(audit, "load_all_functions", lambda: [])
    with pytest.raises(OCFError, match="cover every canonical"):
        audit.canonical_audit()


@pytest.mark.unit
def test_report_writer_is_restricted_and_detects_drift_without_applying(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    monkeypatch.setattr(
        audit, "reports", lambda: {"audit.json": json.dumps({"implemented": False})}
    )
    target = tmp_path / "reports"
    assert audit.main(["--write", "--check", "--output-dir", str(target)]) == 0
    assert json.loads((target / "audit.json").read_text())["implemented"] is False
    (target / "audit.json").write_text("changed", encoding="utf-8")
    assert audit.main(["--check", "--output-dir", str(target)]) == 1
    with pytest.raises(OCFError, match="docs/releases"):
        audit.main(["--write", "--output-dir", str(audit.REPO_ROOT / "functions")])
    with pytest.raises(SystemExit):
        audit.main(["--apply"])


def test_committed_audits_are_fresh_and_do_not_modify_inputs():
    with pytest.raises(OCFError, match="historical editorial audit input drift"):
        audit.main(["--check"])
    assert audit.command_markdown(historical_data()) == (
        audit.REPO_ROOT / "docs/releases/OCF_COMMAND_NAMING_AUDIT.md"
    ).read_text(encoding="utf-8")
    assert audit.identifier_markdown(audit.identifier_audit()) == (
        audit.REPO_ROOT / "docs/releases/OCF_IDENTIFIER_NEUTRALIZATION_AUDIT.md"
    ).read_text(encoding="utf-8")


@pytest.mark.unit
@pytest.mark.parametrize(
    "state,proposed,observed",
    [
        ("KEEP", "PLUS-OLD", None),
        ("RECOMMENDED RENAME", "PLUS-NEW", None),
        ("RECOMMENDED RENAME", "PLUS-NEW", "Plus New"),
    ],
)
def test_historical_projection_with_verified_synthetic_inputs(
    monkeypatch, tmp_path, state, proposed, observed
):
    """Keep historical generation exercised without attributing old code to a new tree."""
    owner = "OCF-COG-999"
    data = {
        "canonical": {"name": "Old Fixture", "command": {"primary": "PLUS-OLD", "modes": []}},
        "commands": [
            {
                "id": "OCF-CMD-COG-999-PRIMARY",
                "function_id": owner,
                "phrase_ref": {"source": "canonical-primary"},
                "role": "activation",
                "designation": "primary",
            }
        ],
        "purpose": {"summary": "Selected fixture operation."},
        "aliases": {"names": ["Old Fixture"], "commands": []},
        "legacy": {
            "name": "Historical Fixture",
            "commands": ["PLUS-OLD"],
            "source_availability": "available",
        },
        "compatibility": {"state": "unchanged"},
        "ocf": {"command_review": "approved"},
        "lifecycle": {
            "activation": "manual",
            "persistence": "temporary",
            "release": {"command": None, "required": False},
        },
    }
    if observed:
        data["commands"][0]["observed_phrase"] = {
            "text": observed,
            "narration_key": "fixture.body",
            "relationship": "variant",
        }
    path = tmp_path / "functions/fixture.yaml"
    path.parent.mkdir()
    path.write_text("original synthetic metadata\n", encoding="utf-8")
    record = FunctionRecord(owner, "fixture", path, data)
    for folder in ("function-content/specifications", "function-content/bindings", "locales/en-US"):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    (tmp_path / "function-content/specifications" / (owner + ".yaml")).write_text(
        "analysis_review:\n  sections:\n    purpose:\n      summary: Original fixture purpose.\n",
        encoding="utf-8",
    )
    (tmp_path / "function-content/bindings" / (owner + ".yaml")).write_text(
        "default_session_template: fixture\n", encoding="utf-8"
    )
    resource = {
        "entries": {
            "fixture.body": {"text": "Think Plus Old. " + (observed or ""), "version": "1.0.0"}
        }
    }
    from ocf_tools.utils import yaml_safe_dump

    (tmp_path / "locales/en-US" / ("hplus-" + owner + ".yaml")).write_text(
        yaml_safe_dump(resource), encoding="utf-8"
    )
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "load_all_functions", lambda: [record])
    monkeypatch.setattr(
        audit,
        "DECISIONS",
        {owner: (state, proposed, [], "Fixture rationale.", "New Fixture", "low")},
    )
    monkeypatch.setattr(
        audit,
        "historical_report",
        lambda: {
            "source_sha256": {
                "functions/fixture.yaml": hashlib.sha256(path.read_bytes()).hexdigest()
            }
        },
    )
    monkeypatch.setattr(audit, "narration_texts", lambda: {"fixture": "Think Plus Old."})
    result = audit.canonical_audit()
    row = result["functions"][0]
    assert row["current_command"] == "PLUS-OLD" and row["proposed_command"] == proposed
    assert result["counts"]["functions"] == result["counts"]["command_records"] == 1
    assert (
        row["observed_narration"][0]["text_sha256"]
        == hashlib.sha256(resource["entries"]["fixture.body"]["text"].encode()).hexdigest()
    )
    assert not result["implemented"]
    assert path.read_text(encoding="utf-8") == "original synthetic metadata\n"
