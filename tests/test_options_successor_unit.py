"""Hash-only Options decision projection has strict scope and safe fallback."""

from types import SimpleNamespace

import pytest
from ocf_tools import options_successor as subject
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


@pytest.fixture
def canonical_decision(monkeypatch):
    keys = {
        "hplus.function.ocf-cog-005.closer",
        "hplus.function.ocf-cog-005.function-body",
    }
    hashes = {key: "a" * 64 for key in keys}
    decision = {
        "id": subject.DECISION_ID,
        "kind": "approved-command-presentation-change",
        "decision_source": "explicit approval",
        "source_commit": "b" * 40,
        "command_id": "OCF-CMD-COG-005-PRIMARY",
        "scope": "two canonical narration entries only",
        "previous_resolved_text_sha256": hashes,
        "current_resolved_text_sha256": hashes,
        "unchanged_protected_count": 175,
        "listening_approval": False,
        "release_ready": False,
    }
    data = {"function_id": subject.OWNER, "record_metadata": {"editorial_decisions": [decision]}}
    monkeypatch.setattr(subject, "resources", lambda _root: [(SimpleNamespace(), data)])
    return decision


def test_hash_only_projection_has_no_predecessor_speech(canonical_decision, tmp_path):
    result = subject.record(tmp_path)
    assert result["function_id"] == subject.OWNER
    assert set(result["speech"]) == set(canonical_decision["previous_resolved_text_sha256"])
    assert all("before" not in row and "after" not in row for row in result["speech"].values())
    assert subject.predecessor(tmp_path, "any-resource", "current") == "current"
    assert subject.before_texts(tmp_path, {"key": "current"}) == {"key": "current"}


@pytest.mark.parametrize("corrupt", ["command", "scope", "digest"])
def test_invalid_canonical_decision_fails_closed(
    monkeypatch, canonical_decision, tmp_path, corrupt
):
    if corrupt == "command":
        canonical_decision["command_id"] = "OCF-CMD-COG-005-OTHER"
    elif corrupt == "scope":
        canonical_decision["current_resolved_text_sha256"].pop("hplus.function.ocf-cog-005.closer")
    else:
        canonical_decision["previous_resolved_text_sha256"]["hplus.function.ocf-cog-005.closer"] = (
            "short"
        )
    with pytest.raises(OCFError, match="decision"):
        subject.record(tmp_path)


def test_absent_canonical_resource_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(subject, "resources", lambda _root: [])
    assert subject.record(tmp_path) is None
