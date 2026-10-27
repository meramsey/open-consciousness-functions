"""Explicit precedence and safe structural overrides; shared locked files are immutable."""

import math
from copy import deepcopy

from .audio_defaults import overlay
from .utils import OCFError
from .validators import _load_schema, validate_against_schema


def resolve(binding: dict, cli: dict | None = None) -> tuple[dict, dict]:
    function = deepcopy(binding.get("session_overrides", {}))
    cli = deepcopy(cli or {})
    for data in (function, cli):

        def finite(value):
            if isinstance(value, float) and not math.isfinite(value):
                raise OCFError("session override numbers must be finite")
            if isinstance(value, dict):
                for child in value.values():
                    finite(child)
            elif isinstance(value, list):
                for child in value:
                    finite(child)

        finite(data)
        errors = validate_against_schema(data, _load_schema("session-overrides.schema.json"))
        if errors:
            raise OCFError("session overrides: " + " | ".join(errors))
        if "ending" in data:
            wake = data["ending"] == "waking"
            if "waking_return" in data and data["waking_return"] != wake:
                raise OCFError("ending and waking_return conflict")
            data["waking_return"] = wake
        elif "waking_return" in data:
            data["ending"] = "waking" if data["waking_return"] else "sleep"
    resolved = overlay(function, cli)
    return resolved, {key: "cli" if key in cli else "function-binding" for key in resolved}


def apply(
    template: dict, pacing: dict, dsp: dict, options: dict
) -> tuple[dict, dict, dict, set, int]:
    template, pacing, dsp = deepcopy(template), deepcopy(pacing), deepcopy(dsp)
    pacing = overlay(pacing, options.get("pacing", {}))
    repetitions = options.get("repetitions", {})
    pacing["repetitions"]["focus11"] = repetitions.get(
        "programming", pacing["repetitions"]["focus11"]
    )
    if repetitions.get("sleep", 1) > 0:
        pacing["repetitions"]["focus20"] = repetitions.get(
            "sleep", pacing["repetitions"]["focus20"]
        )
    removed = set()
    if not options.get("sleep_continuation", True):
        removed.update(("focus20-enter", "sleep20-body", "focus20-close"))
    elif repetitions.get("sleep") == 0:
        removed.add("sleep20-body")
    if not options.get("waking_return", True):
        removed.add("return")
    if "focus_stages" in options:
        if "focus-10" not in options["focus_stages"]:
            removed.add("focus-ten")
        if "focus-11" not in options["focus_stages"]:
            removed.update(("open", "focus11-body", "close"))
            dsp["allow_static"] = True
    template["sections"] = [s for s in template["sections"] if s["id"] not in removed]
    unknown = set(options.get("stage_maximum_seconds", {})) - {
        s["id"] for s in template["sections"]
    }
    if unknown:
        raise OCFError(
            "stage duration limit selects absent stage(s): " + ", ".join(sorted(unknown))
        )
    dsp["ignored_state_events"] = [
        e for e in dsp.get("ignored_state_events", []) if e.split(".")[0] not in removed
    ]
    dsp["stage_backgrounds"] = {
        k: v for k, v in dsp.get("stage_backgrounds", {}).items() if k not in removed
    }
    if "transition_end_anchors" in dsp:
        dsp["transition_end_anchors"] = {
            key: value
            for key, value in dsp["transition_end_anchors"].items()
            if key.split(".")[0] not in removed
        }
    pacing["pacing_auditions"] = {
        k: v
        for k, v in pacing.get("pacing_auditions", {}).items()
        if v.get("stage_id", str(v.get("event_id", "")).split(".")[0]) not in removed
    }
    count = (0 if "focus11-body" in removed else pacing["repetitions"]["focus11"]) + (
        0 if "sleep20-body" in removed else pacing["repetitions"]["focus20"]
    )
    if count < 1:
        raise OCFError("complete function session requires at least one function-body pass")
    errors = validate_against_schema(pacing, _load_schema("session-pacing.schema.json"))
    if errors:
        raise OCFError("resolved pacing overrides: " + " | ".join(errors))
    return template, pacing, dsp, removed, count


def verify_stage_limits(document: dict, measured: list[dict], limits: dict):
    rows = {row["id"]: row for row in measured}
    for section in document["sections"]:
        if section["id"] in limits:
            events = [rows[e["id"]] for e in section["timeline"]]
            duration = max(e["end"] for e in events) - min(e["at"] for e in events)
            if duration > limits[section["id"]]:
                raise OCFError(
                    f"stage {section['id']} measured {duration:.3f}s exceeds explicit maximum {limits[section['id']]}s; narration was not compressed"
                )
