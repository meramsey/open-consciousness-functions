"""DSP support can precede a semantic arrival without redefining the state."""

from copy import deepcopy
from pathlib import Path

import pytest
from ocf_tools.indexes import load_yaml_file
from ocf_tools.locale import iter_events
from ocf_tools.semantic_dsp import gain_at, load_profile, plan_program
from ocf_tools.utils import OCFError
from test_semantic_dsp import TIMES, state_doc

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[1]


def fixture():
    doc = state_doc()
    doc["timeline"][:0] = [
        {"id": "preparation", "at": 1, "semantic": "preparation.relaxation.begin"},
        {"id": "arrival-word", "at": 8, "semantic": "focus.ten.enter"},
    ]
    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    profile["approaches"] = [
        {
            "state": "focus-10",
            "begin_event": "preparation",
            "established_event": "arrival-word",
            "state_event": "ten",
            "curve": "raised-cosine",
        }
    ]
    times = [{"id": "preparation", "at": 1}, {"id": "arrival-word", "at": 8}, *deepcopy(TIMES)]
    return doc, times, profile


def composed_preparation_learning():
    from ocf_tools.session import compose

    template = load_yaml_file(
        REPO_ROOT / "audio/templates/sessions/OCF-TPL-SESSION-PREP-LEARN-001.yaml"
    )
    return list(iter_events(compose(template, {}, title="approach binding", duration=1800.0)))


def test_induction_established_arrival_and_existing_f11_exit_are_separate():
    doc, times, profile = fixture()
    original = deepcopy(doc)
    program = plan_program(doc, times, 100, profile)
    assert doc == original
    assert program["initial_state"] == "ordinary-waking"
    assert program["transitions"][0]["event_id"] == "ten"
    assert program["transitions"][0]["start_s"] == program["transitions"][0]["end_s"] == 10
    assert gain_at(program, "focus-10", 0.9) == 0
    assert gain_at(program, "focus-10", 1) == 0
    assert gain_at(program, "focus-10", 1.01) < 0.001
    assert gain_at(program, "focus-10", 4.5) == pytest.approx(0.5)
    assert gain_at(program, "focus-10", 8) == 1
    assert gain_at(program, "focus-10", 9) == gain_at(program, "focus-10", 10) == 1
    assert all(gain_at(program, "focus-11", time) == 0 for time in (0, 1, 4.5, 8, 20, 29))
    assert gain_at(program, "focus-10", 35) ** 2 + gain_at(
        program, "focus-11", 35
    ) ** 2 == pytest.approx(1)
    assert gain_at(program, "focus-10", 50) == 0 and gain_at(program, "focus-10", 80) == 1
    assert gain_at(program, "focus-10", 99) == 0
    assert program["selections"]["focus-11"]["preset_id"] == "OCF-BG-0006"


def test_timing_is_measured_locale_aware_and_not_inferred_from_words():
    doc, times, profile = fixture()
    doc["timeline"][0]["text"] = "Texto arbitrario: diez once relaxation."
    before = plan_program(doc, times, 100, profile)
    doc["timeline"][0]["text"] = "Completely different wording."
    assert plan_program(doc, times, 100, profile) == before
    changed = deepcopy(times)
    changed[0]["at"] = 2
    changed[1]["at"] = 9
    program = plan_program(doc, changed, 100, profile)
    assert program["approaches"][0]["start_s"] == 2
    assert program["approaches"][0]["established_s"] == 9
    assert gain_at(program, "focus-10", 5.5) == pytest.approx(0.5)
    # Removing the directive restores the pre-existing fallback, regardless of
    # words that happen to contain "relaxation" or "Ten".
    del profile["approaches"]
    legacy = plan_program(doc, times, 100, profile)
    assert "approaches" not in legacy
    assert legacy["transitions"][0]["end_s"] == 15
    assert gain_at(legacy, "focus-10", 9) == 0


@pytest.mark.parametrize(
    "defect",
    [
        "missing",
        "late",
        "wrong-target",
        "duplicate",
        "disabled",
        "overlap",
        "nonfinite",
        "second-ramp",
    ],
)
def test_ambiguous_or_invalid_approaches_fail_instead_of_guessing(defect):
    doc, times, profile = fixture()
    declaration = profile["approaches"][0]
    if defect == "missing":
        declaration["begin_event"] = "not-in-session"
    elif defect == "late":
        times[1]["at"] = 11
    elif defect == "wrong-target":
        declaration["state"] = "focus-11"
    elif defect == "duplicate":
        profile["approaches"].append(deepcopy(declaration))
    elif defect == "disabled":
        profile["states"]["focus-10"] = {"mode": "disabled"}
    elif defect == "overlap":
        declaration["state_event"] = "close"
        times[1]["at"] = 55
    elif defect == "nonfinite":
        times[0]["at"] = float("nan")
    else:
        next(event for event in doc["timeline"] if event["id"] == "ten")["dsp"]["transition_s"] = 2
    with pytest.raises(OCFError):
        plan_program(doc, times, 100, profile)


def test_shipped_induction_profile_binds_only_real_committed_stage_events():
    """The V2.1 profile anchors resolve against committed templates, not prose."""
    events = composed_preparation_learning()
    order = {event["id"]: index for index, event in enumerate(events)}
    stage_types = {
        name: load_yaml_file(REPO_ROOT / f"audio/templates/stages/OCF-TPL-STAGE-{name}.yaml")[
            "type"
        ]
        for name in ("RELAXATION-001", "FOCUS-TEN-001")
    }
    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-INDUCTION-001")
    assert profile["states"]["focus-10"]["preset"] == "OCF-BG-0012"
    assert profile["states"]["focus-11"]["preset"] == "OCF-BG-0006"
    assert profile["states"]["ordinary-waking"]["mode"] == "disabled"
    # Canonical/alternate mapping is the V4-001 mapping, not a new selection.
    assert profile["states"] == load_profile("OCF-DSP-DEVELOPMENT-V4-001")["states"]
    assert profile["transitions"] == load_profile("OCF-DSP-DEVELOPMENT-V4-001")["transitions"]
    assert len(profile["approaches"]) == 1
    approach = profile["approaches"][0]
    assert approach == {
        "state": "focus-10",
        "begin_event": "relaxation.begin",
        "established_event": "focus-ten.enter",
        "state_event": "focus-ten.transition",
        "curve": "raised-cosine",
    }
    assert all(
        approach[key] in order for key in ("begin_event", "established_event", "state_event")
    )
    directives = {event["id"]: event["dsp"] for event in events if event.get("dsp")}
    assert directives[approach["state_event"]] == {"state": "focus-10"}
    assert stage_types["RELAXATION-001"] == "induction"
    assert stage_types["FOCUS-TEN-001"] == "induction"
    # Ordering is template identity, independent of any measured or English time.
    assert order["relaxation.begin"] < order["focus-ten.learn"] < order["focus-ten.count-one"]
    assert order["focus-ten.count-one"] < order["focus-ten.enter"] < order["focus-ten.transition"]
    # Only F10 arrival is rescheduled; F10->F11, return and exit stay untouched.
    assert set(directives) == {
        "focus-ten.transition",
        "open.transition",
        "close.transition",
        "return.complete",
    }
    assert directives["open.transition"] == {"state": {"from": "focus-10", "to": "focus-11"}}
    assert directives["return.complete"] == {"state": "ordinary-waking"}
