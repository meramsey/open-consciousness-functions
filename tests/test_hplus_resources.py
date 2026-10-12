"""Repository integration contracts for reusable HPlus locale resources."""

from types import SimpleNamespace

import pytest
import yaml

from ocf_tools.indexes import load_all_functions
from ocf_tools.paths import REPO_ROOT
from ocf_tools.locale import LocalizationError, iter_events, resolve_document
from ocf_tools.session import compose, load_template, run_compose
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.integration


def test_cli_binds_function_keys_and_fails_for_unauthored_function(tmp_path):
    args = SimpleNamespace(
        template="OCF-TPL-SESSION-HPLUS-STANDARD-001",
        function="OCF-FND-002", slot=[], title=None, id=None,
        locale="en-US", output=tmp_path / "review.yaml", force=False,
    )
    assert run_compose(args) == 0
    args.function = "OCF-BOD-005"
    args.output = tmp_path / "missing.yaml"
    with pytest.raises(OCFError, match="function narration is not authored"):
        run_compose(args)
    assert not args.output.exists()


SELECTIONS = yaml.safe_load((REPO_ROOT / "function-content/hplus-review-selections.yaml").read_text())["selections"]
PROPOSALS = yaml.safe_load((REPO_ROOT / "function-content/hplus-proposed-review-selections.yaml").read_text())["proposals"]
SUPPLEMENTARY_CLOSERS = {"OCF-BOD-004", "OCF-BOD-009", "OCF-COG-001", "OCF-COG-002", "OCF-COG-005", "OCF-COG-006", "OCF-EXP-001", "OCF-FND-001", "OCF-PRF-001"}
SUPPLEMENTARY_OPENERS = {"OCF-BOD-008", "OCF-COG-005"}
COMPLETE_OWNERS = sorted(
    owner
    for owner in [record.id for record in load_all_functions()]
    if all(
        f"hplus.function.{owner.lower()}.{slot}"
        in yaml.safe_load((REPO_ROOT / "locales/en-US" / f"hplus-{owner}.yaml").read_text())["entries"]
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
    assert [event["narration_key"] for event in relaxation["timeline"] if event.get("narration_key")] == [
        f"hplus.shared.relaxation.{part}"
        for part in ("begin", "face", "shoulders", "hands", "torso", "legs")
    ]
    assert relaxation["timeline"][-1]["narration_required"] is False
    with pytest.raises(LocalizationError):
        resolve_document(doc, "es")


def test_all_55_functions_have_review_files_without_fabricated_missing_speech():
    owners = load_all_functions()
    assert len(owners) == 55
    assert len(COMPLETE_OWNERS) == 53
    unavailable = [owner for owner in owners if owner.source_availability == "unavailable"]
    assert len(unavailable) == 16
    for owner in owners:
        path = REPO_ROOT / "locales/en-US" / f"hplus-{owner.id}.yaml"
        doc = yaml.safe_load(path.read_text())
        prefix = f"hplus.function.{owner.id.lower()}."
        if owner.source_availability == "unavailable":
            assert owner.reimplementation_status == "planned"
            assert doc["domain"] == "narration"
            assert owner.id in PROPOSALS
            assert set(doc["entries"]) == {prefix + slot for slot in ("opener", "function-body", "closer")}
            for entry in doc["entries"].values():
                assert entry["status"] in {"draft", "reviewed"}
                assert "User-proposed reconstruction" in entry["notes"]
                assert PROPOSALS[owner.id]["input"]["sha256"] in entry["notes"]
                assert "source availability remains unavailable" in entry["notes"]
        else:
            assert doc["domain"] == "narration"
            selection = SELECTIONS[owner.id]
            for slot in ("opener", "function-body", "closer"):
                if owner.id in SUPPLEMENTARY_CLOSERS and slot == "closer":
                    assert slot in selection["missing"]
                    assert prefix + slot in doc["entries"]
                    assert doc["entries"][prefix + slot]["status"] == (
                        "draft" if owner.id in {"OCF-COG-002", "OCF-FND-001"} else "reviewed"
                    )
                    assert (
                        "not historical wording" in doc["entries"][prefix + slot]["notes"]
                        if owner.id == "OCF-COG-001"
                        else "not historical transcript wording" in doc["entries"][prefix + slot]["notes"]
                        if owner.id == "OCF-COG-002"
                        else "User approved this OCF-authored wording" in doc["entries"][prefix + slot]["notes"]
                        if owner.id == "OCF-COG-005"
                        else "not historical wording" in doc["entries"][prefix + slot]["notes"]
                        if owner.id == "OCF-COG-006"
                        else "not historical wording" in doc["entries"][prefix + slot]["notes"]
                        if owner.id == "OCF-EXP-001"
                        else "not transcript wording" in doc["entries"][prefix + slot]["notes"]
                        if owner.id == "OCF-FND-001"
                        else "not transcript wording" in doc["entries"][prefix + slot]["notes"]
                        if owner.id == "OCF-BOD-004"
                        else "not historical transcript wording" in doc["entries"][prefix + slot]["notes"]
                    )
                elif owner.id in SUPPLEMENTARY_OPENERS and slot == "opener":
                    assert slot in selection["missing"]
                    assert prefix + slot in doc["entries"]
                    assert doc["entries"][prefix + slot]["status"] == "reviewed"
                    assert (
                        "User approved this OCF-authored wording" in doc["entries"][prefix + slot]["notes"]
                        if owner.id == "OCF-COG-005"
                        else "User approved this opener" in doc["entries"][prefix + slot]["notes"]
                    )
                else:
                    assert (prefix + slot in doc["entries"]) == (slot in selection["slots"])
            for entry in doc["entries"].values():
                assert entry["status"] in {"draft", "reviewed"}


@pytest.mark.parametrize("owner", ["OCF-SLP-004", "OCF-BOD-005"])
def test_missing_source_sections_cannot_be_spoken_as_review_status(owner, tmp_path):
    args = SimpleNamespace(
        template="OCF-TPL-SESSION-HPLUS-STANDARD-001",
        function=owner, slot=[], title=None, id=None,
        locale="en-US", output=tmp_path / "missing.yaml", force=False,
    )
    with pytest.raises(OCFError, match="function narration is not authored"):
        run_compose(args)
    assert not args.output.exists()


def test_keyed_slot_rejects_ambiguous_or_unknown_inputs():
    template = load_template("OCF-TPL-SESSION-HPLUS-STANDARD-001")
    with pytest.raises(OCFError, match="both plain text and a narration key"):
        compose(template, {"opener": "text"}, slot_keys={"opener": "test.key"}, title="test")
    with pytest.raises(OCFError, match="unknown slot"):
        compose(template, {}, slot_keys={"unknown": "test.key"}, title="test")
    template["sections"][0]["pace"] = "sequential"
    with pytest.raises(OCFError, match="whole-block pacing"):
        compose(template, {}, slot_keys={"opener": "test.key"}, title="test")
