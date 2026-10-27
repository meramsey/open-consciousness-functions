from copy import deepcopy

import pytest
from ocf_tools import audio_defaults, semantic_dsp
from ocf_tools.complete_session import build_complete_session_plan
from ocf_tools.locale import iter_events
from ocf_tools.paths import REPO_ROOT
from ocf_tools.session import load_pacing_profile
from ocf_tools.session_pacing_audit import duration_budget
from ocf_tools.utils import OCFError
from ocf_tools.voice import _active_bounds


@pytest.mark.unit
@pytest.mark.parametrize("confirmation_end", [80.12, 100.32, 141.75])
def test_exit_follows_measured_audible_confirmation_not_voice_onset(monkeypatch, confirmation_end):
    monkeypatch.setattr(
        "ocf_tools.audio_build._resolve_background_manifest",
        lambda _ref: {"id": "fixture", "engine": "reference-master"},
    )
    profile = semantic_dsp.load_profile(audio_defaults.DSP_ID)
    profile["ignored_state_events"] = []
    profile["initial_state"] = "focus-11"
    profile["default_background_state"] = "focus-11"
    doc = {
        "timeline": [
            {
                "id": "close.close",
                "semantic": "focus.eleven.close",
                "dsp": {"state": {"from": "focus-11", "to": "focus-10"}, "transition_s": 10},
            }
        ]
    }
    unit = {
        "text": "The access signal, the access channel is closed.",
        "start_seconds": confirmation_end - 4,
        "end_seconds": confirmation_end + 0.2,
        "audible_end_seconds": confirmation_end,
    }
    timing = [{"id": "close.close", "at": 40, "end": confirmation_end + 10, "spoken_units": [unit]}]
    result = semantic_dsp.plan_program(doc, timing, 200, profile)
    transition = result["transitions"][0]
    assert transition["start_s"] == pytest.approx(confirmation_end - 10)
    assert transition["end_s"] == confirmation_end
    middle = confirmation_end - 5
    assert semantic_dsp.gain_at(result, "focus-10", middle) == pytest.approx(2**-0.5)
    assert semantic_dsp.gain_at(result, "focus-11", middle) == pytest.approx(2**-0.5)
    for offset in range(-11, 2):
        t = confirmation_end + offset
        assert sum(
            semantic_dsp.gain_at(result, state, t) ** 2 for state in ("focus-10", "focus-11")
        ) == pytest.approx(1)
    for mutation in (
        [],
        [unit, unit],
        [{**unit, "audible_end_seconds": None}],
        [{**unit, "audible_end_seconds": 300}],
    ):
        bad = deepcopy(timing)
        bad[0]["spoken_units"] = mutation
        with pytest.raises(OCFError):
            semantic_dsp.plan_program(doc, bad, 200, profile)


@pytest.mark.unit
def test_audible_bound_excludes_backend_tail_without_trimming_speech():
    samples = [0] * 100 + [1000] * 200 + [0] * 200
    assert _active_bounds(samples, 1000) == (100, 300)
    assert len(samples) == 500


@pytest.mark.integration
def test_successor_relocates_only_approved_sentence_and_preserves_preparation():
    old = build_complete_session_plan("OCF-SEN-001", template="OCF-TPL-SESSION-HPLUS-LOCKED-004")
    new = build_complete_session_plan("OCF-SEN-001")
    previous = list(iter_events(old["template_plan"]))
    current = list(iter_events(new["template_plan"]))
    calm = [
        event
        for event in current
        if event.get("narration_key") == "hplus.shared.focus20.close.ready"
    ]
    assert len(calm) == 1 and calm[0]["id"] == "focus20-enter.calm"
    ids = [event["id"] for event in current]
    assert (
        ids.index("focus20-enter.enter")
        < ids.index(calm[0]["id"])
        < ids.index("sleep20-body.pass-1")
    )
    assert "focus20-close.ready" not in ids
    old_by_id = {event["id"]: event for event in previous}
    for event in current:
        if event["id"].split(".")[0] not in {
            "focus20-enter",
            "focus20-close",
            "sleep20-body",
            "return",
        }:
            assert event == old_by_id[event["id"]]
    assert (
        next(event for event in current if event["id"] == "return.begin")["narration_key"]
        == next(event for event in previous if event["id"] == "return.begin")["narration_key"]
    )
    assert set(new["resolved_dsp_profile"]["states"]) == {"focus-10", "focus-11"}
    assert new["resolved_pacing_profile"]["pauses"]["sleep20_pre_repeat_s"] == 60
    assert new["resolved_pacing_profile"]["pauses"]["sleep20_repeat_gap_s"] == 60
    assert new["resolved_pacing_profile"]["pauses"]["sleep20_post_repeat_s"] == 3
    assert next(stage for stage in new["stages"] if stage["id"] == "sleep20-body")["gain_db"] == -24
    assert sum(event.get("semantic") == "function.instruction" for event in current) == 4


@pytest.mark.integration
def test_immediate_predecessor_locks_verify_without_projection_changes():
    for number in (13, 14, 15):
        path = REPO_ROOT / f"audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-{number:03}.json"
        assert audio_defaults.check_lock(path)["id"] == path.stem


@pytest.mark.integration
def test_pacing_ledger_preserves_predecessors_and_rejects_drift():
    import json

    from ocf_tools.session_pacing_successor import LEDGER, predecessor

    ledger = json.loads((REPO_ROOT / LEDGER).read_text(encoding="utf-8"))
    assert len(ledger["files"]) == 117
    for name, row in ledger["files"].items():
        current = (REPO_ROOT / name).read_text(encoding="utf-8")
        assert predecessor(REPO_ROOT, name, current) == row["before"]
    with pytest.raises(OCFError, match="source drift"):
        predecessor(REPO_ROOT, name, current + "tampering")


@pytest.mark.unit
@pytest.mark.parametrize("seconds", [1700, 2400, 3000, 4000])
def test_duration_window_is_advisory_never_truncates_required_material(seconds):
    preference = {"minimum_seconds": 1800, "maximum_seconds": 2700, "preferred_seconds": 2520}
    result = duration_budget(seconds, preference)
    assert result["actual_seconds"] == seconds
    assert result["content_truncated"] is False and result["advisory"] is True
    assert result["within_preferred_window"] == (1800 <= seconds <= 2700)
    if seconds > 2700:
        assert result["exception"]


@pytest.mark.integration
def test_explicit_sleep_override_remains_authoritative():
    from ocf_tools.session import load_template
    from ocf_tools.session_overrides import apply

    template, pacing, dsp, removed, passes = apply(
        load_template(audio_defaults.TEMPLATE_ID),
        load_pacing_profile(audio_defaults.PACING_ID),
        semantic_dsp.load_profile(audio_defaults.DSP_ID),
        {"pacing": {"pauses": {"sleep20_pre_repeat_s": 90}}},
    )
    assert pacing["pauses"]["sleep20_pre_repeat_s"] == 90
    assert passes == 4 and not removed
