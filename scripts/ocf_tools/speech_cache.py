"""Opt-in, content-addressed PCM synthesis cache scoped to an OCF render job."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import sys
import threading
import wave
from array import array
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from uuid import uuid4

from .paths import work_path
from .utils import OCFError, sha256_of_file

CACHE_VERSION = "ocf-tts-pcm/3"
TEXT_PROCESSING_VERSION = "ocf-spoken-text/1"
CHUNK_CONTEXT_VERSION = "ocf-isolated-cue/1"
MAX_CACHE_BYTES = 2 * 1024**3
STAT_KEYS = (
    "hit",
    "miss",
    "invalidated",
    "bypassed",
    "refreshed",
    "inference_seconds",
    "saved_generation_seconds",
)
TIME_STATS = ("inference_seconds", "saved_generation_seconds")
COUNTER_STATS = ("hit", "miss", "invalidated", "bypassed", "refreshed")
STATS = dict.fromkeys(STAT_KEYS, 0)
_active: ContextVar[bool | None] = ContextVar("ocf_speech_cache", default=None)
_mode: ContextVar[str | None] = ContextVar("ocf_speech_cache_mode", default=None)
_refresh_scope: ContextVar[str | None] = ContextVar("ocf_speech_cache_refresh", default=None)
_scope_function: ContextVar[str | None] = ContextVar("ocf_speech_cache_function", default=None)
_scope_stats: ContextVar[dict | None] = ContextVar("ocf_speech_cache_stats", default=None)
_scope_events: ContextVar[list | None] = ContextVar("ocf_speech_cache_events", default=None)
_last_inference_report: ContextVar[dict | None] = ContextVar(
    "ocf_last_inference_report", default=None
)
_stats_lock = threading.Lock()


def _increment(name: str) -> None:
    with _stats_lock:
        STATS[name] += 1
    if stats := _scope_stats.get():
        stats[name] += 1


def _fresh_stats() -> dict:
    return dict.fromkeys(STAT_KEYS, 0)


def record_inference_report(report: dict) -> None:
    _last_inference_report.set(report)


def _add_seconds(name: str, seconds: float) -> None:
    with _stats_lock:
        STATS[name] += seconds
    if (stats := _scope_stats.get()) is not None:
        stats[name] += seconds


def _event(
    action: str,
    key: str | None,
    text: str,
    data: bytes | None,
    manifest: dict | None,
    *,
    profile_id: str | None = None,
    inference: dict | None = None,
    identity_kind: str = "cache-key",
    identity: dict | None = None,
    voice_spec: dict | None = None,
):
    events = _scope_events.get()
    if events is None:
        return
    metadata = _audio_metadata(data) if data is not None else None
    voice_descriptor = (
        identity["voice"]
        if identity and identity.get("voice")
        else {
            key: (voice_spec or {}).get(key)
            for key in (
                "profile_id",
                "profile_version",
                "name",
                "locale",
                "language",
                "model_identity",
                "reference_sha256",
                "reference_text_sha256",
                "pronunciation",
                "wpm",
                "piper_length_scale",
            )
            if key in (voice_spec or {})
        }
    )
    events.append(
        {
            "action": action,
            "cache_key": key,
            "identity_kind": identity_kind,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "audio_sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
            "sample_rate": metadata.get("sample_rate") if metadata else None,
            "channels": metadata.get("channels") if metadata else None,
            "duration_s": metadata.get("duration_s") if metadata else None,
            "generation_seconds": manifest.get("generation_seconds") if manifest else None,
            "generation_id": manifest.get("generation_id") if manifest else None,
            "profile_id": profile_id,
            "profile_version": (voice_spec or {}).get("profile_version"),
            "backend": (voice_spec or {}).get("name"),
            "locale": (identity or {}).get("locale") or (voice_spec or {}).get("locale"),
            "voice_fingerprint": hashlib.sha256(
                json.dumps(
                    voice_descriptor, sort_keys=True, ensure_ascii=False, default=str
                ).encode()
            ).hexdigest()
            if voice_descriptor
            else None,
            "model_identity": (voice_spec or {}).get("model_identity"),
            "conditioning_reference_sha256": (voice_spec or {}).get("reference_sha256"),
            "function_id": _scope_function.get(),
            "inference": {
                key: inference.get(key)
                for key in (
                    "model_load_seconds",
                    "conditioning_seconds",
                    "model_reused",
                    "speaker_conditioning_reused",
                    "peak_rss_bytes",
                    "peak_cuda_memory_bytes",
                    "device",
                    "generation_seconds",
                )
            }
            if inference
            else None,
        }
    )


def _synthesis_identity(spec: dict, text: str) -> tuple[dict, str]:
    identity = {
        "voice": voice_identity(spec),
        "text": text,
        "locale": spec.get("locale", spec.get("language")),
        "text_processing_version": TEXT_PROCESSING_VERSION,
        "chunk_context_version": CHUNK_CONTEXT_VERSION,
        "context_scope": "isolated-cue",
        "seed": None,
        "generation_policy": "reuse-first-verified-artifact",
    }
    key = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return identity, key


def _uncached_identity_hint(spec: dict, text: str) -> str:
    """Cheap reproducibility grouping for off-mode metrics; never authorizes reuse."""
    keys = (
        "profile_id",
        "name",
        "locale",
        "language",
        "model_identity",
        "reference_sha256",
        "reference_text_sha256",
        "pronunciation",
        "wpm",
        "piper_length_scale",
        "piper_sentence_silence_s",
        "processing_defaults",
    )
    hint = {key: spec.get(key) for key in keys if key in spec}
    hint.update(
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        cache_version=CACHE_VERSION,
        text_processing_version=TEXT_PROCESSING_VERSION,
        chunk_context_version=CHUNK_CONTEXT_VERSION,
        mode="off-no-reuse",
    )
    return hashlib.sha256(
        json.dumps(hint, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


@contextmanager
def policy(mode: str = "auto", *, refresh_scope: str | None = None, function_id: str | None = None):
    """Select cache policy for one render; nested off always wins."""
    if mode not in {"auto", "off", "refresh", "require-hit"}:
        raise OCFError("speech cache mode must be auto, off, refresh or require-hit")
    parent_mode = _mode.get()
    selected = (
        parent_mode
        if parent_mode in {"off", "require-hit"}
        else "refresh"
        if parent_mode == "refresh" and mode == "auto"
        else mode
    )
    scope = refresh_scope or _refresh_scope.get()
    if selected == "refresh" and scope is None:
        scope = uuid4().hex
    mode_token = _mode.set(selected)
    scope_token = _refresh_scope.set(scope)
    function_token = _scope_function.set(function_id or _scope_function.get())
    stats = _scope_stats.get()
    if stats is None:
        stats = _fresh_stats()
    stats_token = _scope_stats.set(stats)
    events = _scope_events.get()
    if events is None:
        events = []
    events_token = _scope_events.set(events)
    try:
        yield stats, events, scope
    finally:
        _scope_events.reset(events_token)
        _scope_stats.reset(stats_token)
        _scope_function.reset(function_token)
        _refresh_scope.reset(scope_token)
        _mode.reset(mode_token)


@contextmanager
def enabled(active: bool = True):
    # None is unselected; an explicit outer False wins over nested opt-ins.
    token = _active.set(active and _active.get() is not False)
    try:
        yield
    finally:
        _active.reset(token)


def voice_identity(spec: dict) -> dict:
    """Fingerprint actual engine/model/config bytes, not filenames or voice labels."""
    if spec.get("name") == "chatterbox-nano":
        from .chatterbox_backend import INFERENCE_PROVENANCE
        from .paths import REPO_ROOT, work_path

        settings = {
            key: value
            for key, value in spec.items()
            if key not in {"reference_audio", "environment"}
        }
        assets = {
            "reference_audio": spec["reference_sha256"],
            "reference_transcript": spec["reference_text_sha256"],
            "renderer": sha256_of_file(Path(__file__).with_name("voice.py")),
            "adapter": sha256_of_file(REPO_ROOT / "scripts/ocf_tools/chatterbox_backend.py"),
        }
        optional_root = work_path("cache").parent / "voice-envs/chatterbox"
        for pattern in (
            "lib/python*/site-packages/chatterbox_tts-*.dist-info/METADATA",
            "lib/python*/site-packages/torch-*.dist-info/METADATA",
            "lib/python*/site-packages/transformers-*.dist-info/METADATA",
            "lib/python*/site-packages/resemble_perth-*.dist-info/METADATA",
            "Lib/site-packages/chatterbox_tts-*.dist-info/METADATA",
        ):
            for metadata in optional_root.glob(pattern):
                assets[metadata.name] = sha256_of_file(metadata)
        return {
            "assets": assets,
            "settings": {**settings, "inference": INFERENCE_PROVENANCE},
            "cache_version": CACHE_VERSION,
        }
    binary = shutil.which(spec["binary"])
    if not binary:
        raise OCFError(f"voice backend is unavailable: {spec['binary']}")
    assets = {"binary": sha256_of_file(Path(binary))}
    # Console scripts may run in a different venv from the OCF process (e.g.
    # pipx/uv-installed Piper). Fingerprint that environment's package records,
    # rather than attributing the OCF interpreter's packages to the backend.
    executable = Path(binary).resolve()
    environment = executable.parent.parent
    with executable.open("rb") as handle:
        first_line = handle.read(512).split(b"\n", 1)[0]
    if first_line.startswith(b"#!"):
        interpreter = Path(first_line[2:].decode("utf-8", "replace").strip())
        if interpreter.is_absolute() and interpreter.is_file():
            environment = interpreter.parent.parent
    runtime_records = {}
    if spec.get("name") == "piper":
        for library in (environment / "lib", environment / "Lib"):
            for pattern in (
                "python*/site-packages/*piper*.dist-info/*",
                "python*/site-packages/onnxruntime*.dist-info/*",
                "site-packages/*piper*.dist-info/*",
                "site-packages/onnxruntime*.dist-info/*",
            ):
                for record in library.glob(pattern):
                    if record.name in {"METADATA", "RECORD"}:
                        runtime_records[record.relative_to(environment).as_posix()] = (
                            sha256_of_file(record)
                        )
    if spec.get("model"):
        model = Path(spec["model"])
        if not model.is_file():
            raise OCFError(f"voice model is unavailable: {model.name}")
        assets["model"] = sha256_of_file(model)
        config = Path(str(model) + ".json")
        assets["model_config"] = sha256_of_file(config) if config.is_file() else None
    packages = {}
    for name in ("piper-tts", "onnxruntime", "onnxruntime-gpu"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {
        "assets": assets,
        "settings": spec,
        "packages": packages,
        "backend_environment": runtime_records,
        "renderer": sha256_of_file(Path(__file__).with_name("voice.py")),
        "cache_version": CACHE_VERSION,
    }


def _valid_pcm(data: bytes) -> bool:
    return _audio_metadata(data) is not None


def _audio_metadata(data: bytes) -> dict | None:
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            frames = reader.getnframes()
            width, channels, sample_rate = (
                reader.getsampwidth(),
                reader.getnchannels(),
                reader.getframerate(),
            )
            raw = reader.readframes(frames)
            if (
                frames <= 0
                or width != 2
                or channels not in (1, 2)
                or sample_rate <= 0
                or len(raw) != frames * width * channels
            ):
                return None
            samples = array("h")
            samples.frombytes(raw)
            if sys.byteorder != "little":
                samples.byteswap()
            peak = max((abs(value) for value in samples), default=0) / 32768
            return {
                "frames": frames,
                "sample_rate": sample_rate,
                "channels": channels,
                "duration_s": frames / sample_rate,
                "sample_peak": peak,
                "clipped_samples": sum(abs(value) >= 32767 for value in samples),
            }
    except (wave.Error, EOFError, OSError):
        return None


def _read_verified(root: Path, key: str) -> tuple[bytes, dict] | None:
    try:
        cache_root = work_path("cache", "tts")
        if root.is_symlink() or not root.resolve().is_relative_to(cache_root.resolve()):
            return None
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("key") != key:
            return None
        generation = manifest.get("generation_id")
        if generation is not None and not re.fullmatch(r"[a-f0-9]{32}", str(generation)):
            return None
        audio_name = manifest.get("audio_file", "speech.wav")
        if not isinstance(audio_name, str) or Path(audio_name).name != audio_name:
            return None
        audio_path = root / audio_name
        if audio_path.is_symlink() or not audio_path.resolve().is_relative_to(root.resolve()):
            return None
        data = audio_path.read_bytes()
        metadata = _audio_metadata(data)
        if (
            not metadata
            or hashlib.sha256(data).hexdigest() != manifest.get("sha256")
            or any(manifest.get(name) != value for name, value in metadata.items())
        ):
            return None
        return data, manifest
    except (OSError, ValueError, TypeError, KeyError):
        return None


def cached_cue(spec: dict, text: str, render) -> bytes:
    import time

    from .progress import advance

    advance("synthesis-cues", detail=spec.get("profile_id") or spec.get("name"))
    selected_mode = _mode.get() or ("auto" if _active.get() else "off")
    if _active.get() is False:
        selected_mode = "off"
    if selected_mode == "off":
        hint = _uncached_identity_hint(spec, text)
        _increment("bypassed")
        started = time.perf_counter()
        token = _last_inference_report.set(None)
        try:
            data = render()
            inference_report = _last_inference_report.get()
        finally:
            _last_inference_report.reset(token)
        elapsed = time.perf_counter() - started
        _add_seconds("inference_seconds", elapsed)
        _event(
            "bypassed",
            hint,
            text,
            data,
            {"generation_seconds": elapsed},
            profile_id=spec.get("profile_id"),
            inference=inference_report,
            identity_kind="uncached-request-hint",
            voice_spec=spec,
        )
        return data
    identity, key = _synthesis_identity(spec, text)
    root = work_path("cache", "tts", key)
    manifest = root / "manifest.json"
    from .dev_jobs import lock

    with lock("speech-cache-key-" + key, wait=True, timeout=900):
        existing = _read_verified(root, key)
        if existing and (
            selected_mode in {"auto", "require-hit"}
            or existing[1].get("refresh_scope") == _refresh_scope.get()
        ):
            _increment("hit")
            _add_seconds(
                "saved_generation_seconds", float(existing[1].get("generation_seconds", 0))
            )
            _event(
                "hit",
                key,
                text,
                existing[0],
                existing[1],
                profile_id=spec.get("profile_id"),
                identity=identity,
                voice_spec=spec,
            )
            return existing[0]
        if selected_mode == "refresh":
            _increment("refreshed")
        else:
            _increment("invalidated" if manifest.exists() else "miss")
        if selected_mode == "require-hit":
            _event(
                "miss-blocked",
                key,
                text,
                None,
                None,
                profile_id=spec.get("profile_id"),
                identity=identity,
                voice_spec=spec,
            )
            raise OCFError("required cached speech is missing or invalid; synthesis was blocked")
        started = time.perf_counter()
        token = _last_inference_report.set(None)
        try:
            data = render()
            inference_report = _last_inference_report.get()
        finally:
            _last_inference_report.reset(token)
        generation_seconds = time.perf_counter() - started
        _add_seconds("inference_seconds", generation_seconds)
        metadata = _audio_metadata(data)
        if not metadata:
            raise OCFError("TTS cache refuses incomplete or invalid PCM output")
        try:
            manifest = _publish(
                root,
                key,
                data,
                identity=identity,
                refresh_scope=_refresh_scope.get() if selected_mode == "refresh" else None,
                generation_seconds=generation_seconds,
            )
        except (OSError, OCFError):
            # Keep valid synthesized PCM if scratch storage is full; cache is optional.
            _increment("bypassed")
            _event(
                "generated-uncached",
                key,
                text,
                data,
                {"generation_seconds": generation_seconds},
                profile_id=spec.get("profile_id"),
                inference=inference_report,
                identity=identity,
                voice_spec=spec,
            )
        else:
            _event(
                "refreshed" if selected_mode == "refresh" else "miss",
                key,
                text,
                data,
                manifest,
                profile_id=spec.get("profile_id"),
                inference=inference_report,
                identity=identity,
                voice_spec=spec,
            )
        return data


def _publish(
    root: Path,
    key: str,
    data: bytes,
    *,
    identity: dict | None = None,
    refresh_scope: str | None = None,
    generation_seconds: float = 0.0,
):
    from .dev_jobs import lock

    with lock("speech-cache", wait=True):
        cache_root = work_path("cache", "tts")
        if root.is_symlink() or not root.resolve().is_relative_to(cache_root.resolve()):
            raise OCFError("speech cache destination escapes the cache root")
        previous = _read_verified(root, key)
        history_reserve = 0
        if (
            previous
            and not (root / "history" / f"{previous[1].get('generation_id', '')}.wav").exists()
        ):
            history_reserve = len(previous[0]) + 4096
        used = sum(
            path.lstat().st_size for path in work_path("cache", "tts").rglob("*") if path.is_file()
        )
        if used + len(data) + 4096 + history_reserve > MAX_CACHE_BYTES:
            raise OCFError("speech cache capacity reached")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        (root / ".ocf-cache-owned").write_text(key, encoding="ascii")
        (root / ".ocf-cache-owned").chmod(0o600)
        token = uuid4().hex
        if previous:
            history = root / "history"
            history.mkdir(exist_ok=True, mode=0o700)
            history.chmod(0o700)
            prior_manifest = previous[1]
            prior_name = prior_manifest.get("generation_id") or uuid4().hex
            prior_audio = (root / prior_manifest.get("audio_file", "speech.wav")).read_bytes()
            history_audio = history / f"{prior_name}.wav"
            if not history_audio.exists():
                history_audio_temp = history / f".{prior_name}.wav"
                history_manifest_temp = history / f".{prior_name}.json"
                history_manifest = history / f"{prior_name}.json"
                try:
                    history_audio_temp.write_bytes(prior_audio)
                    history_audio_temp.chmod(0o600)
                    history_manifest_temp.write_text(
                        json.dumps(
                            {
                                **prior_manifest,
                                "generation_id": prior_name,
                                "audio_file": history_audio.name,
                                "preserved_at": datetime.now(UTC).isoformat(),
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    history_manifest_temp.chmod(0o600)
                    os.replace(history_audio_temp, history_audio)
                    os.replace(history_manifest_temp, history_manifest)
                finally:
                    history_audio_temp.unlink(missing_ok=True)
                    history_manifest_temp.unlink(missing_ok=True)
        audio_info = _audio_metadata(data)
        if not audio_info:
            raise OCFError("speech cache publish received invalid PCM")
        wav_temp = root / f".{token}.wav"
        json_temp = root / f".{token}.json"
        manifest_temp = root / f".{token}.manifest"
        manifest = {
            "key": key,
            "sha256": hashlib.sha256(data).hexdigest(),
            "audio_file": "speech.wav",
            "generation_id": token,
            "refresh_scope": refresh_scope,
            "generation_seconds": generation_seconds,
            "created_at": datetime.now(UTC).isoformat(),
            "provenance": _cache_provenance(identity, key),
            **audio_info,
        }
        try:
            wav_temp.write_bytes(data)
            wav_temp.chmod(0o600)
            json_temp.write_text(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8"
            )
            json_temp.chmod(0o600)
            os.replace(wav_temp, root / "speech.wav")
            os.replace(json_temp, manifest_temp)
            os.replace(manifest_temp, root / "manifest.json")
        finally:
            wav_temp.unlink(missing_ok=True)
            json_temp.unlink(missing_ok=True)
            manifest_temp.unlink(missing_ok=True)
        return manifest


def _cache_provenance(identity: dict | None, key: str) -> dict:
    voice = (identity or {}).get("voice", {})
    settings = voice.get("settings", {})
    text = (identity or {}).get("text", "")
    return {
        "cache_fingerprint": key,
        "voice_fingerprint": hashlib.sha256(
            json.dumps(voice, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
        "voice_profile_id": settings.get("profile_id"),
        "backend": settings.get("name"),
        "model_identity": settings.get("model_identity"),
        "reference_sha256": settings.get("reference_sha256"),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "locale": (identity or {}).get("locale"),
        "text_processing_version": (identity or {}).get("text_processing_version"),
        "chunk_context_version": (identity or {}).get("chunk_context_version"),
    }
