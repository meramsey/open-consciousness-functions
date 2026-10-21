"""Approved speech scope, procedure preservation and fail-closed history."""

import json

import pytest
import yaml
from ocf_tools import command_simplification as subject
from ocf_tools.commands import cue_presentation
from ocf_tools.indexes import load_function_by_id
from ocf_tools.paths import REPO_ROOT
from ocf_tools.utils import OCFError
from tools.check_hplus_narration_integrity import narration_texts

pytestmark = pytest.mark.integration


def test_exact_fifteen_entry_successor_and_immutable_history():
    assert subject.verify() == []
    data = subject.record()
    texts = narration_texts()
    before = subject.before_texts(REPO_ROOT, texts)
    assert len(texts) == len(before) == 177
    assert sum(texts[key] != before[key] for key in texts) == 15
    assert sum(texts[key] == before[key] for key in texts) == 162
    assert not any("shared" in key or key.endswith(".opener") for key in data["speech"])


@pytest.mark.parametrize("owner", subject.PAIRS)
def test_current_cue_preserves_all_behavior_and_legacy_mappings(owner):
    record = load_function_by_id(owner)
    name = record.path.relative_to(REPO_ROOT).as_posix()
    before = yaml.safe_load(subject.record()["files"][name]["before"])
    title, display, _, spoken = subject.PAIRS[owner]
    assert record.canonical_name == title
    assert record.canonical_command == display
    assert cue_presentation(record, strict=True)["spoken_cue"] == spoken
    for field in (
        "legacy",
        "purpose",
        "lifecycle",
        "narration",
        "audio",
        "status",
        "sources",
        "safety",
    ):
        assert record.data[field] == before[field]
    assert [row.id for row in record.command_records] == [row["id"] for row in before["commands"]]
    for command, old in zip(record.command_records, before["commands"], strict=True):
        for field in (
            "procedure",
            "effect_scope_ref",
            "invocation_scope_ref",
            "relationships",
            "role",
        ):
            assert command.data.get(field) == old.get(field)


def test_source_and_speech_drift_cannot_be_projected_as_history():
    data = subject.record()
    name, row = next(iter(data["files"].items()))
    with pytest.raises(OCFError, match="source drift"):
        subject.predecessor(REPO_ROOT, name, row["before"])
    texts = narration_texts()
    texts[next(iter(data["speech"]))] += " extra unapproved suggestion"
    with pytest.raises(OCFError, match="resolved speech drift"):
        subject.before_texts(REPO_ROOT, texts)


def test_tampered_approval_is_rejected(tmp_path):
    data = subject.record()
    data["confirmation"] = "unconfirmed"
    path = tmp_path / subject.LEDGER
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(OCFError, match="immutable"):
        subject.record(tmp_path)
