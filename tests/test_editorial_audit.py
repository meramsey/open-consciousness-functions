"""Editorial output is complete evidence/recommendations, never a mutation engine."""

import json
from collections import Counter

import pytest
from ocf_tools.commands import resolve_phrase
from ocf_tools.indexes import load_all_functions
from ocf_tools.utils import OCFError, sha256_of_file
from tools import editorial_audit as audit


def test_complete_function_command_audit_preserves_every_authoritative_phrase():
    records = load_all_functions()
    data = audit.canonical_audit()
    actual = {row["id"]: row["phrase"] for row in data["commands"]}
    expected = {
        command.id: resolve_phrase(record, command)
        for record in records
        for command in record.command_records
    }
    assert actual == expected and len(actual) == 97
    assert {row["function_id"] for row in data["functions"]} == {record.id for record in records}
    assert data["counts"]["functions"] == 55 and data["counts"]["protected_entries"] == 177
    assert not data["implemented"]
    assert all(row["status"] == audit.PROPOSAL for row in data["functions"])
    assert all(row["audit_status"] == audit.PROPOSAL for row in data["commands"])
    for name, checksum in data["source_sha256"].items():
        assert sha256_of_file(audit.REPO_ROOT / name) == checksum


def test_special_cases_and_shared_roles_are_not_silently_canonicalized():
    data = audit.canonical_audit()
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
    assert audit.main(["--check"]) == 0
