"""Synthetic mathematical fixtures, no reference recordings or native processes."""

import numpy as np
import pytest
from tools import analyze_v4_short
from tools.analyze_v4_short import (
    PAIRS,
    continuum,
    db,
    fit_shape,
    peak,
    projection,
    sha,
    tone_rows,
    write_csv,
)


@pytest.mark.unit
def test_projection_frequency_phase_and_hash_contract(tmp_path):
    fs = 2000
    t = np.arange(fs * 10) / fs
    x = 0.2 * np.cos(2 * np.pi * 79.25 * t + 0.4)
    value = projection(x, fs, 79.25, 0)
    assert abs(value) == pytest.approx(0.2, abs=1e-6)
    assert np.angle(value) == pytest.approx(0.4, abs=1e-5)
    assert peak(x, fs, 79.25) == pytest.approx(79.25, abs=0.005)
    assert db(0) == -400
    path = tmp_path / "signal.txt"
    path.write_bytes(b"signal")
    assert len(sha(path)) == 64 and sha(path) == sha(path)
    write_csv(tmp_path / "measure.csv", [{"value": 2}])
    assert "value" in (tmp_path / "measure.csv").read_text()


@pytest.mark.unit
@pytest.mark.parametrize("modulation", ["am", "pm"])
def test_sideband_classifier_distinguishes_am_from_pm(modulation):
    fs = 44100
    t = np.arange(fs * 20) / fs
    channels = []
    for ear in (0, 1):
        value = np.zeros_like(t)
        for pair in PAIRS:
            phase = 2 * np.pi * pair[ear] * t
            value += 0.05 * (
                (1 + 0.1 * np.cos(2 * np.pi * 2 * t)) * np.cos(phase)
                if modulation == "am"
                else np.cos(phase + 0.1 * np.sin(2 * np.pi * 2 * t))
            )
        channels.append(value)
    rows = tone_rows(np.column_stack(channels), fs, [(0, 20)])
    low = [row for row in rows if row["family_center_hz"] == 40]
    assert len(rows) == 10
    for row in low:
        assert row["frequency_hz"] == pytest.approx(row["nominal_hz"], abs=0.005)
        if modulation == "am":
            assert row["AM_fractional_depth"] == pytest.approx(0.1, abs=0.005)
            assert row["PM_small_signal_rad"] < 0.005
        else:
            assert row["PM_small_signal_rad"] == pytest.approx(0.1, abs=0.005)
            assert row["AM_fractional_depth"] < 0.005


@pytest.mark.unit
def test_smooth_shape_fit_recovers_synthetic_supported_model():
    a, b = 1, -2
    x_star = (-b / a) ** (1 / (2 * b - 2 * a))
    rows = []
    for center in (100, 125, 160, 200, 250, 315, 400, 500, 630, 800):
        ratio = center / (200 / x_star)
        rows.append(
            {
                "center_hz": center,
                "continuum_density_dbfs_hz": -10 * np.log10(ratio ** (-2 * a) + ratio ** (-2 * b))
                - 40,
            }
        )
    result = fit_shape(rows)["fits"]["farfield_supported"]
    assert result["peak_hz"] == pytest.approx(200, abs=0.1)
    assert result["residual_rms_db"] < 0.01


@pytest.mark.unit
def test_shared_noise_bed_has_coherent_zero_delay_and_finite_band_power():
    fs = 44100
    noise = np.random.default_rng(42).normal(0, 0.01, fs * 20)
    bands, shape, delay = continuum(np.column_stack([noise, noise]), fs, 0, 20)
    assert len(bands) == 12 and len(shape) == 30
    assert all(np.isfinite(row["L_RMS_dbfs"]) for row in bands)
    assert all(row["median_coherence"] == pytest.approx(1, abs=1e-8) for row in bands)
    assert abs(delay["R_lag_us"]) < 1e-5


@pytest.mark.unit
def test_independent_noise_does_not_claim_a_coherent_interaural_delay():
    fs = 44100
    random = np.random.default_rng(19)
    samples = np.column_stack((random.normal(0, 0.01, fs * 4), random.normal(0, 0.01, fs * 4)))
    _, _, delay = continuum(samples, fs, 0, 4)
    assert delay is None


@pytest.mark.unit
def test_measurement_driver_orchestrates_synthetic_inputs_without_reference_audio(
    monkeypatch, tmp_path, capsys
):
    import json
    import sys
    from types import SimpleNamespace

    data = np.column_stack((np.arange(400, dtype=float), np.arange(400, dtype=float) + 1))
    f10, f11, output = tmp_path / "f10.flac", tmp_path / "f11.flac", tmp_path / "report"
    f10.write_bytes(b"synthetic placeholder")
    f11.write_bytes(b"synthetic placeholder")
    monkeypatch.setattr(analyze_v4_short.sf, "read", lambda *_args, **_kwargs: (data, 1))
    monkeypatch.setattr(
        analyze_v4_short.sf, "info", lambda _path: SimpleNamespace(subtype="PCM_16")
    )

    centers = [
        25,
        31.5,
        40,
        50,
        63,
        80,
        100,
        125,
        160,
        200,
        250,
        315,
        400,
        500,
        630,
        800,
        1000,
        1250,
        1600,
        2000,
        2500,
        3150,
        4000,
        5000,
        6300,
        8000,
        10000,
        12500,
        16000,
        20000,
    ]

    def continuum(_samples, _rate, start, length):
        ranges = [
            (20, 60),
            (60, 130),
            (130, 230),
            (230, 380),
            (380, 500),
            (500, 1000),
            (1000, 2000),
            (1000, 5000),
            (2000, 5000),
            (5000, 10000),
            (10000, 16000),
            (16000, 20000),
        ]
        bands = [
            {
                "start_s": start,
                "duration_s": length,
                "low_hz": low,
                "high_hz": high,
                "L_RMS_dbfs": -30.0,
                "R_RMS_dbfs": -31.0,
            }
            for low, high in ranges
        ]
        shape = [
            {"start_s": start, "center_hz": center, "continuum_density_dbfs_hz": -30.0}
            for center in centers
        ]
        return bands, shape, None

    def tone_rows(_samples, _rate, windows):
        rows = []
        for _start, length in windows:
            for pair in analyze_v4_short.PAIRS:
                for ear, frequency in zip(("L", "R"), pair):
                    rows.append(
                        {
                            "window_duration_s": length,
                            "family_center_hz": sum(pair) / 2,
                            "ear": ear,
                            "frequency_hz": frequency,
                            "carrier_rms_dbfs": -20.0,
                            "AM_fractional_depth": 0.0,
                            "PM_small_signal_rad": 0.0,
                            "sideband_phase_closure_deg": 0.0,
                            "total_resolved_tone_power_dbfs": -18.0,
                        }
                    )
        return rows

    monkeypatch.setattr(analyze_v4_short, "continuum", continuum)
    monkeypatch.setattr(analyze_v4_short, "tone_rows", tone_rows)
    monkeypatch.setattr(
        analyze_v4_short, "fit_shape", lambda _shape: {"fits": {"farfield_supported": {}}}
    )
    monkeypatch.setattr(analyze_v4_short.signal, "resample_poly", lambda values, *_a, **_k: values)
    monkeypatch.setattr(
        analyze_v4_short.signal,
        "welch",
        lambda *_args, **_kwargs: (np.array([30, 40, 100, 300, 599, 601]), np.ones((6,))),
    )
    monkeypatch.setattr(analyze_v4_short.signal, "medfilt", lambda values, *_a, **_k: values)
    monkeypatch.setattr(
        analyze_v4_short.signal,
        "find_peaks",
        lambda *_args, **_kwargs: (np.array([2, 3, 4]), {}),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["analyze_v4_short", "--f10", str(f10), "--f11", str(f11), "--output", str(output)],
    )

    analyze_v4_short.main()

    summary = json.loads((output / "measurements.json").read_text(encoding="utf-8"))
    assert summary["evidence_class"] == "measured directly from supplied V4-short reference excerpt"
    assert summary["F10"]["channels"] == 2
    assert len(summary["F10"]["tone_aggregates"]) == len(PAIRS)
    assert summary["F11"]["encoding"] == "PCM_16"
    assert (output / "f10-carriers-sidebands.csv").is_file()
    assert (output / "f11-comparison-peaks.csv").is_file()
    assert "independently_authenticated_recordings" not in capsys.readouterr().out
