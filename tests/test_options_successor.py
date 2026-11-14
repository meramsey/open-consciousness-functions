"""The Options cue decision is represented by canonical hash metadata."""

import json

import pytest
from ocf_tools import options_successor as successor
from ocf_tools.indexes import load_function_by_id
from ocf_tools.locale import LocaleCatalog
from ocf_tools.narration_sources import SourceResolver
from ocf_tools.utils import OCFError
from test_narration_sources import fixture

pytestmark = pytest.mark.integration


def test_options_decision_is_canonical_and_hash_only():
    from tools.check_hplus_narration_integrity import check

    assert successor.verify() == check() == []
    data = successor.record()
    assert data["function_id"] == "OCF-COG-005"
    assert data["command_id"] == "OCF-CMD-COG-005-PRIMARY"
    assert len(data["speech"]) == 2
    assert data["unchanged_protected_count"] == 175
    assert not data["release_ready"] and not data["listening_approval"]
    assert all("before" not in row and "after" not in row for row in data["speech"].values())
    owner = load_function_by_id(successor.OWNER)
    assert owner.canonical_command == "PLUS-OPTIONS"
    assert owner.command_records[0].data["spoken"] == successor.NEW
    assert any(item["text"] == successor.OLD for item in owner.data["historical_lookup"])


@pytest.mark.parametrize("mode", ["recording", "hybrid"])
def test_stale_recording_fails_text_validation_including_tts_fallback(tmp_path, mode):
    doc, config, path = fixture(tmp_path, mode=mode)
    row = next(iter(successor.record()["speech"].values()))
    doc["timeline"] = [{"id": "first", "at": 0, "text": "current approved speech"}]
    config["recordings"]["take"]["text_sha256"] = row["before_sha256"]
    config["fallback"] = "tts"
    path.write_text(json.dumps(config), encoding="utf-8")
    original = (tmp_path / "take.wav").read_bytes()
    with pytest.raises(OCFError, match="fingerprint"):
        SourceResolver(doc, path)
    assert (tmp_path / "take.wav").read_bytes() == original


def test_historical_options_phrase_is_lookup_only():
    from ocf_tools.vocabulary import lookup

    row = next(row for row in lookup(successor.OLD) if row["function_id"] == successor.OWNER)
    assert row["cue"]["spoken_cue"] == successor.NEW
    assert row["activation_selected"] is False
    assert all(item["historical"] for item in row["matches"])


def test_options_previous_and_current_hashes_are_not_source_text():
    decision = successor.record()
    resource = LocaleCatalog().require("en-US").localized_functions[successor.OWNER]
    embedded = next(
        item
        for item in resource["record_metadata"]["editorial_decisions"]
        if item["id"] == successor.DECISION_ID
    )
    assert set(decision["speech"]) == set(embedded["previous_resolved_text_sha256"])
    assert set(decision["speech"]) == set(embedded["current_resolved_text_sha256"])
    assert all(
        len(row["before_sha256"]) == 64 and len(row["after_sha256"]) == 64
        for row in decision["speech"].values()
    )
