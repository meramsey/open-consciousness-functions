"""Synthetic measured ledgers exercise timing gates without private audio."""

from copy import deepcopy

import pytest
from ocf_tools.session_pacing_audit import audit_session, duration_budget
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def fixture_report():
    def cue(identity, at, duration=5, text="Synthetic approved instruction."):
        return {"id": identity, "at": at, "duration": duration, "spoken_text": text}

    cues = [
        cue("body-comfort.begin", 0, 10),
        cue("transmutation-box.begin", 30),
        cue("transmutation-box.place", 35),
        cue("transmutation-box.complete", 60),
        cue("focus11-body.pass-1", 100),
        cue("focus11-body.pass-2", 120),
        cue("close.close", 200, 30),
        cue("focus20-enter.enter", 300, 10),
        cue("focus20-enter.calm", 310, 5, "Relax and feel calm and serene in the twentieth state."),
        cue("sleep20-body.pass-1", 375, 20),
        cue("sleep20-body.pass-2", 455, 20),
        cue("return.begin", 478),
    ]
    cues[6]["spoken_units"] = [
        {
            "text": "The access signal, the access channel is closed.",
            "start_seconds": 210,
            "end_seconds": 215,
            "audible_end_seconds": 214.8,
        },
        {"text": "Synthetic final sentence.", "start_seconds": 220, "end_seconds": 230},
    ]
    return {
        "function_id": "OCF-FND-001",
        "narration_timing": {"cues": cues},
        "measurements": {"duration_seconds": 484},
        "stages": [
            {
                "id": "sleep20-body",
                "start_seconds": 375,
                "end_seconds": 478,
                "duration_seconds": 103,
                "gain_db": -24,
            }
        ],
        "state_transitions": [
            {"from": "focus-10", "to": "focus-11", "start_s": 70, "end_s": 95},
            {"from": "focus-11", "to": "focus-10", "start_s": 204.8, "end_s": 214.8},
        ],
        "dsp_profile": {"selections": {"focus-10": {}, "focus-11": {}}},
    }


def pacing():
    return {
        "pauses": {
            "sleep20_pre_repeat_s": 60,
            "sleep20_repeat_gap_s": 60,
            "sleep20_post_repeat_s": 3,
        },
        "transitions": {"focus11_to_focus10_s": 10, "focus10_to_focus11_s": 25},
        "underlay": {"gain_db": -24},
    }


def test_complete_measured_accounting_and_explicit_override():
    report = fixture_report()
    result = audit_session(report, pacing=pacing(), verify_successor=True)
    assert result["successor_checks"] == "PASS"
    assert result["initial_rest_seconds"] == result["inter_pass_rest_seconds"] == 60
    assert result["post_pass_rest_seconds"] == 3
    assert result["fixed_holds_seconds"] == {"breathing": 20, "transmutation_box": 20}
    assert result["closure_alignment_error_seconds"] == 0
    assert len(result["passes"]) == 4
    assert result["duration"]["content_truncated"] is False
    assert audit_session(report)["successor_checks"] == "not requested"
    # An explicit profile can request a different rest; never cap it silently.
    custom = deepcopy(report)
    for cue in custom["narration_timing"]["cues"][9:]:
        cue["at"] += 30
    settings = pacing()
    settings["pauses"]["sleep20_pre_repeat_s"] = 90
    assert (
        audit_session(custom, pacing=settings, verify_successor=True)["initial_rest_seconds"] == 90
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "overlap",
        "missing-pass",
        "missing-calm",
        "duplicate-calm",
        "missing-confirmation",
        "early-exit",
        "missing-audible",
        "wrong-initial",
        "wrong-gain",
        "focus20-dsp",
    ],
)
def test_timing_gate_rejects_corrupt_or_unapproved_measurements(mutation):
    report = fixture_report()
    cues = report["narration_timing"]["cues"]
    if mutation == "duplicate":
        cues.append(deepcopy(cues[-1]))
    elif mutation == "overlap":
        cues[1]["at"] = 1
    elif mutation == "missing-pass":
        cues.pop(5)
    elif mutation == "missing-calm":
        cues[8]["spoken_text"] = "Wrong wording."
    elif mutation == "duplicate-calm":
        cues[11]["spoken_text"] = cues[8]["spoken_text"]
    elif mutation == "missing-confirmation":
        cues[6]["spoken_units"] = []
    elif mutation == "early-exit":
        report["state_transitions"][1]["end_s"] -= 1
    elif mutation == "missing-audible":
        cues[6]["spoken_units"][0].pop("audible_end_seconds")
    elif mutation == "wrong-initial":
        cues[9]["at"] += 1
    elif mutation == "wrong-gain":
        report["stages"][0]["gain_db"] = 0
    else:
        report["dsp_profile"]["selections"]["focus-20"] = {}
    with pytest.raises(OCFError):
        audit_session(report, pacing=pacing(), verify_successor=True)


def test_invalid_duration_policy_is_not_silently_accepted():
    with pytest.raises(OCFError, match="minimum <= preferred"):
        duration_budget(2400, {"minimum_seconds": 2700, "maximum_seconds": 1800})
