"""Bounded real audio-stage benchmark using public text and generated signals only.

This is not a production session/controller or a listening-approved edition.
It calls OCF narration, PCM mixing and encoding APIs, retaining isolated fixtures.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import time
import wave
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from ocf_tools import audio_build, speech_cache, voice
from ocf_tools.bulk_render import _batch_resource_state
from ocf_tools.paths import REPO_ROOT, work_root, workspace_run
from ocf_tools.utils import OCFError, sha256_of_file, write_bytes_atomic, write_text_atomic

COMMON = "This is a public synthetic audio benchmark."


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def make_bed(path, seconds):
    """A synthetic stereo AM signal, NOT an approved Focus/Farfield profile."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise OCFError("public audio benchmark requires ffmpeg and espeak-ng")
    signal = (
        "aevalsrc=0.02*sin(2*PI*220*t)*(0.7+0.3*sin(2*PI*5*t))"
        "|0.02*sin(2*PI*224*t)*(0.7+0.3*sin(2*PI*5*t))"
        f":s=22050:d={seconds}"
    )
    result = workspace_run(
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            signal,
            "-threads",
            "1",
            "-c:a",
            "pcm_s16le",
            str(path),
        ],
        capture_output=True,
        timeout=60,
    )
    if result.returncode:
        raise OCFError("synthetic DSP generation failed")


def render_fixture(root, identity, config, *, fail=False):
    job = root / f"fixture-{identity:03}"
    job.mkdir(exist_ok=True)
    key = digest({"identity": identity, **config})
    inputs = job / "input.json"
    expected = {"key": key}
    if inputs.exists():
        if json.loads(inputs.read_text()) != expected:
            raise OCFError("fixture input identity collision")
    else:
        write_text_atomic(inputs, json.dumps(expected), overwrite=False)
    receipt = job / "receipt.json"
    if receipt.exists():
        data = json.loads(receipt.read_text())
        if data["key"] != key or any(
            sha256_of_file(job / name) != data["hashes"][name]
            for name in ("speech.wav", "master.wav", "master.flac", "bundle.zip")
        ):
            raise OCFError("fixture resume integrity failure")
        return {"identity": identity, "reused": True, "hashes": data["hashes"]}
    stages = {}
    document = {
        "schema_version": "1.0",
        "title": "Public synthetic benchmark",
        "timeline": [
            {"id": "shared", "at": 0, "text": COMMON},
            {
                "id": "unique",
                "at": config["seconds"] / 2,
                "text": f"Public synthetic sample number {identity}.",
            },
        ],
    }
    started = time.perf_counter()
    with speech_cache.enabled(), speech_cache.policy("auto") as (stats, _events, _scope):
        voice.render_narration(document, job / "speech.wav", backend="espeak-ng", sample_rate=22050)
    stages["synthesis_and_narration"] = time.perf_counter() - started
    started = time.perf_counter()
    audio_build.mix(
        job / "speech.wav",
        root / "bed.wav",
        job / "master.wav",
        background_gain=0.25,
        speech_gain=1.0,
        speech_gain_windows=[(1.0, 2.0, -3.0)],
    )
    stages["mixing"] = time.perf_counter() - started
    started = time.perf_counter()
    audio_build._encode(job / "master.wav", "flac", job / "master.flac")
    stages["encoding"] = time.perf_counter() - started
    if fail:
        raise OCFError("injected benchmark interruption before publication")
    started = time.perf_counter()
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_STORED) as archive:
        info = zipfile.ZipInfo("master.flac", date_time=(1980, 1, 1, 0, 0, 0))
        info.external_attr = 0o600 << 16
        archive.writestr(info, (job / "master.flac").read_bytes())
    write_bytes_atomic(job / "bundle.zip", payload.getvalue())
    stages["fixture_packaging"] = time.perf_counter() - started
    started = time.perf_counter()
    with zipfile.ZipFile(job / "bundle.zip") as archive:
        if archive.testzip() is not None:
            raise OCFError("fixture bundle validation failed")
    decoded = workspace_run(
        [
            shutil.which("ffmpeg"),
            "-v",
            "error",
            "-i",
            str(job / "master.flac"),
            "-f",
            "s16le",
            "-c:a",
            "pcm_s16le",
            "-",
        ],
        capture_output=True,
        timeout=60,
    )
    with wave.open(str(job / "master.wav")) as reader:
        pcm = reader.readframes(reader.getnframes())
    if decoded.returncode or decoded.stdout != pcm:
        raise OCFError("fixture lossless encoding changed PCM samples")
    hashes = {
        name: sha256_of_file(job / name)
        for name in ("speech.wav", "master.wav", "master.flac", "bundle.zip")
    }
    stages["validation_and_hashing"] = time.perf_counter() - started
    write_text_atomic(
        receipt, json.dumps({"key": key, "hashes": hashes}, sort_keys=True), overwrite=False
    )
    return {
        "identity": identity,
        "reused": False,
        "hashes": hashes,
        "stages_seconds": stages,
        "speech_cache": {key: stats[key] for key in speech_cache.STAT_KEYS},
    }


def batch(root, config, count, workers, *, fail_id=None):
    started, cpu = time.perf_counter(), time.process_time()

    def run(identity):
        try:
            return render_fixture(root, identity, config, fail=identity == fail_id)
        except OCFError as error:
            if identity != fail_id or "injected benchmark interruption" not in str(error):
                raise
            return {"identity": identity, "injected_failure": True}

    if workers == 1:
        rows = [run(identity) for identity in range(count)]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(run, range(count)))
    wall = time.perf_counter() - started
    return {
        "wall_seconds": wall,
        "parent_cpu_seconds": time.process_time() - cpu,
        "sessions_per_hour": 3600 * count / wall,
        "rows": rows,
    }


def benchmark(output, *, sessions, seconds, worker_counts, source_sha):
    base = work_root().resolve()
    output = output.resolve()
    if output == base or not output.is_relative_to(base):
        raise OCFError("benchmark output must be a dedicated directory inside OCF_WORK_DIR")
    marker = output / ".public-synthetic-benchmark-family"
    if output.exists() and not marker.is_file():
        raise OCFError("refusing an existing unmarked benchmark output directory")
    output.mkdir(parents=True, exist_ok=True)
    if not marker.exists():
        write_text_atomic(marker, "public-synthetic-audio-v1", overwrite=False)
    root = output / uuid4().hex
    root.mkdir()
    original = os.environ.get("OCF_WORK_DIR")
    os.environ["OCF_WORK_DIR"] = str(root / "work")
    work_root().mkdir()
    try:
        config = {
            "format": "public-synthetic-audio-v1",
            "source_sha": source_sha,
            "seconds": seconds,
            "sample_rate": 22050,
            "backend": "espeak-ng",
        }
        cases = []
        for requested in worker_counts:
            case = root / f"workers-{requested}"
            case.mkdir()
            os.environ["OCF_WORK_DIR"] = str(case / "work")
            work_root().mkdir()
            resources = _batch_resource_state(requested)
            workers = resources["selected_workers"]
            dsp_started = time.perf_counter()
            make_bed(case / "bed.wav", seconds)
            dsp_seconds = time.perf_counter() - dsp_started
            cold = batch(case, config, sessions, workers)
            cold["wall_including_shared_dsp_seconds"] = cold["wall_seconds"] + dsp_seconds
            warm_case = case / "warm"
            warm_case.mkdir()
            shutil.copyfile(case / "bed.wav", warm_case / "bed.wav")
            warm = batch(warm_case, config, sessions, workers)
            resume = batch(warm_case, config, sessions, workers)
            recovery_case = case / "recovery"
            recovery_case.mkdir()
            shutil.copyfile(case / "bed.wav", recovery_case / "bed.wav")
            interrupted = batch(recovery_case, config, sessions, workers, fail_id=0)
            recovered = batch(recovery_case, config, sessions, workers)
            expected = [row["hashes"] for row in cold["rows"]]
            if any(
                [row["hashes"] for row in phase["rows"]] != expected
                for phase in (warm, resume, recovered)
            ):
                raise OCFError("cold/warm/resume/recovery fixture bytes differ")
            cases.append(
                {
                    "requested_workers": requested,
                    "resources": resources,
                    "dsp_generation_seconds": dsp_seconds,
                    "cold": cold,
                    "warm": warm,
                    "verified_resume": resume,
                    "injected_interruption": interrupted,
                    "recovery": recovered,
                    "all_artifacts_byte_exact": True,
                }
            )
        return {
            "source_sha": source_sha,
            "sessions": sessions,
            "seconds": seconds,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "tool_sha256": {
                name: sha256_of_file(Path(shutil.which(name))) for name in ("espeak-ng", "ffmpeg")
            },
            "scope": "real public eSpeak TTS, OCF narration/PCM mix/FLAC; synthetic AM bed; fixture ZIP only",
            "not_measured": ["private voices", "GPU", "Farfield", "production release packaging"],
            "cases": cases,
            "retained_fixture_bytes": sum(p.stat().st_size for p in root.rglob("*") if p.is_file()),
        }
    finally:
        if original is None:
            os.environ.pop("OCF_WORK_DIR", None)
        else:
            os.environ["OCF_WORK_DIR"] = original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sessions", type=int, default=4)
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    if (
        not 1 <= args.sessions <= 58
        or not 6 <= args.seconds <= 120
        or any(w not in (1, 2, 4) for w in args.workers)
        or len(set(args.workers)) != len(args.workers)
    ):
        parser.error("sessions 1..58, seconds 6..120, unique workers from 1/2/4 required")
    if args.profile and args.workers != [1]:
        parser.error("profiling requires --workers 1 so worker CPU is actually instrumented")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT):
        raise OCFError("commit the benchmark source before measuring an exact SHA")
    profile = cProfile.Profile()
    if args.profile:
        profile.enable()
    result = benchmark(
        args.output,
        sessions=args.sessions,
        seconds=args.seconds,
        worker_counts=args.workers,
        source_sha=sha,
    )
    if args.profile:
        profile.disable()
        result["profile"] = [
            {
                "file": Path(row.code.co_filename).name,
                "function": row.code.co_name,
                "calls": row.callcount,
                "cumulative_seconds": row.totaltime,
            }
            for row in sorted(profile.getstats(), key=lambda row: row.totaltime, reverse=True)
            if hasattr(row.code, "co_filename")
        ][:30]
    result["profiled"] = args.profile
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
