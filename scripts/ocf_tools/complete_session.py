"""Complete template-driven session auditions using OCF's existing engine stack."""

from __future__ import annotations

import json
import math
import os
import shutil
import wave
from array import array
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .artifact_names import ArtifactNamer, safe_component
from .content import load_layers
from .locale import LocaleCatalog, iter_events, resolve_document
from .paths import (
    AUDIO_RENDERED_DIR,
    publish_workspace_temp_directory,
    record_workspace_failure,
    unique_run_id,
    workspace_run,
    workspace_temp_directory,
)
from .utils import OCFError, sha256_of_file, yaml_safe_dump

REQUIRED_SESSION_SEMANTICS = {
    "focus.ten.enter",
    "focus.ten.transition",
    "focus.eleven.transition.open",
    "focus.eleven.transition.close",
    "focus.twenty.enter",
    "focus.twenty.transition.close",
    "session.return.complete",
    "session.complete",
}
EXPECTED_STATE_TARGETS = [
    "focus-10",
    "focus-11",
    "focus-10",
    "focus-20",
    "focus-10",
    "ordinary-waking",
]


def _resolve_template(
    function_id: str, requested: str | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    from .session import load_template

    layers = load_layers(function_id)
    binding = layers.get("bindings", {})
    allowed = list(binding.get("session_templates", []))
    selected = requested or binding.get("default_session_template")
    if not selected:
        raise OCFError(
            f"{function_id} has no complete default session template; bind one or use "
            "`--mode narration-only` explicitly"
        )
    if selected not in allowed:
        raise OCFError(
            f"session template {selected!r} is not bound to {function_id}; "
            "do not infer a session from a function name"
        )
    template = load_template(selected)
    if template.get("session_completeness") != "complete":
        raise OCFError(
            f"template {selected} is not declared complete; use `--mode narration-only` "
            "or select a bound complete template"
        )
    return template, binding


def _slot_keys(binding: dict[str, Any], template: dict[str, Any]) -> dict[str, str]:
    slot_for_role = {"opener": "opener", "function-body": "function_body", "closer": "closer"}
    result: dict[str, str] = {}
    for resource in (binding.get("narration_plan") or {}).get("sequence", []):
        slot = slot_for_role.get(resource.get("role"))
        if slot:
            if slot in result:
                raise OCFError(f"narration binding has duplicate block role {resource['role']!r}")
            result[slot] = str(resource["key"])
    required = set(template.get("slots", {}).get("required", []))
    missing = required - result.keys()
    if missing:
        raise OCFError(
            "complete session template requires function narration blocks that are not bound: "
            + ", ".join(sorted(missing))
        )
    return result


def _state_directives(doc: dict[str, Any]) -> list[dict[str, Any]]:
    directives = []
    for event in iter_events(doc):
        state = (event.get("dsp") or {}).get("state")
        if state is None:
            continue
        if isinstance(state, str):
            source, target = None, state
        else:
            source, target = state.get("from"), state.get("to")
        directives.append(
            {
                "event_id": event["id"],
                "semantic": event.get("semantic"),
                "from": source,
                "to": target,
            }
        )
    return directives


def _verify_session_structure(
    doc: dict[str, Any],
    binding: dict[str, Any],
    dsp_profile: dict[str, Any],
    *,
    removed: set | None = None,
    body_passes: int = 4,
) -> None:
    events = list(iter_events(doc))
    semantics = {str(event.get("semantic")) for event in events if event.get("semantic")}
    excluded = set()
    stage_semantics = {
        "focus-ten": {"focus.ten.enter", "focus.ten.transition"},
        "open": {"focus.eleven.transition.open"},
        "close": {"focus.eleven.transition.close"},
        "focus20-enter": {"focus.twenty.enter"},
        "focus20-close": {"focus.twenty.transition.close"},
        "return": {"session.return.complete"},
    }
    for stage in removed or ():
        excluded.update(stage_semantics.get(stage, set()))
    missing = REQUIRED_SESSION_SEMANTICS - excluded - semantics
    if missing:
        raise OCFError(
            "complete session is missing required semantic stage(s): " + ", ".join(sorted(missing))
        )
    body_key = next(
        (
            str(item["key"])
            for item in (binding.get("narration_plan") or {}).get("sequence", [])
            if item.get("role") == "function-body"
        ),
        None,
    )
    body_events = [event for event in events if event.get("narration_key") == body_key]
    if body_key is None or len(body_events) != body_passes:
        raise OCFError(
            f"complete session requires exactly {body_passes} bound function-body passes; found {len(body_events)}"
        )
    targets = [item["to"] for item in _state_directives(doc)]
    expected = [
        target
        for stage, target in zip(
            ("focus-ten", "open", "close", "focus20-enter", "focus20-close", "return"),
            EXPECTED_STATE_TARGETS,
            strict=True,
        )
        if stage not in (removed or set())
    ]
    if targets != expected:
        raise OCFError(
            "complete session Focus progression differs from configured sequence: "
            + " -> ".join(str(target) for target in targets)
        )
    required_states = {dsp_profile.get("initial_state"), "focus-10", "focus-11"}
    missing_states = required_states - set(dsp_profile.get("states", {}))
    if missing_states:
        raise OCFError(
            "DSP profile lacks required session state(s): " + ", ".join(sorted(missing_states))
        )
    _verify_stage_background_policy(doc, dsp_profile)


def _verify_stage_background_policy(doc: dict[str, Any], profile: dict[str, Any]) -> None:
    """Check declarative default/per-stage DSP policy against session directives."""
    default_state = profile.get("default_background_state", profile.get("initial_state"))
    if default_state != profile.get("initial_state"):
        raise OCFError("complete-session default background must be active at session start")
    overrides = profile.get("stage_backgrounds", {})
    sections = doc.get("sections", [])
    section_ids = {section["id"] for section in sections}
    unknown_sections = set(overrides) - section_ids
    if unknown_sections:
        raise OCFError(
            "DSP stage-background override refers to unknown section(s): "
            + ", ".join(sorted(unknown_sections))
        )
    states = profile.get("states", {})
    default_choice = states.get(default_state, {})
    if default_choice.get("mode") != "preset":
        raise OCFError("complete-session default background state must select an audio preset")
    ignored = set(profile.get("ignored_state_events", []))
    directives_seen = {item["event_id"] for item in _state_directives(doc)}
    if ignored - directives_seen:
        raise OCFError(
            "DSP profile ignores state event(s) absent from this session: "
            + ", ".join(sorted(ignored - directives_seen))
        )
    current = default_state
    for section in sections:
        expected = overrides.get(section["id"], [default_state])
        missing = set(expected) - states.keys()
        if missing:
            raise OCFError(
                f"section {section['id']} selects unconfigured DSP state(s): "
                + ", ".join(sorted(missing))
            )
        disabled = [state for state in expected if states[state].get("mode") != "preset"]
        if disabled:
            raise OCFError(
                f"section {section['id']} expects disabled background state(s): "
                + ", ".join(disabled)
            )
        allowed = set(expected)
        if current not in allowed:
            raise OCFError(
                f"section {section['id']} does not preserve its incoming background state {current}"
            )
        for event in section.get("timeline", []):
            if event.get("id") in ignored:
                continue
            directive = (event.get("dsp") or {}).get("state")
            if directive is None:
                continue
            if isinstance(directive, str):
                source, target = current, directive
            else:
                source, target = directive.get("from", current), directive.get("to")
            if source != current:
                raise OCFError(
                    f"section {section['id']} has a logical DSP transition from {source}, "
                    f"but its active background state is {current}"
                )
            if target not in allowed:
                raise OCFError(
                    f"section {section['id']} transitions to unconfigured stage background {target}"
                )
            current = target


def _session_plan_summary(
    doc: dict[str, Any],
    template: dict[str, Any],
    resources: list[dict[str, Any]],
    dsp_profile: dict[str, Any],
    narration_pacing_plan: list[dict[str, Any]],
    session_pacing_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    ignored = set(dsp_profile.get("ignored_state_events", []))
    directives = _state_directives(doc)
    return {
        "session_completeness": doc.get("session_completeness"),
        "template": {
            "id": template["id"],
            "version": template.get("version"),
            "origin": template.get("origin"),
            "content_status": template.get("content_status"),
        },
        "pacing_profile": doc.get("pacing_profile"),
        "narration_pacing_policy": doc.get("narration_pacing", {}),
        "pacing_auditions": (session_pacing_profile or {}).get("pacing_auditions", {}),
        "dsp_profile": {
            "id": dsp_profile["id"],
            "version": dsp_profile.get("version"),
            "states": dsp_profile["states"],
            "default_background_state": dsp_profile.get(
                "default_background_state", dsp_profile["initial_state"]
            ),
            "ignored_state_events": dsp_profile.get("ignored_state_events", []),
            "ending_fade_seconds": dsp_profile.get("ending_fade_seconds", 0),
        },
        "stages": [
            {
                "id": section["id"],
                "type": section.get("type"),
                "role": section.get("role"),
                "event_ids": [event["id"] for event in section.get("timeline", [])],
                "narration_keys": list(
                    dict.fromkeys(
                        event["narration_key"]
                        for event in section.get("timeline", [])
                        if event.get("narration_key")
                    )
                ),
                "gain_db": section.get("gain_db"),
                "background_policy_states": dsp_profile.get("stage_backgrounds", {}).get(
                    section["id"],
                    [dsp_profile.get("default_background_state", dsp_profile["initial_state"])],
                ),
            }
            for section in doc.get("sections", [])
        ],
        "state_directives": directives,
        "effective_state_directives": [
            item for item in directives if item["event_id"] not in ignored
        ],
        "ignored_state_directives": [item for item in directives if item["event_id"] in ignored],
        "narration_pacing_plan": narration_pacing_plan,
        "narration_resources": resources,
    }


def build_complete_session_plan(
    function_id: str,
    *,
    locale: str | None = None,
    voice: str | None = None,
    pacing: str = "normal",
    template: str | None = None,
    dsp_profile: str | None = None,
    overrides: dict | None = None,
) -> dict[str, Any]:
    """Resolve a bound complete session and prove stage/state completeness before synthesis."""
    from .narration_first import plan_narration
    from .semantic_dsp import load_profile
    from .session import compose, load_pacing_profile
    from .validators import validate_timed_transcript

    plan = plan_narration(function_id, locale=locale, voice=voice, pacing=pacing)
    layers = load_layers(function_id)
    binding = layers.get("bindings", {})
    template_record, _binding = _resolve_template(function_id, template)
    from .session_overrides import apply as apply_overrides
    from .session_overrides import resolve as resolve_overrides

    options, option_provenance = resolve_overrides(binding, overrides)
    selected_template = template_record["id"]
    selected_dsp = dsp_profile or options.get("dsp_profile") or template_record.get("dsp_profile")
    if not selected_dsp:
        raise OCFError(f"complete session template {selected_template} has no explicit DSP profile")
    dsp = load_profile(selected_dsp)
    selected_pacing = (
        load_pacing_profile(str(options.get("pacing_profile") or template_record["pacing_profile"]))
        if template_record.get("pacing_profile")
        else None
    )
    template_record, selected_pacing, dsp, removed, passes = apply_overrides(
        template_record, selected_pacing, dsp, options
    )

    slot_names = {"opener": "opener", "function-body": "function_body", "closer": "closer"}
    slot_keys = {}
    for resource in (binding.get("narration_plan") or {}).get("sequence", []):
        slot = slot_names.get(resource.get("role"))
        if slot:
            if slot in slot_keys:
                raise OCFError(
                    f"narration-plan role {resource['role']!r} is ambiguous for session slots"
                )
            slot_keys[slot] = str(resource["key"])
    missing = set(template_record.get("slots", {}).get("required", [])) - slot_keys.keys()
    if missing:
        raise OCFError(
            "required complete-session narration slot(s) are unbound: " + ", ".join(sorted(missing))
        )

    doc = compose(
        template_record,
        {},
        title=plan["title"],
        document_id=f"{function_id.lower()}-{plan['requested_locale'].lower()}-complete-session",
        function_id=function_id,
        pacing_profile=selected_pacing,
        slot_keys=slot_keys,
    )
    doc["semantic_dsp_profile"] = selected_dsp
    if voice is None:
        doc.pop("voice_profile", None)
    _verify_session_structure(doc, binding, dsp, removed=removed, body_passes=passes)
    validation = validate_timed_transcript(doc, Path("complete-session-plan"))
    if validation.errors:
        raise OCFError(
            "complete session plan failed timed-script validation: "
            + " | ".join(issue.message for issue in validation.errors)
        )
    resolved = resolve_document(doc, plan["requested_locale"], strict=True)
    resolved_resources = list((resolved.get("narration") or {}).get("resolved", []))
    from .locale import NARRATION_DOMAIN
    from .narration_pacing import plan_event_pacing

    catalog = LocaleCatalog()
    for item in resolved_resources:
        if item.get("key") == "inline":
            raise OCFError(
                "complete session includes inline text rather than bound canonical narration"
            )
        entry, _resolution = catalog.resource(
            str(item["key"]), str(item["locale"]), domain=NARRATION_DOMAIN, fallback=False
        )
        if entry.status not in {"reviewed", "canonical"}:
            raise OCFError(
                f"required complete-session narration {item['key']!r} is not review-ready: {entry.status!r}"
            )
    narration_pacing_plan = []
    for event in iter_events(resolved):
        event_pacing = plan_event_pacing(resolved, event)
        if event_pacing is None:
            continue
        narration_pacing_plan.append(
            {
                "event_id": event["id"],
                "narration_key": event.get("narration_key"),
                "profile_id": event_pacing["profile_id"],
                "rate_scale": event_pacing["rate_scale"],
                "units": event_pacing["units"],
                "internal_pause_seconds": round(
                    sum(
                        unit["pause_after_s"]
                        for unit in event_pacing["units"]
                        if unit["pause_inside_event"]
                    ),
                    3,
                ),
            }
        )
    section_report = _session_plan_summary(
        doc, template_record, resolved_resources, dsp, narration_pacing_plan, selected_pacing
    )
    function_review = (layers.get("specifications") or {}).get("human_review", "unknown")
    return {
        "schema_version": "1.0",
        "function_id": function_id,
        "title": plan["title"],
        "locale": plan["requested_locale"],
        "voice": plan["voice_profile"],
        "voice_selection": {
            "profile_id": plan["voice_profile"]["id"]
            if plan["voice_profile"]
            else options.get("voice_profile", template_record.get("voice_profile")),
            "source": "cli"
            if voice
            else option_provenance.get("voice_profile", "selected-template"),
            "backend_verified": voice is not None,
        },
        "pacing": plan["pacing"],
        "template": section_report["template"],
        "session_completeness": "complete",
        "content_status": template_record.get("content_status"),
        "dsp_profile": section_report["dsp_profile"],
        "stages": section_report["stages"],
        "state_directives": section_report["state_directives"],
        "effective_state_directives": section_report["effective_state_directives"],
        "ignored_state_directives": section_report["ignored_state_directives"],
        "narration_pacing_plan": section_report["narration_pacing_plan"],
        "narration_pacing_policy": section_report["narration_pacing_policy"],
        "pacing_auditions": section_report["pacing_auditions"],
        "narration_resources": resolved_resources,
        "approval_state": {
            "script_status": plan["approval_state"]["script_status"],
            "function_review_status": function_review,
            "template_content_status": template_record.get("content_status"),
            "tts_ready": True,
            "release_ready": False,
            "release_note": "Complete session is an audition; human content/release review and approved artwork remain required.",
        },
        "template_plan": doc,
        "tts_plan": plan,
        "dsp_selections": section_report["dsp_profile"]["states"],
        "resolved_overrides": options,
        "override_provenance": option_provenance,
        "resolved_pacing_profile": selected_pacing,
        "resolved_dsp_profile": dsp,
    }


def _probe_audio(path: Path) -> dict[str, Any]:
    executable = shutil.which("ffprobe")
    if not executable:
        raise OCFError("ffprobe is required to verify a complete stereo session")
    result = workspace_run(
        [executable, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise OCFError(f"ffprobe could not inspect complete session WAV: {result.stderr[-600:]}")
    data = json.loads(result.stdout)
    audio = next(
        (stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"), None
    )
    if audio is None:
        raise OCFError("complete session master has no audio stream")
    return {
        "codec": audio.get("codec_name"),
        "sample_rate": int(audio.get("sample_rate") or 0),
        "channels": int(audio.get("channels") or 0),
        "channel_layout": audio.get("channel_layout"),
        "sample_format": audio.get("sample_fmt"),
        "duration_seconds": float(data.get("format", {}).get("duration") or 0),
        "bit_rate": int(data.get("format", {}).get("bit_rate") or 0) or None,
    }


def _verify_decode(path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise OCFError("ffmpeg is required to decode and verify complete session audio")
    result = workspace_run(
        [ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise OCFError(f"complete session audio decode failed: {result.stderr[-600:]}")


def _stereo_metrics(path: Path, sample_rate: int) -> dict[str, Any]:
    with wave.open(str(path), "rb") as reader:
        if (
            reader.getnchannels() != 2
            or reader.getframerate() != sample_rate
            or reader.getsampwidth() != 2
        ):
            raise OCFError(
                "complete session master must be stereo 16-bit PCM at the configured sample rate"
            )
        frames = reader.getnframes()
        left_peak = right_peak = different = clipped = 0
        left_squares = right_squares = 0
        seen = 0
        while raw := reader.readframes(65536):
            values = array("h")
            values.frombytes(raw)
            if os.sys.byteorder != "little":
                values.byteswap()
            for index in range(0, len(values), 2):
                left, right = values[index], values[index + 1]
                left_peak = max(left_peak, abs(left))
                right_peak = max(right_peak, abs(right))
                different += left != right
                clipped += abs(left) >= 32767 or abs(right) >= 32767
                left_squares += left * left
                right_squares += right * right
                seen += 1
    if frames <= 0 or seen != frames:
        raise OCFError("stereo session master is empty or truncated")
    if different == 0:
        raise OCFError(
            "complete session output has identical L/R channels; binaural stereo is absent"
        )

    def rms_db(squares: int) -> float:
        rms = math.sqrt(squares / frames)
        return round(20 * math.log10(rms / 32768), 2) if rms else float("-inf")

    return {
        "frames": frames,
        "sample_rate": sample_rate,
        "channels": 2,
        "duration_seconds": round(frames / sample_rate, 3),
        "left_peak_int16": left_peak,
        "right_peak_int16": right_peak,
        "left_rms_dbfs": rms_db(left_squares),
        "right_rms_dbfs": rms_db(right_squares),
        "different_channel_frames": different,
        "clipped_sample_count": clipped,
    }


def _background_activity(
    path: Path, stages: list[dict[str, Any]], selections: dict[str, Any]
) -> list[dict[str, Any]]:
    checks = []
    configured_states = {
        state for state, selection in selections.items() if selection.get("mode") == "preset"
    }
    with wave.open(str(path), "rb") as reader:
        rate = reader.getframerate()
        width = reader.getsampwidth()
        channels = reader.getnchannels()
        if channels != 2 or width not in (2, 3, 4):
            raise OCFError("retained background stem must be stereo PCM")
        for stage in stages:
            active_layers = stage.get("background_at_midpoint", [])
            if not active_layers or stage["duration_seconds"] < 5:
                continue
            sample_at = stage["start_seconds"] + stage["duration_seconds"] / 2
            reader.setpos(min(reader.getnframes() - 1, int(sample_at * rate)))
            raw = reader.readframes(min(rate, max(1, reader.getnframes() - int(sample_at * rate))))
            if width == 2:
                values = array("h")
                values.frombytes(raw)
                if os.sys.byteorder != "little":
                    values.byteswap()
                energy = sum(value * value for value in values)
                different_channels = sum(
                    values[index] != values[index + 1] for index in range(0, len(values), 2)
                )
            else:
                step = width * channels
                energy = 0
                different_channels = 0
                for offset in range(0, len(raw), step):
                    left = int.from_bytes(raw[offset : offset + width], "little", signed=True)
                    right = int.from_bytes(
                        raw[offset + width : offset + step], "little", signed=True
                    )
                    energy += left * left + right * right
                    different_channels += left != right
            if energy == 0:
                raise OCFError(f"configured background is silent in active stage {stage['id']}")
            if not different_channels:
                raise OCFError(
                    f"configured binaural background has no independent L/R content in stage {stage['id']}"
                )
            checks.append(
                {
                    "stage_id": stage["id"],
                    "sample_time_seconds": round(sample_at, 3),
                    "layers": active_layers,
                    "different_channel_frames": different_channels,
                    "status": "non-silent",
                }
            )
    if not checks:
        raise OCFError("complete session has no verifiable active background stages")
    checked_states = {layer["state"] for check in checks for layer in check["layers"]}
    if configured_states - checked_states:
        raise OCFError(
            "configured background state(s) were not measured in an active stage: "
            + ", ".join(sorted(configured_states - checked_states))
        )
    for stage in stages:
        expected = set(stage.get("expected_background_states", []))
        if not expected or stage["duration_seconds"] < 5:
            continue
        actual = {layer["state"] for layer in stage.get("background_at_midpoint", [])}
        if not actual or not actual <= expected:
            raise OCFError(
                f"background state mismatch in {stage['id']}: allowed "
                f"{', '.join(sorted(expected))}, found {', '.join(sorted(actual)) or 'silence'}"
            )
    return checks


def _pcm_window(path: Path, start_seconds: float, *, seconds: float = 1.0) -> dict[str, Any]:
    with wave.open(str(path), "rb") as reader:
        rate, channels, width = reader.getframerate(), reader.getnchannels(), reader.getsampwidth()
        first = max(0, min(reader.getnframes() - 1, int(start_seconds * rate)))
        reader.setpos(first)
        raw = reader.readframes(max(1, int(seconds * rate)))
    if channels != 2 or width not in (2, 3, 4):
        raise OCFError("background analysis requires stereo PCM")
    full_scale = 1 << (width * 8 - 1)
    left_squares = right_squares = left_peak = right_peak = different = frames = 0
    if width == 2:
        values = array("h")
        values.frombytes(raw)
        if os.sys.byteorder != "little":
            values.byteswap()
        samples = ((values[index], values[index + 1]) for index in range(0, len(values), 2))
    else:
        step = width * channels
        samples = (
            (
                int.from_bytes(raw[offset : offset + width], "little", signed=True),
                int.from_bytes(raw[offset + width : offset + step], "little", signed=True),
            )
            for offset in range(0, len(raw), step)
        )
    for left, right in samples:
        left_squares += left * left
        right_squares += right * right
        left_peak = max(left_peak, abs(left))
        right_peak = max(right_peak, abs(right))
        different += left != right
        frames += 1
    if not frames:
        raise OCFError(f"background analysis window at {start_seconds:.3f}s is empty")

    def rms_db(squares: int) -> float:
        rms = math.sqrt(squares / frames)
        return round(20 * math.log10(rms / full_scale), 2) if rms else float("-inf")

    return {
        "start_seconds": round(start_seconds, 3),
        "duration_seconds": round(frames / rate, 3),
        "left_rms_dbfs": rms_db(left_squares),
        "right_rms_dbfs": rms_db(right_squares),
        "left_peak": left_peak,
        "right_peak": right_peak,
        "different_channel_frames": different,
        "non_silent": left_squares + right_squares > 0,
    }


def _representative_audio_analysis(
    path: Path,
    stages: list[dict[str, Any]],
    render: dict[str, Any],
    dsp: dict[str, Any],
) -> list[dict[str, Any]]:
    from .semantic_dsp import gain_at

    by_stage = {stage["id"]: stage for stage in stages}
    event_timing = {row["id"]: row for row in render.get("event_timing", [])}
    transitions = {row["event_id"]: row for row in dsp.get("transitions", [])}
    duration = float(dsp["duration_s"])
    fade = float(dsp.get("ending_fade_seconds", 0))
    points: list[tuple[str, float, set[str]]] = [("opening-first-10-seconds", 5.0, {"focus-10"})]
    probes = {
        "body-comfort": "body-comfort-midpoint",
        "transmutation-box": "transmutation-box-midpoint",
        "relaxation": "relaxation-midpoint",
        "focus-ten": "focus-10-induction",
        "focus11-body": "focus-11-programming-midpoint",
        "sleep20-body": "sleep-function-body-midpoint",
        "return": "return-midpoint",
        "function-closer": "function-closer-midpoint",
    }
    for stage_id, label in probes.items():
        if stage_id in by_stage:
            stage = by_stage[stage_id]
            points.append(
                (
                    label,
                    (stage["start_seconds"] + stage["end_seconds"]) / 2,
                    {"focus-11" if stage_id == "focus11-body" else "focus-10"},
                )
            )
    for event_id, label in (
        ("open.transition", "focus-11-entry-transition"),
        ("close.transition", "focus-11-closing-transition"),
    ):
        if event_id in transitions:
            transition = transitions[event_id]
            points.append(
                (label, (transition["start_s"] + transition["end_s"]) / 2, {"focus-10", "focus-11"})
            )
    if "focus20-enter.enter" in event_timing:
        points.append(
            ("sleep-entry", float(event_timing["focus20-enter.enter"]["at"]) + 1, {"focus-10"})
        )
    if fade > 0:
        fade_start = duration - fade
        points.extend(
            [
                ("ending-fade-start", fade_start + 0.25, {"focus-10"}),
                ("ending-fade-midpoint", fade_start + fade / 2, {"focus-10"}),
                ("ending-fade-end", duration - 1.25, {"focus-10"}),
            ]
        )
    report = []
    for label, sample_at, expected_states in points:
        measured = _pcm_window(path, sample_at)
        active_states = {
            state
            for state, selection in dsp["selections"].items()
            if selection.get("mode") == "preset" and gain_at(dsp, state, sample_at) > 1e-4
        }
        if active_states != expected_states:
            raise OCFError(
                f"resolved audio states at {label} differ from policy: expected "
                f"{', '.join(sorted(expected_states))}, found {', '.join(sorted(active_states))}"
            )
        if not measured["non_silent"] or measured["different_channel_frames"] == 0:
            raise OCFError(f"actual background audio is silent or not stereo at {label}")
        report.append(
            {
                "checkpoint": label,
                "expected_states": sorted(expected_states),
                **measured,
                "status": "measured-non-silent-stereo",
            }
        )
    if fade > 0:
        fade_windows = [
            next(row for row in report if row["checkpoint"] == label)["left_rms_dbfs"]
            for label in ("ending-fade-start", "ending-fade-midpoint", "ending-fade-end")
        ]
        if not (fade_windows[0] > fade_windows[1] > fade_windows[2]):
            raise OCFError(f"Focus 10 ending fade is not smoothly descending: {fade_windows}")
    return report


def _verify_background_continuity(
    path: Path, duration: float, fade_seconds: float
) -> dict[str, Any]:
    rate = 44100
    scanned_seconds = max(0, int(math.floor(duration - fade_seconds)))
    silent_seconds = []
    with wave.open(str(path), "rb") as reader:
        rate = reader.getframerate()
        channels = reader.getnchannels()
        for second in range(scanned_seconds):
            raw = reader.readframes(rate)
            if not raw or not any(raw):
                silent_seconds.append(second)
    if silent_seconds:
        raise OCFError(
            "background bed contains silent full-second window(s) before the ending fade: "
            + ", ".join(str(value) for value in silent_seconds[:10])
        )
    return {
        "scanned_seconds_before_fade": scanned_seconds,
        "silent_full_seconds_before_fade": silent_seconds,
        "ending_fade_seconds": fade_seconds,
        "sample_rate": rate,
        "channels": channels,
        "status": "continuous-through-pauses",
    }


def _build_stage_report(doc: dict, render: dict, dsp: dict) -> list[dict[str, Any]]:
    from .semantic_dsp import gain_at

    timing = {event["id"]: event for event in render.get("event_timing", [])}
    transitions = dsp.get("transitions", [])
    selections = dsp.get("selections", {})
    report = []
    for section in doc.get("sections", []):
        events = section.get("timeline", [])
        rows = [timing[event["id"]] for event in events if event["id"] in timing]
        start = min((float(row["at"]) for row in rows), default=0.0)
        end = max((float(row["end"]) for row in rows), default=start)
        active_state = dsp.get("initial_state", "ordinary-waking")
        overlapping = []
        for transition in transitions:
            if float(transition["end_s"]) <= start:
                active_state = transition["to"]
            elif float(transition["start_s"]) < end and float(transition["end_s"]) > start:
                overlapping.append(transition)
        template_stage = next(
            (
                stage["id"]
                for stage in doc.get("stages", [])
                if stage.get("instance") == section["id"]
            ),
            None,
        )
        midpoint = start + max(0.0, end - start) / 2
        active_layers = [
            {
                "state": state,
                "gain": round(gain_at(dsp, state, midpoint), 6),
                "preset_id": selection.get("preset_id"),
            }
            for state, selection in selections.items()
            if selection.get("mode") == "preset" and gain_at(dsp, state, midpoint) > 1e-4
        ]
        report.append(
            {
                "id": section["id"],
                "template_stage": template_stage,
                "type": section.get("type"),
                "role": section.get("role"),
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "duration_seconds": round(max(0.0, end - start), 3),
                "gain_db": section.get("gain_db"),
                "expected_background_states": dsp.get("stage_backgrounds", {}).get(
                    section["id"],
                    [dsp.get("default_background_state", dsp["initial_state"])],
                ),
                "state_at_start": active_state,
                "background_at_start": selections.get(active_state, {"mode": "unconfigured"}),
                "background_at_midpoint": active_layers,
                "transition_windows": overlapping,
                "narration_keys": list(
                    dict.fromkeys(
                        event["narration_key"] for event in events if event.get("narration_key")
                    )
                ),
                "events": [
                    {
                        "id": row["id"],
                        "start_seconds": round(float(row["at"]), 3),
                        "end_seconds": round(float(row["end"]), 3),
                        "semantic": row.get("semantic"),
                        "dsp": row.get("dsp"),
                    }
                    for row in rows
                ],
            }
        )
    return report


def render_complete_session(
    function_id: str,
    *,
    locale: str | None = None,
    voice: str | None = None,
    pacing: str = "normal",
    template: str | None = None,
    dsp_profile: str | None = None,
    voice_gain: float | None = None,
    background_gain: float | None = None,
    output: str | Path | None = None,
    dry_run: bool = False,
    sample_rate: int = 44100,
    created_at: datetime | None = None,
    overrides: dict | None = None,
) -> dict[str, Any]:
    """Expand the bound complete session and render/mix it using OCF's engines."""
    from . import audio_build
    from .narration_first import _adjusted_profile, _voice_profile
    from .session_overrides import resolve as resolve_overrides
    from .session_overrides import verify_stage_limits

    selected_template, binding = _resolve_template(function_id, template)
    explicit_voice = voice
    options, _ = resolve_overrides(binding, overrides)
    voice = voice or options.get("voice_profile") or selected_template.get("voice_profile")
    voice_gain = voice_gain if voice_gain is not None else options.get("narration_gain", 1.0)
    background_gain = (
        background_gain if background_gain is not None else options.get("background_gain")
    )

    session_plan = build_complete_session_plan(
        function_id,
        locale=locale,
        voice=voice,
        pacing=pacing,
        template=template,
        dsp_profile=dsp_profile,
        overrides=overrides,
    )
    session_plan["voice_selection"]["source"] = (
        "cli"
        if explicit_voice
        else (
            "cli"
            if (overrides or {}).get("voice_profile")
            else "function-binding"
            if binding.get("session_overrides", {}).get("voice_profile")
            else "selected-template"
        )
    )
    if dry_run:
        return {"dry_run": True, "session_plan": session_plan}
    tts_plan = session_plan["tts_plan"]
    doc = session_plan["template_plan"]
    selected_dsp = session_plan["resolved_dsp_profile"]["id"]
    session_pacing_profile = session_plan["resolved_pacing_profile"]

    default_dir = (
        AUDIO_RENDERED_DIR
        / "auditions"
        / "-".join(
            (
                function_id,
                safe_component(tts_plan["requested_locale"], max_length=16),
                safe_component(tts_plan["voice_profile"]["id"], max_length=24),
                "complete-session",
            )
        )
        / unique_run_id(function_id)
    )
    output_dir = Path(output or default_dir).expanduser().resolve()
    if output_dir.exists():
        raise OCFError(f"refusing to overwrite existing complete-session audition: {output_dir}")
    try:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        stage = workspace_temp_directory(prefix="ocf-session-stage-")
    except OSError as exc:
        raise OCFError(f"cannot create session audition staging directory: {exc}") from exc

    try:
        if options:
            resolved_dsp_path = stage / "resolved-dsp.yaml"
            resolved_dsp_path.write_text(
                yaml_safe_dump(session_plan["resolved_dsp_profile"]), encoding="utf-8"
            )
            selected_dsp = str(resolved_dsp_path)
        (stage / "render-context.json").write_text(
            json.dumps(
                {
                    "function_id": function_id,
                    "output_directory": str(output_dir),
                    "template": session_plan["template"],
                    "dsp_profile": selected_dsp,
                    "status": "rendering",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        from .narration_first import _adjusted_profile, _voice_profile

        catalog = LocaleCatalog()
        profile_data, _resolved_voice = _voice_profile(voice, tts_plan["requested_locale"], catalog)
        adjusted_voice = _adjusted_profile(tts_plan, profile_data)
        script_path = stage / "session-plan.yaml"
        script_path.write_text(yaml_safe_dump(doc), encoding="utf-8", newline="\n")
        render_dir = stage / "engine-render"
        render_dir.mkdir()
        transient_manifest = {
            "function_id": function_id,
            "title": tts_plan["title"],
            "language": tts_plan["requested_locale"],
            "narrator": None,
            "transcript_path": str(script_path.resolve()),
            "background_audio": {"strategy": "none", "preset": None},
        }
        bg_gain = 1.0 if background_gain is None else float(background_gain)
        if not math.isfinite(bg_gain) or bg_gain < 0:
            raise OCFError("background_gain must be a finite nonnegative linear gain")
        built = audio_build.build(
            "complete-session",
            manifest_override=transient_manifest,
            document_override=doc,
            render_label="complete-session",
            out_root=render_dir,
            formats=["wav"],
            voice=adjusted_voice,
            voice_gain=voice_gain,
            background_gain=bg_gain,
            sample_rate=sample_rate,
            locale=tts_plan["requested_locale"],
            strict=True,
            overwrite=False,
            dsp_profile=selected_dsp,
            retain_background_stem=True,
        )
        verify_stage_limits(doc, built["event_timing"], options.get("stage_maximum_seconds", {}))
        render_master = render_dir / built["master"]["file"]
        background_info = built.get("background_stem")
        if not background_info:
            raise OCFError("complete session rendered no retained background layer")
        render_background = render_dir / background_info["file"]
        master_name = ArtifactNamer().filename(
            function_id,
            tts_plan["title"],
            tts_plan["requested_locale"],
            "wav",
            variant=f"{tts_plan['voice_profile']['id']}-session",
        )
        background_name = ArtifactNamer().filename(
            function_id,
            tts_plan["title"],
            tts_plan["requested_locale"],
            "wav",
            variant="background-stem",
        )
        master_path = stage / master_name
        background_path = stage / background_name
        shutil.copy2(render_master, master_path)
        shutil.copy2(render_background, background_path)

        master_probe = _probe_audio(master_path)
        background_probe = _probe_audio(background_path)
        if master_probe["channels"] != 2 or master_probe["sample_rate"] != sample_rate:
            raise OCFError(f"complete session master is not {sample_rate} Hz stereo")
        if abs(master_probe["duration_seconds"] - background_probe["duration_seconds"]) > 0.01:
            raise OCFError("background layer does not span the complete master duration")
        master_metrics = _stereo_metrics(master_path, sample_rate=sample_rate)
        if master_metrics["clipped_sample_count"]:
            raise OCFError(
                f"complete session mix contains {master_metrics['clipped_sample_count']} clipped samples"
            )
        _verify_decode(master_path)
        _verify_decode(background_path)
        stages = _build_stage_report(doc, built, built.get("semantic_dsp") or {})
        activity = _background_activity(
            background_path, stages, (built.get("semantic_dsp") or {}).get("selections", {})
        )
        audio_analysis = _representative_audio_analysis(
            background_path, stages, built, built.get("semantic_dsp") or {}
        )
        continuity = _verify_background_continuity(
            background_path,
            background_probe["duration_seconds"],
            float((built.get("semantic_dsp") or {}).get("ending_fade_seconds", 0)),
        )

        cues = built.get("narration_timing", {}).get("cues", [])
        cues = sorted(cues, key=lambda cue: (float(cue.get("at", 0)), str(cue.get("id", ""))))
        transcript = "\n\n".join(
            str(cue.get("spoken_text") or "").strip()
            for cue in cues
            if str(cue.get("spoken_text") or "").strip()
        )
        transcript += "\n"
        transcript_path = stage / ArtifactNamer().filename(
            function_id, tts_plan["title"], tts_plan["requested_locale"], "txt", variant="session"
        )
        transcript_path.write_text(transcript, encoding="utf-8", newline="\n")

        from .pacing_auditions import write_timing_reports_and_auditions

        timing_artifact, pacing_auditions, timing_report = write_timing_reports_and_auditions(
            stage=stage,
            master_path=master_path,
            function_id=function_id,
            title=tts_plan["title"],
            locale=tts_plan["requested_locale"],
            voice=tts_plan["voice_profile"],
            session_pacing=tts_plan["pacing"],
            pacing_profile=session_pacing_profile,
            document=doc,
            render=built,
            session_duration=float(built["master"]["duration"]),
            sample_rate=sample_rate,
        )

        created = datetime.now(UTC)
        manifest = {
            "schema_version": "1.0",
            "render_type": "complete-session-audition",
            "function_id": function_id,
            "audio_implementation_id": None,
            "title": tts_plan["title"],
            "requested_locale": tts_plan["requested_locale"],
            "voice_profile": tts_plan["voice_profile"],
            "pacing": tts_plan["pacing"],
            "session_pacing_profile": {
                "id": session_pacing_profile["id"],
                "version": session_pacing_profile["version"],
                "status": session_pacing_profile["status"],
            },
            "narration_pacing": built.get("narration_pacing", {}),
            "template": session_plan["template"],
            "dsp_profile": {
                key: value
                for key, value in (built.get("semantic_dsp") or {}).items()
                if key not in {"external_commands"}
            },
            "approval_state": session_plan["approval_state"],
            "release_ready": False,
            "mix": {
                "voice_gain": float(voice_gain),
                "background_gain": bg_gain,
                "narration_gain_windows": built.get("narration_gain_windows", []),
                "limiting": "audio_build FFmpeg limiter (0.97 linear ceiling)",
                "ending_fade_seconds": (built.get("semantic_dsp") or {}).get(
                    "ending_fade_seconds", 0
                ),
            },
            "stages": stages,
            "state_transitions": (built.get("semantic_dsp") or {}).get("transitions", []),
            "ignored_state_directives": (built.get("semantic_dsp") or {}).get(
                "ignored_state_directives", []
            ),
            "background_activity_checks": activity,
            "representative_audio_analysis": audio_analysis,
            "background_continuity": continuity,
            "measurements": {
                **master_metrics,
                "background_sample_rate": background_probe["sample_rate"],
                "background_channels": background_probe["channels"],
                "background_duration_seconds": round(background_probe["duration_seconds"], 3),
                "spoken_segment_count": len(cues),
                "spoken_duration_seconds": round(
                    sum(float(cue.get("speech_duration", cue.get("duration", 0))) for cue in cues),
                    3,
                ),
                "narration_audio_duration_seconds": float(
                    built.get("narration_timing", {}).get("duration_seconds", 0)
                ),
            },
            "narration_resources": session_plan["narration_resources"],
            "pacing_auditions": pacing_auditions,
            "artifacts": {
                "wav": {
                    "path": master_name,
                    "format": "wav",
                    "size_bytes": master_path.stat().st_size,
                    "sha256": sha256_of_file(master_path),
                },
                "background_stem": {
                    "path": background_name,
                    "format": "wav",
                    "size_bytes": background_path.stat().st_size,
                    "sha256": sha256_of_file(background_path),
                },
                "transcript": {
                    "path": transcript_path.name,
                    "format": "text/plain; charset=utf-8",
                    "size_bytes": transcript_path.stat().st_size,
                    "sha256": sha256_of_file(transcript_path),
                },
                "session_plan": {
                    "path": script_path.name,
                    "format": "application/yaml",
                    "size_bytes": script_path.stat().st_size,
                    "sha256": sha256_of_file(script_path),
                },
                "timing_report": timing_artifact,
                **{
                    f"pacing_{audition_id}_{artifact_name}": artifact
                    for audition_id, audition in pacing_auditions.items()
                    for artifact_name, artifact in audition.items()
                    if artifact_name in {"wav", "timing_report"}
                },
            },
            "created_at": created.isoformat().replace("+00:00", "Z"),
        }
        report_path = stage / "session-report.json"
        report_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        for item in manifest["artifacts"].values():
            path = stage / item["path"]
            if not path.is_file() or path.stat().st_size != item["size_bytes"]:
                raise OCFError(f"session artifact failed read-back verification: {item['path']}")
            if sha256_of_file(path) != item["sha256"]:
                raise OCFError(f"session artifact checksum failed: {item['path']}")
        if transcript_path.read_text(encoding="utf-8") != transcript or not transcript.endswith(
            "\n"
        ):
            raise OCFError("complete session transcript verification failed")
        shutil.rmtree(render_dir)
        (stage / "render-context.json").unlink(missing_ok=True)
        publish_workspace_temp_directory(stage, output_dir)
        return {"dry_run": False, "output_directory": str(output_dir), "manifest": manifest}
    except OSError as exc:
        if stage.exists():
            record_workspace_failure(
                stage.name, f"filesystem failure: {exc}; retained scratch: {stage}"
            )
        raise OCFError(f"complete session render failed due to a filesystem error: {exc}") from exc
    except BaseException as exc:
        if stage.exists():
            record_workspace_failure(
                stage.name,
                f"render failure: {type(exc).__name__}: {exc}; retained scratch: {stage}",
            )
        raise
