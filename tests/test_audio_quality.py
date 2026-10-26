import math
import shutil
import struct
import wave
from types import SimpleNamespace

import pytest
from ocf_tools import audio_quality
from ocf_tools.utils import OCFError

LOG = """[Parsed_ebur128] t: 1.0 TARGET:-23 LUFS M: -15.1 S: -15.0 I: -17.0 LUFS LRA: 5.0 LU
[Parsed_ebur128] t: 2.0 TARGET:-23 LUFS M: -14.0 S: -14.2 I: -16.9 LUFS LRA: 5.1 LU
Summary:
Integrated loudness:
  I: -17.5 LUFS
Loudness range:
  LRA: 5.5 LU
True peak:
  Peak: -0.2 dBFS
"""


@pytest.mark.unit
def test_ebur128_parser_records_metrics_without_mastering_targets():
    result = audio_quality.parse_ebur128(LOG)
    assert result["integrated_loudness_lufs"] == -17.5
    assert result["loudness_range_lu"] == 5.5
    assert result["true_peak_dbfs"] == -0.2
    assert result["maximum_short_term_lufs"] == -14.2
    assert result["maximum_short_term_at_seconds"] == 2.0
    assert result["mastering_target_applied"] is False
    with pytest.raises(OCFError, match="missing integrated loudness"):
        audio_quality.parse_ebur128("no EBU statistics")


@pytest.mark.unit
def test_ebur128_measurement_checks_ffmpeg_and_hashes_source(monkeypatch, tmp_path):
    audio = tmp_path / "master.wav"
    audio.write_bytes(b"fixture")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stderr=LOG, stdout="ffmpeg version fixture\n")

    monkeypatch.setattr(audio_quality, "workspace_run", run)
    result = audio_quality.measure_ebur128(audio)
    assert result["ffmpeg_version"] == "ffmpeg version fixture"
    assert result["audio_sha256"]
    assert "ebur128=peak=true" in calls[0]
    assert calls[1] == ["ffmpeg", "-version"]


@pytest.mark.integration
@pytest.mark.audio_integration
@pytest.mark.external_tool
def test_short_synthetic_audio_gets_real_ebur128_measurements(tmp_path, monkeypatch):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg is optional for objective audio integration")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    path = tmp_path / "fixture.wav"
    rate = 44100
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(rate)
        frames = []
        for index in range(4 * rate):
            left = round(5000 * math.sin(2 * math.pi * 440 * index / rate))
            right = round(4000 * math.sin(2 * math.pi * 660 * index / rate))
            frames.append(struct.pack("<hh", left, right))
        output.writeframes(b"".join(frames))
    original = path.read_bytes()
    result = audio_quality.measure_ebur128(path)
    assert result["audio_sha256"]
    assert result["integrated_loudness_lufs"] < 0
    assert result["true_peak_dbfs"] < 0
    assert result["short_term_measurement_available"]
    assert result["mastering_target_applied"] is False
    assert path.read_bytes() == original
