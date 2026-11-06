"""Approval scope lives with each canonical locale function resource."""

import json
from copy import deepcopy

import pytest
from ocf_tools import candidate_approval as approval
from ocf_tools.editorial_candidates import CANDIDATES, review, verify_approvals
from ocf_tools.indexes import load_function_by_id
from ocf_tools.locale import LocaleCatalog, iter_events
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.integration


def test_canonical_approval_records_and_protected_narration_integrity():
    from ocf_tools.options_successor import verify as verify_options
    from tools.check_hplus_narration_integrity import check

    assert approval.verify() == verify_approvals() == verify_options() == check() == []
    data = approval.record()
    assert len(data["approvals"]) == 4
    assert all(row["user_response"] == "1" for row in data["approvals"].values())
    assert data["release_ready"] is data["listening_approval"] is False
    assert all("before" not in row and "text" not in row for row in data["approvals"].values())


@pytest.mark.parametrize("name", CANDIDATES)
def test_current_narration_matches_embedded_resolved_hashes_and_four_pass_plan(name):
    from ocf_tools.complete_session import build_complete_session_plan

    preview = review(name)
    assert preview["editorial_status"] == "approved and implemented"
    assert not preview["pending_approval"]
    assert not preview["release_ready"]
    owner = load_function_by_id(preview["function_id"])
    assert owner.audio_script_status == "approved"
    assert all(
        row.data["spoken_review"] == "reviewed"
        for row in owner.command_records
        if row.role != "legacy-alias"
    )
    catalog = LocaleCatalog()
    for entry in preview["entries"]:
        live, _ = catalog.resource(entry["key"], "en-US", domain="narration", fallback=False)
        assert live.text.encode("utf-8") == entry["text"].encode("utf-8")
        assert live.status in {"reviewed", "canonical"}
        assert live.version == entry["version"]
    plan = build_complete_session_plan(owner.id, locale="en-US")
    assert (
        len([e for e in iter_events(plan["template_plan"]) if e.get("slot_ref") == "function_body"])
        == 4
    )


@pytest.mark.parametrize("mode", ["recording", "hybrid"])
def test_unmatched_recording_is_stale_including_tts_fallback(tmp_path, mode):
    from ocf_tools.narration_sources import SourceResolver
    from test_narration_sources import fixture

    doc, config, path = fixture(tmp_path, mode=mode)
    entry = review("manifest-v2")["entries"][0]
    doc["timeline"] = [{"id": "first", "at": 0, "text": entry["text"]}]
    config["recordings"]["take"]["text_sha256"] = "0" * 64
    config["fallback"] = "tts"
    path.write_text(json.dumps(config), encoding="utf-8")
    original = (tmp_path / "take.wav").read_bytes()
    with pytest.raises(OCFError, match="fingerprint"):
        SourceResolver(doc, path)
    assert (tmp_path / "take.wav").read_bytes() == original


def test_canonical_approval_does_not_disable_draft_script_gate(monkeypatch):
    from ocf_tools import narration_first

    owner = deepcopy(load_function_by_id("OCF-EXP-006"))
    owner.data["audio"]["script_status"] = "draft"
    monkeypatch.setattr(narration_first, "load_function_by_id", lambda _: owner)
    with pytest.raises(OCFError, match="not approved"):
        narration_first.plan_narration(owner.id)
