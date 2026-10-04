"""Resolve actual speech-dependent anchors without silently cutting narration."""

from __future__ import annotations

import math

from .locale import iter_events
from .transcript import resolve_timeline
from .utils import OCFError


def schedule_timeline(doc: dict, speech_durations: dict[str, float]) -> list[dict]:
    """Fixed anchors remain fixed; explicit reflow can delay spoken events.

    End-relative dependencies follow measured duration. Overlapping fixed
    speech fails before writing an artifact, instead of overwriting samples.
    """
    pending = {event["id"]: event for event in iter_events(doc)}
    starts: dict[str, float] = {}
    rows = []
    speech_available = 0.0
    while pending:
        events, problems = resolve_timeline(
            doc, speech_durations=speech_durations, start_overrides=starts
        )
        if problems:
            raise OCFError("timeline problems: " + " | ".join(problems))
        times = {event.id: event.at for event in events}
        eligible = [
            event
            for event in pending.values()
            if not event.get("after") or event["after"] in starts
        ]
        # resolve_timeline already rejects missing targets and cycles. The
        # remaining dependency graph is a DAG, so it always has an eligible node.
        event = min(
            eligible, key=lambda item: times[item["id"]] if times[item["id"]] is not None else -1
        )
        identifier = event["id"]
        at = times[identifier]
        if at is None:
            raise OCFError(f"event {identifier} has no timestamp")
        if not math.isfinite(at) or at < 0:
            raise OCFError(f"event {identifier} has an invalid resolved timestamp")
        duration = speech_durations.get(identifier, 0.0)
        if not math.isfinite(duration) or duration < 0:
            raise OCFError(f"event {identifier} has an invalid measured speech duration")
        timing = event.get("timing") or {}
        if timing.get("maximum_duration") is not None and duration > timing["maximum_duration"]:
            raise OCFError(f"event {identifier}: measured speech exceeds explicit maximum_duration")
        if duration and at < speech_available - 1e-6:
            if timing.get("policy", "fixed") == "reflow":
                at = speech_available
            else:
                raise OCFError(
                    f"fixed speech overlap at event {identifier}: starts {at:.3f}s, "
                    f"previous narration/pause ends {speech_available:.3f}s; "
                    "use a speech-end dependency or explicit timing.policy: reflow"
                )
        starts[identifier] = at
        pause = float(timing.get("pause_after", 0))
        if duration:
            speech_available = at + duration + pause
        event_duration = max(duration, float((event.get("dsp") or {}).get("transition_s", 0)))
        rows.append(
            {
                "id": identifier,
                "at": round(at, 6),
                "speech_duration": duration,
                "end": round(at + event_duration + pause, 6),
                **{key: event[key] for key in ("semantic", "dsp", "auditory_cue") if key in event},
            }
        )
        pending.pop(identifier)
    return sorted(rows, key=lambda row: row["at"])
