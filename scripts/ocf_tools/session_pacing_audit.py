"""Measured complete-session accounting and successor-only technical timing gates."""

from __future__ import annotations

from .utils import OCFError


def speech_end(cue):
    """Last measured unit endpoint, including internal pauses but not event holds."""
    return max(
        (unit["end_seconds"] for unit in cue.get("spoken_units", [])),
        default=float(cue["at"]) + float(cue["duration"]),
    )


def duration_budget(seconds, preference):
    """Advisory only: never add silence, truncate content or reject long sessions."""
    minimum = preference.get("minimum_seconds", 1800)
    maximum = preference.get("maximum_seconds", 2700)
    preferred = preference.get("preferred_seconds", 2520)
    if not 0 < minimum <= preferred <= maximum:
        raise OCFError("duration preference requires minimum <= preferred <= maximum")
    return {
        "actual_seconds": round(seconds, 3),
        "minimum_seconds": minimum,
        "maximum_seconds": maximum,
        "preferred_seconds": preferred,
        "within_preferred_window": minimum <= seconds <= maximum,
        "advisory": True,
        "content_truncated": False,
        "exception": "Required narration, preserved preparation, repetitions and selected overrides take precedence."
        if seconds > maximum
        else None,
    }


def audit_session(report, *, pacing=None, verify_successor=False):
    cues = report["narration_timing"]["cues"]
    by_id = {cue["id"]: cue for cue in cues}
    if len(by_id) != len(cues):
        raise OCFError("duplicate narration event in session audit")
    for previous, following in zip(cues, cues[1:]):
        if speech_end(previous) > float(following["at"]) + 0.002:
            raise OCFError("overlapping measured narration in session audit")
    passes = [cue for cue in cues if cue["id"].startswith(("focus11-body.", "sleep20-body."))]
    quiet = [cue for cue in passes if cue["id"].startswith("sleep20-body.")]
    if len(passes) != 4 or len(quiet) != 2:
        raise OCFError("session audit requires four complete function-body passes")
    calm = [
        cue
        for cue in cues
        if " ".join(cue["spoken_text"].split())
        == "Relax and feel calm and serene in the twentieth state."
    ]
    if len(calm) != 1:
        raise OCFError("session audit requires exactly one approved twentieth-state sentence")
    closure = by_id["close.close"]
    confirmation = [
        unit
        for unit in closure["spoken_units"]
        if unit["text"] == "The access signal, the access channel is closed."
    ]
    if len(confirmation) != 1:
        raise OCFError("session audit requires unique measured closure confirmation")
    exit_window = next(
        row
        for row in report["state_transitions"]
        if row["from"] == "focus-11" and row["to"] == "focus-10"
    )
    entry = next(row for row in report["state_transitions"] if row["to"] == "focus-11")
    initial = float(quiet[0]["at"]) - speech_end(calm[0])
    inter = float(quiet[1]["at"]) - speech_end(quiet[0])
    post = float(by_id["return.begin"]["at"]) - speech_end(quiet[1])
    holds = {
        "breathing": float(by_id["transmutation-box.begin"]["at"])
        - speech_end(by_id["body-comfort.begin"]),
        "transmutation_box": float(by_id["transmutation-box.complete"]["at"])
        - speech_end(by_id["transmutation-box.place"]),
    }
    audible_end = confirmation[0].get("audible_end_seconds")
    result = {
        "function_id": report["function_id"],
        "duration": duration_budget(
            report["measurements"]["duration_seconds"],
            (pacing or {}).get("duration_preference", {}),
        ),
        "stages": [
            {key: stage[key] for key in ("id", "start_seconds", "end_seconds", "duration_seconds")}
            for stage in report["stages"]
        ],
        "passes": [
            {
                "event_id": cue["id"],
                "start_seconds": cue["at"],
                "speech_end_seconds": speech_end(cue),
                "measured_unit_count": len(cue.get("spoken_units", [])),
            }
            for cue in passes
        ],
        "fixed_holds_seconds": holds,
        "initial_rest_seconds": round(initial, 6),
        "inter_pass_rest_seconds": round(inter, 6),
        "post_pass_rest_seconds": round(post, 6),
        "closure_confirmation_end_seconds": confirmation[0]["end_seconds"],
        "closure_audible_end_seconds": audible_end,
        "exit_transition": exit_window,
        "closure_alignment_error_seconds": None
        if audible_end is None
        else round(exit_window["end_s"] - audible_end, 6),
        "successor_checks": "not requested",
    }
    if verify_successor:
        pauses = pacing["pauses"]
        checks = [
            abs(
                (exit_window["end_s"] - exit_window["start_s"])
                - pacing["transitions"]["focus11_to_focus10_s"]
            )
            < 0.001,
            audible_end is not None and abs(exit_window["end_s"] - audible_end) < 0.001,
            abs((entry["end_s"] - entry["start_s"]) - pacing["transitions"]["focus10_to_focus11_s"])
            < 0.001,
            speech_end(by_id["focus20-enter.enter"]) <= float(calm[0]["at"]) + 0.002,
            float(calm[0]["at"]) < float(quiet[0]["at"]),
            abs(initial - pauses["sleep20_pre_repeat_s"]) < 0.002,
            abs(inter - pauses["sleep20_repeat_gap_s"]) < 0.002,
            abs(post - pauses["sleep20_post_repeat_s"]) < 0.002,
            all(abs(value - 20) < 0.002 for value in holds.values()),
            next(stage for stage in report["stages"] if stage["id"] == "sleep20-body")["gain_db"]
            == pacing["underlay"]["gain_db"],
            set(report["dsp_profile"]["selections"]) == {"focus-10", "focus-11"},
        ]
        if not all(checks):
            raise OCFError(f"successor session timing verification failed: {checks}")
        result["successor_checks"] = "PASS"
    return result


def audit_shared_v3(report, *, pacing):
    """Measured routine v3 accounting; old editions retain their old audit."""
    cues = report["narration_timing"]["cues"]
    by_id = {cue["id"]: cue for cue in cues}
    if len(by_id) != len(cues):
        raise OCFError("duplicate v3 narration event")
    for previous, following in zip(cues, cues[1:]):
        if speech_end(previous) > float(following["at"]) + 0.002:
            raise OCFError("overlapping v3 narration")
    transitions = report["state_transitions"]
    closing = next(t for t in transitions if t["from"] == "focus-11" and t["to"] == "focus-10")
    opening = next(t for t in transitions if t["to"] == "focus-11")
    units = [u for u in by_id["close.close"].get("spoken_units", []) if u["text"] == "Ten."]
    if len(units) != 4 or units[-1].get("audible_end_seconds") is None:
        raise OCFError("v3 close requires four measured Ten anchors")
    passes = [c for c in cues if c["id"].startswith(("focus11-body.", "sleep20-body."))]
    holds = {
        "breathing": float(by_id["transmutation-box.begin"]["at"])
        - speech_end(by_id["body-comfort.begin"]),
        "placement": float(by_id["transmutation-box.complete"]["at"])
        - speech_end(by_id["transmutation-box.place"]),
        "initial_ten": float(by_id["open.prepare"]["at"]) - speech_end(by_id["focus-ten.ready"]),
        "eleven_repeat": float(by_id["focus11-body.pass-2"]["at"])
        - speech_end(by_id["focus11-body.pass-1"]),
        "post_close_ten": float(by_id["focus20-enter.enter"]["at"])
        - speech_end(by_id["close.ready"]),
        "pre_sleep_body": float(by_id["sleep20-body.pass-1"]["at"])
        - speech_end(by_id["focus20-enter.calm"]),
        "sleep_repeat": float(by_id["sleep20-body.pass-2"]["at"])
        - speech_end(by_id["sleep20-body.pass-1"]),
        "post_sleep_body": float(by_id["return.begin"]["at"])
        - speech_end(by_id["sleep20-body.pass-2"]),
    }
    expected = dict(zip(holds, (20, 20, 40, 15, 60, 60, 60, 3), strict=True))
    checks = [
        len(passes) == 4,
        all(abs(holds[k] - v) < 0.002 for k, v in expected.items()),
        abs(closing["end_s"] - units[-1]["audible_end_seconds"]) < 0.002,
        abs(closing["end_s"] - closing["start_s"] - 10) < 0.002,
        abs(opening["end_s"] - opening["start_s"] - pacing["transitions"]["focus10_to_focus11_s"])
        < 0.002,
        float(by_id["close.confirmed"]["at"]) >= closing["end_s"],
        speech_end(by_id["focus20-enter.enter"])
        <= float(by_id["focus20-enter.calm"]["at"]) + 0.002,
        next(s for s in report["stages"] if s["id"] == "sleep20-body")["gain_db"] == -24,
        set(report["dsp_profile"]["selections"]) == {"focus-10", "focus-11"},
    ]
    if not all(checks):
        raise OCFError(f"shared v3 measured timing verification failed: {checks}")
    return {
        "successor_checks": "PASS",
        "edition": "shared-v3",
        "holds_seconds": holds,
        "closing_transition": closing,
        "duration": duration_budget(
            report["measurements"]["duration_seconds"], pacing.get("duration_preference", {})
        ),
    }
