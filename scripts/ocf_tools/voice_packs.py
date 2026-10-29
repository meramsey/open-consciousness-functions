"""Private, reference-based zero-shot voice packs backed by OCF voice profiles."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import queue
import re
import subprocess
import sys
import threading
import wave
from array import array
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from . import custom_voices
from .indexes import load_voice_profiles
from .paths import REPO_ROOT, unique_run_id, work_path, workspace_environment, workspace_run
from .utils import OCFError, sha256_of_file, write_text_atomic, yaml_safe_dump

CHATTERBOX_REVISION = "5de7a54aa4e5e2baadb0182dde554908b48b85c2"
_worker_scope_lock = threading.Lock()
_worker_io_lock = threading.RLock()
_worker_scopes = 0
_worker_process: subprocess.Popen | None = None
_worker_responses: queue.Queue[str | None] | None = None
_worker_log_path: Path | None = None
_active_voice_pack: ContextVar[dict | None] = ContextVar("ocf_active_zero_shot_pack", default=None)


@contextmanager
def persistent_worker(voice_id: str | None = None):
    """Share one optional Chatterbox model across an OCF render scope."""
    global _worker_scopes
    inherited_pack = _active_voice_pack.get()
    selected_pack = inherited_pack
    if voice_id:
        if inherited_pack and inherited_pack["id"] == voice_id:
            selected_pack = inherited_pack
        else:
            try:
                candidate = inspect_pack(voice_id)["profile"]
                selected_pack = (
                    candidate if candidate.get("backend") == "chatterbox-nano" else inherited_pack
                )
            except OCFError:
                selected_pack = inherited_pack
    pack_token = _active_voice_pack.set(selected_pack)
    with _worker_scope_lock:
        _worker_scopes += 1
    try:
        yield
    finally:
        with _worker_scope_lock:
            _worker_scopes -= 1
            if _worker_scopes == 0:
                _stop_worker()
        _active_voice_pack.reset(pack_token)


def _profile_for_synthesis(query: str) -> dict:
    active = _active_voice_pack.get()
    return active if active and active["id"] == query else inspect_pack(query)["profile"]


def _read_worker_stdout(process: subprocess.Popen, responses: queue.Queue) -> None:
    try:
        for line in process.stdout:
            responses.put(line)
    finally:
        responses.put(None)


def _stop_worker() -> None:
    global _worker_process, _worker_responses, _worker_log_path
    with _worker_io_lock:
        process = _worker_process
        _worker_process = None
        _worker_responses = None
        _worker_log_path = None
        if process is None:
            return
        if process.stdin:
            process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if process.stdout:
            process.stdout.close()


def _persistent_inference(request: dict, interpreter: Path, timeout: int) -> dict:
    global _worker_process, _worker_responses, _worker_log_path
    with _worker_io_lock:
        process = _worker_process
        if process is None or process.poll() is not None:
            if process is not None:
                _stop_worker()
            log_dir = work_path("logs", "voice-inference", "workers")
            log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            log_dir.chmod(0o700)
            _worker_log_path = log_dir / (unique_run_id("chatterbox-worker") + ".log")
            env = workspace_environment(
                {
                    "PYTHONPATH": str(REPO_ROOT / "scripts")
                    + os.pathsep
                    + os.environ.get("PYTHONPATH", "")
                }
            )
            with _worker_log_path.open("ab") as stderr:
                _worker_log_path.chmod(0o600)
                _worker_process = subprocess.Popen(
                    [str(interpreter), "-m", "ocf_tools.chatterbox_backend", "--worker"],
                    cwd=REPO_ROOT,
                    env=env,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=stderr,
                    text=True,
                    encoding="utf-8",
                    bufsize=1,
                )
            _worker_responses = queue.Queue()
            threading.Thread(
                target=_read_worker_stdout,
                args=(_worker_process, _worker_responses),
                daemon=True,
                name="ocf-chatterbox-output",
            ).start()
        process = _worker_process
        responses = _worker_responses
        try:
            assert process and process.stdin and responses
            process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            process.stdin.flush()
            line = responses.get(timeout=timeout)
        except (OSError, queue.Empty) as exc:
            _stop_worker()
            raise OCFError(f"persistent Chatterbox worker failed or timed out: {exc}") from exc
        if line is None:
            log_hint = f"; see {_worker_log_path}" if _worker_log_path else ""
            _stop_worker()
            raise OCFError("persistent Chatterbox worker exited unexpectedly" + log_hint)
        try:
            return json.loads(line)
        except ValueError as exc:
            _stop_worker()
            raise OCFError("persistent Chatterbox worker returned invalid JSON") from exc


def create_pack(
    reference: Path,
    *,
    voice_id: str,
    name: str,
    locale: str,
    transcript: str | None = None,
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
    if not locale.lower().startswith("en-"):
        raise OCFError("Chatterbox Nano voice packs currently support English locales only")
    if transcript is not None and not transcript.strip():
        raise OCFError("a supplied reference transcript must not be empty")
    if not consent_declaration.strip():
        raise OCFError("an explicit consent declaration is required")
    reference = Path(reference).expanduser().resolve()
    if not reference.is_file() or reference.suffix.lower() != ".wav":
        raise OCFError("voice-pack reference must be a prepared local WAV file")
    try:
        with wave.open(str(reference), "rb") as wav:
            if wav.getnframes() / wav.getframerate() <= 5:
                raise OCFError("Chatterbox Nano requires a reference longer than five seconds")
            if (wav.getnchannels(), wav.getframerate(), wav.getsampwidth()) != (1, 24000, 2):
                raise OCFError(
                    "voice-pack references must be mono 24 kHz PCM16; run prepare-reference"
                )
    except (wave.Error, ZeroDivisionError) as exc:
        raise OCFError(f"prepared reference is not a valid WAV: {exc}") from exc
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
    asset_dir.mkdir(parents=True, mode=0o700)
    asset_dir.chmod(0o700)
    asset = asset_dir / "reference.wav"
    try:
        asset.write_bytes(reference.read_bytes())
        asset.chmod(0o600)
        consent = asset_dir / "consent.txt"
        consent.write_text(consent_declaration.strip() + "\n", encoding="utf-8")
        consent.chmod(0o600)
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
            "consent_status": "self-recorded"
            if source_type == "original-recording"
            else "authorized-contributor",
            "consent_record": f"{voice_id}/consent.txt",
            "license": "Chatterbox Nano model card reports MIT; review transitive dependency licenses separately.",
            "reference_audio": {
                "asset": f"{voice_id}/reference.wav",
                "sha256": digest,
                **({"reference_text": transcript.strip()} if transcript else {}),
                "locale": locale,
                "speaker": voice_id,
                "consent_status": "self-recorded"
                if source_type == "original-recording"
                else "authorized-contributor",
                "consent_record": f"{voice_id}/consent.txt",
                "source_type": source_type,
                "transcript_status": "confirmed" if transcript else "not-provided",
                "model_identifier": model_identifier,
                "model_revision": model_revision,
                "adapter_revision": CHATTERBOX_REVISION,
                "source_sha256": source_digest,
            },
            "creation_provenance": {
                "created_by": "OCF local voice-pack CLI",
                "created_at": datetime.now(UTC).isoformat(),
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
        "inference_verified": inference_verified(profile),
        "inference_receipts": inference_receipts(profile["id"]),
    }


def inference_receipts(voice_id: str) -> list[dict]:
    root = work_path("logs", "voice-inference", voice_id)
    receipts = []
    for path in sorted(root.glob("*.json")) if root.is_dir() else ():
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
            if receipt.get("voice_id") == voice_id and receipt.get("status") == "success":
                receipts.append(receipt)
        except (OSError, ValueError):
            continue
    return receipts


def _receipt_proves_inference(receipt: dict, reference_sha256: str | None = None) -> bool:
    def valid_sha(value: object) -> bool:
        return isinstance(value, str) and bool(re.fullmatch(r"[a-f0-9]{64}", value))

    return (
        receipt.get("status") == "success"
        and receipt.get("backend") == "chatterbox-nano"
        and receipt.get("model_identifier") == "ResembleAI/chatterbox-nano"
        and bool(re.fullmatch(r"[a-f0-9]{40}", str(receipt.get("model_revision", ""))))
        and bool(re.fullmatch(r"[a-f0-9]{40}", str(receipt.get("adapter_revision", ""))))
        and valid_sha(receipt.get("model_tree_sha256"))
        and valid_sha(receipt.get("output_sha256"))
        and valid_sha(receipt.get("reference_sha256"))
        and valid_sha(receipt.get("reference_text_sha256"))
        and valid_sha(receipt.get("text_sha256"))
        and (reference_sha256 is None or receipt.get("reference_sha256") == reference_sha256)
        and receipt.get("sample_rate") == 24000
        and isinstance(receipt.get("duration_s"), (int, float))
        and receipt["duration_s"] > 0
        and isinstance(receipt.get("sample_peak"), (int, float))
        and 0 < receipt["sample_peak"] <= 0.98
    )


def inference_verified(profile: dict) -> bool:
    root = work_path("renders", "voice-pack-auditions", profile["id"]).resolve()
    for receipt in inference_receipts(profile["id"]):
        if not _receipt_proves_inference(receipt, profile.get("reference_audio", {}).get("sha256")):
            continue
        output = Path(receipt.get("output", ""))
        try:
            resolved = output.resolve(strict=True)
            if (
                output.is_symlink()
                or not resolved.is_relative_to(root)
                or sha256_of_file(resolved) != receipt["output_sha256"]
            ):
                continue
        except OSError:
            continue
        return True
    return False


def cached_model_revision() -> str | None:
    ref = work_path(
        "cache", "huggingface", "hub", "models--ResembleAI--chatterbox-nano", "refs", "main"
    )
    try:
        return ref.read_text(encoding="ascii").strip() if ref.is_file() else None
    except OSError:
        return None


def cached_model_tree_fingerprint() -> str | None:
    revision = cached_model_revision()
    if not revision:
        return None
    try:
        entries = _cached_model_file_hashes(revision)
        if not entries:
            return None
        return hashlib.sha256(
            json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    except OSError:
        return None


def _cached_model_file_hashes(revision: str) -> dict[str, str]:
    snapshot = (
        work_path("cache").parent
        / "cache/huggingface/hub/models--ResembleAI--chatterbox-nano/snapshots"
        / revision
    )
    return {
        path.relative_to(snapshot).as_posix(): sha256_of_file(path)
        for path in sorted(snapshot.rglob("*"))
        if path.is_file()
    }


def synthesize(query: str, text: str, *, device: str = "auto", timeout: int = 900) -> dict:
    """Run the real optional Chatterbox worker without importing ML into OCF Python."""
    profile = _profile_for_synthesis(query)
    if profile.get("backend") != "chatterbox-nano":
        raise OCFError("this MVP audition supports only chatterbox-nano voice packs")
    if profile.get("reference_audio", {}).get("model_identifier") != "ResembleAI/chatterbox-nano":
        raise OCFError(
            "voice pack model identifier differs from the implemented Chatterbox Nano adapter"
        )
    if not text.strip():
        raise OCFError("audition text must not be empty")
    configured = os.environ.get("OCF_CHATTERBOX_PYTHON")
    if configured:
        interpreter = Path(configured).expanduser().resolve()
    elif sys.platform == "win32":
        interpreter = work_path("cache").parent / "voice-envs/chatterbox/Scripts/python.exe"
    else:
        interpreter = work_path("cache").parent / "voice-envs/chatterbox/bin/python"
    if not interpreter.is_file():
        raise OCFError(
            "Chatterbox optional environment is missing; see docs/VOICE_PACKS.md for setup"
        )
    reference = custom_voices._contained(
        custom_voices.asset_root(), profile["reference_audio"]["asset"]
    )
    if not reference.is_file() or sha256_of_file(reference) != profile["reference_audio"]["sha256"]:
        raise OCFError("Chatterbox voice-pack reference is missing or fails its checksum")
    output = work_path(
        "renders", "voice-pack-auditions", profile["id"], unique_run_id("audition") + ".wav"
    )
    request = json.dumps(
        {
            "reference": str(reference),
            "reference_text_sha256": hashlib.sha256(
                profile["reference_audio"].get("reference_text", "").encode()
            ).hexdigest(),
            "text": text,
            "output": str(output),
            "device": device,
        }
    )
    try:
        with _worker_scope_lock:
            persistent = _worker_scopes > 0
        if persistent:
            report = _persistent_inference(json.loads(request), interpreter, timeout)
            result = None
        else:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO_ROOT / "scripts") + os.pathsep + env.get("PYTHONPATH", "")
            result = workspace_run(
                [str(interpreter), "-m", "ocf_tools.chatterbox_backend"],
                input=request,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OCFError(f"Chatterbox worker could not complete: {exc}") from exc
    if result is not None:
        if result.returncode:
            raise OCFError(
                (result.stderr or result.stdout or "Chatterbox inference failed")[-3000:]
            )
        try:
            report = json.loads(result.stdout)
        except (ValueError, TypeError) as exc:
            raise OCFError("Chatterbox worker returned invalid result metadata") from exc
    if report.get("error") or not output.is_file() or not output.stat().st_size:
        raise OCFError(report.get("error", "Chatterbox produced no WAV output"))
    report_model = report.get("model_revision")
    declared_model = profile["reference_audio"]["model_revision"]
    if declared_model not in {"main", report_model}:
        raise OCFError("loaded Chatterbox model revision differs from the voice-pack declaration")
    declared_adapter = profile["reference_audio"].get("adapter_revision")
    if declared_adapter and report.get("adapter_revision") != declared_adapter:
        raise OCFError(
            "installed Chatterbox adapter revision differs from the voice-pack declaration"
        )
    if report.get("reference_sha256") != profile["reference_audio"]["sha256"]:
        raise OCFError("Chatterbox used an unexpected reference fingerprint")
    if (
        report.get("reference_text_sha256")
        != hashlib.sha256(profile["reference_audio"].get("reference_text", "").encode()).hexdigest()
    ):
        raise OCFError("Chatterbox transcript fingerprint differs from the pack metadata")
    if report.get("text_sha256") != hashlib.sha256(text.encode()).hexdigest():
        raise OCFError("Chatterbox output text fingerprint differs from the requested text")
    if (
        not isinstance(report.get("sample_peak"), (int, float))
        or not 0 < report["sample_peak"] <= 0.98
    ):
        raise OCFError("Chatterbox output peak failed audio integrity checks")
    try:
        import wave

        with wave.open(str(output), "rb") as wav:
            if wav.getnframes() <= 0 or wav.getsampwidth() != 2 or wav.getnchannels() != 1:
                raise OCFError("Chatterbox output failed WAV/PCM integrity checks")
            if wav.getframerate() != report.get("sample_rate"):
                raise OCFError("Chatterbox output sample rate differs from its report")
            if (
                abs(wav.getnframes() / wav.getframerate() - report.get("duration_s", 0))
                > 1 / wav.getframerate()
            ):
                raise OCFError("Chatterbox output duration differs from its report")
    except (wave.Error, OSError, ZeroDivisionError) as exc:
        raise OCFError(f"Chatterbox output is not a valid WAV: {exc}") from exc
    if sha256_of_file(output) != report.get("output_sha256"):
        raise OCFError("Chatterbox output SHA-256 differs from its inference receipt")
    report["output"] = str(output)
    report["voice_id"] = profile["id"]
    previous_reference_metadata = dict(profile["reference_audio"])
    profile["reference_audio"]["model_revision"] = report_model or declared_model
    profile["reference_audio"]["adapter_revision"] = report.get("adapter_revision") or profile[
        "reference_audio"
    ].get("adapter_revision")
    if report.get("model_tree_sha256"):
        profile["reference_audio"]["model_tree_sha256"] = report["model_tree_sha256"]
    if report.get("model_files"):
        profile["reference_audio"]["model_files"] = report["model_files"]
    if profile["reference_audio"] != previous_reference_metadata:
        profile_path = work_path("cache", "voices", "profiles", profile["id"] + ".yaml")
        write_text_atomic(profile_path, yaml_safe_dump(profile))
    receipt = {
        **report,
        "status": "success",
        "text": text,
        "profile_version": profile.get("version"),
        "created_at": datetime.now(UTC).isoformat(),
    }
    receipt_root = work_path("logs", "voice-inference", profile["id"])
    receipt_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt_root.chmod(0o700)
    write_text_atomic(
        receipt_root / (Path(report["output"]).stem + ".json"),
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        overwrite=False,
    )
    from .speech_cache import record_inference_report

    record_inference_report(report)
    return report


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
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    out.chmod(0o700)
    digest = sha256_of_file(source)
    destination = out / f"{digest[:16]}-{first}-{last}.wav"
    if not destination.exists():
        with wave.open(str(destination), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(rate)
            writer.writeframes(selected.tobytes())
    destination.chmod(0o600)
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
