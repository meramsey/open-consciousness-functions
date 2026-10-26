"""Locale-neutral sentence-unit segmentation and semantic narration pacing."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

from .utils import OCFError

SENTENCE_ENDINGS = frozenset(".!?…。！？．｡؟۔।॥։።፧⁈⁉")
_CLOSING_PUNCTUATION = frozenset("\"'’”»)]}）〕〉》」』】〗〙〛")


def _sentence_units(paragraph: str) -> list[str]:
    units = []
    start = 0
    cursor = 0
    while cursor < len(paragraph):
        char = paragraph[cursor]
        if char not in SENTENCE_ENDINGS:
            cursor += 1
            continue
        if char == "." and cursor > 0 and cursor + 1 < len(paragraph):
            if paragraph[cursor - 1].isdigit() and paragraph[cursor + 1].isdigit():
                cursor += 1
                continue
        end = cursor + 1
        while end < len(paragraph) and paragraph[end] in SENTENCE_ENDINGS:
            end += 1
        while end < len(paragraph) and (
            paragraph[end] in _CLOSING_PUNCTUATION
            or unicodedata.category(paragraph[end]) in {"Pe", "Pf"}
        ):
            end += 1
        # CJK and some other scripts conventionally omit inter-sentence
        # spaces after a full-width terminal. The ASCII period keeps its
        # whitespace boundary (plus the decimal guard above) for abbreviations.
        no_space_terminal = char in SENTENCE_ENDINGS - {"."}
        if end == len(paragraph) or paragraph[end].isspace() or no_space_terminal:
            unit = " ".join(paragraph[start:end].split())
            if unit:
                units.append(unit)
            cursor = end
            while cursor < len(paragraph) and paragraph[cursor].isspace():
                cursor += 1
            start = cursor
        else:
            cursor = end
    remainder = " ".join(paragraph[start:].split())
    if remainder:
        units.append(remainder)
    return units


def split_speech_units(text: str) -> list[dict[str, Any]]:
    """Split by Unicode sentence terminals and authored blank-line paragraphs.

    Newline wrapping alone is not treated as a breath/pause boundary. Sentence
    text, terminal punctuation, and order are retained; only surrounding layout
    whitespace is normalized for per-unit TTS requests.
    """
    paragraphs = re.split(r"\n[\t ]*\n+", text.replace("\r\n", "\n").replace("\r", "\n").strip())
    normalized = ["\n".join(part.splitlines()) for part in paragraphs]
    result = []
    for index, paragraph in enumerate(normalized):
        paragraph_units = _sentence_units(paragraph)
        for unit_index, unit in enumerate(paragraph_units):
            result.append(
                {
                    "text": unit,
                    "paragraph_after": index < len(normalized) - 1
                    and unit_index == len(paragraph_units) - 1,
                }
            )
    return result


def event_pacing(
    doc: dict[str, Any], event: dict[str, Any], unit_count: int
) -> dict[str, Any] | None:
    """Resolve the profile and locale-specific semantic unit roles for an event."""
    key = event.get("narration_key")
    policy = doc.get("narration_pacing") or {}
    profile_id = (policy.get("entries") or {}).get(key)
    if (
        profile_id is None
        and event.get("slot_ref") == "function_body"
        and "function-body" in (policy.get("profiles") or {})
    ):
        profile_id = "function-body"
    if profile_id is None:
        return None
    profile = (policy.get("profiles") or {}).get(profile_id)
    if not isinstance(profile, dict):
        raise OCFError(f"narration pacing profile {profile_id!r} for {key!r} is unavailable")
    scale = profile.get("rate_scale")
    if (
        not isinstance(scale, (int, float))
        or isinstance(scale, bool)
        or not math.isfinite(float(scale))
        or not 0.5 <= float(scale) <= 1.0
    ):
        raise OCFError(f"narration pacing profile {profile_id!r} has invalid rate_scale")
    declared = (event.get("timing") or {}).get("narration_pacing_units")
    default_unit = str(profile.get("default_unit", "sentence"))
    if declared is None:
        if profile.get("require_unit_kinds"):
            raise OCFError(
                f"localized narration {key!r} requires locale-specific timing.pacing_units"
            )
        unit_kinds = [default_unit] * unit_count
    else:
        if not isinstance(declared, list) or len(declared) != unit_count:
            raise OCFError(
                f"narration pacing metadata for {key!r} declares "
                f"{len(declared) if isinstance(declared, list) else 'invalid'} unit(s), "
                f"but localized speech segments into {unit_count} sentence unit(s)"
            )
        unit_kinds = [str(kind) for kind in declared]
    pauses = profile.get("pauses") or {}
    if not isinstance(pauses, dict):
        raise OCFError(f"narration pacing profile {profile_id!r} pauses must be a mapping")
    for kind in unit_kinds:
        if kind not in pauses:
            raise OCFError(
                f"narration pacing profile {profile_id!r} has no pause for unit kind {kind!r}"
            )
    ramp_end = float(profile.get("countdown_rate_scale_end", scale))
    if not math.isfinite(ramp_end) or not 0.5 <= ramp_end <= 1.0:
        raise OCFError(
            f"narration pacing profile {profile_id!r} has invalid countdown rate endpoint"
        )
    countdown_indexes = [
        index for index, kind in enumerate(unit_kinds) if kind in {"countdown", "final_countdown"}
    ]
    countdown_ordinal = {index: ordinal for ordinal, index in enumerate(countdown_indexes)}
    unit_rate_scales = []
    for index, kind in enumerate(unit_kinds):
        scale_for_unit = float(scale)
        if index in countdown_ordinal and countdown_indexes:
            progress = countdown_ordinal[index] / max(1, len(countdown_indexes) - 1)
            scale_for_unit += (ramp_end - float(scale)) * progress
        unit_rate_scales.append(scale_for_unit)
    return {
        "profile_id": str(profile_id),
        "rate_scale": float(scale),
        "countdown_rate_scale_end": ramp_end,
        "unit_kinds": unit_kinds,
        "unit_rate_scales": unit_rate_scales,
        "pauses": pauses,
    }


def plan_event_pacing(doc: dict[str, Any], event: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve sentence units, semantic pause roles, and exact event-end pause."""
    text = str(event.get("text") or "")
    units = split_speech_units(text)
    pacing = event_pacing(doc, event, len(units))
    if pacing is None:
        return None
    if not units:
        raise OCFError(f"paced narration event {event.get('id', '?')} has no speech units")
    pauses = pacing["pauses"]
    original_timing = event.get("timing") or {}
    planned_units = []
    for index, (unit, kind) in enumerate(zip(units, pacing["unit_kinds"], strict=True)):
        pause_kind = (
            "paragraph" if unit["paragraph_after"] and kind in {"sentence", "instruction"} else kind
        )
        inside_event = index < len(units) - 1
        if inside_event:
            if pause_kind not in pauses:
                raise OCFError(
                    f"narration pacing profile {pacing['profile_id']!r} lacks pause for {pause_kind!r}"
                )
            pause_after = float(pauses[pause_kind])
        else:
            pause_after = float(original_timing.get("pause_after", 0) or 0)
        if not math.isfinite(pause_after) or pause_after < 0:
            raise OCFError(
                f"narration pacing for event {event.get('id', '?')} has an invalid pause"
            )
        planned_units.append(
            {
                "text": unit["text"],
                "kind": kind,
                "pause_kind": pause_kind,
                "rate_scale": round(pacing["unit_rate_scales"][index], 4),
                "pause_after_s": pause_after,
                "pause_inside_event": inside_event,
            }
        )
    return {**pacing, "units": planned_units}
