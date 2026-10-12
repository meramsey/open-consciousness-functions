"""Repository integration contracts for reusable HPlus locale resources."""

from types import SimpleNamespace

import pytest
import yaml
from ocf_tools.indexes import load_all_functions
from ocf_tools.locale import LocalizationError, iter_events, resolve_document
from ocf_tools.paths import REPO_ROOT
from ocf_tools.session import compose, load_template, run_compose
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.integration


def test_cli_binds_function_keys_and_composes_eat_no_eat_body(tmp_path):
    args = SimpleNamespace(
        template="OCF-TPL-SESSION-HPLUS-STANDARD-001",
        function="OCF-FND-002",
        slot=[],
        title=None,
        id=None,
        locale="en-US",
        output=tmp_path / "review.yaml",
        force=False,
    )
    assert run_compose(args) == 0
    args.function = "OCF-BOD-005"
    args.output = tmp_path / "missing.yaml"
    assert run_compose(args) == 0
    assert args.output.exists()


SELECTIONS = yaml.safe_load(
    (REPO_ROOT / "function-content/hplus-review-selections.yaml").read_text()
)["selections"]
PROPOSALS = yaml.safe_load(
    (REPO_ROOT / "function-content/hplus-proposed-review-selections.yaml").read_text()
)["proposals"]
SUPPLEMENTARY_CLOSERS = {
    "OCF-BOD-004",
    "OCF-BOD-009",
    "OCF-COG-001",
    "OCF-COG-002",
    "OCF-COG-005",
    "OCF-COG-006",
    "OCF-EXP-001",
    "OCF-FND-001",
    "OCF-PRF-001",
}
SUPPLEMENTARY_OPENERS = {"OCF-BOD-008", "OCF-COG-005"}
COMPLETE_OWNERS = sorted(
    owner
    for owner in [record.id for record in load_all_functions()]
    if all(
        f"hplus.function.{owner.lower()}.{slot}"
        in yaml.safe_load((REPO_ROOT / "locales/en-US" / f"hplus-{owner}.yaml").read_text())[
            "entries"
        ]
        for slot in ("opener", "function-body", "closer")
    )
)


@pytest.mark.parametrize("owner", COMPLETE_OWNERS)
def test_standard_shared_and_function_resources_resolve_without_local_sources(owner):
    template = load_template("OCF-TPL-SESSION-HPLUS-STANDARD-001")
    keys = {
        slot: f"hplus.function.{owner.lower()}.{slot.replace('_', '-')}"
        for slot in ("opener", "function_body", "closer")
    }
    doc = compose(template, {}, slot_keys=keys, title="HPlus review", function_id=owner)
    events = list(iter_events(doc))
    body = [event for event in events if event.get("slot_ref") == "function_body"]
    assert len(body) == 4
    assert {event["narration_key"] for event in body} == {keys["function_body"]}
    assert all("text" not in event for event in body)
    assert doc["slots"] == {}
    resolved = resolve_document(doc, "en-US")
    assert all(event.get("text") for event in iter_events(resolved) if event.get("narration_key"))
    relaxation = next(section for section in resolved["sections"] if section["id"] == "relaxation")
    assert [
        event["narration_key"] for event in relaxation["timeline"] if event.get("narration_key")
    ] == [
        f"hplus.shared.relaxation.{part}"
        for part in ("begin", "face", "shoulders", "hands", "torso", "legs")
    ]
    assert relaxation["timeline"][-1]["narration_required"] is False
    with pytest.raises(LocalizationError):
        resolve_document(doc, "es")


def test_all_55_functions_have_review_files_without_fabricated_missing_speech():
    owners = load_all_functions()
    assert len(owners) == 55
    assert len(COMPLETE_OWNERS) == 55
    unavailable = [owner for owner in owners if owner.source_availability == "unavailable"]
    assert len(unavailable) == 16
    for owner in owners:
        assert owner.audio_script_status == "approved"
        path = REPO_ROOT / "locales/en-US" / f"hplus-{owner.id}.yaml"
        doc = yaml.safe_load(path.read_text())
        prefix = f"hplus.function.{owner.id.lower()}."
        if owner.source_availability == "unavailable":
            assert owner.reimplementation_status == "planned"
            assert doc["domain"] == "narration"
            proposal = PROPOSALS[owner.id]
            proposal_input = proposal["input"]
            proposal_slots = proposal["selection"]["slots"]
            assert proposal_input["file"]
            assert len(proposal_input["sha256"]) == 64
            assert set(proposal_slots) == {"opener", "function-body", "closer"}
            assert set(doc["entries"]) == {
                prefix + slot for slot in ("opener", "function-body", "closer")
            }
            for entry in doc["entries"].values():
                assert entry["status"] == "reviewed"
                # The resource notes must bind this narration to the structured
                # reconstruction record, without making prose capitalization or
                # one preferred description part of the provenance contract.
                assert proposal_input["file"] in entry["notes"]
                assert proposal_input["sha256"] in entry["notes"]
        else:
            assert doc["domain"] == "narration"
            selection = SELECTIONS[owner.id]
            for slot in ("opener", "function-body", "closer"):
                entry_key = prefix + slot
                assert (slot in selection["slots"]) ^ (slot in selection["missing"])
                if owner.id in SUPPLEMENTARY_CLOSERS and slot == "closer":
                    assert slot in selection["missing"]
                    assert entry_key in doc["entries"]
                    assert doc["entries"][entry_key]["status"] == "reviewed"
                    assert doc["entries"][entry_key]["notes"].strip()
                elif owner.id in SUPPLEMENTARY_OPENERS and slot == "opener":
                    assert slot in selection["missing"]
                    assert entry_key in doc["entries"]
                    assert doc["entries"][entry_key]["status"] == "reviewed"
                    assert doc["entries"][entry_key]["notes"].strip()
                else:
                    assert (entry_key in doc["entries"]) == (
                        slot in selection["slots"] or slot in selection["missing"]
                    )
            for entry in doc["entries"].values():
                assert entry["status"] == "reviewed"


def test_four_reviewed_shared_resources_keep_reviewed_entry_status():
    shared_files = (
        "hplus-focus20.yaml",
        "hplus-relaxation.yaml",
        "hplus-transmutation-box.yaml",
        "hplus-waking-return.yaml",
    )
    for filename in shared_files:
        data = yaml.safe_load((REPO_ROOT / "locales/en-US" / filename).read_text())
        assert data["domain"] == "narration"
        assert data["entries"]
        assert all(entry["status"] == "reviewed" for entry in data["entries"].values())


def test_keyed_slot_rejects_ambiguous_or_unknown_inputs():
    template = load_template("OCF-TPL-SESSION-HPLUS-STANDARD-001")
    with pytest.raises(OCFError, match="both plain text and a narration key"):
        compose(template, {"opener": "text"}, slot_keys={"opener": "test.key"}, title="test")
    with pytest.raises(OCFError, match="unknown slot"):
        compose(template, {}, slot_keys={"unknown": "test.key"}, title="test")
    template["sections"][0]["pace"] = "sequential"
    with pytest.raises(OCFError, match="whole-block pacing"):
        compose(template, {}, slot_keys={"opener": "test.key"}, title="test")
