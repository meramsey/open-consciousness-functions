"""Opt-in, content-addressed PCM synthesis cache scoped to an OCF render job."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import wave
from contextlib import contextmanager
from contextvars import ContextVar
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from uuid import uuid4

from .paths import work_path
from .utils import OCFError, sha256_of_file

CACHE_VERSION = "ocf-tts-pcm/1"
MAX_CACHE_BYTES = 2 * 1024**3
STATS = {"hit": 0, "miss": 0, "invalidated": 0, "bypassed": 0}
_active: ContextVar[bool | None] = ContextVar("ocf_speech_cache", default=None)


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
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            frames = reader.getnframes()
            return (
                frames > 0
                and reader.getsampwidth() == 2
                and reader.getnchannels() in (1, 2)
                and len(reader.readframes(frames))
                == frames * reader.getsampwidth() * reader.getnchannels()
            )
    except (wave.Error, EOFError, OSError):
        return False


def cached_cue(spec: dict, text: str, render) -> bytes:
    from .progress import advance

    advance("synthesis-cues", detail=spec.get("profile_id") or spec.get("name"))
    if not _active.get():
        STATS["bypassed"] += 1
        return render()
    identity = {
        "voice": voice_identity(spec),
        "text": text,
        "locale": spec.get("locale", spec.get("language")),
    }
    key = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    root = work_path("cache", "tts", key)
    manifest = root / "manifest.json"
    try:
        info = json.loads(manifest.read_text(encoding="utf-8"))
        data = (root / "speech.wav").read_bytes()
        if (
            info["key"] == key
            and info["sha256"] == hashlib.sha256(data).hexdigest()
            and _valid_pcm(data)
        ):
            STATS["hit"] += 1
            return data
    except (OSError, ValueError, KeyError, TypeError):
        pass
    STATS["invalidated" if manifest.exists() else "miss"] += 1
    data = render()
    if not _valid_pcm(data):
        raise OCFError("TTS cache refuses incomplete or invalid PCM output")
    try:
        _publish(root, key, data)
    except (OSError, OCFError):
        # Caching is optional. Keep valid synthesized PCM if storage/cleanup
        # contention prevents a cache write; do not turn it into a render failure.
        STATS["bypassed"] += 1
    return data


def _publish(root: Path, key: str, data: bytes):
    from .dev_jobs import lock

    with lock("speech-cache", wait=True):
        used = sum(
            path.lstat().st_size for path in work_path("cache", "tts").glob("*/*") if path.is_file()
        )
        if used + len(data) + 4096 > MAX_CACHE_BYTES:
            raise OCFError("speech cache capacity reached")
        root.mkdir(parents=True, exist_ok=True)
        (root / ".ocf-cache-owned").write_text(key, encoding="ascii")
        token = uuid4().hex
        wav_temp = root / f".{token}.wav"
        json_temp = root / f".{token}.json"
        try:
            wav_temp.write_bytes(data)
            json_temp.write_text(
                json.dumps({"key": key, "sha256": hashlib.sha256(data).hexdigest()}),
                encoding="utf-8",
            )
            os.replace(wav_temp, root / "speech.wav")
            os.replace(json_temp, root / "manifest.json")
        finally:
            wav_temp.unlink(missing_ok=True)
            json_temp.unlink(missing_ok=True)
