"""Integration contracts for the explicitly approved spoken-text successor."""

import json

import pytest
import yaml
from ocf_tools import options_successor as successor
from ocf_tools.cue_templates import preview
from ocf_tools.paths import REPO_ROOT
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.integration


def test_options_exact_speech_scope_behavior_and_predecessors():
    from ocf_tools.editorial_successors import verify
    from tools.check_hplus_narration_integrity import check

    assert successor.verify() == verify() == check() == []
    record = successor.record()
    assert len(record["speech"]) == 2
    assert len(record["unchanged_protected"]) == 175
    assert sum(row["before"].count(successor.OLD) for row in record["speech"].values()) == 3
    before = yaml.safe_load(record["files"][successor.FUNCTION]["before"])
    after = yaml.safe_load((REPO_ROOT / successor.FUNCTION).read_text(encoding="utf-8"))
    assert after == successor.approved_function(before)
    assert after["lifecycle"] == before["lifecycle"]
    assert after["commands"][0]["procedure"] == before["commands"][0]["procedure"]
    assert [row["id"] for row in before["commands"]] == [row["id"] for row in after["commands"]]
    assert after["canonical"]["command"]["primary"] == "PLUS-OPTIONS"
    assert after["commands"][0]["spoken"] == "Plus Options"
    result = json.dumps(preview(successor.OWNER))
    assert successor.OLD not in result
    assert successor.NEW in result


@pytest.mark.parametrize("mode", ["recording", "hybrid"])
def test_superseded_options_recordings_fail_text_validation(tmp_path, mode):
    from ocf_tools.narration_sources import SourceResolver
    from test_narration_sources import fixture

    doc, config, path = fixture(tmp_path, mode=mode)
    row = next(iter(successor.record()["speech"].values()))
    doc["timeline"] = [{"id": "first", "at": 0, "text": row["after"]}]
    config["recordings"]["take"]["text_sha256"] = row["before_sha256"]
    config["fallback"] = "tts"
    path.write_text(json.dumps(config), encoding="utf-8")
    original = (tmp_path / "take.wav").read_bytes()
    with pytest.raises(OCFError, match="fingerprint"):
        SourceResolver(doc, path)
    assert (tmp_path / "take.wav").read_bytes() == original
    assert row["before_sha256"] != row["after_sha256"]


def test_options_historical_lookup_is_not_activation():
    from ocf_tools.vocabulary import lookup

    row = next(row for row in lookup(successor.OLD) if row["function_id"] == successor.OWNER)
    assert row["cue"]["spoken_cue"] == successor.NEW
    assert row["activation_selected"] is False
    assert all(item["historical"] for item in row["matches"])


def test_options_ledger_and_files_cannot_be_relabelled(tmp_path):
    path = tmp_path / successor.LEDGER
    path.parent.mkdir(parents=True)
    data = successor.record()
    data["approval"]["after"] = "Other speech"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(OCFError, match="immutable"):
        successor.record(tmp_path)
    with pytest.raises(OCFError, match="source drift"):
        successor.predecessor(REPO_ROOT, successor.FUNCTION, "changed behavior")
