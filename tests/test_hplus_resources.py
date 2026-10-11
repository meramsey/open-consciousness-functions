"""Repository integration contracts for reusable HPlus locale resources."""

from types import SimpleNamespace

import pytest

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
    args.function = "OCF-COG-001"
    args.output = tmp_path / "missing.yaml"
    with pytest.raises(OCFError, match="function narration is not authored"):
        run_compose(args)
    assert not args.output.exists()


@pytest.mark.parametrize("owner", ["OCF-FND-002", "OCF-BOD-002", "OCF-SLP-002"])
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


def test_keyed_slot_rejects_ambiguous_or_unknown_inputs():
    template = load_template("OCF-TPL-SESSION-HPLUS-STANDARD-001")
    with pytest.raises(OCFError, match="both plain text and a narration key"):
        compose(template, {"opener": "text"}, slot_keys={"opener": "test.key"}, title="test")
    with pytest.raises(OCFError, match="unknown slot"):
        compose(template, {}, slot_keys={"unknown": "test.key"}, title="test")
    template["sections"][0]["pace"] = "sequential"
    with pytest.raises(OCFError, match="whole-block pacing"):
        compose(template, {}, slot_keys={"opener": "test.key"}, title="test")
