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
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def db(amplitude):
    return float(20*np.log10(max(abs(amplitude), 1e-20)))


def block(path, start, seconds):
    info = sf.info(path)
    return sf.read(path, start=round(start*info.samplerate), frames=round(seconds*info.samplerate), always_2d=True)[0], info.samplerate


def stats(path):
    power = np.zeros(2)
    count = 0
    peak = 0
    clipping = 0
    digest = hashlib.sha256()
    with sf.SoundFile(path) as reader:
        for data in reader.blocks(blocksize=262144, dtype="float64", always_2d=True):
            power += (data*data).sum(axis=0)
            count += len(data)
            peak = max(peak, float(np.max(abs(data))))
            clipping += int(np.sum(abs(data) >= 1))
            digest.update(data.tobytes())
    return {"frames": count, "duration_s": count/reader.samplerate, "sample_rate": reader.samplerate, "channels": reader.channels, "peak_dbfs": db(peak), "rms_L_R_dbfs": [db(v) for v in np.sqrt(power/count)], "clipped_samples": clipping, "decoded_float64_sha256": digest.hexdigest()}


def amplitudes(path, start, seconds, frequencies):
    data, fs = block(path, start, seconds)
    data = signal.resample_poly(data, 1, 20, axis=0)
    time = np.arange(len(data))/(fs/20)+start
    window = signal.windows.hann(len(data), sym=False)
    return {frequency: 2*np.sum(data*window[:, None]*np.exp(-2j*np.pi*frequency*time)[:, None], axis=0)/window.sum() for frequency in frequencies}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    directory = args.directory
    manifest = yaml.safe_load((directory/"render-manifest.yaml").read_text())
    program = manifest["DSP"]
    bed = next(directory.glob("*-DSP-bed.wav"))
    master = next(directory.glob("*-master.wav"))
    flac = next(directory.glob("*-listening.flac"))
    results = {"master": stats(master), "lossless": stats(flac), "bed": stats(bed)}
    assert results["master"]["decoded_float64_sha256"] == results["lossless"]["decoded_float64_sha256"]
    assert results["master"]["clipped_samples"] == results["bed"]["clipped_samples"] == 0
    assert results["master"]["channels"] == 2 and results["master"]["sample_rate"] == 44100
    assert abs(results["master"]["duration_s"]-manifest["total_duration_s"]) < 1/44100
    assert _sha(next(directory.glob("*-narration.wav"))) == manifest["v1_speech_sha256"]
    checks = []
    for start, seconds in [(0, 490), (1237.4, .5)]:
        data, _ = block(bed, start, seconds)
        assert np.max(abs(data)) == 0
        checks.append({"silence_start_s": start, "duration_s": seconds, "peak": 0})
    pairs = [(39.75,40.25),(79.25,80.75),(158.05,161.95),(198,202),(317.95,322.05)]
    expected = [3.9,0,-4.8,-8.2,-10.9]
    frequencies = [frequency for pair in pairs for frequency in pair]
    for start in [510, 1060]:
        amps = amplitudes(bed, start, 60, frequencies)
        levels = [np.array([db(amps[pair[0]][0]), db(amps[pair[1]][1])]) for pair in pairs]
        relative = [list(level-levels[1]) for level in levels]
        assert max(abs(np.array(relative)-np.array(expected)[:,None]).ravel()) < .6
        assert max(abs(level[0]-level[1]) for level in levels) < .6
        # Offset probes on each side are well below the intended carrier.
        off = amplitudes(bed, start, 60, [f+.15 for f in frequencies])
        assert all(db(off[pair[ear]+.15][ear]/amps[pair[ear]][ear]) < -20 for pair in pairs for ear in [0,1])
        checks.append({"F10_start_s": start, "duration_s": 60, "pairs_hz": pairs, "relative_L_R_db": relative, "frequency_offset_probe_hz": .15, "carrier_over_offset_min_db": 20})
    carriers = [256.869,323.625,384.875]
    frequencies = [frequency for carrier in carriers for frequency in [carrier,carrier-40,carrier+40]] + [175,179]
    amps = amplitudes(bed, 720, 120, frequencies)
    sam = []
    for carrier in carriers:
        ratios = [amps[carrier+offset]/amps[carrier] for offset in [-40,40]]
        phase = [float(np.angle(ratio[0]/ratio[1],deg=True)) for ratio in ratios]
        assert all(abs(abs(value)-180) < 5 for value in phase)
        sam.append({"carrier_hz": carrier, "sideband_relative_L_R_db": [[db(value) for value in ratio] for ratio in ratios], "sideband_interaural_phase_deg": phase})
    theta = {str(frequency): [db(value/amps[323.625][ear]) for ear,value in enumerate(amps[frequency])] for frequency in [175,179]}
    assert max(value for row in theta.values() for value in row) < -30
    checks.append({"F11_start_s": 720, "duration_s": 120, "SAM": sam, "theta175_179_relative_db": theta})
    boundaries = []
    for transition in program["transitions"]:
        for time in [transition["start_s"],transition["end_s"]]:
            data, fs = block(bed, time-.02,.04)
            derivative = np.max(abs(np.diff(data,axis=0)),axis=1)
            index = round(.02*fs)-1
            jump = float(derivative[index])
            surrounding = np.concatenate((derivative[:index-2],derivative[index+3:]))
            assert jump <= 3*float(np.max(surrounding))+1e-7
            boundaries.append({"time_s": time, "boundary_sample_step": jump, "surrounding_max_sample_step": float(np.max(surrounding))})
    results.update({"acceptance": "passed", "checks": checks, "boundaries": boundaries, "speech_byte_identical": True, "limitations": ["No listener review performed", "F10 PM and staggered AM omitted; approximate bed", "Frequency localization probes bound error, not a new source identification", "Sample-step checks and analytic envelopes do not prove perceptual seamlessness", "Cues disabled; no production mastering"]})
    (directory/"verification.json").write_text(json.dumps(results,indent=2)+"\n")
    print(json.dumps(results,indent=2))


if __name__ == "__main__":
    main()
