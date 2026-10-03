"""Objective acoustic acceptance of the DSP-only V2 audition (research deps)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml
from scipy import signal


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def db(amplitude):
    return float(20 * np.log10(max(abs(amplitude), 1e-20)))


def block(path, start, seconds):
    info = sf.info(path)
    return sf.read(
        path,
        start=round(start * info.samplerate),
        frames=round(seconds * info.samplerate),
        always_2d=True,
    )[0], info.samplerate


def stats(path):
    power = np.zeros(2)
    count = 0
    peak = 0
    clipping = 0
    digest = hashlib.sha256()
    with sf.SoundFile(path) as reader:
        for data in reader.blocks(blocksize=262144, dtype="float64", always_2d=True):
            power += (data * data).sum(axis=0)
            count += len(data)
            peak = max(peak, float(np.max(abs(data))))
            clipping += int(np.sum(abs(data) >= 1))
            digest.update(data.tobytes())
    return {
        "frames": count,
        "duration_s": count / reader.samplerate,
        "sample_rate": reader.samplerate,
        "channels": reader.channels,
        "peak_dbfs": db(peak),
        "rms_L_R_dbfs": [db(v) for v in np.sqrt(power / count)],
        "clipped_samples": clipping,
        "decoded_float64_sha256": digest.hexdigest(),
    }


def amplitudes(path, start, seconds, frequencies):
    data, fs = block(path, start, seconds)
    data = signal.resample_poly(data, 1, 20, axis=0)
    time = np.arange(len(data)) / (fs / 20) + start
    window = signal.windows.hann(len(data), sym=False)
    return {
        frequency: 2
        * np.sum(data * window[:, None] * np.exp(-2j * np.pi * frequency * time)[:, None], axis=0)
        / window.sum()
        for frequency in frequencies
    }


def window_rms(path, start, seconds):
    data, _ = block(path, start, seconds)
    return db(np.sqrt((data * data).sum(axis=1).mean()))


def approach_rise(bed, approaches, duration):
    """Objective acceptance of pre-arrival emergence and arrival hold."""
    results = []
    for approach in approaches:
        start = approach["start_s"]
        established = approach["established_s"]
        arrival = approach["arrival_s"]
        assert 0 <= start < established < arrival <= duration
        span = established - start
        window = max(2.0, span / 100)
        sustained = window_rms(bed, arrival + 2, 30)
        probes = []
        for fraction in (0.125, 0.25, 0.5, 0.75):
            expected = db((1 - np.cos(np.pi * fraction)) / 2)
            measured = window_rms(bed, start + span * fraction, window) - sustained
            assert abs(measured - expected) < 1.5, (fraction, measured, expected)
            probes.append(
                {
                    "approach_fraction": fraction,
                    "offset_s": span * fraction,
                    "measured_relative_db": measured,
                    "declared_raised_cosine_relative_db": expected,
                }
            )
        # Full sustained level already before the arrival directive, and no
        # second ramp or level jump when the state is committed at arrival.
        assert abs(window_rms(bed, established, window) - sustained) < 0.5
        assert abs(window_rms(bed, arrival - 4, window) - sustained) < 0.5
        assert abs(window_rms(bed, arrival + 0.5, window) - sustained) < 0.5
        onset, later = (
            amplitudes(bed, start + span * 0.125, window, [39.75, 40.25]),
            amplitudes(bed, arrival + 2, 30, [39.75, 40.25]),
        )
        emergence = []
        for frequency, ear in ((39.75, 0), (40.25, 1)):
            # The intended ear is already inaudible this early in induction; a
            # cross-ear ratio at that level would only measure quantization noise.
            assert db(onset[frequency][ear] / later[frequency][ear]) < -24
            emergence.append(
                {
                    "frequency_hz": frequency,
                    "ear": ["left", "right"][ear],
                    "emergence_db": db(onset[frequency][ear] / later[frequency][ear]),
                }
            )
        results.append(
            {
                "approach": approach["begin_semantic"],
                "state": approach["state"],
                "begin_s": start,
                "established_s": established,
                "arrival_s": arrival,
                "probes": probes,
                "sustained_relative_dbfs": sustained,
                "first_pair_carrier_emergence": emergence,
            }
        )
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    directory = args.directory
    manifest = yaml.safe_load((directory / "render-manifest.yaml").read_text())
    program = manifest["DSP"]
    duration = manifest["total_duration_s"]
    bed = next(directory.glob("*-DSP-bed.wav"))
    master = next(directory.glob("*-master.wav"))
    flac = next(directory.glob("*-listening.flac"))
    results = {"master": stats(master), "lossless": stats(flac), "bed": stats(bed)}
    assert (
        results["master"]["decoded_float64_sha256"] == results["lossless"]["decoded_float64_sha256"]
    )
    assert results["master"]["clipped_samples"] == results["bed"]["clipped_samples"] == 0
    assert results["master"]["channels"] == 2 and results["master"]["sample_rate"] == 44100
    assert abs(results["master"]["duration_s"] - manifest["total_duration_s"]) < 1 / 44100
    assert _sha(next(directory.glob("*-narration.wav"))) == manifest["v1_speech_sha256"]
    checks = []
    approaches = program.get("approaches") or []
    tail = max(transition["end_s"] for transition in program["transitions"])
    silent = [(0, 490), (1237.4, 0.5)]
    for approach in approaches:
        # The whole point of the induction change: the selected program is
        # already audibly present long before the arrival directive.
        silent[0] = (0, approach["start_s"] - 0.5)
    for start, seconds in silent:
        data, _ = block(bed, start, seconds)
        assert np.max(abs(data)) == 0
        checks.append({"silence_start_s": start, "duration_s": seconds, "peak": 0})
    assert np.max(abs(block(bed, tail, max(0.25, duration - tail - 0.1))[0])) < 1e-4
    if approaches:
        checks.extend(approach_rise(bed, approaches, duration))
    pairs = [(39.75, 40.25), (79.25, 80.75), (158.05, 161.95), (198, 202), (317.95, 322.05)]
    expected = [3.9, 0, -4.8, -8.2, -10.9]
    frequencies = [frequency for pair in pairs for frequency in pair]
    for start in [510, 1060]:
        amps = amplitudes(bed, start, 60, frequencies)
        levels = [np.array([db(amps[pair[0]][0]), db(amps[pair[1]][1])]) for pair in pairs]
        relative = [list(level - levels[1]) for level in levels]
        assert max(abs(np.array(relative) - np.array(expected)[:, None]).ravel()) < 0.6
        assert max(abs(level[0] - level[1]) for level in levels) < 0.6
        # Offset probes on each side are well below the intended carrier.
        off = amplitudes(bed, start, 60, [f + 0.15 for f in frequencies])
        assert all(
            db(off[pair[ear] + 0.15][ear] / amps[pair[ear]][ear]) < -20
            for pair in pairs
            for ear in [0, 1]
        )
        checks.append(
            {
                "F10_start_s": start,
                "duration_s": 60,
                "pairs_hz": pairs,
                "relative_L_R_db": relative,
                "frequency_offset_probe_hz": 0.15,
                "carrier_over_offset_min_db": 20,
            }
        )
    carriers = [256.869, 323.625, 384.875]
    frequencies = [
        frequency for carrier in carriers for frequency in [carrier, carrier - 40, carrier + 40]
    ] + [175, 179]
    amps = amplitudes(bed, 720, 120, frequencies)
    sam = []
    for carrier in carriers:
        ratios = [amps[carrier + offset] / amps[carrier] for offset in [-40, 40]]
        phase = [float(np.angle(ratio[0] / ratio[1], deg=True)) for ratio in ratios]
        assert all(abs(abs(value) - 180) < 5 for value in phase)
        sam.append(
            {
                "carrier_hz": carrier,
                "sideband_relative_L_R_db": [[db(value) for value in ratio] for ratio in ratios],
                "sideband_interaural_phase_deg": phase,
            }
        )
    theta = {
        str(frequency): [
            db(value / amps[323.625][ear]) for ear, value in enumerate(amps[frequency])
        ]
        for frequency in [175, 179]
    }
    assert max(value for row in theta.values() for value in row) < -30
    checks.append(
        {"F11_start_s": 720, "duration_s": 120, "SAM": sam, "theta175_179_relative_db": theta}
    )
    boundaries = []
    points = [
        time
        for transition in program["transitions"]
        for time in (transition["start_s"], transition["end_s"])
    ]
    for approach in approaches:
        points += [approach["start_s"], approach["established_s"]]
    for time in sorted(set(points)):
        data, fs = block(bed, time - 0.02, 0.04)
        derivative = np.max(abs(np.diff(data, axis=0)), axis=1)
        index = round(0.02 * fs) - 1
        jump = float(derivative[index])
        surrounding = np.concatenate((derivative[: index - 2], derivative[index + 3 :]))
        assert jump <= 3 * float(np.max(surrounding)) + 1e-7
        boundaries.append(
            {
                "time_s": time,
                "boundary_sample_step": jump,
                "surrounding_max_sample_step": float(np.max(surrounding)),
            }
        )
    results.update(
        {
            "acceptance": "passed",
            "checks": checks,
            "boundaries": boundaries,
            "speech_byte_identical": True,
            "limitations": [
                "No listener review performed",
                "F10 PM and staggered AM omitted; approximate bed",
                "Frequency localization probes bound error, not a new source identification",
                "Sample-step checks and analytic envelopes do not prove perceptual seamlessness",
                "Cues disabled; no production mastering",
                "Approach windows check declared OCF envelope design and arrival hold, not perceived appropriateness of level or curve",
            ],
        }
    )
    (directory / "verification.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
