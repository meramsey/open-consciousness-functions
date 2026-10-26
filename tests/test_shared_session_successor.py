import yaml
from ocf_tools.indexes import load_all_functions
from ocf_tools.locale import iter_events, resolve_document
from ocf_tools.narration_pacing import plan_event_pacing
from ocf_tools.paths import REPO_ROOT
from ocf_tools.session import compose, load_pacing_profile, load_template


def test_shared_session_successor_preserves_approved_counts_and_body_passes():
    template = load_template("OCF-TPL-SESSION-HPLUS-LOCKED-004")
    assert template["pacing_profile"] == "OCF-PACING-HPLUS-LOCKED-004"
    assert template["dsp_profile"] == "OCF-DSP-HPLUS-LOCKED-002"
    owner = "OCF-SEN-001"
    slot_keys = {
        slot: f"hplus.function.{owner.lower()}.{slot.replace('_', '-')}"
        for slot in ("opener", "function_body", "closer")
    }
    doc = compose(template, {}, slot_keys=slot_keys, title="Hearing", function_id=owner)
    resolved = resolve_document(doc, "en-US")
    body_events = [
        event for event in iter_events(resolved) if event.get("slot_ref") == "function_body"
    ]
    assert [event["id"] for event in body_events] == [
        "focus11-body.pass-1",
        "focus11-body.pass-2",
        "sleep20-body.pass-1",
        "sleep20-body.pass-2",
    ]
    for event in body_events:
        pacing = plan_event_pacing(resolved, event)
        assert pacing and len(pacing["units"]) > 1
        assert " ".join(unit["text"] for unit in pacing["units"]) == " ".join(event["text"].split())
        assert all(unit["pause_after_s"] == 0.4 for unit in pacing["units"][:-1])
        assert pacing["units"][-1]["pause_inside_event"] is False

    focus_ten = next(
        event for event in iter_events(resolved) if event["id"] == "focus-ten.count-one"
    )
    assert focus_ten["text"] == "2"
    assert [
        next(
            event["text"]
            for event in iter_events(resolved)
            if event["id"] == f"focus-ten.count-{part}"
        )
        for part in (
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
        )
    ] == ["2", "3", "4", "5", "6", "7", "8", "9", "10"]
    assert (
        next(event["text"] for event in iter_events(resolved) if event["id"] == "focus-ten.enter")
        == "10"
    )
    focus11_close = next(event for event in iter_events(resolved) if event["id"] == "close.close")
    assert focus11_close["text"].startswith("You will close your plus access channel now as")
    assert "Ten. Ten." in focus11_close["text"]
    assert focus11_close["dsp"]["state"] == {"from": "focus-11", "to": "focus-10"}
    assert focus11_close["dsp"]["transition_s"] == 10
    sleep_close = next(
        event for event in iter_events(resolved) if event["id"] == "focus20-close.ready"
    )
    assert sleep_close["text"] == "Relax and feel calm and serene in the twentieth state."
    # The other return-ready use remains the correct tenth-state instruction.
    immediate_return = next(
        event for event in iter_events(resolved) if event["id"] == "close.ready"
    )
    assert immediate_return["text"] == "Relax and feel calm and serene in the ten state."
    sleep_entry = next(
        event for event in iter_events(resolved) if event["id"] == "focus20-enter.enter"
    )
    assert sleep_entry["text"].count("Twenty.") == 2
    assert len(load_all_functions()) == 58


def test_successor_hold_and_transition_are_speech_anchored_and_version_locked():
    root = REPO_ROOT
    prep = yaml.safe_load(
        (root / "audio/templates/stages/OCF-TPL-STAGE-HPLUS-BODY-COMFORT-002.yaml").read_text()
    )
    hold = next(event for event in prep["events"] if event["id"] == "breathing-hold")
    assert hold["after"] == "begin"
    assert hold["semantic"] == "preparation.breathing-practice-hold"
    assert hold["timing"] == {"anchor": "speech-end", "pause_after": 20}

    close = yaml.safe_load(
        (
            root / "audio/templates/stages/OCF-TPL-STAGE-HPLUS-FOCUS-ELEVEN-CLOSE-002.yaml"
        ).read_text()
    )
    close_event = next(event for event in close["events"] if event["id"] == "close")
    assert close_event["dsp"]["state"] == {"from": "focus-11", "to": "focus-10"}
    assert close_event["pacing_key"] == "transitions.focus11_to_focus10_s"
    pacing = load_pacing_profile("OCF-PACING-HPLUS-LOCKED-004")
    assert pacing["transitions"]["focus10_to_focus11_s"] == 25
    assert pacing["transitions"]["focus11_to_focus10_s"] == 10
    assert pacing["pauses"]["transmutation_box_place_s"] == 20
    assert pacing["underlay"]["gain_db"] == -24
    assert pacing["repetitions"] == {"focus11": 2, "focus20": 2}

    lock = yaml.safe_load((root / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-011.json").read_text())
    assert lock["profiles"]["template"]["id"] == "OCF-TPL-SESSION-HPLUS-LOCKED-001"
    assert (
        yaml.safe_load(
            (root / "audio/templates/sessions/OCF-TPL-SESSION-HPLUS-LOCKED-001.yaml").read_text()
        )["version"]
        == "1.0.0"
    )
