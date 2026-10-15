from ocf_tools.audio_defaults import DSP_ID, PACING_ID, TEMPLATE_ID, check_lock
from ocf_tools.complete_session import _verify_session_structure
from ocf_tools.locale import iter_events, resolve_document
from ocf_tools.narration_pacing import plan_event_pacing
from ocf_tools.semantic_dsp import load_profile
from ocf_tools.session import compose, load_pacing_profile, load_template


def test_locked_defaults_and_relative_session_regression():
    lock = check_lock()
    assert lock["human_listening_approval"] is None
    template = load_template(TEMPLATE_ID)
    pacing = load_pacing_profile(PACING_ID)
    dsp = load_profile(DSP_ID)
    slots = {
        name: f"hplus.function.ocf-slp-005.{role}"
        for name, role in (
            ("opener", "opener"),
            ("function_body", "function-body"),
            ("closer", "closer"),
        )
    }
    doc = compose(template, {}, title="Regression", slot_keys=slots, pacing_profile=pacing)
    binding = {
        "narration_plan": {"sequence": [{"key": slots["function_body"], "role": "function-body"}]}
    }
    _verify_session_structure(doc, binding, dsp)
    assert dsp["states"] == {
        "focus-10": {"mode": "preset", "preset": "OCF-BG-0012"},
        "focus-11": {"mode": "preset", "preset": "OCF-BG-0006"},
    }
    assert dsp["initial_state"] == "focus-10"
    assert dsp["ending_fade_seconds"] == 10
    assert dsp["transitions"] == {"curve": "equal-power", "fallback_seconds": 25}
    assert pacing["transitions"]["focus10_to_focus11_s"] == 25
    assert pacing["transitions"]["focus11_to_focus10_s"] == 25
    assert pacing["repetitions"] == {"focus11": 2, "focus20": 2}
    assert next(s for s in doc["sections"] if s["id"] == "sleep20-body")["gain_db"] == -24
    resolved = resolve_document(doc, "en-US", strict=True)
    plans = {
        e.get("narration_key"): plan_event_pacing(resolved, e)
        for e in iter_events(resolved)
        if e.get("narration_key")
    }
    comfort = plans["hplus.shared.body-comfort"]["units"]
    assert len(comfort) == 7
    assert all(u["pause_after_s"] == 3 for u in comfort[:-1])
    assert all(u["rate_scale"] == 1 for u in comfort)
    assert all(u["pause_after_s"] == 5 for u in plans["hplus.shared.focus20.enter"]["units"][4:-1])
    assert [u["pause_after_s"] for u in plans["hplus.shared.waking.begin"]["units"][4:24]] == [
        3
    ] * 19 + [4]
