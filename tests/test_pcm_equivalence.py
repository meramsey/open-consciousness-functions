"""Byte-exact reference contracts for faster PCM primitives, not new mix rules."""

import io
import math
import wave
from types import SimpleNamespace

import pytest
from ocf_tools import audio_build, voice

pytestmark = pytest.mark.unit


def reference_clip(value):
    return max(-32768, min(32767, value))


def reference_bytes(values):
    return b"".join(
        int(reference_clip(value)).to_bytes(2, "little", signed=True) for value in values
    )


def test_every_pcm16_value_decodes_and_serializes_exactly():
    values = list(range(-32768, 32768))
    data = reference_bytes(values)
    assert voice.struct_unpack_le16(data) == values
    assert voice.struct_unpack_le16(data + b"x") == values
    assert voice._pcm16_bytes(values) == data
    assert voice.struct_unpack_le16(b"") == []
    assert voice.struct_unpack_le16(b"x") == []


@pytest.mark.parametrize(
    "value",
    [
        -100000,
        -32769,
        -32768,
        -32768.0,
        -32767.9,
        -0.0,
        False,
        True,
        0,
        0.5,
        32766.9,
        32767.0,
        32767,
        32768,
        100000,
        math.inf,
        -math.inf,
        math.nan,
    ],
)
def test_clipping_keeps_original_values_types_and_nonfinite_behavior(value):
    expected = reference_clip(value)
    for clip in (voice._clip, audio_build._clip):
        actual = clip(value)
        assert actual == expected and type(actual) is type(expected)
    assert voice._pcm16_bytes([value]) == reference_bytes([value])


@pytest.mark.parametrize("writer", [voice._write_wav, audio_build._write_wav])
@pytest.mark.parametrize("channels", [1, 2])
def test_complete_wav_bytes_match_the_original_writer(writer, channels, tmp_path):
    values = [-100000, -32768, -3.9, 0, 1.9, 32767, 100000, math.nan]
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(22050)
        stream.writeframes(reference_bytes(values))
    target = tmp_path / "fixture.wav"
    writer(target, values, 22050, overwrite=True, channels=channels)
    assert target.read_bytes() == buffer.getvalue()


def test_native_big_endian_array_branch_is_little_endian_on_disk(monkeypatch):
    class BigEndianArray:
        """Model the native short-array operations on a big-endian host."""

        def __init__(self, code, values=()):
            assert code == "h"
            self.values = list(values)

        def frombytes(self, data):
            self.values = [
                int.from_bytes(data[i : i + 2], "big", signed=True) for i in range(0, len(data), 2)
            ]

        def byteswap(self):
            self.values = [
                int.from_bytes(v.to_bytes(2, "big", signed=True), "little", signed=True)
                for v in self.values
            ]

        def tolist(self):
            return list(self.values)

        def tobytes(self):
            return b"".join(v.to_bytes(2, "big", signed=True) for v in self.values)

    monkeypatch.setattr(voice, "array", BigEndianArray)
    monkeypatch.setattr(voice, "sys", SimpleNamespace(byteorder="big"))
    values = [-32768, -1234, -1, 0, 42, 1234, 32767]
    data = reference_bytes(values)
    assert voice.struct_unpack_le16(data) == values
    assert voice._pcm16_bytes(values) == data


def test_mono_downmix_preserves_negative_floor_rounding(tmp_path):
    path = tmp_path / "stereo.wav"
    voice._write_wav(path, [-3, -2, 4, 3, -32768, 32767], 22050, channels=2, overwrite=True)
    rate, samples = audio_build._read_mono_pcm(path)
    assert rate == 22050 and samples == [-3, 3, -1]
