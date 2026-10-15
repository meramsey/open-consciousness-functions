"""Deterministic private recording validation; no cloud upload or unverified training."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sys
import wave
from array import array
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

from .paths import REPO_ROOT
from .utils import OCFError, read_json_object, sha256_of_file, write_text_atomic
from .validators import _load_schema, validate_against_schema


def initialize(root: Path, *, dataset_id: str = "my-voice", sample_rate: int = 22050) -> dict:
    script = json.loads((REPO_ROOT / "audio/voices/recording-script.json").read_text())
    records = []
    from .narration_pacing import split_speech_units

    for role, text in script["passages"].items():
        for i, unit in enumerate(split_speech_units(text), 1):
            name = f"{role}-{i:03d}"
            partition = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) % 10
            records.append(
                {
                    "id": name,
                    "audio": f"audio/{name}.wav",
                    "text": unit["text"],
                    "split": "test"
                    if partition == 0
                    else "validation"
                    if partition == 1
                    else "train",
                }
            )
    # A short script can hash into only two buckets. Keep assignments stable but
    # deterministically repair missing held-out splits for newly created datasets.
    for split in ("train", "validation", "test"):
        if not any(record["split"] == split for record in records):
            counts = {
                name: sum(r["split"] == name for r in records)
                for name in ("train", "validation", "test")
            }
            donor = max(counts, key=counts.get)
            candidate = max(
                (r for r in records if r["split"] == donor),
                key=lambda r: hashlib.sha256(r["id"].encode()).hexdigest(),
            )
            candidate["split"] = split
    data = {
        "schema_version": "1.0",
        "id": dataset_id,
        "locale": "en-US",
        "sample_rate": sample_rate,
        "consent_status": "unknown",
        "license": "unknown",
        "privacy": "private",
        "sessions": [],
        "records": records,
    }
    errors = validate_against_schema(data, _load_schema("voice-dataset.schema.json"))
    if errors:
        raise OCFError(" | ".join(errors))
    if root.exists():
        raise OCFError("dataset destination already exists; refusing to overwrite recordings")
    (root / "audio").mkdir(parents=True)
    write_text_atomic(
        root / "dataset.json",
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        overwrite=False,
    )
    write_text_atomic(
        root / "recording-guide.txt",
        "Record each original prompt into its named mono 16-bit PCM WAV. Keep the exact spoken transcript and label train/validation/test. Consent is unknown until you explicitly document ownership/authorization. See docs/VOICE_WORKFLOWS.md.\n",
        overwrite=False,
    )
    return {
        "path": str(root / "dataset.json"),
        "prompts": len(records),
        "consent_status": "unknown",
        "audio_recorded": False,
    }


def validate_dataset(manifest: Path) -> dict:
    data = read_json_object(manifest)
    errors = validate_against_schema(data, _load_schema("voice-dataset.schema.json"))
    if errors:
        raise OCFError("dataset schema: " + " | ".join(errors))
    root = manifest.parent.resolve()
    findings, measurements, seen, ids = [], [], {}, set()
    for record in data["records"]:

        def finding(code, message, severity="error"):
            findings.append(
                {"record": record["id"], "code": code, "message": message, "severity": severity}
            )

        if record["id"] in ids:
            finding("duplicate-id", "sample IDs must be unique")
        ids.add(record["id"])
        relative = Path(record["audio"])
        path = (root / relative).resolve()
        if (
            relative.is_absolute()
            or PureWindowsPath(record["audio"]).drive
            or "\\" in record["audio"]
            or ".." in relative.parts
            or not path.is_relative_to(root)
        ):
            finding("unsafe-path", "audio path escapes dataset")
            continue
        if not record["text"].strip():
            finding("missing-transcript", "spoken transcript is empty")
        if record.get("text_sha256") and record["text_sha256"] != text_fingerprint(record["text"]):
            finding(
                "transcript-changed", "transcript differs from the imported source text fingerprint"
            )
        if record.get("source_sha256") and record.get("sha256") != record["source_sha256"]:
            finding(
                "source-checksum", "unconverted imported audio must retain the source file checksum"
            )
        if not path.is_file():
            finding("missing-audio", "record the named WAV sample")
            continue
        try:
            if record.get("sha256") and sha256_of_file(path) != record["sha256"]:
                finding("checksum-mismatch", "audio file differs from the imported checksum")
            with wave.open(str(path), "rb") as reader:
                rate, channels, width, frames = (
                    reader.getframerate(),
                    reader.getnchannels(),
                    reader.getsampwidth(),
                    reader.getnframes(),
                )
                if channels != 1 or width != 2 or rate != data["sample_rate"]:
                    finding(
                        "audio-format",
                        f"expected mono PCM16 at {data['sample_rate']} Hz; got {channels} channels, {width * 8} bits, {rate} Hz",
                    )
                    continue
                if not 0 < frames <= rate * 120:
                    finding("duration", "utterance must be nonempty and at most 120 seconds")
                    continue
                payload = reader.readframes(frames)
                if len(payload) != frames * 2:
                    finding("truncated-audio", "WAV payload is shorter than its header")
                    continue
            checksum = hashlib.sha256(payload).hexdigest()
            if checksum in seen:
                finding(
                    "duplicate-audio",
                    f"same PCM as {seen[checksum]}; remove duplicates and split leakage",
                )
            seen[checksum] = record["id"]
            pcm = array("h", payload)
            if sys.byteorder != "little":
                pcm.byteswap()
            peak = max(abs(v) for v in pcm)
            clipped = sum(v <= -32768 or v >= 32767 for v in pcm)
            silence = sum(abs(v) < 104 for v in pcm) / len(pcm)
            rms = math.sqrt(sum(v * v for v in pcm) / len(pcm))
            if clipped:
                finding("clipping", f"{clipped} full-scale samples; re-record with lower gain")
            if silence > 0.5:
                finding(
                    "excessive-silence", f"{silence:.1%} of samples below approximately -50 dBFS"
                )
            if peak < 32767 * 10 ** (-24 / 20):
                finding("low-level", "peak below -24 dBFS; inspect recording gain", "warning")
            measurements.append(
                {
                    "id": record["id"],
                    "split": record["split"],
                    "duration_seconds": frames / rate,
                    "sample_rate": rate,
                    "peak_dbfs": 20 * math.log10(max(peak, 1) / 32768),
                    "rms_dbfs": 20 * math.log10(max(rms, 1) / 32768),
                    "clipped_samples": clipped,
                    "silence_fraction": silence,
                    "pcm_sha256": checksum,
                }
            )
        except (wave.Error, EOFError, OSError) as exc:
            finding("decode", str(exc))
    splits = {r["split"] for r in data["records"]}
    if splits != {"train", "validation", "test"}:
        findings.append(
            {
                "severity": "warning",
                "code": "split-coverage",
                "message": "all three dataset splits should be represented",
            }
        )
    sessions = {session["id"]: session for session in data.get("sessions", [])}
    if len(sessions) != len(data.get("sessions", [])):
        findings.append(
            {
                "severity": "error",
                "code": "duplicate-session",
                "message": "session IDs must be unique",
            }
        )
    prompt_splits = {}
    for record in data["records"]:
        if record.get("session_id"):
            session = sessions.get(record["session_id"])
            if not session or session["speaker"] != record.get("speaker"):
                findings.append(
                    {
                        "severity": "error",
                        "record": record["id"],
                        "code": "session-speaker",
                        "message": "record must reference a declared session with the same speaker",
                    }
                )
        prompt = record.get("prompt_id", record["id"])
        if prompt in prompt_splits and prompt_splits[prompt] != record["split"]:
            findings.append(
                {
                    "severity": "error",
                    "record": record["id"],
                    "code": "prompt-split-leakage",
                    "message": "all sessions/takes of a prompt must stay in the same split",
                }
            )
        prompt_splits[prompt] = record["split"]
    authorization = data["consent_status"] in {"self-recorded", "authorized-contributor"}
    consent_present = False
    if data.get("consent_record"):
        try:
            consent_present = _contained(root, data["consent_record"]).is_file()
        except OCFError:
            findings.append(
                {
                    "severity": "error",
                    "code": "unsafe-consent-path",
                    "message": "consent record must be contained in the private dataset",
                }
            )
    error_count = sum(f["severity"] == "error" for f in findings)
    blockers = []
    if error_count:
        blockers.append("Resolve dataset audio/metadata validation errors.")
    if not authorization or not consent_present:
        blockers.append(
            "Supply explicitly declared speaker authorization and a local consent record."
        )
    if splits != {"train", "validation", "test"}:
        blockers.append("Supply independent train, validation and test samples.")
    speakers = sorted({r["speaker"] for r in data["records"] if r.get("speaker")})
    if len(speakers) > 1:
        blockers.append(
            "Multiple speakers require an explicitly verified multi-speaker training adapter."
        )
    provenance_complete = all(
        all(
            r.get(key)
            for key in ("sha256", "source_sha256", "text_sha256", "session_id", "speaker")
        )
        for r in data["records"]
    )
    if not provenance_complete:
        blockers.append(
            "Complete per-prompt import provenance (checksum, text fingerprint, session and speaker)."
        )
    if any(f["severity"] == "warning" and f["code"] != "split-coverage" for f in findings):
        blockers.append("Review recording quality warnings before preparing a training dataset.")
    split_summary = split_report(data, measurements=measurements)
    return {
        "status": "failed" if error_count else "passed",
        "dataset_id": data["id"],
        "records": len(data["records"]),
        "errors": error_count,
        "warnings": len(findings) - error_count,
        "diagnostics": findings,
        "measurements": measurements,
        "consent_status": data["consent_status"],
        "authorization_verified": False,
        "quality_summary": {
            "measured_records": len(measurements),
            "duration_seconds": sum(m["duration_seconds"] for m in measurements),
            "clipped_samples": sum(m["clipped_samples"] for m in measurements),
            "sessions": len(sessions),
            "speakers": speakers,
            "room_noise_measured": False,
        },
        "readiness": {
            "dataset_ready": not blockers,
            "authorization_declared": authorization,
            "consent_record_present": consent_present,
            "provenance_complete": provenance_complete,
            "blockers": blockers,
        },
        "split_report": split_summary,
        "guidance": recording_guidance(findings),
        "privacy": "local-only; no upload or redistribution",
    }


def training_plan(
    manifest: Path | None = None, *, backend: str = "piper", probe_gpu: bool = False
) -> dict:
    from .voice_capabilities import backend_capability, local_preflight

    capability = backend_capability(backend)
    resources = local_preflight(probe_gpu=probe_gpu)
    validation = validate_dataset(manifest) if manifest else None
    blockers = [
        "No OCF training adapter has produced and tested a model; no training command will be fabricated."
    ]
    if validation:
        blockers.extend(validation["readiness"]["blockers"])
    else:
        blockers.append("Supply a validated, explicitly authorized dataset.")
    if not capability["upstream"]["training"]:
        blockers.append("This backend has no evaluated upstream model-training workflow.")
    if capability["upstream"]["training"] and not resources["torch_installed"]:
        blockers.append("Optional upstream training dependency torch is not installed.")
    blockers.append(resources["resource_note"])
    return {
        "backend": backend,
        "training_supported": capability["ocf"]["training_supported"],
        "inference_supported": capability["ocf"]["inference_supported"],
        "guide": capability["guide"],
        "license_note": capability["license_note"],
        "capability": capability,
        "status": "unsupported-until-verified",
        "torch_installed": resources["torch_installed"],
        "resources": resources,
        "dataset": validation,
        "ready": False,
        "model_produced": False,
        "blockers": blockers,
        "platform_note": "Portable profile/PCM validation is supported on Linux/macOS/Windows. Training OS/GPU requirements belong to the selected upstream version; no native training verification is claimed.",
    }


def _contained(root: Path, value: str) -> Path:
    relative = Path(value)
    if not relative.parts or any(ord(character) < 32 for character in value):
        raise OCFError("path must be a contained private dataset reference")
    path = (root / relative).resolve()
    if (
        not value
        or relative.is_absolute()
        or PureWindowsPath(value).drive
        or "\\" in value
        or ".." in relative.parts
        or not path.is_relative_to(root.resolve())
    ):
        raise OCFError("path must be a contained private dataset reference")
    return path


def text_fingerprint(text: str) -> str:
    """Exact UTF-8 source text identity; no normalization or transcript rewriting."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_report(data: dict | Path, *, measurements: list[dict] | None = None) -> dict:
    """Stable split membership, keeping alternate sessions of a prompt together."""
    if isinstance(data, Path):
        data = read_json_object(data)
    measured = {m["id"]: m["duration_seconds"] for m in measurements or []}
    splits = {}
    for split in ("train", "validation", "test"):
        records = sorted((r for r in data["records"] if r["split"] == split), key=lambda r: r["id"])
        splits[split] = {
            "record_ids": [r["id"] for r in records],
            "prompt_ids": sorted({r.get("prompt_id", r["id"]) for r in records}),
            "records": len(records),
            "measured_seconds": sum(measured.get(r["id"], 0) for r in records),
        }
    return {
        "policy": "explicit manifest splits; new scaffolds use sha256-prompt-id-mod10 with deterministic coverage repair; takes inherit prompt split",
        "splits": splits,
    }


def recording_guidance(findings: list[dict] | None = None) -> list[str]:
    guidance = [
        "Use a quiet, soft-furnished room; record separate room tone and inspect it manually. Speech RMS is not a measured noise floor.",
        "Keep microphone distance and posture consistent (approximately 15–25 cm, slightly off-axis); log room, microphone and gain for each session.",
        "Set speech peaks near -12 to -6 dBFS; retain unprocessed originals. Never relabel a sample rate or automatically denoise an imported take.",
    ]
    codes = {f["code"] for f in findings or []}
    if "clipping" in codes:
        guidance.append(
            "Lower input gain and re-record clipped takes; normalization cannot recover flattened peaks."
        )
    if "low-level" in codes:
        guidance.append(
            "Check microphone/input gain and room noise before re-recording low-level takes; avoid simply amplifying noise."
        )
    if "excessive-silence" in codes:
        guidance.append(
            "Review excessive leading/trailing silence and transcript alignment; preserve natural breaths."
        )
    return guidance


@contextmanager
def _dataset_import_lock(manifest: Path):
    """Portable, fail-fast exclusion: never wait, queue, or reclaim another lock."""
    lock = manifest.with_name(f".{manifest.name}.import.lock")
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise OCFError("dataset import is busy; retry after the active import completes") from exc
    try:
        yield lock
    finally:
        (lock / "recording.wav").unlink(missing_ok=True)
        lock.rmdir()


def import_recording(
    manifest: Path,
    prompt_id: str,
    source: Path,
    *,
    session_id: str,
    speaker: str,
    transcript: str | None = None,
    session_metadata: dict | None = None,
) -> dict:
    """Import one exact prompt take, without capture, conversion or destructive overwrite."""
    manifest = Path(manifest).expanduser().resolve()
    try:
        with _dataset_import_lock(manifest) as transaction_directory:
            return _import_recording_locked(
                manifest,
                prompt_id,
                source,
                session_id=session_id,
                speaker=speaker,
                transcript=transcript,
                session_metadata=session_metadata,
                transaction_directory=transaction_directory,
            )
    except OSError as exc:
        raise OCFError(f"recording import failed: {exc}") from exc


def _import_recording_locked(
    manifest: Path,
    prompt_id: str,
    source: Path,
    *,
    session_id: str,
    speaker: str,
    transcript: str | None,
    session_metadata: dict | None,
    transaction_directory: Path,
) -> dict:
    source = Path(source).expanduser().resolve()
    manifest_checksum = sha256_of_file(manifest)
    data = read_json_object(manifest)
    errors = validate_against_schema(data, _load_schema("voice-dataset.schema.json"))
    if errors:
        raise OCFError("dataset schema: " + " | ".join(errors))
    matches = [r for r in data["records"] if r["id"] == prompt_id]
    if len(matches) != 1:
        raise OCFError("select one existing prompt ID")
    prompt = matches[0]
    if transcript is not None and transcript != prompt["text"]:
        raise OCFError(
            "source transcript must exactly match the prompt; correct the manifest explicitly before import"
        )
    if not source.is_file() or source.suffix.lower() != ".wav":
        raise OCFError(
            "import requires a local mono PCM16 WAV; no automatic conversion is performed"
        )
    try:
        with wave.open(str(source), "rb") as reader:
            frames = reader.getnframes()
            if (
                reader.getnchannels() != 1
                or reader.getsampwidth() != 2
                or reader.getframerate() != data["sample_rate"]
                or reader.getcomptype() != "NONE"
            ):
                raise OCFError(
                    f"expected mono PCM16 WAV at {data['sample_rate']} Hz; convert deliberately outside this import"
                )
            if not 0 < frames <= data["sample_rate"] * 120:
                raise OCFError("utterance must be nonempty and at most 120 seconds")
            if len(reader.readframes(frames)) != frames * 2:
                raise OCFError("truncated WAV payload")
    except (wave.Error, EOFError, OSError) as exc:
        raise OCFError(f"cannot decode recording WAV: {exc}") from exc
    session = {"id": session_id, "speaker": speaker, **(session_metadata or {})}
    if session["id"] != session_id or session["speaker"] != speaker:
        raise OCFError("session metadata cannot replace the session or speaker identity")
    sessions = data.setdefault("sessions", [])
    existing = [s for s in sessions if s["id"] == session_id]
    if existing and (
        len(existing) != 1
        or existing[0]["speaker"] != speaker
        or (session_metadata and existing[0] != session)
    ):
        raise OCFError("session already exists with different speaker or metadata")
    if not existing:
        sessions.append(session)
    root = manifest.parent.resolve()
    _contained(root, prompt["audio"])
    # A recorder may already have populated the scaffold's declared WAV slot.
    # Its first import completes that row; file presence is not import provenance.
    first = not any(
        key in prompt for key in ("sha256", "source_sha256", "session_id", "imported_at")
    )
    canonical_prompt = prompt.get("prompt_id", prompt_id)
    record_id = prompt_id if first else f"{canonical_prompt}-{session_id}"
    if not first and any(r["id"] == record_id for r in data["records"]):
        raise OCFError("prompt/session already imported; choose a new session for another take")
    relative = f"audio/{session_id}/{canonical_prompt}.wav"
    destination = _contained(root, relative)
    if destination.exists() or destination.is_symlink():
        raise OCFError("recording destination already exists; refusing overwrite")
    checksum = sha256_of_file(source)
    record = {
        "id": record_id,
        "prompt_id": canonical_prompt,
        "audio": relative,
        "text": prompt["text"],
        "split": prompt["split"],
        "session_id": session_id,
        "speaker": speaker,
        "sha256": checksum,
        "source_sha256": checksum,
        "source_name": source.name,
        "text_sha256": text_fingerprint(prompt["text"]),
        "imported_at": datetime.now(UTC).isoformat(),
    }
    if first:
        data["records"][data["records"].index(prompt)] = record
    else:
        data["records"].append(record)
    data["privacy"] = "private"
    errors = validate_against_schema(data, _load_schema("voice-dataset.schema.json"))
    if errors:
        raise OCFError("recording metadata: " + " | ".join(errors))
    encoded = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    staged = transaction_directory / "recording.wav"
    with source.open("rb") as incoming, staged.open("xb") as out:
        shutil.copyfileobj(incoming, out)
        out.flush()
        os.fsync(out.fileno())
    if sha256_of_file(staged) != checksum:
        raise OCFError("staged recording checksum mismatch; manifest was not updated")
    destination.parent.mkdir(parents=True, exist_ok=True)
    created = None
    manifest_write_started = False
    try:
        # Exclusive creation is portable and cannot replace a prior recording.
        with staged.open("rb") as incoming, destination.open("xb") as out:
            created = os.fstat(out.fileno())
            shutil.copyfileobj(incoming, out)
            out.flush()
            os.fsync(out.fileno())
        if sha256_of_file(destination) != checksum:
            raise OCFError("copied recording checksum mismatch; manifest was not updated")
        if sha256_of_file(manifest) != manifest_checksum:
            raise OCFError(
                "dataset manifest changed during import; retry with the updated manifest"
            )
        manifest_write_started = True
        write_text_atomic(manifest, encoded)
    except BaseException:
        # A writer can raise after atomic replacement. Never remove audio already
        # referenced by the committed manifest, or any pre-existing/replaced file.
        committed = False
        if manifest_write_started:
            try:
                committed = manifest.read_bytes() == encoded.encode("utf-8")
            except OSError:
                pass
        if created is not None and not committed:
            try:
                current = destination.lstat()
                if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
                    destination.unlink()
            except FileNotFoundError:
                pass
        raise
    return {
        "manifest": str(manifest),
        "record": record,
        "audio_imported": True,
        "microphone_captured": False,
        "converted": False,
        "source_preserved": True,
    }


def recording_workflow(manifest: Path) -> dict:
    """Import-first wizard checkpoint; no microphone adapter is claimed."""
    data = read_json_object(manifest)
    report = validate_dataset(manifest)
    return {
        "workflow": "import-first",
        "capture_supported": False,
        "import_supported": True,
        "manifest": str(manifest),
        "locale": data["locale"],
        "sample_rate": data["sample_rate"],
        "prompts": [
            {
                "id": r["id"],
                "text": r["text"],
                "split": r["split"],
                "imported": bool(r.get("sha256")),
                "session_id": r.get("session_id"),
            }
            for r in data["records"]
        ],
        "next_action": "Record externally, then call import_recording with prompt, session and speaker identities.",
        "validation": report,
        "guidance": report["guidance"],
    }
