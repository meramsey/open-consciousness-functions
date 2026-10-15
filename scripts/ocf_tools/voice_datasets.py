"""Deterministic private recording validation; no cloud upload or unverified training."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
import wave
from array import array
from pathlib import Path

from .paths import REPO_ROOT
from .utils import OCFError, read_json_object, write_text_atomic
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
    data = {
        "schema_version": "1.0",
        "id": dataset_id,
        "locale": "en-US",
        "sample_rate": sample_rate,
        "consent_status": "unknown",
        "license": "unknown",
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
        if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root):
            finding("unsafe-path", "audio path escapes dataset")
            continue
        if not record["text"].strip():
            finding("missing-transcript", "spoken transcript is empty")
        if not path.is_file():
            finding("missing-audio", "record the named WAV sample")
            continue
        try:
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
            clipped = sum(abs(v) >= 32767 for v in pcm)
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
    error_count = sum(f["severity"] == "error" for f in findings)
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
        "privacy": "local-only; no upload or redistribution",
    }


def training_plan(manifest: Path | None = None, *, backend: str = "piper") -> dict:
    adapters = {
        "piper": {
            "training_supported": False,
            "inference_supported": True,
            "guide": "https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/TRAINING.md",
            "license_note": "GPL engine; each model/dataset has separate terms.",
        },
        "f5-tts": {
            "training_supported": False,
            "inference_supported": False,
            "guide": "https://github.com/SWivid/F5-TTS",
            "license_note": "MIT code; upstream pretrained models documented as CC-BY-NC. Do not infer redistribution permission.",
        },
    }
    if backend not in adapters:
        raise OCFError("unknown evaluated training adapter")
    validation = validate_dataset(manifest) if manifest else None
    return {
        "backend": backend,
        **adapters[backend],
        "status": "unsupported-until-verified",
        "torch_installed": importlib.util.find_spec("torch") is not None,
        "dataset": validation,
        "model_produced": False,
        "blockers": [
            "No OCF training adapter has produced and tested a model; no training command will be fabricated.",
            "Supply a validated, explicitly authorized dataset and verify upstream training in a dedicated environment.",
        ],
        "platform_note": "Portable profile/PCM validation is supported on Linux/macOS/Windows. Training OS/GPU requirements belong to the selected upstream version; no native training verification is claimed.",
    }
