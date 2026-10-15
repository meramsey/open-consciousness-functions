"""Opt-in, source-neutral streamed final mixing; no preset or DSP mutation.

``load_mix_profile(dict | Path)`` validates and fills schema defaults without
mutating the input. ``mix_master`` accepts the same profile and returns exact
processing/filtergraph/argv metadata. Narration-only mixes are supported;
enabled bed ducking requires a bed. No audio payload is loaded into Python.
The legacy no-profile path remains in audio_build, including its filtergraph.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator

from .paths import SCHEMAS_DIR, ensure_dir, workspace_run
from .utils import OCFError, yaml_safe_load

MIX_TIMEOUT_SECONDS = 3600
LOUDNESS_FILTER = "loudnorm=print_format=json"


def load_mix_profile(profile: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Load a YAML/JSON file or dict, rejecting unknown/nonfinite controls.

    Defaults are defined by the schema, not a mutable default profile file.
    This may be called before creating any render outputs or scratch.
    """
    if isinstance(profile, (str, Path)):
        try:
            value = yaml_safe_load(Path(profile).read_text(encoding="utf-8"))
        except (OSError, ValueError, yaml.YAMLError) as exc:
            raise OCFError(f"cannot read mix profile: {exc}") from exc
    else:
        value = profile
    try:
        # Schema numbers by themselves do not exclude NaN. Round-trip also
        # detaches nested caller objects so defaults never mutate them.
        value = json.loads(json.dumps(value, allow_nan=False))
    except (ValueError, TypeError, OverflowError) as exc:
        raise OCFError("mix profile must contain finite JSON values") from exc
    schema = json.loads((SCHEMAS_DIR / "mix-profile.schema.json").read_text(encoding="utf-8"))
    errors = list(Draft7Validator(schema).iter_errors(value))
    if errors:
        raise OCFError("invalid mix profile: " + "; ".join(error.message for error in errors))
    normalized = {}
    for name, spec in schema["properties"].items():
        if spec.get("type") == "object":
            normalized[name] = {
                key: value.get(name, {}).get(key, field["default"])
                for key, field in spec["properties"].items()
            }
        else:
            normalized[name] = value.get(name, spec["default"])
    return normalized


def _run(argv: list[str], **kwargs):
    try:
        result = workspace_run(argv, timeout=MIX_TIMEOUT_SECONDS, **kwargs)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OCFError(f"ffmpeg mix tool failed: {exc}") from exc
    if result.returncode:
        raise OCFError("ffmpeg mix tool failed: " + result.stderr.decode(errors="replace")[-2000:])
    return result


def measure_loudness(path: Path, *, ffmpeg: str) -> dict[str, Any]:
    """Measure the completed encoded PCM master in a separate streaming pass.

    loudnorm's *input* metrics describe the actual master. Its processed audio
    goes to the null muxer, never back to the master or a Python audio buffer.
    With progress disabled, stderr contains a bounded summary, not per-frame logs.
    Undefined/nonfinite measurements (e.g. silent integrated LUFS) become null.
    """
    argv = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-v",
        "info",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-af",
        LOUDNESS_FILTER,
        "-f",
        "null",
        "-",
    ]
    result = _run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    text = result.stderr.decode(errors="replace")
    try:
        report = json.loads(text[text.rindex("{") : text.rindex("}") + 1])
        metrics = {}
        for name, key in (
            ("integrated_loudness_lufs", "input_i"),
            ("true_peak_dbfs", "input_tp"),
            ("loudness_range_lu", "input_lra"),
            ("threshold_lufs", "input_thresh"),
        ):
            number = float(report[key])
            metrics[name] = number if math.isfinite(number) else None
    except (ValueError, KeyError, TypeError) as exc:
        raise OCFError("ffmpeg did not return final mix loudness measurements") from exc
    return {**metrics, "filtergraph": LOUDNESS_FILTER, "argv": argv}


def mix_master(
    speech_path: Path,
    background_path: Path | None,
    out_path: Path,
    *,
    mix_profile: dict[str, Any] | str | Path,
    sample_rate: int,
    background_gain: float = 0.25,
    speech_gain: float = 1.0,
    speech_gain_windows: list[tuple[float, float, float]] | None = None,
) -> dict[str, Any]:
    """Render an explicitly profiled PCM16 stereo WAV using bounded FFmpeg work.

    Gains/windows precede the detector and are retained verbatim in the receipt.
    The bed is only scaled (and optionally multiplied by a shared duck envelope).
    Final headroom/limiting/fades operate on the sum. Existing composed bed fades
    are not inferred, removed, or repeated here.
    """
    profile = load_mix_profile(mix_profile)
    duck = profile["background_ducking"]
    if duck["enabled"] and background_path is None:
        raise OCFError("mix profile background ducking requires a background stem")
    windows = list(speech_gain_windows or [])
    numbers = [speech_gain, background_gain, *(v for window in windows for v in window)]
    try:
        valid = all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            for v in numbers
        )
    except OverflowError:
        valid = False
    if not valid or speech_gain < 0 or background_gain < 0:
        raise OCFError("mix gains and windows must be finite; linear gains must be nonnegative")
    narration = [f"aformat=channel_layouts=stereo,volume={speech_gain:.6f}"]
    try:
        for start, end, db in windows:
            factor = 10.0 ** (db / 20.0)
            if not math.isfinite(factor):
                raise OverflowError
            narration.append(f"volume={factor:.6f}:enable='between(t,{start:.3f},{end:.3f})'")
    except OverflowError as exc:
        raise OCFError("mix narration window gain is unrepresentable") from exc
    graph = "[0:a]" + ",".join(narration) + "[n];"
    parameters: dict[str, Any] = {
        "profile": profile,
        "speech_gain": speech_gain,
        "background_gain": background_gain if background_path is not None else 0.0,
        "speech_gain_windows": [
            {"start": start, "end": end, "gain_db": db} for start, end, db in windows
        ],
        "headroom_linear_gain": 10.0 ** (-profile["output_headroom_db"] / 20.0),
        "limiter_auto_level": False,
        "limiter_latency_compensation": False,
    }
    if background_path is not None:
        graph += f"[1:a]volume={background_gain:.6f}[b];"
        bed = "[b]"
        if duck["enabled"]:
            threshold = 10.0 ** (duck["threshold_dbfs"] / 20.0)
            graph += (
                "[n]asplit=2[voice][sc];"
                f"[b][sc]sidechaincompress=threshold={threshold}:ratio={duck['ratio']}"
                f":attack={duck['attack_ms']}:release={duck['release_ms']}:knee={duck['knee']}"
                ":mode=downward:link=maximum:detection=rms:level_in=1:level_sc=1:makeup=1:mix=1[d];"
            )
            bed = "[d]"
            parameters["ducking"] = {
                "threshold_linear": threshold,
                "link": "maximum",
                "detection": "rms",
                "mode": "downward",
                "level_in": 1,
                "level_sc": 1,
                "makeup": 1,
                "mix": 1,
            }
        voice = "[voice]" if duck["enabled"] else "[n]"
        graph += voice + bed + "amix=inputs=2:duration=first:normalize=0"
    else:
        graph += "[n]anull"
    if profile["output_headroom_db"]:
        graph += f",volume={parameters['headroom_linear_gain']}"
    limiter = profile["limiter"]
    if limiter["enabled"]:
        graph += (
            f",alimiter=limit={limiter['ceiling']}:attack={limiter['attack_ms']}"
            f":release={limiter['release_ms']}:level=false:latency=false"
        )
    if profile["fade_in_s"] or profile["fade_out_s"]:
        # Read only a WAV header; never read the full narration to locate EOF.
        try:
            with wave.open(str(speech_path), "rb") as reader:
                duration = reader.getnframes() / reader.getframerate()
        except (OSError, wave.Error, EOFError) as exc:
            raise OCFError(f"cannot read narration duration for mix fades: {exc}") from exc
        if profile["fade_in_s"] + profile["fade_out_s"] > duration:
            raise OCFError("final mix fades must not overlap or exceed narration duration")
        parameters["fade_duration_reference_s"] = duration
        if profile["fade_in_s"]:
            graph += f",afade=t=in:st=0:d={profile['fade_in_s']}:curve=tri"
        if profile["fade_out_s"]:
            graph += (
                f",afade=t=out:st={duration - profile['fade_out_s']}"
                f":d={profile['fade_out_s']}:curve=tri"
            )
    graph += "[out]"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise OCFError("ffmpeg is required for an explicit mix profile; install ffmpeg")
    argv = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-v",
        "error",
        "-y",
        "-i",
        str(speech_path),
    ]
    if background_path is not None:
        argv += ["-i", str(background_path)]
    argv += [
        "-filter_complex",
        graph,
        "-map",
        "[out]",
        "-ar",
        str(sample_rate),
        "-ac",
        "2",
        "-c:a",
        "pcm_s16le",
        str(out_path),
    ]
    ensure_dir(out_path.parent)
    _run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    result = {
        "parameters": parameters,
        "filtergraph": graph,
        "argv": argv,
        "timeout_seconds": MIX_TIMEOUT_SECONDS,
        "output": {"sample_rate": sample_rate, "channels": 2, "codec": "pcm_s16le"},
    }
    if profile["measure_loudness"]:
        result["loudness"] = measure_loudness(out_path, ffmpeg=ffmpeg)
    return result
