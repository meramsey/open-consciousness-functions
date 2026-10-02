"""Explicit event-to-recording source, independent of TTS and English strings."""

from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import wave
from pathlib import Path

from .indexes import load_yaml_file
from .locale import iter_events, normalize_tag
from .utils import OCFError
from .validators import _load_schema, validate_against_schema


def prepare_recordings(reference: str | Path, doc: dict, locale: str) -> tuple[dict, dict]:
    path = Path(reference).expanduser().resolve()
    package = load_yaml_file(path)
    errors = validate_against_schema(package, _load_schema("narration-package.schema.json"))
    if errors:
        raise OCFError("narration package: " + " | ".join(errors))
    if normalize_tag(package["locale"]) != normalize_tag(locale):
        raise OCFError(f"recording package locale {package['locale']} does not match {locale}; select matching recordings")
    expected = {event["id"] for event in iter_events(doc) if event.get("text", "").strip()}
    supplied = set(package["recordings"])
    missing, extra = expected-supplied, supplied-expected
    if missing or extra:
        raise OCFError(f"recordings do not match spoken event IDs; missing={sorted(missing)}, extra={sorted(extra)}")
    prepared = {}
    provenance = {"package_id": package["id"], "package_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "source_type": package["source_type"], "locale": package["locale"], "author": package["author"], "license": package["license"], "redistribution_permission": package["redistribution_permission"], "speech_content_review": "pending; declared text/locale is not speech recognition", "recordings": {}}
    # Validate every original before invoking a decoder or producing output.
    originals = {}
    for identifier, entry in package["recordings"].items():
        source = (path.parent / entry["file"]).resolve()
        if Path(entry["file"]).is_absolute() or not source.is_relative_to(path.parent):
            raise OCFError(f"recording {identifier}: use a relative file inside the package directory")
        if not source.is_file():
            raise OCFError(f"recording {identifier} is unavailable: {entry['file']}")
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise OCFError(f"recording {identifier}: checksum mismatch; preserve/review the original before updating the manifest")
        originals[identifier] = (entry, data)
    for identifier, (entry, data) in originals.items():
        converted = False
        try:
            with wave.open(io.BytesIO(data)) as reader:
                compatible = reader.getsampwidth() == 2 and reader.getnchannels() in (1, 2) and reader.getcomptype() == "NONE"
        except (wave.Error, EOFError):
            compatible = False
        if not compatible:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise OCFError(f"recording {identifier}: install ffmpeg for this format, or supply PCM16 mono/stereo WAV; no TTS fallback")
            result = subprocess.run([ffmpeg, "-v", "error", "-i", "pipe:0", "-f", "wav", "-c:a", "pcm_s16le", "-ac", "1", "pipe:1"], input=data, capture_output=True, timeout=120)
            if result.returncode:
                raise OCFError(f"recording {identifier}: decode failed: {result.stderr.decode(errors='replace')[-1000:]}")
            data = result.stdout
            converted = True
        with wave.open(io.BytesIO(data)) as reader:
            rate = reader.getframerate()
            channels = reader.getnchannels()
            # Streaming WAV output may carry an unknown frame count; measure PCM.
            frames = len(reader.readframes(reader.getnframes()))//(channels*2)
        if not rate or not frames:
            raise OCFError(f"recording {identifier}: empty or invalid decoded audio")
        prepared[identifier] = data
        provenance["recordings"][identifier] = {**entry, "decoded_sample_rate": rate, "decoded_channels": channels, "measured_duration_s": frames/rate, "decoded_to_pcm16": converted, "original_preserved": True}
    return prepared, provenance
