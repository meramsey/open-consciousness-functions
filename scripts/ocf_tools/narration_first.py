"""Narration-first localized TTS planning and non-destructive audition renders."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import shutil
import wave
from array import array
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .artifact_names import ArtifactNamer, safe_component
from .content import load_layers
from .indexes import load_function_by_id, load_voice_profiles
from .locale import LocaleCatalog, normalize_tag
from .paths import (
    AUDIO_RENDERED_DIR,
    publish_workspace_temp_directory,
    record_workspace_failure,
    unique_run_id,
    workspace_temp_directory,
)
from .utils import OCFError, sha256_of_file

PACING_PRESETS: dict[str, dict[str, float | str]] = {
    "normal": {
        "description": "Natural instruction pacing with brief paragraph transitions.",
        "speech_rate_scale": 1.0,
        "tts_headroom_db": -3.0,
        "paragraph_pause_s": 0.8,
        "section_pause_s": 2.0,
        "leading_silence_s": 0.5,
        "ending_silence_s": 2.0,
    },
    "relaxed": {
        "description": "Gentler delivery with unhurried paragraph and section transitions.",
        "speech_rate_scale": 1.04,
        "tts_headroom_db": -3.0,
        "paragraph_pause_s": 1.5,
        "section_pause_s": 4.0,
        "leading_silence_s": 1.5,
        "ending_silence_s": 4.0,
    },
    "sleep": {
        "description": "Gentle sleep-oriented delivery with longer configured transitions.",
        "speech_rate_scale": 1.08,
        "tts_headroom_db": -3.0,
        "paragraph_pause_s": 2.0,
        "section_pause_s": 6.0,
        "leading_silence_s": 2.0,
        "ending_silence_s": 6.0,
    },
}

_ALLOWED_RESOURCE_STATUSES = {"reviewed", "canonical"}


def _normalized_paragraphs(text: str) -> list[str]:
    """Split a resource at authored blank lines, retaining words and line breaks."""
    return [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]


def _voice_profile(
    query: str, locale: str, catalog: LocaleCatalog
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve an existing voice profile without exposing its local model path."""
    from .voice import check_backend_locale, resolve_backend

    profiles = load_voice_profiles()
    lowered = query.strip().lower()
    profile = next(
        (
            item
            for item in profiles
            if any(str(item.get(key, "")).lower() == lowered for key in ("id", "slug", "name"))
        ),
        None,
    )
    if profile is None:
        raise OCFError(f"unknown voice profile {query!r}; use `ocf voice list`")
    resolved = resolve_backend(profile, profiles, locale=locale, catalog=catalog)
    executable = shutil.which(resolved["binary"])
    if not executable:
        raise OCFError(
            f"voice backend {resolved['name']} executable is not available: {resolved['binary']}"
        )
    if resolved["name"] == "piper" and (
        not resolved.get("model") or not Path(str(resolved["model"])).is_file()
    ):
        raise OCFError(
            f"Piper model for {profile['id']} is unavailable; configure its existing piper_model path"
        )
    check_backend_locale(resolved)
    return dict(profile), resolved


def _profile_for_pacing(
    profile: dict[str, Any], resolved_voice: dict[str, Any], pacing: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply a preset's supported rate multiplier to a copy of the profile."""
    adjusted = dict(profile)
    factor = float(pacing["speech_rate_scale"])
    if resolved_voice["name"] == "piper":
        base = float(profile.get("piper_length_scale") or 1.0)
        adjusted["piper_length_scale"] = round(base * factor, 4)
    elif resolved_voice.get("wpm"):
        adjusted["words_per_min"] = max(80, round(float(resolved_voice["wpm"]) / factor))
    return adjusted


def plan_narration(
    function_id: str,
    *,
    locale: str | None = None,
    voice: str | None = None,
    pacing: str = "normal",
    catalog: LocaleCatalog | None = None,
) -> dict[str, Any]:
    """Resolve a bound canonical narration sequence into exact TTS segments.

    Text is loaded exclusively from existing locale resources. The function's
    established ``audio.script_status`` and each resource status gate TTS
    readiness; function specification review and package-release readiness are
    reported independently and are never promoted here.
    """
    record = load_function_by_id(function_id)
    if record is None:
        raise OCFError(f"unknown function {function_id}")
    if record.data.get("audio", {}).get("script_status") != "approved":
        raise OCFError(
            f"{function_id} is not approved for TTS: audio.script_status is "
            f"{record.data.get('audio', {}).get('script_status')!r}"
        )
    selected_pacing = PACING_PRESETS.get(pacing)
    if selected_pacing is None:
        raise OCFError(f"unknown pacing preset {pacing!r}; choose from {', '.join(PACING_PRESETS)}")
    catalog = catalog or LocaleCatalog()
    try:
        requested_locale = normalize_tag(locale) if locale else catalog.canonical_locale
    except OCFError as exc:
        raise OCFError(f"invalid locale {locale!r}: {exc}") from exc
    if not requested_locale:
        raise OCFError(f"invalid locale {locale!r}")
    from .commands import cue_presentation

    localized_primary_cue = cue_presentation(record, requested_locale, catalog=catalog, strict=True)
    voice_profile, resolved_voice = (
        _voice_profile(voice, requested_locale, catalog)
        if voice is not None
        else ({}, {"name": "unselected"})
    )
    layers = load_layers(function_id)
    specification = layers.get("specifications") or {}
    binding = layers.get("bindings") or {}
    narration_plan = record.data.get("narration") or binding.get("narration_plan")
    if not isinstance(narration_plan, dict) or not narration_plan.get("sequence"):
        raise OCFError(f"{function_id} has no explicit function-content narration_plan binding")

    segments: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    from .voice import BACKENDS, apply_pronunciation

    for block in narration_plan["sequence"]:
        key = str(block["key"])
        entry, resolution = catalog.resource(
            key, requested_locale, domain="narration", fallback=False
        )
        if entry.status not in _ALLOWED_RESOURCE_STATUSES:
            raise OCFError(
                f"narration resource {key!r} is not TTS-ready: status is {entry.status!r}"
            )
        for token in entry.required_pronunciation if voice is not None else ():
            if (
                resolved_voice["name"] not in BACKENDS
                or not BACKENDS[resolved_voice["name"]].get("phonemes")
                or not entry.hint_for(resolved_voice["name"], token)
            ):
                raise OCFError(
                    f"resource {key!r} requires pronunciation for {token!r} that is unavailable "
                    f"on {resolved_voice['name']}"
                )
        paragraphs = _normalized_paragraphs(entry.text)
        if not paragraphs:
            raise OCFError(f"narration resource {key!r} contains no spoken text")
        resources.append(
            {
                "key": key,
                "requested_locale": resolution.locale,
                "resolved_locale": resolution.origin_locale,
                "fallback": resolution.fallback,
                "version": entry.version,
                **(
                    {
                        "raw_template_sha256": hashlib.sha256(
                            entry.raw_template.encode("utf-8")
                        ).hexdigest(),
                        "resolved_text_sha256": hashlib.sha256(
                            entry.text.encode("utf-8")
                        ).hexdigest(),
                    }
                    if entry.raw_template is not None
                    else {}
                ),
                "status": entry.status,
                "paragraph_count": len(paragraphs),
                "repetitions": int(block["repetitions"]),
                "role": str(block["role"]),
            }
        )
        for playback in range(1, int(block["repetitions"]) + 1):
            for paragraph_index, text in enumerate(paragraphs, start=1):
                segments.append(
                    {
                        "id": f"seg-{len(segments) + 1:03d}",
                        "resource_key": key,
                        "resolved_locale": resolution.origin_locale,
                        "role": str(block["role"]),
                        "playback": playback,
                        "paragraph": paragraph_index,
                        "canonical_text": text,
                        "spoken_text": apply_pronunciation(
                            text, entry.pronunciation, resolved_voice["name"]
                        ),
                    }
                )

    if not segments:
        raise OCFError(f"{function_id} narration plan resolved to no TTS segments")

    configured_rate = resolved_voice.get("wpm")
    word_rate = float(configured_rate) if configured_rate else 155.0
    words = sum(len(segment["canonical_text"].split()) for segment in segments)
    pauses = 0.0
    sequence = narration_plan["sequence"]
    for segment in segments:
        is_resource_end = segment["paragraph"] == next(
            resource["paragraph_count"]
            for resource in resources
            if resource["key"] == segment["resource_key"]
        )
        repeated_body_end = (
            segment["role"] == "function-body"
            and is_resource_end
            and segment["playback"]
            < next(
                int(block["repetitions"])
                for block in sequence
                if block["key"] == segment["resource_key"]
            )
        )
        pause = float(
            selected_pacing["section_pause_s"]
            if is_resource_end and not repeated_body_end
            else selected_pacing["paragraph_pause_s"]
        )
        if repeated_body_end:
            pause = float(selected_pacing["section_pause_s"])
        segment["pause_after_s"] = pause
        pauses += pause
    previous_pause = float(segments[-1]["pause_after_s"])
    segments[-1]["pause_after_s"] = float(selected_pacing["ending_silence_s"])
    pauses += float(selected_pacing["ending_silence_s"]) - previous_pause

    estimate = (
        words / word_rate * 60.0
        + pauses
        + float(selected_pacing["leading_silence_s"])
        + float(selected_pacing["ending_silence_s"])
        + len(segments) * 0.4
        + 1.0
    )
    title_key = record.documentation.get("title_key")
    if title_key:
        title_entry, title_resolution = catalog.resource(
            title_key, requested_locale, domain="ui", fallback=True
        )
        title = title_entry.render(
            {}, plural_rules=catalog.plural_rules_for(title_resolution.origin_locale)
        )
        title_provenance = {
            "requested_locale": title_resolution.locale,
            "resolved_locale": title_resolution.origin_locale,
            "fallback": title_resolution.fallback,
            "resource_key": title_key,
        }
    else:
        title = record.canonical_name
        title_provenance = {
            "requested_locale": requested_locale,
            "resolved_locale": "canonical-record",
            "fallback": True,
            "resource_key": None,
        }

    if localized_primary_cue and localized_primary_cue["binding_status"] == "resolved":
        origins = [
            title_provenance["resolved_locale"],
            localized_primary_cue["spoken_locale"],
            *(row["resolved_locale"] for row in resources),
        ]
        if any(origin.split("-", 1)[0] != requested_locale.split("-", 1)[0] for origin in origins):
            raise OCFError(
                "complete localized title, cue and teaching must resolve in the requested language"
            )

    return {
        "schema_version": "1.0",
        "function_id": record.id,
        "title": title,
        "cue_presentation": localized_primary_cue,
        "title_resolution": title_provenance,
        "requested_locale": requested_locale,
        "voice_profile": {
            "id": voice_profile["id"],
            "slug": voice_profile["slug"],
            "name": voice_profile["name"],
            "backend": resolved_voice["name"],
            "language": resolved_voice.get("language"),
        }
        if voice is not None
        else None,
        "pacing": {"id": pacing, **selected_pacing},
        "approval_state": {
            "script_status": record.data.get("audio", {}).get("script_status"),
            "function_review_status": specification.get("human_review", "unknown"),
            "resource_statuses": {item["key"]: item["status"] for item in resources},
            "tts_ready": True,
            "release_ready": False,
            "release_note": (
                "Function-content human review remains required; this audition does not approve release."
                if specification.get("human_review") != "approved"
                else "Rights and final release approval must still be verified separately."
            ),
        },
        "narration_resources": resources,
        "segments": segments,
        "estimated_duration_seconds": round(estimate, 2),
        "word_count": words,
    }


def _dynamic_document(plan: dict[str, Any]) -> dict[str, Any]:
    """Convert ordered TTS segments to a speech-end-linked timed document."""
    from .transcript import format_timestamp

    events = []
    previous = None
    for index, segment in enumerate(plan["segments"]):
        event: dict[str, Any] = {
            "id": segment["id"],
            "text": segment["spoken_text"],
            "locale": segment["resolved_locale"],
            "source_resource_key": segment["resource_key"],
            "narration_role": segment["role"],
            "playback": segment["playback"],
            "paragraph": segment["paragraph"],
            "timing": {
                "anchor": "start" if previous is None else "speech-end",
                "pause_after": segment["pause_after_s"],
            },
        }
        if previous is None:
            event["at"] = format_timestamp(float(plan["pacing"]["leading_silence_s"]))
        else:
            event["after"] = previous
            event["offset"] = 0.0
        events.append(event)
        previous = event["id"]
    return {
        "schema_version": "1.0",
        "id": f"{plan['function_id'].lower()}-{plan['requested_locale'].lower()}-narration-first",
        "title": plan["title"],
        "function_id": plan["function_id"],
        "locale": plan["requested_locale"],
        "timing_mode": "natural",
        "voice_profile": plan["voice_profile"]["id"],
        "timeline": events,
    }


def _adjusted_profile(plan: dict[str, Any], voice_profile: dict[str, Any]) -> dict[str, Any]:
    from .voice import effective_profile_defaults

    profile = effective_profile_defaults(voice_profile)
    factor = float(plan["pacing"]["speech_rate_scale"])
    if plan["voice_profile"]["backend"] == "piper":
        profile["piper_length_scale"] = round(
            float(profile.get("piper_length_scale") or 1.0) * factor, 4
        )
    elif profile.get("words_per_min"):
        profile["words_per_min"] = max(80, round(float(profile["words_per_min"]) / factor))
    return profile


def _apply_tts_headroom(data: bytes, gain_db: float) -> tuple[bytes, int]:
    """Apply a modest fixed headroom gain to each TTS cue before PCM assembly."""
    from .voice import _read_pcm_from_bytes

    sample_rate, samples = _read_pcm_from_bytes(data)
    rail_samples = sum(1 for sample in samples if abs(sample) >= 32767)
    factor = 10.0 ** (gain_db / 20.0)
    adjusted = array("h", (max(-32768, min(32767, round(sample * factor))) for sample in samples))
    if os.sys.byteorder != "little":
        adjusted.byteswap()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(adjusted.tobytes())
    return buffer.getvalue(), rail_samples


def _measure_wav(
    path: Path,
    expected_rate: int,
    expected_cues: int,
    render: dict,
    pacing: Mapping[str, Any],
) -> dict[str, Any]:
    with wave.open(str(path), "rb") as reader:
        channels = reader.getnchannels()
        sample_width = reader.getsampwidth()
        sample_rate = reader.getframerate()
        frames = reader.getnframes()
        if sample_width != 2 or sample_rate != expected_rate or channels != 1:
            raise OCFError(
                f"unexpected WAV format: {sample_rate} Hz, {channels} channel(s), {sample_width * 8}-bit"
            )
        peak = 0
        squares = 0
        samples_seen = 0
        clipped = 0
        first_audible: int | None = None
        last_audible = -1
        cursor = 0
        block_frames = 65536
        while raw := reader.readframes(block_frames):
            samples = array("h")
            samples.frombytes(raw)
            if os.sys.byteorder != "little":
                samples.byteswap()
            for offset, value in enumerate(samples):
                magnitude = abs(value)
                peak = max(peak, magnitude)
                squares += value * value
                samples_seen += 1
                if magnitude >= 32767:
                    clipped += 1
                if magnitude > 64:
                    position = cursor + offset
                    if first_audible is None:
                        first_audible = position
                    last_audible = position
            cursor += len(samples)

    if frames <= 0 or samples_seen <= 0:
        raise OCFError("rendered WAV is empty")
    cues = render.get("cue_stats", [])
    if len(cues) != expected_cues:
        raise OCFError(f"render contains {len(cues)} segments; expected {expected_cues}")
    actual_by_id = {item["id"]: item for item in render.get("event_timing", [])}
    previous_end = -math.inf
    ordered_cues = sorted(cues, key=lambda item: float(item["at"]))
    source_events = {event["id"]: event for event in render.get("source_events", [])}
    for index, cue in enumerate(ordered_cues):
        event_id = cue["id"]
        timing = actual_by_id.get(event_id)
        if timing is None:
            raise OCFError(f"render timing is missing segment {event_id}")
        start = float(timing["at"])
        duration = float(cue["duration"])
        if start < previous_end - 1.0 / sample_rate:
            raise OCFError(f"rendered segments overlap near {event_id}")
        previous_end = start + duration
        if index + 1 < len(ordered_cues):
            source_event = source_events.get(event_id)
            if source_event is None:
                raise OCFError(f"source timeline is missing segment {event_id}")
            expected_next = start + duration + float(source_event["timing"]["pause_after"])
            actual_next = float(actual_by_id[ordered_cues[index + 1]["id"]]["at"])
            # The renderer ledger rounds cue durations to milliseconds for its
            # public manifest; tolerate that serialization precision only.
            if abs(actual_next - expected_next) > max(0.002, 2.0 / sample_rate):
                raise OCFError(f"dynamic timing mismatch after segment {event_id}")
    duration = frames / sample_rate
    expected_duration = (
        max(
            (
                float(actual_by_id[cue["id"]]["at"])
                + float(cue["duration"])
                + float(
                    next(
                        event["timing"]["pause_after"]
                        for event in render["source_events"]
                        if event["id"] == cue["id"]
                    )
                )
                for cue in cues
            ),
            default=0.0,
        )
        + 1.0
    )
    if abs(duration - expected_duration) > max(0.002, 2.0 / sample_rate):
        raise OCFError("audio duration does not match the measured narration timeline")
    if render.get("duration") is not None and abs(float(render["duration"]) - duration) > 0.002:
        raise OCFError("WAV duration differs from renderer timing metadata")
    mean_square = squares / samples_seen
    rms = math.sqrt(mean_square)
    rms_dbfs = 20.0 * math.log10(rms / 32768.0) if rms else float("-inf")
    measurements = {
        "duration_seconds": round(duration, 3),
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width_bits": sample_width * 8,
        "frames": frames,
        "spoken_segment_count": len(cues),
        "measured_segment_duration_seconds": round(sum(float(cue["duration"]) for cue in cues), 3),
        "configured_pause_seconds": round(
            sum(
                float(event.get("timing", {}).get("pause_after", 0))
                for event in render.get("source_events", [])
            ),
            3,
        ),
        "leading_silence_seconds": round(
            (first_audible if first_audible is not None else frames) / sample_rate, 3
        ),
        "trailing_silence_seconds": round(
            (frames - 1 - last_audible if last_audible >= 0 else frames) / sample_rate, 3
        ),
        "peak_int16": peak,
        "rms_dbfs": round(rms_dbfs, 2),
        "clipped_sample_count": clipped,
    }
    if measurements["leading_silence_seconds"] > float(pacing["leading_silence_s"]) + 3.0:
        raise OCFError("render has unexpected extended leading silence")
    if measurements["trailing_silence_seconds"] > float(pacing["ending_silence_s"]) + 3.0:
        raise OCFError("render has unexpected extended trailing silence")
    return measurements


def render_narration_first(
    function_id: str,
    *,
    locale: str | None = None,
    voice: str,
    pacing: str = "normal",
    output: str | Path | None = None,
    dry_run: bool = False,
    sample_rate: int = 44100,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Plan or render a localized narration-bound audition without a fixed timeline."""
    from .voice import render_narration

    catalog = LocaleCatalog()
    plan = plan_narration(function_id, locale=locale, voice=voice, pacing=pacing, catalog=catalog)
    if dry_run:
        return {"dry_run": True, "plan": plan}

    default_dir = (
        AUDIO_RENDERED_DIR
        / "auditions"
        / "-".join(
            (
                function_id,
                safe_component(plan["requested_locale"], max_length=16),
                safe_component(plan["voice_profile"]["id"], max_length=24),
                safe_component(pacing, max_length=16),
            )
        )
        / unique_run_id(function_id)
    )
    output_dir = Path(output or default_dir).expanduser().resolve()
    if output_dir.exists():
        raise OCFError(f"refusing to overwrite existing audition: {output_dir}")
    try:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        stage = workspace_temp_directory(prefix="ocf-narration-stage-")
    except OSError as exc:
        raise OCFError(f"cannot create audition staging directory: {exc}") from exc

    (stage / "render-context.json").write_text(
        json.dumps(
            {
                "function_id": function_id,
                "output_directory": str(output_dir),
                "status": "rendering",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        wav_name = ArtifactNamer().filename(
            function_id,
            plan["title"],
            plan["requested_locale"],
            "wav",
            variant=plan["voice_profile"]["id"],
        )
        transcript_name = ArtifactNamer().filename(
            function_id, plan["title"], plan["requested_locale"], "txt"
        )
        source_doc = _dynamic_document(plan)
        from .validators import validate_timed_transcript

        timed_validation = validate_timed_transcript(source_doc, Path("narration-first-plan"))
        if timed_validation.errors:
            raise OCFError(
                "generated narration plan failed timed-script validation: "
                + " | ".join(issue.message for issue in timed_validation.errors)
            )
        profile, _resolved = _voice_profile(voice, plan["requested_locale"], catalog)
        voice_profile = _adjusted_profile(plan, profile)
        from .voice import render_cue_wav, resolve_backend

        tts_backend = resolve_backend(
            voice_profile, locale=plan["requested_locale"], catalog=catalog
        )
        source_rail_samples = 0

        def render_cue(spoken_text: str) -> bytes:
            nonlocal source_rail_samples
            raw = render_cue_wav(tts_backend, spoken_text)
            adjusted, rail_samples = _apply_tts_headroom(
                raw, float(plan["pacing"]["tts_headroom_db"])
            )
            source_rail_samples += rail_samples
            return adjusted

        output_wav = stage / wav_name
        render = render_narration(
            source_doc,
            output_wav,
            backend=voice_profile,
            sample_rate=sample_rate,
            overwrite=False,
            render_cue=render_cue,
            locale=plan["requested_locale"],
            catalog=catalog,
            strict=True,
        )
        render["source_events"] = source_doc["timeline"]
        measurements = _measure_wav(
            output_wav,
            sample_rate,
            len(plan["segments"]),
            render,
            plan["pacing"],
        )
        measurements["tts_source_rail_sample_count"] = source_rail_samples
        measurements["tts_headroom_gain_db"] = float(plan["pacing"]["tts_headroom_db"])
        expected_spoken = [segment["spoken_text"] for segment in plan["segments"]]
        actual_spoken = [
            cue["text"] for cue in sorted(render["cue_stats"], key=lambda item: float(item["at"]))
        ]
        if actual_spoken != expected_spoken:
            raise OCFError("rendered spoken segments differ from the resolved narration plan")
        if measurements["clipped_sample_count"]:
            raise OCFError(
                f"render contains {measurements['clipped_sample_count']} clipped samples"
            )
        transcript_lines = [
            str(cue.get("text", "")).strip()
            for cue in sorted(render["cue_stats"], key=lambda item: float(item["at"]))
        ]
        transcript = "\n\n".join(line for line in transcript_lines if line) + "\n"
        transcript_path = stage / transcript_name
        transcript_path.write_text(transcript, encoding="utf-8", newline="\n")
        created = created_at or datetime.now(UTC)
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        manifest = {
            "schema_version": "1.0",
            "render_type": "narration-first-audition",
            "function_id": function_id,
            "title": plan["title"],
            "locale": plan["requested_locale"],
            "title_resolution": plan["title_resolution"],
            "voice": {
                **plan["voice_profile"],
                "options": render.get("voice_options", {}),
            },
            "pacing": plan["pacing"],
            "approval_state": plan["approval_state"],
            "narration_resources": plan["narration_resources"],
            "segments": [
                {
                    "id": cue["id"],
                    "source_ids": cue.get("source_ids", [cue["id"]]),
                    "source_resource_key": next(
                        segment["resource_key"]
                        for segment in plan["segments"]
                        if segment["id"] == cue["id"]
                    ),
                    "role": next(
                        segment["role"]
                        for segment in plan["segments"]
                        if segment["id"] == cue["id"]
                    ),
                    "playback": next(
                        segment["playback"]
                        for segment in plan["segments"]
                        if segment["id"] == cue["id"]
                    ),
                    "at_seconds": round(float(cue["at"]), 6),
                    "measured_duration_seconds": cue["duration"],
                    "spoken_text": cue["text"],
                }
                for cue in sorted(render["cue_stats"], key=lambda item: float(item["at"]))
            ],
            "measurements": measurements,
            "artifacts": {
                "wav": {
                    "path": wav_name,
                    "size_bytes": output_wav.stat().st_size,
                    "sha256": sha256_of_file(output_wav),
                },
                "transcript": {
                    "path": transcript_name,
                    "size_bytes": transcript_path.stat().st_size,
                    "sha256": sha256_of_file(transcript_path),
                },
            },
            "created_at": created.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "release_ready": bool(plan["approval_state"]["release_ready"]),
        }
        from .audition_exports import attach_render_artwork

        attach_render_artwork(manifest, stage)
        plan_path = stage / "tts-plan.json"
        manifest_path = stage / "render-manifest.json"
        plan_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        if transcript_path.read_text(encoding="utf-8") != transcript:
            raise OCFError("transcript read-back verification failed")
        for artifact in (output_wav, transcript_path):
            if not artifact.is_file() or artifact.stat().st_size <= 0:
                raise OCFError(f"render artifact is missing or empty: {artifact.name}")
        if sha256_of_file(output_wav) != manifest["artifacts"]["wav"]["sha256"]:
            raise OCFError("WAV checksum changed during render publication")
        (stage / "render-context.json").unlink(missing_ok=True)
        publish_workspace_temp_directory(stage, output_dir)
        return {"dry_run": False, "output_directory": str(output_dir), "manifest": manifest}
    except OSError as exc:
        if stage.exists():
            record_workspace_failure(
                stage.name, f"filesystem failure: {exc}; retained scratch: {stage}"
            )
        raise OCFError(f"narration-first render failed due to a filesystem error: {exc}") from exc
    except BaseException as exc:
        if stage.exists():
            record_workspace_failure(
                stage.name,
                f"render failure: {type(exc).__name__}: {exc}; retained scratch: {stage}",
            )
        raise
