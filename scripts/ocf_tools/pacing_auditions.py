"""Measured timing reports and profile-declared excerpts from a rendered session."""

from __future__ import annotations

import json
import math
import wave
from pathlib import Path
from typing import Any

from .artifact_names import ArtifactNamer, safe_component
from .utils import OCFError, sha256_of_file


def _cue_timing_rows(cues: list[dict[str, Any]], document: dict[str, Any]) -> list[dict[str, Any]]:
    event_by_id = {
        event["id"]: event
        for section in document.get("sections", [])
        for event in section.get("timeline", [])
    }
    rows = []
    for cue in cues:
        event_ids = list(cue.get("source_ids", [cue["id"]]))
        rows.append(
            {
                "event_ids": event_ids,
                "narration_keys": list(
                    dict.fromkeys(
                        event_by_id[event_id]["narration_key"]
                        for event_id in event_ids
                        if event_id in event_by_id and event_by_id[event_id].get("narration_key")
                    )
                ),
                "spoken_text": cue.get("spoken_text", cue.get("display_text", "")),
                "start_seconds": round(float(cue["at"]), 6),
                "end_seconds": round(float(cue["at"]) + float(cue["duration"]), 6),
                "audio_duration_seconds": float(cue["duration"]),
                "speech_duration_seconds": float(cue.get("speech_duration", cue["duration"])),
                "pacing": cue.get("pacing"),
                "spoken_units": cue.get("spoken_units", []),
            }
        )
    return rows


def _extract_window(
    source: Path,
    destination: Path,
    *,
    start_seconds: float,
    end_seconds: float,
    sample_rate: int,
) -> float:
    with wave.open(str(source), "rb") as reader:
        channels = reader.getnchannels()
        width = reader.getsampwidth()
        if reader.getframerate() != sample_rate or channels != 2 or width != 2:
            raise OCFError("pacing auditions require stereo 16-bit PCM session audio")
        start_frame = max(0, int(math.floor(start_seconds * sample_rate)))
        end_frame = min(reader.getnframes(), int(math.ceil(end_seconds * sample_rate)))
        if start_frame >= end_frame:
            raise OCFError(f"pacing audition resolves to an empty window: {destination.name}")
        reader.setpos(start_frame)
        with wave.open(str(destination), "wb") as writer:
            writer.setnchannels(2)
            writer.setsampwidth(2)
            writer.setframerate(sample_rate)
            remaining = end_frame - start_frame
            while remaining:
                count = min(65536, remaining)
                data = reader.readframes(count)
                if not data:
                    raise OCFError(f"session audio ended during pacing audition {destination.name}")
                writer.writeframesraw(data)
                remaining -= len(data) // (channels * width)
            writer.writeframes(b"")
        return (end_frame - start_frame) / sample_rate


def write_timing_reports_and_auditions(
    *,
    stage: Path,
    master_path: Path,
    function_id: str,
    title: str,
    locale: str,
    voice: dict[str, Any],
    session_pacing: dict[str, Any],
    pacing_profile: dict[str, Any],
    document: dict[str, Any],
    render: dict[str, Any],
    session_duration: float,
    sample_rate: int,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    """Write an overall measured timing report and configured local excerpt auditions."""
    cues = sorted(
        render.get("narration_timing", {}).get("cues", []),
        key=lambda cue: (float(cue.get("at", 0)), str(cue.get("id", ""))),
    )
    rows = _cue_timing_rows(cues, document)
    timing_report = {
        "schema_version": "1.0",
        "function_id": function_id,
        "locale": locale,
        "voice_profile": voice,
        "backend": (render.get("voice") or {}).get("backend"),
        "speaking_rate_configuration": session_pacing,
        "narration_pacing_policy": pacing_profile.get("narration_pacing", {}),
        "total_narration_audio_seconds": float(render["narration_timing"]["duration_seconds"]),
        "total_session_seconds": session_duration,
        "sample_rate": sample_rate,
        "segments": rows,
    }
    timing_path = stage / "session-timing-report.json"
    timing_path.write_text(
        json.dumps(timing_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    timing_artifact = {
        "path": timing_path.name,
        "format": "application/json",
        "size_bytes": timing_path.stat().st_size,
        "sha256": sha256_of_file(timing_path),
    }

    configured = pacing_profile.get("pacing_auditions", {})
    if not configured:
        return timing_artifact, {}, timing_report
    section_by_id = {section["id"]: section for section in document.get("sections", [])}
    event_timing = {row["id"]: row for row in render.get("event_timing", [])}
    audition_root = stage / "pacing-auditions"
    audition_root.mkdir()
    auditions: dict[str, dict[str, Any]] = {}
    for audition_id, selection in configured.items():
        if "stage_id" in selection:
            section = section_by_id.get(selection["stage_id"])
            if section is None:
                raise OCFError(f"pacing audition {audition_id!r} selects an unknown stage")
            event_ids = [event["id"] for event in section.get("timeline", [])]
        else:
            event_ids = [str(selection["event_id"])]
        missing = set(event_ids) - event_timing.keys()
        if missing:
            raise OCFError(
                f"pacing audition {audition_id!r} has unmeasured event(s): "
                + ", ".join(sorted(missing))
            )
        start = min(float(event_timing[event_id]["at"]) for event_id in event_ids)
        end = max(float(event_timing[event_id]["end"]) for event_id in event_ids)
        safe_id = safe_component(str(selection.get("file_name") or audition_id), max_length=24)
        wav_name = ArtifactNamer().filename(
            function_id,
            title,
            locale,
            "wav",
            variant=f"pacing-{safe_id}",
        )
        wav_path = audition_root / wav_name
        actual_duration = _extract_window(
            master_path,
            wav_path,
            start_seconds=start,
            end_seconds=end,
            sample_rate=sample_rate,
        )
        selected_rows = [
            {
                **row,
                "excerpt_start_seconds": round(row["start_seconds"] - start, 6),
                "excerpt_end_seconds": round(row["end_seconds"] - start, 6),
            }
            for row in rows
            if set(row["event_ids"]) & set(event_ids)
        ]
        audition_timing = {
            "schema_version": "1.0",
            "audition_id": audition_id,
            "label": selection["label"],
            "source_master": master_path.name,
            "session_start_seconds": round(start, 6),
            "session_end_seconds": round(end, 6),
            "total_duration_seconds": round(actual_duration, 6),
            "sample_rate": sample_rate,
            "channels": 2,
            "voice_profile": voice,
            "backend": timing_report["backend"],
            "speaking_rate_configuration": session_pacing,
            "narration_pacing_policy": pacing_profile.get("narration_pacing", {}),
            "segments": selected_rows,
        }
        report_path = wav_path.with_suffix(".timing.json")
        report_path.write_text(
            json.dumps(audition_timing, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        auditions[audition_id] = {
            "label": selection["label"],
            "duration_seconds": round(actual_duration, 6),
            "wav": {
                "path": wav_path.relative_to(stage).as_posix(),
                "format": "wav",
                "size_bytes": wav_path.stat().st_size,
                "sha256": sha256_of_file(wav_path),
            },
            "timing_report": {
                "path": report_path.relative_to(stage).as_posix(),
                "format": "application/json",
                "size_bytes": report_path.stat().st_size,
                "sha256": sha256_of_file(report_path),
            },
        }
    return timing_artifact, auditions, timing_report
