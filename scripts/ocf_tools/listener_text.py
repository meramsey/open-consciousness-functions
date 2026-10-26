"""Listener text from measured synthesis/recording cues, never estimated alignment."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .cue_templates import reject_unexpanded
from .transcript import export_lrc, export_srt, export_vtt, format_timestamp, parse_timestamp
from .utils import OCFError, sha256_of_file, write_text_atomic

_BODY_PASS = re.compile(r"^(focus11-body|sleep20-body)\.pass-([1-9][0-9]*)$")


def _ordered_cues(render: dict) -> list[dict]:
    if not isinstance(render, dict) or not isinstance(render.get("narration_timing", {}), dict):
        raise OCFError("listener text requires a measured narration object")
    cues = render.get("narration_timing", {}).get("cues", [])
    if not isinstance(cues, list) or any(not isinstance(cue, dict) for cue in cues):
        raise OCFError("measured narration cues must be a list of objects")
    try:
        return sorted(cues, key=lambda row: (float(row.get("at", 0)), str(row.get("id", ""))))
    except (TypeError, ValueError, OverflowError) as exc:
        raise OCFError("invalid measured narration onset") from exc


def plain_transcript(render_doc: dict) -> str:
    """Export exactly the final post-transform utterances in canonical order."""
    lines = []
    for cue in _ordered_cues(render_doc):
        if "spoken_text" not in cue:
            raise OCFError(
                f"render cue {cue.get('id', '?')!r} has no final spoken_text; rebuild with current OCF"
            )
        text = str(cue["spoken_text"]).strip()
        reject_unexpanded(text)
        if text:
            lines.append(text)
    return "\n\n".join(lines).rstrip() + "\n"


def measured_document(render: dict, duration: float) -> dict:
    """Use measured units where present, otherwise retain whole utterance timing.

    Unit onsets are absolute session offsets, not offsets inside their parent cue.
    Rounded cue bounds may differ from unit bounds by half a millisecond.
    """
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration <= 0
    ):
        raise OCFError("listener text requires a finite positive media duration")
    cues = _ordered_cues(render)
    if not cues:
        raise OCFError("listener text requires measured narration cues")
    timeline = []
    previous = -1.0
    for cue in cues:
        text = cue.get("spoken_text")
        if not isinstance(text, str):
            raise OCFError("listener text requires final spoken_text on every cue")
        reject_unexpanded(text)
        if not text.strip():
            continue
        try:
            start = float(cue["at"])
            end = start + float(cue["duration"])
            units = cue.get("spoken_units") or []
            if units and " ".join(text.split()) != " ".join(
                " ".join(unit["text"].split()) for unit in units
            ):
                raise OCFError("measured spoken units do not cover the final spoken_text")
            rows = (
                [
                    (float(unit["start_seconds"]), float(unit["end_seconds"]), unit["text"])
                    for unit in units
                ]
                if units
                else [(start, end, text)]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise OCFError("incomplete measured narration timing") from exc
        if not all(math.isfinite(v) for v in (start, end)) or start < 0 or end > duration + 0.001:
            raise OCFError("measured narration cue is outside media bounds")
        for onset, finish, spoken in rows:
            if (
                not all(math.isfinite(v) for v in (onset, finish))
                or onset < 0
                or onset < previous
                or finish <= onset
                or finish > duration + 0.001
                or onset < start - 0.001
                or finish > end + 0.001
                or round(finish * 1000) <= round(onset * 1000)
            ):
                raise OCFError("invalid, unordered or out-of-bounds measured speech interval")
            previous = onset
            source_ids = [str(value) for value in cue.get("source_ids", [])]
            if not source_ids:
                source_ids = [str(cue.get("id", ""))]
            sections = [value.split(".", 1)[0] for value in source_ids if value]
            body_passes = [match for value in source_ids if (match := _BODY_PASS.match(value))]
            pass_types = {
                "programming" if match.group(1) == "focus11-body" else "sleep_reinforcement"
                for match in body_passes
            }
            pass_indexes = {int(match.group(2)) for match in body_passes}
            if len(pass_types) > 1 or len(pass_indexes) > 1:
                raise OCFError("one measured speech unit maps to conflicting body passes")
            row = {
                "id": f"speech-{len(timeline) + 1}",
                "at": format_timestamp(onset),
                "ends_at": format_timestamp(min(finish, duration)),
                "text": " ".join(spoken.split()),
                "granularity": "measured_speech_unit" if units else "utterance",
                "source_event_ids": source_ids,
                "semantic_section": sections[0] if len(set(sections)) == 1 and sections else None,
            }
            if pass_types:
                row["pass_type"] = next(iter(pass_types))
                row["pass_index"] = next(iter(pass_indexes))
            timeline.append(row)
    if not timeline:
        raise OCFError("listener text has no spoken passages")
    return {"timeline": timeline}


def write_listener_text(render: dict, duration: float, audio_path: Path) -> dict:
    """Write UTF-8, same-basename sidecars and an honest timing receipt."""
    doc = measured_document(render, duration)
    text = plain_transcript(render)
    measured = {
        event["id"]: parse_timestamp(event["ends_at"]) - parse_timestamp(event["at"])
        for event in doc["timeline"]
    }
    contents = {
        "txt": text,
        "lrc": export_lrc(doc),
        "srt": export_srt(doc, measured=measured),
        "vtt": export_vtt(doc, measured=measured),
    }
    receipt = {
        "schema_version": "1.0",
        "timing_source": "measured narration ledger",
        "granularity": "measured speech units where available, otherwise utterances; not word alignment",
        "timestamp_precision": "SRT/VTT/SYLT milliseconds; LRC centiseconds (truncated)",
        "media_duration_seconds": duration,
        "spoken_intervals": len(doc["timeline"]),
        "timeline": doc["timeline"],
        "body_pass_coverage": {
            kind: sorted(
                {row["pass_index"] for row in doc["timeline"] if row.get("pass_type") == kind}
            )
            for kind in ("programming", "sleep_reinforcement")
            if any(row.get("pass_type") == kind for row in doc["timeline"])
        },
        "artifacts": {},
    }
    for fmt, content in contents.items():
        path = audio_path.with_suffix("." + fmt)
        write_text_atomic(path, content, overwrite=False)
        receipt["artifacts"][fmt] = {
            "path": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_of_file(path),
        }
    path = audio_path.with_suffix(".timing.json")
    write_text_atomic(
        path, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", overwrite=False
    )
    receipt["timing_receipt"] = {
        "path": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_of_file(path),
    }
    return receipt


def embed_listener_text(audio_path: Path, render: dict, duration: float, locale: str) -> None:
    """Update only native metadata on a staged copy; read it back independently."""
    try:
        from mutagen.flac import FLAC
        from mutagen.id3 import ID3, SYLT, USLT
    except ImportError as exc:
        raise OCFError("embedded lyrics require the optional 'listener' extra (mutagen)") from exc
    doc = measured_document(render, duration)
    plain = audio_path.with_suffix(".txt").read_text(encoding="utf-8")
    lrc = audio_path.with_suffix(".lrc").read_text(encoding="utf-8")
    if audio_path.suffix.lower() == ".mp3":
        # ID3 language is ISO 639-2, not a BCP-47 tag. Unknown languages are 'und'.
        language = {"en": "eng", "es": "spa"}.get(locale.split("-")[0].lower(), "und")
        tags = ID3(audio_path)
        description = "OCF spoken-session transcript"
        synced = [
            (event["text"], round(parse_timestamp(event["at"]) * 1000)) for event in doc["timeline"]
        ]
        tags.add(USLT(encoding=1, lang=language, desc=description, text=plain))
        tags.add(SYLT(encoding=1, lang=language, format=2, type=1, desc=description, text=synced))
        tags.save(audio_path, v2_version=3)
        readback = ID3(audio_path)
        if (
            readback[f"USLT:{description}:{language}"].text != plain
            or readback[f"SYLT:{description}:{language}"].text != synced
            or readback.version[:2] != (2, 3)
        ):
            raise OCFError("ID3 lyric read-back failed")
    elif audio_path.suffix.lower() == ".flac":
        tags = FLAC(audio_path)
        tags["LYRICS"] = lrc
        tags["UNSYNCEDLYRICS"] = plain
        tags.save()
        readback = FLAC(audio_path)
        if readback["LYRICS"] != [lrc] or readback["UNSYNCEDLYRICS"] != [plain]:
            raise OCFError("FLAC lyric read-back failed")
    else:
        raise OCFError("embedded lyrics support only MP3 and FLAC")
