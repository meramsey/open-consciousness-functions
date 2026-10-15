"""Independent, non-destructive recording preparation with verified local receipts.

``process_recording`` returns (PCM16 RIFF/WAV bytes, JSON-compatible report).
``inspect_recording`` measures native PCM or FFmpeg-decoded floating-point audio.
No CLI/session wiring or narration approval is implied. PCM WAV (8/16/24/32-bit)
inspection and PCM16/channel-only processing need no external tools. Resampling,
compressed/float decoding, highpass, compression and loudness use optional FFmpeg
and ffprobe. Resampling uses swresample, no dither, and one codec/filter thread.

Measurements use sample peaks (not true peaks), per-channel population RMS/DC,
frame silence at -60 dBFS on ALL channels, and Pearson stereo correlation. The
10th-percentile non-overlapping 50ms-window RMS is a signal-level estimate, NOT
room noise, SNR, speech recognition, listening approval, or a quality score.
Zero logarithms/undefined correlation are represented by null, never NaN/Inf.
Audio is held in memory; input and decoded PCM each have a 256 MiB ceiling.
Decoded and intermediate sample magnitudes are limited to 1e6 (120 dBFS);
larger or nonfinite values raise OCFError before measurement/processing math.
Unrepresentable peak-normalization gains also raise OCFError, including for
subnormal signals; silence remains valid and is never amplified into a signal.
Cache receipts verify both immutable generation files before reuse; publishing
the small manifest is atomic even between concurrent readers/writers. Superseded
generations are retained for diagnostics rather than deleted under readers.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import wave
from array import array
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft7Validator

from .paths import (
    SCHEMAS_DIR,
    cleanup_workspace_temp,
    record_workspace_failure,
    work_path,
    workspace_run,
    workspace_temp_directory,
)
from .utils import OCFError

MAX_BYTES = 256 * 1024**2
MAX_SAMPLE_MAGNITUDE = 1e6
TIMEOUT = 120
DEMUXERS = {".wav": "wav", ".flac": "flac", ".mp3": "mp3", ".m4a": "mov"}
DEFAULTS = {
    "remove_dc": False,
    "gain_db": 0,
    "fade_in_s": 0,
    "fade_out_s": 0,
    "measure_loudness": False,
}
NESTED_DEFAULTS = {
    "trim_silence": {"threshold_dbfs": -60, "leading": True, "trailing": True},
    "compression": {"threshold_dbfs": -18, "ratio": 2, "attack_ms": 20, "release_ms": 200},
    "loudness": {"integrated_lufs": -23, "true_peak_dbfs": -2, "range_lu": 7},
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _normalize(processing: dict | None) -> dict:
    value = {} if processing is None else processing
    schema = json.loads((SCHEMAS_DIR / "recording-processing.schema.json").read_text())
    errors = list(Draft7Validator(schema).iter_errors(value))
    try:
        _json(value)  # JSON Schema's number type alone does not exclude NaN/infinity.
    except (ValueError, TypeError) as exc:
        raise OCFError("recording processing must contain finite JSON values") from exc
    if errors:
        raise OCFError("invalid recording processing: " + "; ".join(e.message for e in errors))
    normalized = {**DEFAULTS, **value}
    for name, defaults in NESTED_DEFAULTS.items():
        if name in value:
            normalized[name] = {**defaults, **value[name]}
    return normalized


def _source(source: Path) -> tuple[bytes, str]:
    if source.suffix.lower() not in DEMUXERS:
        raise OCFError("recording format must be WAV, FLAC, MP3 or M4A")
    try:
        with source.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise OCFError(f"cannot read recording {source}: {exc}") from exc
    if not data or len(data) > MAX_BYTES:
        raise OCFError("recording is empty or exceeds the 256 MiB input limit")
    return data, _sha(data)


def _native(data: bytes):
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            width, channels, rate, frames = (
                reader.getsampwidth(),
                reader.getnchannels(),
                reader.getframerate(),
                reader.getnframes(),
            )
            raw = reader.readframes(frames)
    except (wave.Error, EOFError):
        return None
    if channels not in (1, 2) or not 8000 <= rate <= 192000:
        raise OCFError("recordings require mono/stereo and 8000..192000 Hz")
    if width not in (1, 2, 3, 4) or not frames or len(raw) != frames * channels * width:
        raise OCFError("empty, truncated or unsupported PCM WAV")
    if len(raw) // width * 8 > MAX_BYTES:
        raise OCFError("decoded recording exceeds the 256 MiB limit")
    if width == 1:
        samples = array("d", ((v - 128) / 128 for v in raw))
    else:
        scale = 2 ** (width * 8 - 1)
        samples = array(
            "d",
            (
                int.from_bytes(raw[i : i + width], "little", signed=True) / scale
                for i in range(0, len(raw), width)
            ),
        )
    return (
        samples,
        rate,
        channels,
        {
            "container": "wav",
            "codec": f"pcm_{'u8' if width == 1 else 's' + str(width * 8) + 'le'}",
            "bits_per_sample": width * 8,
        },
    )


def _run(argv: list[str], data: bytes | None = None, *, timeout: int = TIMEOUT):
    try:
        result = workspace_run(argv, input=data, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OCFError(f"recording tool failed: {exc}") from exc
    if result.returncode:
        raise OCFError("recording tool failed: " + result.stderr.decode(errors="replace")[-2000:])
    return result


def _tools() -> dict:
    tools = {}
    for name in ("ffmpeg", "ffprobe"):
        executable = shutil.which(name)
        if not executable:
            raise OCFError(
                "install optional FFmpeg (ffmpeg and ffprobe) for this recording operation"
            )
        version = _run([executable, "-version"], timeout=10).stdout.decode(errors="replace")
        tools[name] = {
            "executable": executable,
            "version": version,
            "sha256": _sha(Path(executable).read_bytes()),
        }
    return tools


def _base(tools: dict) -> list[str]:
    return [
        tools["ffmpeg"]["executable"],
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-threads",
        "1",
        "-filter_threads",
        "1",
        "-protocol_whitelist",
        "file,pipe",
    ]


def _float_bytes(samples: array) -> bytes:
    _validate_samples(samples)
    result = array("d", samples)
    if sys.byteorder != "little":
        result.byteswap()
    return result.tobytes()


def _floats(data: bytes, channels: int) -> array:
    if not data or len(data) > MAX_BYTES or len(data) % (8 * channels):
        raise OCFError("invalid or oversized decoded PCM")
    result = array("d")
    result.frombytes(data)
    if sys.byteorder != "little":
        result.byteswap()
    _validate_samples(result)
    return result


def _validate_samples(samples: array) -> None:
    """Bound arithmetic inputs, including filter results and PCM quantization."""
    for value in samples:
        if not math.isfinite(value):
            raise OCFError("recording contains nonfinite samples")
        if abs(value) > MAX_SAMPLE_MAGNITUDE:
            raise OCFError(
                "recording sample magnitude exceeds supported limit of "
                f"+/-{MAX_SAMPLE_MAGNITUDE:g}; reduce the source level or processing gain"
            )


def _decode(data: bytes, suffix: str, tools: dict):
    scratch = workspace_temp_directory("ocf-recording-decode-")
    try:
        path = scratch / ("input" + suffix)
        path.write_bytes(data)  # Snapshot exactly the bytes that were hashed; never modify source.
        probe = _run(
            [
                tools["ffprobe"]["executable"],
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-f",
                DEMUXERS[suffix],
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ]
        )
        info = json.loads(probe.stdout)
        streams = [s for s in info["streams"] if s["codec_type"] == "audio"]
        if len(streams) != 1:
            raise OCFError("recording must have exactly one audio stream")
        stream = streams[0]
        channels, rate = int(stream["channels"]), int(stream["sample_rate"])
        if channels not in (1, 2) or not 8000 <= rate <= 192000:
            raise OCFError("recordings require mono/stereo and 8000..192000 Hz")
        argv = _base(tools) + [
            "-f",
            DEMUXERS[suffix],
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-vn",
            "-f",
            "f64le",
            "-c:a",
            "pcm_f64le",
            "-fs",
            str(MAX_BYTES + 1),
            "pipe:1",
        ]
        samples = _floats(_run(argv).stdout, channels)
        fmt = {
            "container": info["format"]["format_name"],
            "codec": stream["codec_name"],
            "bits_per_sample": stream.get("bits_per_raw_sample")
            or stream.get("bits_per_sample")
            or None,
        }
    except Exception as exc:
        record_workspace_failure(scratch.name, f"recording decode: {exc}; retained {scratch}")
        raise
    cleanup_workspace_temp(scratch)
    return samples, rate, channels, fmt


def _db(value: float) -> float | None:
    return 20 * math.log10(value) if value > 0 else None


def _rms(values: array) -> float:
    """Scale before squaring so quiet/subnormal signals retain measurable RMS."""
    peak = max(abs(v) for v in values)
    if not peak:
        return 0.0
    return peak * math.sqrt(math.fsum((v / peak) ** 2 for v in values) / len(values))


def _measure(samples: array, rate: int, channels: int, fmt: dict) -> dict:
    _validate_samples(samples)
    frames = len(samples) // channels
    stats = []
    for channel in range(channels):
        values = samples[channel::channels]
        rms = _rms(values)
        peak = max(abs(v) for v in values)
        bits = fmt.get("bits_per_sample")
        ceiling = (
            1 - 2 ** (1 - int(bits))
            if bits
            and (
                fmt["codec"] == "flac"
                or (fmt["codec"].startswith("pcm_") and "f" not in fmt["codec"])
            )
            else 1
        )
        clipped = sum(v <= -1 or v >= ceiling for v in values)
        stats.append(
            {
                "peak": peak,
                "peak_dbfs": _db(peak),
                "rms": rms,
                "rms_dbfs": _db(rms),
                "dc_offset": math.fsum(values) / frames,
                "clipped_samples": clipped,
                "clipped_fraction": clipped / frames,
            }
        )
    silent = sum(
        all(abs(samples[i + c]) <= 0.001 for c in range(channels))
        for i in range(0, len(samples), channels)
    )
    window = max(1, round(rate * 0.05)) * channels
    windows = [_rms(samples[i : i + window]) for i in range(0, len(samples), window)]
    windows.sort()
    estimate = windows[math.floor((len(windows) - 1) * 0.1)]
    correlation = imbalance = None
    if channels == 2:
        left, right = samples[::2], samples[1::2]
        # Normalize channels independently before centering or multiplying.
        # sqrt(aa * bb) underflows even for ordinary finite 1e-100 signals.
        left_peak, right_peak = stats[0]["peak"], stats[1]["peak"]
        left = array("d", (v / left_peak for v in left)) if left_peak else left
        right = array("d", (v / right_peak for v in right)) if right_peak else right
        a, b = math.fsum(left) / frames, math.fsum(right) / frames
        aa = math.fsum((v - a) ** 2 for v in left)
        bb = math.fsum((v - b) ** 2 for v in right)
        if aa and bb:
            correlation = max(
                -1.0,
                min(
                    1.0,
                    math.fsum((x - a) * (y - b) for x, y in zip(left, right))
                    / (math.sqrt(aa) * math.sqrt(bb)),
                ),
            )
        if stats[0]["rms"] and stats[1]["rms"]:
            # Subtract logarithms instead of forming an overflowing level ratio.
            imbalance = _db(stats[0]["rms"]) - _db(stats[1]["rms"])
    return {
        "frames": frames,
        "duration_s": frames / rate,
        "sample_rate": rate,
        "channels": channels,
        "format": fmt,
        "per_channel": stats,
        "sample_peak": max(s["peak"] for s in stats),
        "clipping_definition": "samples at/beyond integer full-scale rails; decoded lossy/float samples at/beyond +/-1; not proof of source waveform clipping",
        "silence_threshold_dbfs": -60,
        "silent_frames": silent,
        "silence_fraction": silent / frames,
        "channel_imbalance_db_left_minus_right": imbalance,
        "stereo_correlation": correlation,
        "noise_estimate": {
            "method": "10th-percentile 50ms non-overlapping window RMS; signal-level proxy, not measured room noise or SNR",
            "window_s": 0.05,
            "percentile": 10,
            "rms": estimate,
            "dbfs": _db(estimate),
        },
        "integrated_loudness_lufs": None,
    }


def _filter(
    samples: array, rate: int, channels: int, tools: dict, filters: list[str], output_rate: int
):
    argv = _base(tools) + [
        "-f",
        "f64le",
        "-ar",
        str(rate),
        "-ac",
        str(channels),
        "-i",
        "pipe:0",
        "-af",
        ",".join(filters),
        "-ar",
        str(output_rate),
        "-ac",
        str(channels),
        "-c:a",
        "pcm_f64le",
        "-f",
        "f64le",
        "-fs",
        str(MAX_BYTES + 1),
        "pipe:1",
    ]
    return _floats(_run(argv, _float_bytes(samples)).stdout, channels), argv


def _loudness(samples: array, rate: int, channels: int, tools: dict):
    argv = _base(tools)
    argv[argv.index("error")] = "info"
    argv += [
        "-f",
        "f64le",
        "-ar",
        str(rate),
        "-ac",
        str(channels),
        "-i",
        "pipe:0",
        "-af",
        "loudnorm=I=-23:TP=-2:LRA=7:print_format=json",
        "-f",
        "null",
        "-",
    ]
    text = _run(argv, _float_bytes(samples)).stderr.decode(errors="replace")
    try:
        value = float(json.loads(text[text.rfind("{") : text.rfind("}") + 1])["input_i"])
    except (ValueError, KeyError) as exc:
        raise OCFError("FFmpeg did not return integrated loudness measurements") from exc
    return value if math.isfinite(value) else None, argv


def _pcm(samples: array, rate: int, channels: int) -> bytes:
    _validate_samples(samples)
    pcm = array("h", (max(-32768, min(32767, round(v * 32768))) for v in samples))
    if sys.byteorder != "little":
        pcm.byteswap()
    out = io.BytesIO()
    with wave.open(out, "wb") as writer:
        writer.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
        writer.writeframes(pcm.tobytes())
    return out.getvalue()


def inspect_recording(source: Path) -> dict:
    """Inspect original bytes without effects, cache writes or loudness subprocesses."""
    source = Path(source)
    data, sha = _source(source)
    native = _native(data)
    tools = {} if native is not None else _tools()
    samples, rate, channels, fmt = native or _decode(data, source.suffix.lower(), tools)
    return {
        "input_sha256": sha,
        "original": _measure(samples, rate, channels, fmt),
        "decoder": tools or {"name": "stdlib.wave"},
    }


def _cache_read(root: Path, identity: dict, key: str):
    try:
        manifest = json.loads((root / "manifest.json").read_bytes())
        generation = manifest["generation"]
        if (
            not isinstance(generation, str)
            or len(generation) != 32
            or any(c not in "0123456789abcdef" for c in generation)
        ):
            return None
        audio = (root / f"{generation}.wav").read_bytes()
        report_bytes = (root / f"{generation}.json").read_bytes()
        if (
            _sha(audio) != manifest["audio_sha256"]
            or _sha(report_bytes) != manifest["report_sha256"]
        ):
            return None
        report = json.loads(report_bytes)
        native = _native(audio)
        if (
            report["cache_identity"] != identity
            or report["cache_key"] != key
            or report["processed_sha256"] != _sha(audio)
            or native is None
            or native[1:3] != (identity["sample_rate"], identity["channels"])
            or native[3]["bits_per_sample"] != 16
        ):
            return None
        measured = _measure(*native)
        measured["integrated_loudness_lufs"] = report["processed"]["integrated_loudness_lufs"]
        if measured != report["processed"]:
            return None
        report["cache_hit"] = True
        return audio, report
    except (OSError, ValueError, KeyError, TypeError, OCFError):
        return None


def _publish(root: Path, audio: bytes, report: dict):
    root.mkdir(parents=True, exist_ok=True)
    generation = uuid4().hex
    report_bytes = _json(report)
    (root / ".ocf-cache-owned").write_text(report["cache_key"], encoding="ascii")
    # Immutable generation files are invisible to readers until the atomic pointer swap.
    (root / f"{generation}.wav").write_bytes(audio)
    (root / f"{generation}.json").write_bytes(report_bytes)
    temporary = root / f".{generation}.manifest"
    temporary.write_bytes(
        _json(
            {
                "generation": generation,
                "audio_sha256": _sha(audio),
                "report_sha256": _sha(report_bytes),
            }
        )
    )
    os.replace(temporary, root / "manifest.json")


def process_recording(
    source: Path,
    *,
    sample_rate=44100,
    channels=1,
    processing: dict | None = None,
    expected_sha256: str | None = None,
) -> tuple[bytes, dict]:
    """Prepare a recording; verify expected SHA before decoding or cache lookup.

    ``channels=2`` preserves stereo (mono is duplicated); ``channels=1`` explicitly
    averages L/R without hidden loudness compensation. Config keys/defaults and
    bounds are specified by recording-processing.schema.json. Effects never edit
    the source. Report paths are local private cache paths, not release assets.
    """
    config = _normalize(processing)
    if type(sample_rate) is not int or not 8000 <= sample_rate <= 192000:
        raise OCFError("sample_rate must be an integer in 8000..192000")
    if type(channels) is not int or channels not in (1, 2):
        raise OCFError("channels must be 1 or 2")
    if expected_sha256 is not None and (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(c not in "0123456789abcdefABCDEF" for c in expected_sha256)
    ):
        raise OCFError("expected_sha256 must be a 64-digit hexadecimal SHA256")
    source = Path(source)
    data, sha = _source(source)
    if expected_sha256 is not None and sha != expected_sha256.lower():
        raise OCFError("recording checksum mismatch")
    native = _native(data)
    needs_tools = (
        native is None
        or native[1] != sample_rate
        or any(k in config for k in ("highpass_hz", "compression", "loudness"))
        or config["measure_loudness"]
    )
    tools = _tools() if needs_tools else {}
    identity = {
        "version": "ocf-recording/1",
        "input_sha256": sha,
        "input_suffix": source.suffix.lower(),
        "sample_rate": sample_rate,
        "channels": channels,
        "processing": config,
        "tools": tools,
        "python": platform.python_version(),
        "runtime_platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "implementation": platform.python_implementation(),
        },
        "byteorder": sys.byteorder,
        "code_sha256": _sha(Path(__file__).read_bytes()),
        "workspace_code_sha256": _sha(Path(__file__).with_name("paths.py").read_bytes()),
        "schema_sha256": _sha((SCHEMAS_DIR / "recording-processing.schema.json").read_bytes()),
    }
    key = _sha(_json(identity))
    root = work_path("cache", "recordings", key)
    cached = _cache_read(root, identity, key)
    if cached is not None:
        return cached
    samples, rate, count, fmt = native or _decode(data, source.suffix.lower(), tools)
    if math.ceil(len(samples) / count * sample_rate / rate) * channels * 8 > MAX_BYTES:
        raise OCFError("converted recording exceeds the 256 MiB decoded limit")
    original = _measure(samples, rate, count, fmt)
    argv, filters = [], []
    if config["measure_loudness"] or "loudness" in config:
        original["integrated_loudness_lufs"], command = _loudness(samples, rate, count, tools)
        argv.append(command)
    if count != channels:
        samples = (
            array("d", ((samples[i] + samples[i + 1]) / 2 for i in range(0, len(samples), 2)))
            if channels == 1
            else array("d", (v for s in samples for v in (s, s)))
        )
    if rate != sample_rate:
        chain = [f"aresample={sample_rate}:resampler=swr:dither_method=none"]
        samples, command = _filter(samples, rate, channels, tools, chain, sample_rate)
        filters.extend(chain)
        argv.append(command)
    rate = sample_rate
    if config["remove_dc"]:
        means = [
            math.fsum(samples[c::channels]) / (len(samples) // channels) for c in range(channels)
        ]
        samples = array("d", (v - means[i % channels] for i, v in enumerate(samples)))
    trimmed = {"leading_frames": 0, "trailing_frames": 0}
    if "trim_silence" in config:
        trim = config["trim_silence"]
        threshold = 10 ** (trim["threshold_dbfs"] / 20)
        start, end = 0, len(samples)
        if trim["leading"]:
            while start < end and all(
                abs(v) <= threshold for v in samples[start : start + channels]
            ):
                start += channels
        if trim["trailing"]:
            while end > start and all(abs(v) <= threshold for v in samples[end - channels : end]):
                end -= channels
        if start == end:
            raise OCFError("explicit silence trim would remove the entire recording")
        trimmed = {
            "leading_frames": start // channels,
            "trailing_frames": (len(samples) - end) // channels,
        }
        samples = samples[start:end]
    chain = []
    if "highpass_hz" in config:
        if config["highpass_hz"] >= rate / 2:
            raise OCFError("highpass must be below Nyquist")
        chain.append(f"highpass=f={config['highpass_hz']}:p=2")
    # Keep gain before compression, without quantizing/clipping intermediate samples.
    if chain:
        samples, command = _filter(samples, rate, channels, tools, chain, rate)
        filters.extend(chain)
        argv.append(command)
    gain = 10 ** (config["gain_db"] / 20)
    samples = array("d", (v * gain for v in samples))
    _validate_samples(samples)
    chain = []
    if "compression" in config:
        c = config["compression"]
        chain.append(
            f"acompressor=threshold={10 ** (c['threshold_dbfs'] / 20)}:ratio={c['ratio']}:attack={c['attack_ms']}:release={c['release_ms']}:makeup=1"
        )
    if "loudness" in config:
        loudness = config["loudness"]
        chain.append(
            f"loudnorm=I={loudness['integrated_lufs']}:TP={loudness['true_peak_dbfs']}:LRA={loudness['range_lu']}:linear=false"
        )
    if chain:
        samples, command = _filter(samples, rate, channels, tools, chain, rate)
        filters.extend(chain)
        argv.append(command)
    peak_gain = 1.0
    if "peak_target_dbfs" in config:
        peak = max(abs(v) for v in samples)
        peak_gain = 10 ** (config["peak_target_dbfs"] / 20) / peak if peak else 1.0
        if not math.isfinite(peak_gain):
            raise OCFError(
                "peak normalization gain exceeds supported floating-point range; "
                "increase the source level or disable peak normalization"
            )
    frames = len(samples) // channels
    fade_in, fade_out = round(config["fade_in_s"] * rate), round(config["fade_out_s"] * rate)
    if fade_in > frames or fade_out > frames:
        raise OCFError("fade duration exceeds processed recording duration")
    pre_quantization_clipped = 0
    for i in range(len(samples)):
        frame = i // channels
        scale = min(1.0, frame / max(1, fade_in - 1)) if fade_in else 1.0
        if fade_out:
            scale *= min(1.0, (frames - 1 - frame) / max(1, fade_out - 1))
        samples[i] *= peak_gain * scale
        pre_quantization_clipped += samples[i] < -1 or samples[i] > 32767 / 32768
    audio = _pcm(samples, rate, channels)
    processed = _measure(*_native(audio))
    if config["measure_loudness"] or "loudness" in config:
        processed["integrated_loudness_lufs"], command = _loudness(
            _native(audio)[0], rate, channels, tools
        )
        argv.append(command)
    report = {
        "input_sha256": sha,
        "processed_sha256": _sha(audio),
        "original": original,
        "processed": processed,
        "processing": config,
        "filter_argv": argv,
        "filters": filters,
        "processing_order": [
            "channel_conversion",
            "resample",
            "remove_dc",
            "trim_silence",
            "highpass_hz",
            "gain_db",
            "compression",
            "loudness",
            "peak_target_dbfs",
            "fades",
            "pcm16_quantization",
        ],
        "channel_conversion": "unchanged"
        if count == channels
        else ("arithmetic_mean_L_R" if channels == 1 else "duplicate_mono"),
        "trimmed": trimmed,
        "peak_gain": peak_gain,
        "pre_quantization_clipped_samples": pre_quantization_clipped,
        "original_preserved": True,
        "cache_key": key,
        "cache_identity": identity,
        "cache_path": str(root),
        "cache_hit": False,
        "warnings": ["PCM16 saturation occurred"] if pre_quantization_clipped else [],
    }
    _publish(root, audio, report)
    return audio, report
