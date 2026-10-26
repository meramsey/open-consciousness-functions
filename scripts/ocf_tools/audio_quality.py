"""Read-only EBU R128 loudness and peak measurements for verified audio."""

from __future__ import annotations

import math
import re
from pathlib import Path

from .paths import workspace_run
from .utils import OCFError, sha256_of_file

_FRAME = re.compile(r"t:\s*(-?\d+(?:\.\d+)?).*?\bS:\s*(-?\d+(?:\.\d+)?)")


def parse_ebur128(log: str) -> dict:
    summary = log.rsplit("Summary:", 1)[-1]
    integrated = re.search(r"\bI:\s*(-?\d+(?:\.\d+)?)\s+LUFS", summary)
    loudness_range = re.search(r"\bLRA:\s*(-?\d+(?:\.\d+)?)\s+LU", summary)
    true_peak = re.search(r"True peak:\s*Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", summary, re.DOTALL)
    if not (integrated and loudness_range and true_peak):
        raise OCFError("FFmpeg EBU R128 output is missing integrated loudness, LRA or true peak")
    short_term = [
        (float(time), float(value))
        for time, value in _FRAME.findall(log.split("Summary:", 1)[0])
        if math.isfinite(float(value))
    ]
    loudest = max(short_term, key=lambda row: row[1]) if short_term else None
    return {
        "standard": "ITU-R BS.1770 / EBU R128 as reported by FFmpeg ebur128",
        "integrated_loudness_lufs": float(integrated.group(1)),
        "loudness_range_lu": float(loudness_range.group(1)),
        "true_peak_dbfs": float(true_peak.group(1)),
        "maximum_short_term_lufs": loudest[1] if loudest else None,
        "maximum_short_term_at_seconds": loudest[0] if loudest else None,
        "short_term_measurement_available": bool(short_term),
        "mastering_target_applied": False,
    }


def measure_ebur128(audio: str | Path) -> dict:
    path = Path(audio).expanduser().resolve()
    if not path.is_file():
        raise OCFError(f"audio quality input does not exist: {path}")
    result = workspace_run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-filter_complex",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise OCFError("FFmpeg EBU R128 measurement failed: " + result.stderr[-1200:])
    version = workspace_run(["ffmpeg", "-version"], capture_output=True, text=True)
    if version.returncode:
        raise OCFError("could not identify FFmpeg used for quality measurements")
    return {
        **parse_ebur128(result.stderr),
        "audio_sha256": sha256_of_file(path),
        "ffmpeg_version": version.stdout.splitlines()[0],
    }
