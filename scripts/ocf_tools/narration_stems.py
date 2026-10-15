"""Whole-session recordings with explicit, speech-bound semantic marker ledgers.

Callers supply a composed, locale-resolved document. No markers, boundaries,
speech durations or content are inferred from audio, filenames or text. Planning
prepares/measures at the original rate/channel count; rendering prepares at the
requested output format. Both return the render_narration metadata contract.
Original audio and interior cadence are preserved; there is no inserted tail,
pause, trimming, speed/pitch adjustment or implicit processing profile.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import wave
from copy import deepcopy
from pathlib import Path

from .locale import document_locale, iter_events, normalize_tag
from .recording_audio import inspect_recording, process_recording
from .recordings import session_fingerprint
from .semantics import bind_document_cues
from .timing import schedule_timeline
from .utils import OCFError, OCFFileExistsError, sha256_of_file
from .validators import _load_schema, validate_against_schema

CONTENT_VERIFICATION = "pending; text fingerprints bind declarations, not speech recognition or listening/release approval"


def _source_path(root, name):
    # Deferred to let SourceResolver import this adapter without an import cycle.
    from .narration_sources import _safe_source

    return _safe_source(Path(root).resolve(), name)


def _text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate(doc, spec, root, locale):
    try:
        json.dumps(spec, allow_nan=False)
        json.dumps(doc, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise OCFError("narration stem requires finite JSON-compatible values") from exc
    errors = validate_against_schema(spec, _load_schema("narration-stem.schema.json"))
    if errors:
        raise OCFError("narration stem: " + " | ".join(errors))
    target = normalize_tag(locale)
    if not target or normalize_tag(spec["locale"]) != target or document_locale(doc) != target:
        raise OCFError("narration stem locale does not match resolved session locale")
    if spec.get("session_fingerprint") and spec["session_fingerprint"] != session_fingerprint(doc):
        raise OCFError(
            "narration stem belongs to a different session/version (session fingerprint)"
        )
    events = list(iter_events(doc))
    identifiers = [event.get("id") for event in events]
    if any(not isinstance(key, str) or not key for key in identifiers) or len(identifiers) != len(
        set(identifiers)
    ):
        raise OCFError("narration stem requires unique composed event IDs")
    missing = set(identifiers) - spec["markers"].keys()
    extra = spec["markers"].keys() - set(identifiers)
    if missing or extra:
        raise OCFError(
            f"narration stem markers must cover all composed event IDs; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    for event in events:
        identifier = event["id"]
        marker = spec["markers"][identifier]
        text = event.get("text", "")
        if not isinstance(text, str) or (event.get("narration_key") and not text.strip()):
            raise OCFError(f"stem event {identifier}: requires resolved narration text")
        if event.get("locale") and normalize_tag(event["locale"]) != target:
            raise OCFError(f"stem event {identifier}: locale mismatch")
        spoken = bool(text.strip())
        if spoken and marker.get("text_sha256") != _text_sha(text):
            raise OCFError(f"stem event {identifier}: missing or stale exact text_sha256")
        if not spoken and marker["speech_duration"] != 0:
            raise OCFError(f"stem event {identifier}: nonspoken marker requires speech_duration=0")
        if spoken and marker["speech_duration"] <= 0:
            raise OCFError(
                f"stem event {identifier}: spoken marker requires positive speech_duration"
            )
        if "text_sha256" in marker and marker["text_sha256"] != _text_sha(text):
            raise OCFError(f"stem event {identifier}: stale exact text_sha256")
    source = _source_path(root, spec["file"])
    if sha256_of_file(source) != spec["sha256"]:
        raise OCFError("narration stem checksum mismatch; no TTS fallback")
    return source, events, target


def _ledger(doc, spec, events, sample_rate):
    tolerance = min(0.02, 1 / sample_rate)
    scheduled = schedule_timeline(
        doc, {key: marker["speech_duration"] for key, marker in spec["markers"].items()}
    )
    by_id = {event["id"]: event for event in events}
    ledger = []
    for row in scheduled:
        identifier = row["id"]
        marker = spec["markers"][identifier]
        if abs(marker["at"] - row["at"]) > tolerance + 1e-6:
            raise OCFError(
                f"stem event {identifier}: marker at does not reproduce scheduled anchor within one frame (<=20ms)"
            )
        event = by_id[identifier]
        pause = float((event.get("timing") or {}).get("pause_after", 0))
        structural_end = (
            marker["at"]
            + max(marker["speech_duration"], float((event.get("dsp") or {}).get("transition_s", 0)))
            + pause
        )
        if "end" in marker and (
            abs(marker["end"] - row["end"]) > tolerance + 1e-6
            or abs(marker["end"] - structural_end) > tolerance + 1e-6
        ):
            raise OCFError(
                f"stem event {identifier}: marker end does not match structural event end"
            )
        ledger.append(
            {
                **row,
                "at": marker["at"],
                "end": structural_end,
                "utterance_id": identifier,
                "utterance_ids": [identifier],
            }
        )
    ledger.sort(key=lambda row: row["at"])
    available = 0.0
    for row in ledger:
        if row["speech_duration"]:
            if row["at"] < available - 1e-6:
                raise OCFError(f"stem event {row['id']}: manual speech/pause overlap")
            available = (
                row["at"]
                + row["speech_duration"]
                + float((by_id[row["id"]].get("timing") or {}).get("pause_after", 0))
            )
    return ledger, tolerance


def _check_audio(data, receipt, spec, ledger, sample_rate, channels):
    """Check actual frame bytes, receipt and marker extent before publication."""
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            frames = reader.getnframes()
            if (
                reader.getsampwidth() != 2
                or reader.getframerate() != sample_rate
                or reader.getnchannels() != channels
                or frames <= 0
                or len(reader.readframes(frames)) != frames * channels * 2
            ):
                raise OCFError(
                    "narration stem processed PCM frame/format mismatch or truncated audio"
                )
    except (wave.Error, EOFError) as exc:
        raise OCFError("narration stem processed audio is not PCM WAV") from exc
    original, processed = receipt["original"], receipt["processed"]
    duration = frames / sample_rate
    if (
        processed["frames"] != frames
        or processed["sample_rate"] != sample_rate
        or processed["channels"] != channels
        or abs(processed["duration_s"] - duration) > 1e-9
        or receipt["input_sha256"] != spec["sha256"]
        or receipt["processed_sha256"] != hashlib.sha256(data).hexdigest()
        or not receipt["original_preserved"]
    ):
        raise OCFError("narration stem measurement/checksum receipt frame mismatch")
    if (
        any(receipt["trimmed"].values())
        or abs(frames - original["frames"] * sample_rate / original["sample_rate"]) > 1 + 1e-6
    ):
        raise OCFError("narration stem processing changed timeline frames; trimming is forbidden")
    for row in ledger:
        # Extents are strict in both domains: never hide truncated audio using
        # the scheduler's one-frame alignment tolerance.
        if (
            max(
                row["at"],
                row["at"] + row["speech_duration"],
                row["end"],
                spec["markers"][row["id"]].get("end", row["end"]),
            )
            > min(duration, original["duration_s"]) + 1e-6
        ):
            raise OCFError(f"stem event {row['id']}: marker beyond audio or truncated audio")
    return duration


def _prepare(doc, spec, root, *, locale, sample_rate=None, channels=None):
    source, events, target = _validate(doc, spec, root, locale)
    if sample_rate is None:
        # Native-rate planning avoids requiring a resampler for a PCM fixture.
        measured = inspect_recording(source)
        sample_rate = measured["original"]["sample_rate"]
        channels = measured["original"]["channels"]
    if type(sample_rate) is not int or not 8000 <= sample_rate <= 192000:
        raise OCFError("sample_rate must be an integer in 8000..192000")
    if type(channels) is not int or channels not in (1, 2):
        raise OCFError("channels must be 1 or 2")
    ledger, tolerance = _ledger(doc, spec, events, sample_rate)
    data, receipt = process_recording(
        source,
        sample_rate=sample_rate,
        channels=channels,
        processing=deepcopy(spec.get("processing") or {}),
        expected_sha256=spec["sha256"],
    )
    duration = _check_audio(data, receipt, spec, ledger, sample_rate, channels)
    actual = {row["id"]: row for row in ledger}
    auditory_cues = bind_document_cues(doc)
    seen = set()
    by_id = {event["id"]: event for event in events}
    for binding in auditory_cues:
        binding["at"] = actual[binding["event_id"]]["at"]
        signature = (binding["identity"], binding["at"])
        if signature in seen and not by_id[binding["event_id"]].get("intentional_repeat"):
            raise OCFError(f"duplicate auditory cue at resolved anchor: {binding['identity']}")
        seen.add(signature)
    sources, cues = [], []
    for event in events:
        identifier = event["id"]
        marker = deepcopy(spec["markers"][identifier])
        row = {
            "event_id": identifier,
            "source": "recorded-stem",
            "file": spec["file"],
            "sha256": spec["sha256"],
            "checksum_sha256": spec["sha256"],
            "processed_sha256": receipt["processed_sha256"],
            "speaker": spec["speaker"],
            "version": spec["version"],
            "locale": target,
            "narration_key": event.get("narration_key"),
            "function_id": doc.get("function_id"),
            "role": event.get("semantic"),
            "text_sha256": marker.get("text_sha256"),
            "marker": marker,
            "rights": deepcopy(spec.get("rights") or {}),
            "approval": spec.get("approval", "pending"),
            "content_verification": CONTENT_VERIFICATION,
            "speech_content_review": "pending",
            "text_compatibility": "fingerprint-match-not-transcript-verification",
            "intentional_nonspoken_event": not bool(event.get("text", "").strip()),
            "original_preserved": True,
            "internal_cadence": "preserved-no-inserted-semantic-pauses",
        }
        sources.append(row)
        if not row["intentional_nonspoken_event"]:
            cues.append(
                {
                    "id": identifier,
                    "source_ids": [identifier],
                    "at": actual[identifier]["at"],
                    "cues": 1,
                    "text": event["text"],
                    "display_text": event["text"],
                    "samples": round(marker["speech_duration"] * sample_rate),
                    "duration": marker["speech_duration"],
                    "speech_duration": marker["speech_duration"],
                    "pacing": None,
                    "spoken_units": [],
                    "cut_previous": False,
                    "narration_source": deepcopy(row),
                }
            )
    provenance = {
        "source_type": "recorded-stem",
        "mode": "recording",
        "file": spec["file"],
        "sha256": spec["sha256"],
        "speaker": spec["speaker"],
        "speakers": [spec["speaker"]],
        "version": spec["version"],
        "locale": target,
        "session_fingerprint": session_fingerprint(doc),
        "declared_session_fingerprint": spec.get("session_fingerprint"),
        "rights": deepcopy(spec.get("rights") or {}),
        "approval": spec.get("approval", "pending"),
        "content_verification": CONTENT_VERIFICATION,
        "speech_content_review": "pending",
        "original_preserved": True,
        "original": deepcopy(receipt["original"]),
        "processed": deepcopy(receipt["processed"]),
        "preparation": deepcopy(receipt),
        "markers": deepcopy(spec["markers"]),
        "marker_tolerance_s": tolerance,
        "events": sources,
    }
    metadata = {
        "backend": "prerecorded-stem",
        "profile_id": None,
        "locale": target,
        "voice": target,
        "voice_options": {},
        "locale_notes": [],
        "pronunciation_hints": 0,
        "narration_source": provenance,
        "sample_rate": sample_rate,
        "channels": channels,
        "duration": duration,
        "cues": len(cues),
        "utterances": len(cues),
        "cue_stats": cues,
        "narration_pacing": {
            "policy_id": (doc.get("pacing_profile") or {}).get("id"),
            "profiles": {},
            "internal_cadence": "preserved-no-inserted-semantic-pauses",
        },
        "event_timing": ledger,
        "auditory_cues": auditory_cues,
        "narration_resolution": deepcopy(doc.get("narration")),
        "overlap_mode": "reject-fixed-overlap",
        "timing_mode": "explicit-stem-markers",
        "even_counts": None,
    }
    return data, metadata, source


def plan_stem(doc, spec, root: Path, *, locale) -> dict:
    """Validate/measure a complete stem at its native rate/channels; publish nothing.

    Recording preparation may populate the verified recording cache and require
    optional FFmpeg for compressed audio or explicitly selected filters.
    """
    return _prepare(doc, spec, root, locale=locale)[1]


def _publish(path, data, *, overwrite):
    """Publish complete bytes atomically, with a race-safe no-clobber path.

    Output-side staging (as in utils.write_text_atomic's cross-filesystem
    fallback) keeps replace/link on the same filesystem. It is always removed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise OCFFileExistsError(f"Refusing to overwrite existing file: {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def render_stem(
    doc, spec, root: Path, out_path, *, locale, sample_rate=44100, channels=1, overwrite=True
) -> dict:
    """Publish the prepared whole PCM16 stem with render_narration metadata.

    Stereo output preserves L/R ordering; no reassembly, added silence, gain or
    fades occur beyond explicitly declared recording processing. Existing source
    files (including symlink/hardlink aliases) can never be output destinations.
    """
    source, _events, _target = _validate(doc, spec, root, locale)
    target = Path(out_path)
    if target.resolve() == source or (target.exists() and target.samefile(source)):
        raise OCFError("narration stem output must not overwrite the original source")
    if not overwrite and target.exists():
        raise OCFFileExistsError(f"Refusing to overwrite existing file: {target}")
    data, metadata, _source = _prepare(
        doc, spec, root, locale=locale, sample_rate=sample_rate, channels=channels
    )
    _publish(target, data, overwrite=overwrite)
    return metadata
