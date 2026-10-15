from __future__ import annotations

import wave
from array import array

from ocf_tools.pacing_auditions import _extract_window


def test_pacing_audition_excerpt_uses_stereo_frames_not_samples(tmp_path):
    source = tmp_path / "source.wav"
    left = list(range(20))
    right = list(range(100, 120))
    samples = array("h", [sample for pair in zip(left, right, strict=True) for sample in pair])
    with wave.open(str(source), "wb") as writer:
        writer.setnchannels(2)
        writer.setsampwidth(2)
        writer.setframerate(10)
        writer.writeframes(samples.tobytes())

    destination = tmp_path / "excerpt.wav"
    duration = _extract_window(
        source, destination, start_seconds=0.5, end_seconds=1.5, sample_rate=10
    )
    with wave.open(str(destination), "rb") as reader:
        excerpt = array("h", reader.readframes(reader.getnframes()))
        assert reader.getnframes() == 10
        assert reader.getnchannels() == 2
    assert duration == 1.0
    assert excerpt == samples[10:30]
