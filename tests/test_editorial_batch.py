"""The collected approvals authorize naming only, never procedures or controls."""

import hashlib
import json
from copy import deepcopy

import pytest
import yaml
from ocf_tools import editorial_batch as batch
from ocf_tools import editorial_successors as successors
from ocf_tools.paths import REPO_ROOT
from ocf_tools.utils import OCFError


def digest(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


@pytest.mark.unit
@pytest.mark.parametrize("field", ["id", "previous", "cue", "substitutions", "scope", "kept"])
def test_authorization_pin_cannot_be_expanded_by_self_consistent_edits(monkeypatch, field):
    data = {
        "id": batch.BATCH_ID,
        "previous": "old cue",
        "cue": "new cue",
        "substitutions": [],
        "scope": "naming",
        "kept": ["Options", "Nutricia"],
    }
    monkeypatch.setattr(batch, "BATCH_DIGEST", digest(data))
    batch.check_record(data)
    data[field] = "unauthorized"
    with pytest.raises(OCFError, match="explicit reviewed authorization"):
        batch.check_record(data)


@pytest.mark.unit
def test_intermediate_shared_file_drift_cannot_be_hidden_by_latest_successor(tmp_path, monkeypatch):
    path = "shared.yaml"
    (tmp_path / path).write_text("current", encoding="utf-8")
    records = [
        {
            "source_files": {
                path: {
                    "after_sha256": successors.sha("expected intermediate"),
                    "before_sha256": successors.sha("original"),
                }
            },
            "predecessor_files": {path: "original"},
        },
        {
            "source_files": {
                path: {
                    "after_sha256": successors.sha("current"),
                    "before_sha256": successors.sha("wrong intermediate"),
                }
            },
            "predecessor_files": {path: "wrong intermediate"},
        },
    ]
    monkeypatch.setattr(successors, "records", lambda root: records)
    with pytest.raises(OCFError, match="successor file drift"):
        successors.before_file(tmp_path, path)


@pytest.mark.integration
def test_all_28_approvals_preserve_procedures_controls_and_deferred_metadata():
    from ocf_tools.commands import cue_presentation, is_active
    from ocf_tools.indexes import load_all_functions
    from ocf_tools.narration_first import plan_narration
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    ledger = successors.records()[-1]
    batch.check_record(ledger)
    assert len(ledger["decisions"]) == 28
    assert len(ledger["allowed_text_changes"]) == 41
    assert successors.verify() == []
    texts = narration_texts()
    current = text_fingerprints(texts)
    previous = json.loads((REPO_ROOT / ledger["previous_integrity_baseline"]).read_text())
    assert len(current) == len(previous) == 177
    assert {key for key in current if current[key] != previous[key]} == {
        row["identity"] for row in ledger["allowed_text_changes"]
    }
    assert sum(current[key] == previous[key] for key in previous) == 136
    owners = {owner.id: owner for owner in load_all_functions()}
    assert len(owners) == 55
    assert sum(len(owner.command_records) for owner in owners.values()) == 97
    assert (
        sum(is_active(command) for owner in owners.values() for command in owner.command_records)
        == 79
    )
    for decision in ledger["decisions"]:
        owner = owners[decision["function_id"]]
        old = yaml.safe_load(ledger["predecessor_files"][decision["function_file"]])
        assert owner.canonical_name == decision["current_title"]
        assert owner.canonical_command == decision["display_cue"]
        assert cue_presentation(owner, strict=True)["spoken_cue"] == decision["spoken_cue"]
        # These are intentionally outside every naming approval, including known mismatches.
        for field in (
            "purpose",
            "lifecycle",
            "legacy",
            "narration",
            "audio",
            "status",
            "sources",
            "safety",
        ):
            assert owner.data[field] == old[field], (owner.id, field)
        for command in owner.command_records:
            prior = next(row for row in old["commands"] if row["id"] == command.id)
            for field in ("procedure", "relationships", "effect_scope_ref", "role"):
                assert command.data.get(field) == prior.get(field)
            if (
                command.designation != "primary"
                and command.id not in decision["historical_command_ids"]
            ):
                assert command.data == prior  # Includes Recall, Release and all sensory LESS cues.
        plan = plan_narration(owner.id, locale="en-US")
        for role, count in (("function-body", 4), ("closer", 1)):
            key = f"hplus.function.{owner.id.lower()}.{role}"
            for playback in range(1, count + 1):
                speech = "\n\n".join(
                    segment["canonical_text"]
                    for segment in plan["segments"]
                    if segment["resource_key"] == key and segment["playback"] == playback
                )
                assert speech == texts[decision["narration_file"] + "::" + key]
                assert "{{" not in speech
    # Frozen shared/pilot resources fall outside the batch's two allowed resource roles.
    assert all(
        row["identity"].endswith((".function-body", ".closer"))
        for row in ledger["allowed_text_changes"]
    )
    assert owners["OCF-BOD-006"].canonical_name == "Heart Flow"
    assert cue_presentation(owners["OCF-BOD-006"], strict=True)["spoken_cue"] == "Plus Heart Better"


@pytest.mark.integration
def test_keep_decisions_and_historical_lookup_are_distinct_from_activation():
    from ocf_tools.indexes import load_function_by_id
    from ocf_tools.vocabulary import lookup
    from tools.current_title_cues import build

    ledger = successors.records()[-1]
    assert {row["function_id"] for row in ledger["kept_decisions"]} == {
        "OCF-COG-005",
        "OCF-BOD-010",
    }
    report = build()
    for row in ledger["kept_decisions"]:
        owner = load_function_by_id(row["function_id"])
        name = owner.path.relative_to(REPO_ROOT).as_posix()
        assert (
            successors.sha(owner.path.read_text(encoding="utf-8"))
            == ledger["unaffected_function_sha256"][name]
        )
        item = next(item for item in report["functions"] if item["function_id"] == owner.id)
        assert item["decision_status"] == "EXISTING PAIR RETAINED"
        assert item["unselected_proposal"] is None
    for decision in ledger["decisions"]:
        for key, new in (("title", "current_title"), ("spoken_cue", "spoken_cue")):
            prior = decision["previous"][key]
            if prior == decision[new]:
                continue
            item = next(
                item for item in lookup(prior) if item["function_id"] == decision["function_id"]
            )
            assert item["title"] == decision["current_title"]
            assert item["cue"]["spoken_cue"] == decision["spoken_cue"]
            assert item["activation_selected"] is False


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["recording", "hybrid"])
@pytest.mark.parametrize("owner", ["OCF-BOD-015", "OCF-SEN-005"])
def test_stale_cue_or_title_recording_never_falls_back_to_tts(tmp_path, mode, owner):
    from ocf_tools.locale import LocaleCatalog
    from ocf_tools.narration_sources import SourceResolver
    from test_narration_sources import fixture

    doc, config, path = fixture(tmp_path, mode=mode)
    row = next(
        row
        for row in successors.records()[-1]["allowed_text_changes"]
        if row["function_id"] == owner and row["identity"].endswith("closer")
    )
    entry, _ = LocaleCatalog().resource(
        row["identity"].split("::")[1], "en-US", domain="narration", fallback=False
    )
    doc["timeline"] = [{"id": "first", "at": 0, "text": entry.text}]
    config["recordings"]["take"]["text_sha256"] = row["before_sha256"]
    config["fallback"] = "tts"
    path.write_text(json.dumps(config), encoding="utf-8")
    original = path.read_bytes(), (tmp_path / "take.wav").read_bytes()
    with pytest.raises(OCFError, match="fingerprint"):
        SourceResolver(doc, path)
    assert original == (path.read_bytes(), (tmp_path / "take.wav").read_bytes())


@pytest.mark.integration
def test_batch_cannot_retire_release_or_retrieval_controls():
    ledger = successors.records()[-1]
    decision = deepcopy(
        next(row for row in ledger["decisions"] if row["function_id"] == "OCF-BOD-015")
    )
    before = yaml.safe_load(ledger["predecessor_files"][decision["function_file"]])
    decision["historical_command_ids"].append("OCF-CMD-BOD-015-LEGACY-02")
    with pytest.raises(OCFError, match="control command"):
        batch.approved_function(before, decision)
