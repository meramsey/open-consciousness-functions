"""Known PCM boundary measurements; dead channels are not binaural stereo."""

import wave

import pytest
from ocf_tools.complete_session import _background_activity, _pcm_window, _stereo_metrics
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def wav(path, *, width=2, channels=2, left=8192, right=-4096, frames=1000):
    with wave.open(str(path), "wb") as writer:
        writer.setparams((channels, width, 100, 0, "NONE", ""))
        frame = left.to_bytes(width, "little", signed=width != 1)
        if channels == 2:
            frame += right.to_bytes(width, "little", signed=width != 1)
        writer.writeframes(frame * frames)


@pytest.mark.parametrize("width", [2, 3, 4])
@pytest.mark.parametrize("start,expected_duration", [(-1, 1), (0, 1), (100, 0.01)])
def test_pcm_window_signed_widths_and_edge_clamping(tmp_path, width, start, expected_duration):
    path = tmp_path / "background.wav"
    left, right = 1 << (8 * width - 3), -(1 << (8 * width - 4))
    wav(path, width=width, left=left, right=right)
    measured = _pcm_window(path, start)
    assert measured["left_peak"] == left and measured["right_peak"] == abs(right)
    assert measured["left_rms_dbfs"] == pytest.approx(-12.04, abs=0.01)
    assert measured["right_rms_dbfs"] == pytest.approx(-18.06, abs=0.01)
    assert measured["duration_seconds"] == expected_duration
    assert measured["different_channel_frames"] > 0


def test_pcm_window_reports_silence_and_rejects_empty_or_unsupported_audio(tmp_path):
    path = tmp_path / "background.wav"
    wav(path, left=0, right=0)
    result = _pcm_window(path, 0)
    assert not result["non_silent"]
    assert result["left_rms_dbfs"] == result["right_rms_dbfs"] == float("-inf")
    wav(path, frames=0)
    with pytest.raises(OCFError, match="empty"):
        _pcm_window(path, 0)
    wav(path, channels=1)
    with pytest.raises(OCFError, match="stereo PCM"):
        _pcm_window(path, 0)


@pytest.mark.parametrize("width", [2, 3, 4])
@pytest.mark.parametrize("left,right", [(0, 1000), (1000, 0)])
def test_one_dead_background_channel_is_rejected_in_all_supported_widths(
    tmp_path, width, left, right
):
    path = tmp_path / "background.wav"
    wav(path, width=width, left=left, right=right)
    stages = [
        {
            "id": "active",
            "start_seconds": 0,
            "duration_seconds": 6,
            "background_at_midpoint": [{"state": "focus-10"}],
        }
    ]
    with pytest.raises(OCFError, match="silent stereo channel"):
        _background_activity(path, stages, {"focus-10": {"mode": "preset"}})


@pytest.mark.parametrize("left,right", [(0, 1000), (1000, 0)])
def test_one_dead_master_channel_is_not_accepted_as_independent_stereo(tmp_path, left, right):
    path = tmp_path / "master.wav"
    wav(path, left=left, right=right)
    with pytest.raises(OCFError, match="silent stereo channel"):
        _stereo_metrics(path, 100)


def test_healthy_master_and_background_remain_accepted(tmp_path):
    path = tmp_path / "master.wav"
    wav(path)
    measured = _stereo_metrics(path, 100)
    assert measured["frames"] == 1000 and measured["clipped_sample_count"] == 0
    stages = [
        {
            "id": "active",
            "start_seconds": 0,
            "duration_seconds": 6,
            "background_at_midpoint": [{"state": "focus-10"}],
        }
    ]
    assert (
        _background_activity(path, stages, {"focus-10": {"mode": "preset"}})[0]["status"]
        == "non-silent"
    )


@pytest.mark.parametrize(
    "left,right,accepted", [(8192, -4096, True), (0, 1000, False), (1000, 0, False)]
)
def test_representative_acceptance_checks_both_measured_channels(
    monkeypatch, tmp_path, left, right, accepted
):
    from ocf_tools import complete_session, semantic_dsp

    path = tmp_path / "background.wav"
    wav(path, left=left, right=right)
    monkeypatch.setattr(semantic_dsp, "gain_at", lambda *a: 1.0)
    dsp = {"duration_s": 10, "selections": {"focus-10": {"mode": "preset"}}}
    if accepted:
        result = complete_session._representative_audio_analysis(path, [], {}, dsp)
        assert result[0]["checkpoint"] == "opening-first-10-seconds"
        assert result[0]["left_peak"] == left
    else:
        with pytest.raises(OCFError, match="silent or not stereo"):
            complete_session._representative_audio_analysis(path, [], {}, dsp)


@pytest.mark.parametrize("kind", ["rate", "identical", "empty"])
def test_master_format_and_empty_or_non_binaural_output_fail_clearly(tmp_path, kind):
    path = tmp_path / "master.wav"
    wav(
        path,
        left=1000,
        right=1000 if kind == "identical" else -500,
        frames=0 if kind == "empty" else 1000,
    )
    with pytest.raises(
        OCFError, match="configured sample rate|binaural stereo is absent|empty or truncated"
    ):
        _stereo_metrics(path, 101 if kind == "rate" else 100)
