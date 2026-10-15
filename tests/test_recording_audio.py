"""Synthetic, private recording preparation contracts; real codecs are explicit."""

from __future__ import annotations

import hashlib
import io
import json
import math
import shutil
import struct
import subprocess
import wave
from array import array
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from ocf_tools import recording_audio as recording
from ocf_tools.paths import SCHEMAS_DIR, work_path, workspace_run
from ocf_tools.utils import OCFError


def wav_bytes(values, *, rate=44100, channels=1, width=2):
    data = io.BytesIO()
    with wave.open(data, "wb") as writer:
        writer.setparams((channels, width, rate, 0, "NONE", "not compressed"))
        raw = (
            bytes(values)
            if width == 1
            else b"".join(int(v).to_bytes(width, "little", signed=True) for v in values)
        )
        writer.writeframes(raw)
    return data.getvalue()


def read_pcm(data):
    with wave.open(io.BytesIO(data), "rb") as reader:
        return [
            int.from_bytes(reader.readframes(1), "little", signed=True)
            for _ in range(reader.getnframes())
        ]


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    path = tmp_path / "original.wav"
    path.write_bytes(wav_bytes([0, 1000, -2000, 3000, -4000] * 100))
    return path


@pytest.mark.unit
def test_default_pcm_exact_preserves_source_and_cache(source, monkeypatch):
    monkeypatch.setattr(
        recording, "_tools", lambda: pytest.fail("default PCM must not discover FFmpeg")
    )
    original = source.read_bytes()
    sha = hashlib.sha256(original).hexdigest()
    audio, report = recording.process_recording(source, expected_sha256=sha.upper())
    assert audio == original == source.read_bytes()
    assert report["input_sha256"] == sha
    assert report["original_preserved"] is True
    assert report["processing"] == recording.DEFAULTS
    assert report["filters"] == report["filter_argv"] == []
    assert report["cache_hit"] is False
    again, hit = recording.process_recording(source)
    assert again == audio and hit["cache_hit"] is True
    assert Path(hit["cache_path"]).is_relative_to(work_path("cache", "recordings"))


@pytest.mark.unit
@pytest.mark.parametrize(
    "what", ["audio", "report", "manifest", "identity", "measurements", "traversal"]
)
def test_cache_corruption_is_regenerated(source, what):
    expected, report = recording.process_recording(source)
    root = Path(report["cache_path"])
    manifest = json.loads((root / "manifest.json").read_bytes())
    generation = manifest["generation"]
    if what == "audio":
        (root / f"{generation}.wav").write_bytes(b"corrupt")
    elif what == "report":
        (root / f"{generation}.json").write_bytes(b"{}")
    elif what == "manifest":
        (root / "manifest.json").write_bytes(b"not json")
    elif what == "traversal":
        manifest["generation"] = "../" + "f" * 29
        (root / "manifest.json").write_text(json.dumps(manifest))
    else:
        if what == "identity":
            report["cache_identity"]["sample_rate"] = 8000
        else:
            report["processed"]["duration_s"] = 1000
        data = json.dumps(report).encode()
        (root / f"{generation}.json").write_bytes(data)
        manifest["report_sha256"] = hashlib.sha256(data).hexdigest()
        (root / "manifest.json").write_text(json.dumps(manifest))
    audio, fresh = recording.process_recording(source)
    assert audio == expected
    assert fresh["cache_hit"] is False
    assert recording.process_recording(source)[1]["cache_hit"] is True


@pytest.mark.unit
def test_stereo_preserved_explicit_downmix_and_mono_duplicate(source):
    values = [1000, -1000, 4000, 2000, -4000, -2000] * 100
    source.write_bytes(wav_bytes(values, channels=2))
    audio, stereo = recording.process_recording(source, channels=2)
    assert audio == source.read_bytes()
    assert stereo["channel_conversion"] == "unchanged"
    assert stereo["original"]["channels"] == stereo["processed"]["channels"] == 2
    mono, info = recording.process_recording(source, channels=1)
    expected = [(values[i] + values[i + 1]) // 2 for i in range(0, len(values), 2)]
    assert read_pcm(mono) == expected
    assert info["channel_conversion"] == "arithmetic_mean_L_R"
    source.write_bytes(mono)
    duplicated, info = recording.process_recording(source, channels=2)
    with wave.open(io.BytesIO(duplicated)) as reader:
        raw = reader.readframes(reader.getnframes())
    assert raw == b"".join(v.to_bytes(2, "little", signed=True) * 2 for v in expected)
    assert info["channel_conversion"] == "duplicate_mono"


@pytest.mark.unit
def test_processor_upgrade_invalidates_cache(source, monkeypatch):
    original_audio, previous = recording.process_recording(source)
    code = Path(recording.__file__).read_bytes()
    real_sha = recording._sha
    monkeypatch.setattr(
        recording, "_sha", lambda data: "0" * 64 if data == code else real_sha(data)
    )
    audio, upgraded = recording.process_recording(source)
    assert audio == original_audio
    assert upgraded["cache_key"] != previous["cache_key"]
    assert upgraded["cache_hit"] is False
    assert recording.process_recording(source)[1]["cache_hit"] is True


@pytest.mark.unit
def test_objective_metrics_clipping_dc_silence_noise(source):
    source.write_bytes(wav_bytes([0, 32767, -32768, 0], rate=8000))
    info = recording.inspect_recording(source)["original"]
    channel = info["per_channel"][0]
    assert info["frames"] == 4 and info["duration_s"] == 4 / 8000
    assert info["sample_rate"] == 8000 and info["format"]["bits_per_sample"] == 16
    assert channel["peak"] == 1
    assert channel["clipped_samples"] == 2
    assert channel["clipped_fraction"] == 0.5
    assert channel["dc_offset"] == -1 / (32768 * 4)
    assert channel["rms"] == pytest.approx(math.sqrt((32767**2 + 32768**2) / 4) / 32768)
    assert info["silence_fraction"] == 0.5
    assert "not measured room noise" in info["noise_estimate"]["method"]
    assert info["noise_estimate"]["rms"] == channel["rms"]
    assert info["integrated_loudness_lufs"] is None


@pytest.mark.unit
def test_stereo_correlation_and_imbalance(source):
    values = [v for x in [1000, -2000, 3000, -4000] * 100 for v in (x, -x // 2)]
    source.write_bytes(wav_bytes(values, channels=2))
    info = recording.inspect_recording(source)["original"]
    assert info["stereo_correlation"] == pytest.approx(-1)
    assert info["channel_imbalance_db_left_minus_right"] == pytest.approx(20 * math.log10(2))


@pytest.mark.unit
def test_silence_metrics_are_json_safe_and_peak_target_does_not_invent_signal(source):
    source.write_bytes(wav_bytes([0, 0] * 500, channels=2))
    audio, info = recording.process_recording(
        source, channels=2, processing={"peak_target_dbfs": -3}
    )
    assert audio == source.read_bytes()
    assert info["processed"]["silence_fraction"] == 1
    assert info["processed"]["per_channel"][0]["peak_dbfs"] is None
    assert info["processed"]["stereo_correlation"] is None
    json.dumps(info, allow_nan=False)


@pytest.mark.unit
def test_window_percentile_is_signal_proxy(source):
    # Twenty full 50ms windows: the 10th percentile is the second sorted window.
    source.write_bytes(wav_bytes([100] * 800 + [10000] * 7200, rate=8000))
    noise = recording.inspect_recording(source)["original"]["noise_estimate"]
    assert noise["rms"] == pytest.approx(100 / 32768)


FLOAT_FORMAT = {"container": "wav", "codec": "pcm_f64le", "bits_per_sample": 64}


def fake_float_decode(source, monkeypatch, values, channels):
    """Exercise the public decoded-float path without launching unit subprocesses."""
    original = source.read_bytes()
    real_native = recording._native
    raw = struct.pack(f"<{len(values)}d", *values)
    monkeypatch.setattr(recording, "_tools", lambda: {})
    monkeypatch.setattr(
        recording, "_native", lambda data: None if data == original else real_native(data)
    )
    monkeypatch.setattr(
        recording,
        "_decode",
        lambda *_: (recording._floats(raw, channels), 44100, channels, FLOAT_FORMAT),
    )


@pytest.mark.unit
@pytest.mark.parametrize("value", [1e308, -1e308, float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("channels", [1, 2])
def test_float_decode_rejects_unsupported_magnitudes(value, channels):
    raw = struct.pack(f"<{channels}d", *([value] * channels))
    message = "sample magnitude exceeds supported limit" if math.isfinite(value) else "nonfinite"
    with pytest.raises(OCFError, match=message):
        recording._floats(raw, channels)


@pytest.mark.unit
@pytest.mark.parametrize("channels", [1, 2])
def test_measure_rejects_huge_finite_samples_before_squaring(channels):
    with pytest.raises(OCFError, match="reduce the source level or processing gain"):
        recording._measure(array("d", [1e308, -1e308] * channels), 44100, channels, FLOAT_FORMAT)


@pytest.mark.unit
@pytest.mark.parametrize("api", [recording.inspect_recording, recording.process_recording])
@pytest.mark.parametrize("channels", [1, 2])
def test_public_apis_reject_huge_finite_float_audio(source, monkeypatch, api, channels):
    before = source.read_bytes()
    fake_float_decode(source, monkeypatch, [1e308, -1e308] * channels, channels)
    with pytest.raises(OCFError, match="sample magnitude exceeds supported limit"):
        api(source)
    assert source.read_bytes() == before
    assert not list(work_path("cache", "recordings").glob("*/manifest.json"))


@pytest.mark.unit
@pytest.mark.parametrize("level", [1e-100, 1e-200, math.ulp(0.0)])
def test_quiet_stereo_correlation_rms_and_reports_are_finite(level):
    samples = array("d", (v for x in [level, -level] * 4 for v in (x, -x)))
    report = recording._measure(samples, 44100, 2, FLOAT_FORMAT)
    assert report["stereo_correlation"] == pytest.approx(-1)
    assert report["channel_imbalance_db_left_minus_right"] == pytest.approx(0)
    assert report["per_channel"][0]["rms"] == level
    assert math.isfinite(report["per_channel"][0]["rms_dbfs"])
    assert report["noise_estimate"]["rms"] == level
    json.dumps(report, allow_nan=False)


@pytest.mark.unit
@pytest.mark.parametrize(
    "left,right", [(1.0, math.ulp(0.0)), (math.ulp(0.0), 1.0), (1e6, math.ulp(0.0))]
)
def test_extreme_stereo_imbalance_uses_log_difference(left, right):
    report = recording._measure(array("d", [left, right, -left, -right]), 44100, 2, FLOAT_FORMAT)
    assert report["stereo_correlation"] == pytest.approx(1)
    assert report["channel_imbalance_db_left_minus_right"] == pytest.approx(
        20 * (math.log10(left) - math.log10(right))
    )
    json.dumps(report, allow_nan=False)


@pytest.mark.unit
@pytest.mark.parametrize("channels", [1, 2])
def test_subnormal_normalization_raises_actionable_error(source, monkeypatch, channels):
    before = source.read_bytes()
    fake_float_decode(source, monkeypatch, [math.ulp(0.0), -math.ulp(0.0)] * channels, channels)
    with pytest.raises(OCFError, match="peak normalization gain.*increase the source level"):
        recording.process_recording(source, channels=channels, processing={"peak_target_dbfs": -3})
    assert source.read_bytes() == before


@pytest.mark.unit
@pytest.mark.parametrize("level", [1e-100, 1e-308, 5e-309])
@pytest.mark.parametrize("channels", [1, 2])
def test_tiny_peak_normalization_with_representable_gain_is_finite(
    source, monkeypatch, level, channels
):
    fake_float_decode(source, monkeypatch, [level, -level] * channels, channels)
    _, report = recording.process_recording(
        source, channels=channels, processing={"peak_target_dbfs": -30}
    )
    assert math.isfinite(report["peak_gain"])
    assert report["processed"]["per_channel"][0]["peak_dbfs"] == pytest.approx(-30, abs=0.01)
    json.dumps(report, allow_nan=False)


@pytest.mark.unit
def test_processing_gain_respects_supported_magnitude(source, monkeypatch):
    fake_float_decode(source, monkeypatch, [1e6, -1e6], 1)
    with pytest.raises(
        OCFError, match="sample magnitude.*reduce the source level or processing gain"
    ):
        recording.process_recording(source, processing={"gain_db": 24})


@pytest.mark.unit
@pytest.mark.parametrize("channels", [1, 2])
def test_subnormal_audio_without_normalization_has_finite_reports(source, monkeypatch, channels):
    values = [math.ulp(0.0), -math.ulp(0.0)] * channels
    fake_float_decode(source, monkeypatch, values, channels)
    inspected = recording.inspect_recording(source)
    audio, report = recording.process_recording(source, channels=channels)
    assert report["processed"]["sample_peak"] == 0
    assert report["processed"]["per_channel"][0]["rms_dbfs"] is None
    assert inspected["original"]["sample_peak"] == math.ulp(0.0)
    json.dumps(inspected, allow_nan=False)
    json.dumps(report, allow_nan=False)
    assert recording.process_recording(source, channels=channels)[0] == audio


@pytest.mark.unit
@pytest.mark.parametrize("api", [recording.inspect_recording, recording.process_recording])
@pytest.mark.parametrize(
    "kind", ["missing", "directory", "permission", "read_failure", "null_byte"]
)
def test_source_io_errors_are_ocf_errors(source, monkeypatch, api, kind):
    if kind == "missing":
        source = source.with_name("missing.wav")
    elif kind == "directory":
        source = source.parent / "directory.wav"
        source.mkdir()
    elif kind == "null_byte":
        source = source.with_name("invalid\0.wav")
    else:
        real_open = Path.open

        class Unreadable:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, *args):
                raise OSError("simulated source read failure")

        def failing_open(path, *args, **kwargs):
            if path == source:
                if kind == "permission":
                    raise PermissionError("simulated source permission denial")
                return Unreadable()
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(Path, "open", failing_open)
    with pytest.raises(OCFError, match="cannot read recording") as error:
        api(source)
    assert isinstance(error.value.__cause__, (OSError, ValueError))


@pytest.mark.unit
def test_gain_peak_target_saturation_and_cache_inputs(source):
    values = [10000, -10000] * 100
    source.write_bytes(wav_bytes(values))
    gain, report = recording.process_recording(source, processing={"gain_db": 6.020599913279624})
    assert read_pcm(gain) == [v * 2 for v in values]
    assert report["original"]["sample_peak"] * 2 == report["processed"]["sample_peak"]
    peak, peak_report = recording.process_recording(source, processing={"peak_target_dbfs": -6})
    assert peak_report["processed"]["per_channel"][0]["peak_dbfs"] == pytest.approx(-6, abs=0.001)
    clipped, clipped_report = recording.process_recording(source, processing={"gain_db": 24})
    assert read_pcm(clipped) == [32767, -32768] * 100
    assert clipped_report["pre_quantization_clipped_samples"] == 200
    assert clipped_report["warnings"] == ["PCM16 saturation occurred"]
    assert len({report["cache_key"], peak_report["cache_key"], clipped_report["cache_key"]}) == 3
    assert source.read_bytes() == wav_bytes(values)


@pytest.mark.unit
def test_dc_removal_is_per_channel(source):
    source.write_bytes(wav_bytes([1000, -3000, 3000, -1000] * 100, channels=2))
    _, info = recording.process_recording(source, channels=2, processing={"remove_dc": True})
    assert [c["dc_offset"] for c in info["processed"]["per_channel"]] == [0, 0]
    assert info["original"]["per_channel"][0]["dc_offset"] != 0


@pytest.mark.unit
def test_trim_only_explicit_edges_preserves_interior_and_fades(source):
    values = [0] * 20 + [10000] * 20 + [0] * 40 + [-10000] * 20 + [0] * 20
    source.write_bytes(wav_bytes(values, rate=8000))
    untrimmed, _ = recording.process_recording(source, sample_rate=8000)
    assert read_pcm(untrimmed) == values
    trimmed, info = recording.process_recording(
        source, sample_rate=8000, processing={"trim_silence": {}}
    )
    assert read_pcm(trimmed) == values[20:-20]
    assert info["trimmed"] == {"leading_frames": 20, "trailing_frames": 20}
    faded, _ = recording.process_recording(
        source,
        sample_rate=8000,
        processing={"trim_silence": {}, "fade_in_s": 0.001, "fade_out_s": 0.001},
    )
    assert read_pcm(faded)[0] == read_pcm(faded)[-1] == 0
    assert read_pcm(faded)[20:60] == [0] * 40
    leading, _ = recording.process_recording(
        source, sample_rate=8000, processing={"trim_silence": {"trailing": False}}
    )
    assert read_pcm(leading) == values[20:]


@pytest.mark.unit
@pytest.mark.parametrize(
    "processing",
    [
        {"filter": "volume=1;amovie=/etc/passwd"},
        {"gain_db": "2;evil"},
        {"gain_db": True},
        {"gain_db": float("nan")},
        {"gain_db": float("inf")},
        {"gain_db": 25},
        {"remove_dc": 1},
        {"trim_silence": True},
        {"trim_silence": {"threshold_dbfs": -1}},
        {"loudness": {"unknown": 2}},
        {"compression": {"ratio": 10}},
        {"highpass_hz": -3},
        {"fade_out_s": -1},
        [],
    ],
)
def test_invalid_or_unsafe_configs(source, processing):
    before = source.read_bytes()
    with pytest.raises(OCFError):
        recording.process_recording(source, processing=processing)
    assert source.read_bytes() == before
    assert not work_path("cache", "recordings").exists()


@pytest.mark.unit
@pytest.mark.parametrize(
    "kwargs",
    [
        {"sample_rate": True},
        {"sample_rate": 4000},
        {"sample_rate": 44100.0},
        {"channels": True},
        {"channels": 3},
        {"expected_sha256": "invalid"},
        {"expected_sha256": "0" * 64},
    ],
)
def test_invalid_output_and_hash_checked_before_cache(source, kwargs):
    recording.process_recording(source)
    with pytest.raises(OCFError):
        recording.process_recording(source, **kwargs)


@pytest.mark.unit
@pytest.mark.parametrize(
    "width,values,expected",
    [
        (1, [0, 128, 255], [-32768, 0, 32512]),
        (3, [-8388608, 0, 8388352], [-32768, 0, 32767]),
        (4, [-2147483648, 0, 2147418112], [-32768, 0, 32767]),
    ],
)
def test_native_pcm_width_conversion_and_precision(source, width, values, expected):
    source.write_bytes(wav_bytes(values, width=width))
    before = source.read_bytes()
    output, info = recording.process_recording(source)
    assert read_pcm(output) == expected
    assert info["original"]["format"]["bits_per_sample"] == width * 8
    assert info["processed"]["format"]["bits_per_sample"] == 16
    assert source.read_bytes() == before


@pytest.mark.unit
def test_native_high_resolution_peak_is_not_falsely_labeled_clipped(source):
    source.write_bytes(wav_bytes([8388352, -8388352], width=3))
    assert recording.inspect_recording(source)["original"]["per_channel"][0]["clipped_samples"] == 0


@pytest.mark.unit
def test_empty_truncated_unsupported_all_silent_trim_and_long_fade(source):
    source.write_bytes(wav_bytes([]))
    with pytest.raises(OCFError):
        recording.inspect_recording(source)
    source.write_bytes(wav_bytes([1000] * 100)[:-4])
    with pytest.raises(OCFError, match="truncated"):
        recording.inspect_recording(source)
    source.write_bytes(wav_bytes([0] * 100))
    with pytest.raises(OCFError, match="entire"):
        recording.process_recording(source, processing={"trim_silence": {}})
    with pytest.raises(OCFError, match="fade"):
        recording.process_recording(source, processing={"fade_in_s": 1})
    with pytest.raises(OCFError, match="format"):
        recording.inspect_recording(source.with_suffix(".ogg"))


@pytest.mark.unit
def test_tool_requirement_is_actionable(source, monkeypatch):
    monkeypatch.setattr(recording.shutil, "which", lambda _: None)
    with pytest.raises(OCFError, match="optional FFmpeg"):
        recording.process_recording(source, sample_rate=48000)


@pytest.mark.unit
def test_timeout_is_bounded_and_translated(monkeypatch):
    def timeout(argv, **kwargs):
        assert kwargs["timeout"] == recording.TIMEOUT
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    monkeypatch.setattr(recording, "workspace_run", timeout)
    with pytest.raises(OCFError, match="tool failed"):
        recording._run(["ffmpeg", "-version"])


@pytest.mark.unit
def test_cache_publication_interruption_keeps_previous_generation(source, monkeypatch):
    audio, report = recording.process_recording(source)
    root = Path(report["cache_path"])
    manifest = (root / "manifest.json").read_bytes()

    def interrupted(*args):
        raise OSError("interrupted publish")

    monkeypatch.setattr(recording.os, "replace", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        recording._publish(root, audio, report)
    assert (root / "manifest.json").read_bytes() == manifest
    assert recording.process_recording(source)[1]["cache_hit"] is True


@pytest.mark.unit
def test_schema_and_explicit_defaults(source):
    schema = json.loads((SCHEMAS_DIR / "recording-processing.schema.json").read_bytes())
    Draft7Validator.check_schema(schema)
    normalized = recording._normalize({name: {} for name in recording.NESTED_DEFAULTS})
    assert normalized == {**recording.DEFAULTS, **recording.NESTED_DEFAULTS}
    Draft7Validator(schema).validate(normalized)


@pytest.fixture
def ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("optional FFmpeg/ffprobe unavailable")
    return shutil.which("ffmpeg")


def tone(rate=44100, seconds=1, channels=1):
    return [
        v
        for i in range(round(rate * seconds))
        for v in (
            [round(8000 * math.sin(2 * math.pi * 440 * i / rate))]
            if channels == 1
            else [
                round(8000 * math.sin(2 * math.pi * 440 * i / rate)),
                round(4000 * math.sin(2 * math.pi * 660 * i / rate)),
            ]
        )
    ]


@pytest.mark.integration
@pytest.mark.external_tool
@pytest.mark.parametrize(
    "extension,codec",
    [("flac", "flac"), ("mp3", "libmp3lame"), ("m4a", "aac"), ("wav", "pcm_f32le")],
)
def test_actual_format_decode_stereo_and_resample(source, tmp_path, ffmpeg, extension, codec):
    source.write_bytes(wav_bytes(tone(seconds=0.4, channels=2), channels=2))
    encoded = tmp_path / f"encoded.{extension}"
    result = workspace_run(
        [ffmpeg, "-v", "error", "-i", str(source), "-c:a", codec, str(encoded)],
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    before = encoded.read_bytes()
    inspected = recording.inspect_recording(encoded)
    output, info = recording.process_recording(encoded, sample_rate=48000, channels=2)
    assert encoded.read_bytes() == before
    assert inspected["original"]["channels"] == 2
    assert info["processed"]["sample_rate"] == 48000
    assert info["processed"]["channels"] == 2
    assert info["processed"]["duration_s"] == pytest.approx(
        info["original"]["duration_s"], abs=0.001
    )
    assert info["processed"]["stereo_correlation"] < 0.1
    assert info["cache_identity"]["tools"]["ffmpeg"]["version"]
    assert info["cache_identity"]["tools"]["ffprobe"]["sha256"]
    assert "aresample=48000:resampler=swr:dither_method=none" in info["filters"]
    assert recording.process_recording(encoded, sample_rate=48000, channels=2)[0] == output
    assert (
        recording.process_recording(encoded, sample_rate=48000, channels=2)[1]["cache_hit"] is True
    )


@pytest.mark.integration
@pytest.mark.external_tool
def test_actual_filters_and_integrated_loudness(source, ffmpeg):
    source.write_bytes(wav_bytes(tone(seconds=3)))
    before = source.read_bytes()
    config = {
        "highpass_hz": 80,
        "compression": {},
        "loudness": {},
        "peak_target_dbfs": -3,
        "measure_loudness": True,
        "fade_in_s": 0.01,
        "fade_out_s": 0.02,
    }
    output, info = recording.process_recording(source, processing=config)
    assert output != before == source.read_bytes()
    assert info["processed"]["duration_s"] == pytest.approx(3, abs=0.002)
    assert math.isfinite(info["original"]["integrated_loudness_lufs"])
    assert math.isfinite(info["processed"]["integrated_loudness_lufs"])
    # Peak normalization precedes fades, which may reduce the transient peak further.
    assert -10 < info["processed"]["per_channel"][0]["peak_dbfs"] <= -3 + 0.001
    assert read_pcm(output)[0] == read_pcm(output)[-1] == 0
    assert any(f.startswith("acompressor=") for f in info["filters"])
    assert any(f.startswith("loudnorm=") for f in info["filters"])
    assert info["filter_argv"]
    assert recording.process_recording(source, processing=config)[1]["cache_hit"] is True


@pytest.mark.integration
@pytest.mark.external_tool
def test_actual_failed_decode_keeps_diagnostics(source, ffmpeg):
    source.write_bytes(b"not audio at all")
    with pytest.raises(OCFError, match="tool failed"):
        recording.process_recording(source)
    assert list(work_path("logs").glob("*.log"))
    assert list(work_path("tmp").glob("ocf-recording-decode-*"))


@pytest.mark.integration
@pytest.mark.external_tool
def test_actual_lossless_full_scale_metrics(source, tmp_path, ffmpeg):
    source.write_bytes(wav_bytes([32767, -32768, 0] * 500))
    encoded = tmp_path / "rails.flac"
    result = workspace_run(
        [ffmpeg, "-v", "error", "-i", str(source), "-c:a", "flac", str(encoded)],
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    info = recording.inspect_recording(encoded)
    assert info["original"]["per_channel"][0]["clipped_samples"] == 1000
    assert info["original"]["per_channel"][0]["rms"] == pytest.approx(
        recording.inspect_recording(source)["original"]["per_channel"][0]["rms"]
    )


@pytest.mark.integration
@pytest.mark.external_tool
def test_actual_resampling_is_deterministic_without_cache(source, ffmpeg):
    source.write_bytes(wav_bytes(tone(rate=48000, seconds=0.2), rate=48000))
    first, report = recording.process_recording(source, sample_rate=16000)
    root = Path(report["cache_path"])
    (root / "manifest.json").write_text("corrupt")
    second, fresh = recording.process_recording(source, sample_rate=16000)
    assert first == second
    assert not fresh["cache_hit"]
    assert fresh["processed"]["frames"] == 3200
