"""Explicit event-to-recording source, independent of TTS and English strings."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import wave
from copy import deepcopy
from pathlib import Path

from .indexes import load_yaml_file
from .locale import iter_events, normalize_tag
from .utils import OCFError
from .validators import _load_schema, validate_against_schema


def session_fingerprint(doc: dict) -> str:
    canonical = deepcopy(doc)
    canonical.pop("narration", None)
    for event in iter_events(canonical):
        if event.get("narration_key"):
            event.pop("text", None)
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def unique_mapping(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OCFError(f"duplicate recording event mapping: {key}")
        result[key] = value
    return result


def prepare_recordings(reference: str | Path, doc: dict, locale: str) -> tuple[dict, dict]:
    path = Path(reference).expanduser().resolve()
    package = load_yaml_file(path)
    errors = validate_against_schema(package, _load_schema("narration-package.schema.json"))
    if errors:
        raise OCFError("narration package: " + " | ".join(errors))
    if normalize_tag(package["locale"]) != normalize_tag(locale):
        raise OCFError(
            f"recording package locale {package['locale']} does not match {locale}; select matching recordings"
        )
    if package.get("session_fingerprint") and package["session_fingerprint"] != session_fingerprint(
        doc
    ):
        raise OCFError(
            "recording package belongs to a different session/version; re-map and review the recordings"
        )
    by_id = {event["id"]: event for event in iter_events(doc)}
    for identifier, entry in package["recordings"].items():
        if (
            entry.get("text_sha256")
            and identifier in by_id
            and entry["text_sha256"]
            != hashlib.sha256(by_id[identifier].get("text", "").encode()).hexdigest()
        ):
            raise OCFError(
                f"recording {identifier}: canonical narration text changed; review this recording"
            )
    expected = {event["id"] for event in iter_events(doc) if event.get("text", "").strip()}
    supplied = set(package["recordings"])
    missing, extra = expected - supplied, supplied - expected
    if missing or extra:
        raise OCFError(
            f"recordings do not match spoken event IDs; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    prepared = {}
    provenance = {
        "package_id": package["id"],
        "package_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_type": package["source_type"],
        "locale": package["locale"],
        "author": package["author"],
        "license": package["license"],
        "redistribution_permission": package["redistribution_permission"],
        "speech_content_review": "pending; declared text/locale is not speech recognition",
        "recordings": {},
    }
    # Validate every original before invoking a decoder or producing output.
    originals = {}
    for identifier, entry in package["recordings"].items():
        source = (path.parent / entry["file"]).resolve()
        if Path(entry["file"]).is_absolute() or not source.is_relative_to(path.parent):
            raise OCFError(
                f"recording {identifier}: use a relative file inside the package directory"
            )
        if not source.is_file():
            raise OCFError(f"recording {identifier} is unavailable: {entry['file']}")
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise OCFError(
                f"recording {identifier}: checksum mismatch; preserve/review the original before updating the manifest"
            )
        originals[identifier] = (entry, data)
    for identifier, (entry, data) in originals.items():
        converted = False
        try:
            with wave.open(io.BytesIO(data)) as reader:
                compatible = (
                    reader.getsampwidth() == 2
                    and reader.getnchannels() in (1, 2)
                    and reader.getcomptype() == "NONE"
                )
        except (wave.Error, EOFError):
            compatible = False
        if not compatible:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise OCFError(
                    f"recording {identifier}: install ffmpeg for this format, or supply PCM16 mono/stereo WAV; no TTS fallback"
                )
            result = subprocess.run(
                [
                    ffmpeg,
                    "-v",
                    "error",
                    "-i",
                    "pipe:0",
                    "-f",
                    "wav",
                    "-c:a",
                    "pcm_s16le",
                    "-ac",
                    "1",
                    "pipe:1",
                ],
                input=data,
                capture_output=True,
                timeout=120,
            )
            if result.returncode:
                raise OCFError(
                    f"recording {identifier}: decode failed: {result.stderr.decode(errors='replace')[-1000:]}"
                )
            data = result.stdout
            converted = True
        with wave.open(io.BytesIO(data)) as reader:
            rate = reader.getframerate()
            channels = reader.getnchannels()
            # Streaming WAV output may carry an unknown frame count; measure PCM.
            frames = len(reader.readframes(reader.getnframes())) // (channels * 2)
        if not rate or not frames:
            raise OCFError(f"recording {identifier}: empty or invalid decoded audio")
        prepared[identifier] = data
        provenance["recordings"][identifier] = {
            **entry,
            "decoded_sample_rate": rate,
            "decoded_channels": channels,
            "measured_duration_s": frames / rate,
            "decoded_to_pcm16": converted,
            "original_preserved": True,
        }
    return prepared, provenance


def import_directory(
    doc: dict,
    directory: Path,
    mapping: dict,
    output: Path,
    *,
    locale: str,
    author: str,
    license: str,
    speaker: str | None = None,
) -> dict:
    """Explicit occurrence mapping; filenames never imply semantic operations."""
    from .locale import resolve_document
    from .utils import sha256_of_file, write_text_atomic, yaml_safe_dump

    doc = resolve_document(doc, locale, strict=True)
    events = {event["id"]: event for event in iter_events(doc) if event.get("text", "").strip()}
    if not isinstance(mapping, dict) or any(not isinstance(name, str) for name in mapping.values()):
        raise OCFError("recording mapping must be an object of event ID to relative filename")
    if set(mapping) != set(events):
        raise OCFError(
            f"recording mapping: missing={sorted(set(events) - set(mapping))}, unknown={sorted(set(mapping) - set(events))}"
        )
    directory, output = directory.resolve(), output.resolve()
    if not directory.is_relative_to(output.parent):
        raise OCFError(
            "package output must be in the recordings directory or its parent; do not create escaping file references"
        )
    if output.exists():
        raise OCFError("refusing to overwrite existing narration package; choose another output")
    entries = {}
    selected = set()
    for identifier, name in mapping.items():
        source = (directory / name).resolve()
        if not source.is_relative_to(directory) or not source.is_file():
            raise OCFError(f"recording {identifier}: missing or escaping file {name}")
        selected.add(source)
        entries[identifier] = {
            "file": source.relative_to(output.parent).as_posix(),
            "sha256": sha256_of_file(source),
            "text_sha256": hashlib.sha256(events[identifier]["text"].encode()).hexdigest(),
            "narration_key": events[identifier].get("narration_key"),
            "original_filename": source.name,
            "speaker": speaker,
            "validation_status": "pending-content-review",
        }
    unknown = [
        path.name
        for path in directory.rglob("*")
        if path.is_file()
        and path.suffix.lower()
        in (".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus", ".aif", ".aiff")
        and path.resolve() not in selected
    ]
    if unknown:
        raise OCFError("unmapped audio recordings: " + ", ".join(sorted(unknown)))
    package = {
        "schema_version": "1.0",
        "id": f"recordings-{doc.get('id', 'session')}",
        "source_type": "prerecorded-user",
        "locale": locale,
        "author": author,
        "license": license,
        "redistribution_permission": False,
        "session_id": doc.get("id"),
        "session_fingerprint": session_fingerprint(doc),
        "recordings": entries,
    }
    # Validate/decode through the same engine preflight using a temporary package;
    # only derived metadata is written, originals remain untouched.
    import tempfile

    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".yaml", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        temporary.write_text(yaml_safe_dump(package), encoding="utf-8")
        _, provenance = prepare_recordings(temporary, doc, locale)
    finally:
        temporary.unlink()
    for identifier, info in provenance["recordings"].items():
        entries[identifier].update(
            measured_duration_s=info["measured_duration_s"],
            sample_rate=info["decoded_sample_rate"],
            channels=info["decoded_channels"],
            codec="PCM16 WAV"
            if not info["decoded_to_pcm16"]
            else "ffmpeg-decoded PCM16; original codec not probed",
        )
    write_text_atomic(output, yaml_safe_dump(package), overwrite=False)
    return package
