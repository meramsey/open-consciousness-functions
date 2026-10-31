"""Optional Chatterbox Nano inference worker; importable only in its extra environment."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import sys
import time
import traceback
import wave
from array import array
from pathlib import Path

try:
    import resource
except ImportError:  # Windows Python does not expose getrusage.
    resource = None

INFERENCE_SETTINGS = {
    "temperature": 0.8,
    "top_k": 1000,
    "top_p": 0.95,
    "repetition_penalty": 1.2,
    "min_p": 0.0,
    "cfg_weight": 0.0,
    "exaggeration": 0.0,
    "norm_loudness": True,
}
INFERENCE_PROVENANCE = {
    **INFERENCE_SETTINGS,
    "seed": None,
    "determinism": "not-guaranteed",
}


def synthesize(
    reference: Path,
    text: str,
    output: Path,
    *,
    reference_text_sha256: str,
    device: str = "auto",
    engine=None,
) -> dict:
    if not text.strip():
        raise ValueError("synthesis text must not be empty")
    reference, output = Path(reference), Path(output)
    if not reference.is_file():
        raise FileNotFoundError(f"reference audio not found: {reference}")
    with wave.open(str(reference), "rb") as wav:
        if wav.getnframes() / wav.getframerate() <= 5:
            raise ValueError("Chatterbox Nano requires a reference longer than five seconds")
    try:
        import torch
        from chatterbox.tts_turbo import ChatterboxTurboTTS
    except ImportError as exc:
        raise RuntimeError(
            "Chatterbox Nano import failed in the optional environment; reinstall the documented dependencies: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    selected_device = (
        "cuda"
        if device == "auto" and torch.cuda.is_available()
        else ("cpu" if device == "auto" else device)
    )
    if selected_device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA was requested but is unavailable in the optional voice environment"
        )
    started = time.perf_counter()
    cpu_started = time.process_time()
    model_load_seconds = conditioning_seconds = 0.0
    model_reused = speaker_conditioning_reused = False
    if engine is None:
        model_load_started = time.perf_counter()
        model = ChatterboxTurboTTS.from_pretrained(device=selected_device, nano=True)
        model_load_seconds = time.perf_counter() - model_load_started
        if selected_device == "cuda":
            torch.cuda.reset_peak_memory_stats()
    else:
        (
            model,
            model_reused,
            speaker_conditioning_reused,
            model_load_seconds,
            conditioning_seconds,
        ) = engine.prepare(torch, ChatterboxTurboTTS, selected_device, reference)
    with torch.inference_mode():
        audio = model.generate(
            text,
            **({} if engine is not None else {"audio_prompt_path": str(reference)}),
            **INFERENCE_SETTINGS,
        )
    model_metadata = engine.model_metadata if engine is not None else _model_metadata()
    samples = audio.detach().float().cpu().reshape(-1).numpy()
    if not len(samples) or not all(math.isfinite(float(value)) for value in samples):
        raise RuntimeError("Chatterbox produced empty or non-finite audio")
    pcm, gain, peak_before_gain = _pcm16(samples)
    peak = max((abs(value) for value in pcm), default=0) / 32768
    if not peak:
        raise RuntimeError("Chatterbox produced silent audio")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.parent.chmod(0o700)
    with wave.open(str(output), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(int(model.sr))
        writer.writeframes(pcm.tobytes())
    output.chmod(0o600)
    return {
        "backend": "chatterbox-nano",
        "model_identifier": "ResembleAI/chatterbox-nano",
        **model_metadata,
        "sample_rate": int(model.sr),
        "duration_s": len(samples) / int(model.sr),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "reference_text_sha256": reference_text_sha256,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "sample_peak": peak,
        "peak_before_gain": peak_before_gain,
        "applied_gain": gain,
        "generation_seconds": time.perf_counter() - started,
        "model_load_seconds": model_load_seconds,
        "conditioning_seconds": conditioning_seconds,
        "model_reused": model_reused,
        "speaker_conditioning_reused": speaker_conditioning_reused,
        "cpu_seconds": time.process_time() - cpu_started,
        "peak_rss_bytes": _peak_rss_bytes(),
        "peak_cuda_memory_bytes": (
            torch.cuda.max_memory_allocated() if selected_device == "cuda" else None
        ),
        "device": selected_device,
        "output": str(output),
    }


def _pcm16(samples) -> tuple[array, float, float]:
    peak = max(abs(float(value)) for value in samples)
    gain = min(1.0, 0.98 / peak) if peak else 1.0
    return array("h", (round(float(value) * gain * 32767) for value in samples)), gain, peak


class PersistentEngine:
    """One in-memory Nano model with conditioning isolated by reference checksum."""

    def __init__(self):
        self.device = None
        self.model = None
        self.reference_sha256 = None
        self.model_metadata = {}

    def prepare(self, torch, model_class, device: str, reference: Path):
        load_seconds = conditioning_seconds = 0.0
        reused_model = self.model is not None and self.device == device
        if not reused_model:
            started = time.perf_counter()
            self.model = model_class.from_pretrained(device=device, nano=True)
            load_seconds = time.perf_counter() - started
            self.device = device
            self.reference_sha256 = None
            self.model_metadata = _model_metadata()
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        reference_sha = hashlib.sha256(reference.read_bytes()).hexdigest()
        reused_conditioning = self.reference_sha256 == reference_sha
        if not reused_conditioning:
            started = time.perf_counter()
            self.model.prepare_conditionals(
                str(reference),
                exaggeration=INFERENCE_SETTINGS["exaggeration"],
                norm_loudness=INFERENCE_SETTINGS["norm_loudness"],
            )
            conditioning_seconds = time.perf_counter() - started
            self.reference_sha256 = reference_sha
        return (
            self.model,
            reused_model,
            reused_conditioning,
            load_seconds,
            conditioning_seconds,
        )

    def reset(self, torch=None):
        self.model = None
        self.device = None
        self.reference_sha256 = None
        self.model_metadata = {}
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()


def _model_metadata() -> dict:
    model_files = _model_files()
    model_tree_sha256 = (
        hashlib.sha256(
            json.dumps(model_files, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if model_files
        else None
    )
    try:
        adapter_version = importlib.metadata.version("chatterbox-tts")
    except importlib.metadata.PackageNotFoundError:
        adapter_version = None
    return {
        "model_revision": _cached_model_revision(),
        "model_tree_sha256": model_tree_sha256,
        "model_files": model_files,
        "adapter_version": adapter_version,
        "adapter_revision": _installed_adapter_revision(),
        "environment_packages": _package_versions(),
        "inference_settings": INFERENCE_PROVENANCE,
    }


def _cached_model_revision() -> str | None:
    try:
        from huggingface_hub.constants import HF_HUB_CACHE

        ref = Path(HF_HUB_CACHE) / "models--ResembleAI--chatterbox-nano/refs/main"
        return ref.read_text(encoding="ascii").strip() if ref.is_file() else None
    except (ImportError, OSError):
        return None


def _model_files() -> dict[str, str]:
    try:
        from huggingface_hub.constants import HF_HUB_CACHE

        revision = _cached_model_revision()
        if not revision:
            return {}
        snapshot = Path(HF_HUB_CACHE) / "models--ResembleAI--chatterbox-nano/snapshots" / revision
        return {
            path.relative_to(snapshot).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(snapshot.rglob("*"))
            if path.is_file()
        }
    except (ImportError, OSError):
        return {}


def _installed_adapter_revision() -> str | None:
    try:
        direct_url = importlib.metadata.distribution("chatterbox-tts").read_text("direct_url.json")
        if direct_url:
            return json.loads(direct_url)["vcs_info"]["commit_id"]
        package = importlib.util.find_spec("chatterbox")
        if package and package.origin:
            return hashlib.sha256(Path(package.origin).read_bytes()).hexdigest()
        return None
    except (KeyError, TypeError, ValueError, importlib.metadata.PackageNotFoundError):
        return None


def _package_versions() -> dict[str, str | None]:
    packages = {}
    for name in ("torch", "torchaudio", "transformers", "diffusers", "resemble-perth"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return packages


def _peak_rss_bytes() -> int | None:
    if not resource:
        return None
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def _run_request(request: dict, engine=None) -> dict:
    return synthesize(
        Path(request["reference"]),
        request["text"],
        Path(request["output"]),
        reference_text_sha256=request["reference_text_sha256"],
        device=request.get("device", "auto"),
        engine=engine,
    )


def worker_main() -> int:
    engine = PersistentEngine()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            import torch
    except ImportError as exc:
        print(json.dumps({"error": f"RuntimeError: {exc}"}), flush=True)
        return 1
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                response = _run_request(request, engine)
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            engine.reset(torch)
            response = {"error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(response, ensure_ascii=False), flush=True)
    engine.reset(torch)
    return 0


def main() -> int:
    if "--worker" in sys.argv[1:]:
        return worker_main()
    request = json.load(sys.stdin)
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = _run_request(request)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
