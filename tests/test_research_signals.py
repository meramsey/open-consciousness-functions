"""Synthetic mathematical fixtures, no reference recordings or native processes."""

import numpy as np
import pytest
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
    noise = np.random.default_rng(42).normal(0, 0.01, fs * 4)
    bands, shape, delay = continuum(np.column_stack([noise, noise]), fs, 0, 4)
    assert len(bands) == 12 and len(shape) == 30
    assert all(np.isfinite(row["L_RMS_dbfs"]) for row in bands)
    assert all(row["median_coherence"] == pytest.approx(1, abs=1e-8) for row in bands)
    assert abs(delay["R_lag_us"]) < 1e-5
