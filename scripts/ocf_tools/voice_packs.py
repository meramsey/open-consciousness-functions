"""Private, reference-based zero-shot voice packs backed by OCF voice profiles."""

from __future__ import annotations

import json
import io
import math
import re
import wave
from array import array
from datetime import datetime, timezone
from pathlib import Path

from . import custom_voices
from .indexes import load_voice_profiles
from .paths import work_path
from .utils import OCFError, sha256_of_file, write_text_atomic, yaml_safe_dump


def create_pack(
    reference: Path,
    *,
    voice_id: str,
    name: str,
    locale: str,
    transcript: str,
    consent_declaration: str,
    source_type: str = "original-recording",
    model_identifier: str = "ResembleAI/chatterbox-nano",
    model_revision: str = "main",
) -> dict:
    """Register a private reference pack; model weights remain an external dependency."""
    if not re.fullmatch(r"OCF-VOICE-[0-9]{4}", voice_id):
        raise OCFError("voice ID must match OCF-VOICE-NNNN")
    if any(profile["id"] == voice_id for profile in load_voice_profiles()):
        raise OCFError(f"voice ID already exists: {voice_id}")
    if source_type not in {"original-recording", "generated-tts", "authorized-other"}:
        raise OCFError("unsupported reference source type")
    if not transcript.strip() or not consent_declaration.strip():
        raise OCFError("an exact reference transcript and explicit consent declaration are required")
    reference = Path(reference).expanduser().resolve()
    if not reference.is_file() or reference.suffix.lower() != ".wav":
        raise OCFError("voice-pack reference must be a prepared local WAV file")
    prepared_digest = sha256_of_file(reference)
    prep_path = reference.with_suffix(".json")
    preparation = json.loads(prep_path.read_text(encoding="utf-8")) if prep_path.is_file() else {}
    if preparation and preparation.get("prepared_sha256") != prepared_digest:
        raise OCFError("prepared reference metadata checksum mismatch")
    source_digest = preparation.get("source_sha256", prepared_digest)
    root = custom_voices.asset_root()
    asset_dir = root / voice_id
    if asset_dir.exists() or asset_dir.is_symlink():
        raise OCFError("private voice-pack asset directory already exists")
    asset_dir.mkdir(parents=True)
    asset = asset_dir / "reference.wav"
    try:
        asset.write_bytes(reference.read_bytes())
        consent = asset_dir / "consent.txt"
        consent.write_text(consent_declaration.strip() + "\n", encoding="utf-8")
        digest = sha256_of_file(asset)
        profile = {
            "schema_version": "1.0",
            "id": voice_id,
            "slug": voice_id.lower(),
            "name": name,
            "version": "1.0.0",
            "backend": "chatterbox-nano",
            "customization_method": "reference-audio",
            "voice_kind": "cloned",
            "locale": locale,
            "language": locale.split("-")[0],
            "privacy": "private",
            "distribution_permission": "private-only",
            "consent_status": "self-recorded" if source_type == "original-recording" else "authorized-contributor",
            "consent_record": f"{voice_id}/consent.txt",
            "license": "Model weights are external; verify the selected model revision license before use or redistribution.",
            "reference_audio": {
                "asset": f"{voice_id}/reference.wav",
                "sha256": digest,
                "reference_text": transcript.strip(),
                "locale": locale,
                "speaker": voice_id,
                "consent_status": "self-recorded" if source_type == "original-recording" else "authorized-contributor",
                "consent_record": f"{voice_id}/consent.txt",
                "source_type": source_type,
                "transcript_status": "confirmed",
                "model_identifier": model_identifier,
                "model_revision": model_revision,
                "source_sha256": source_digest,
            },
            "creation_provenance": {
                "created_by": "OCF local voice-pack CLI",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "pack_type": "reference-based-zero-shot",
                "source_sha256": source_digest,
            },
        }
        custom_voices.validate_profile(profile)
        destination = work_path("cache", "voices", "profiles", voice_id + ".yaml")
        write_text_atomic(destination, yaml_safe_dump(profile), overwrite=False)
    except Exception:
        # Preserve diagnostics but remove the incomplete registration; audio stays private.
        raise
    return {
        "profile": profile,
        "path": str(destination),
        "reference_sha256": digest,
        "inference_verified": False,
        "note": "Reference pack registered; zero-shot model inference is not yet verified.",
    }


def inspect_pack(query: str) -> dict:
    matches = [p for p in load_voice_profiles() if p["id"] == query or p.get("slug") == query]
    if len(matches) != 1:
        raise OCFError("select one unambiguous private OCF voice ID or slug")
    profile = matches[0]
    return {
        "profile": profile,
        "validation": custom_voices.validate_profile(profile),
        "pack_type": (profile.get("creation_provenance") or {}).get("pack_type", "legacy-profile"),
    }


def prepare_reference(
    source: Path, *, start_s: float | None = None, duration_s: float | None = None
) -> dict:
    """Decode privately to mono 24 kHz PCM16 and retain one explicit or energetic clip."""
    from .recording_audio import inspect_recording, process_recording

    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise OCFError(f"reference audio does not exist: {source}")
    if source.suffix.lower() not in {".wav", ".flac", ".mp3"}:
        raise OCFError("reference input must be WAV, FLAC or MP3")
    if (start_s is None) != (duration_s is None):
        raise OCFError("specify both start and duration for a manual clip")
    if start_s is not None and (
        not math.isfinite(start_s)
        or not math.isfinite(duration_s)
        or start_s < 0
        or duration_s <= 0
    ):
        raise OCFError("clip start must be nonnegative and duration must be positive")
    inspection = inspect_recording(source)
    converted, report = process_recording(source, sample_rate=24000, channels=1)
    with wave.open(io.BytesIO(converted), "rb") as reader:
        frames, rate = reader.getnframes(), reader.getframerate()
        pcm = array("h")
        pcm.frombytes(reader.readframes(frames))
    if start_s is not None:
        first, last = round(start_s * rate), round((start_s + duration_s) * rate)
        if last > frames:
            raise OCFError("requested reference clip extends beyond recording duration")
    else:
        # Select the longest energetic region; this is a speech candidate, not speech recognition.
        window = max(1, round(rate * 0.05))
        active = [
            math.sqrt(sum((v / 32768) ** 2 for v in pcm[i : i + window]) / len(pcm[i : i + window]))
            > 0.01
            for i in range(0, frames, window)
        ]
        active_windows = [index for index, value in enumerate(active) if value]
        runs = []
        if active_windows:
            begin = previous = active_windows[0]
            for index in active_windows[1:]:
                if index - previous > 11:  # retain pauses up to 500 ms in a sentence candidate
                    runs.append((begin * window, min((previous + 1) * window, frames)))
                    begin = index
                previous = index
            runs.append((begin * window, min((previous + 1) * window, frames)))
        if not runs:
            raise OCFError("no energetic reference region detected; provide explicit clip bounds")
        first, last = max(runs, key=lambda item: item[1] - item[0])
    selected = pcm[first:last]
    if len(selected) < rate:
        raise OCFError("reference clip must be at least one second")
    peak = max((abs(value) for value in selected), default=0) / 32768
    out = work_path("cache", "voices", "prepared")
    out.mkdir(parents=True, exist_ok=True)
    digest = sha256_of_file(source)
    destination = out / f"{digest[:16]}-{first}-{last}.wav"
    if not destination.exists():
        with wave.open(str(destination), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(rate)
            writer.writeframes(selected.tobytes())
    metadata = {
        "schema_version": "1.0",
        "source_sha256": digest,
        "prepared_sha256": sha256_of_file(destination),
        "source": inspection,
        "processing": report,
        "clip": {"start_s": first / rate, "duration_s": len(selected) / rate},
        "format": {"sample_rate": rate, "channels": 1, "sample_format": "pcm_s16le"},
        "sample_peak": peak,
        "clipping_sample_count": sum(abs(value) >= 32767 for value in selected),
        "automatic_selection": start_s is None,
        "transcript_status": "not-provided",
    }
    write_text_atomic(destination.with_suffix(".json"), json.dumps(metadata, indent=2) + "\n")
    return {"path": str(destination), "metadata": metadata}
