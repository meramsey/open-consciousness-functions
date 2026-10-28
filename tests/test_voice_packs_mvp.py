"""Portable private voice-pack and preparation contract tests; no speech inference."""

import math
import wave
from array import array
from pathlib import Path

import pytest

from ocf_tools import voice_packs
from ocf_tools.custom_voices import asset_root, validate_profile
from ocf_tools.utils import OCFError, sha256_of_file


def tone(path: Path, seconds=2, rate=24000, silence_prefix=0):
    pcm = array("h")
    pcm.extend([0] * int(silence_prefix * rate))
    pcm.extend(
        round(6000 * math.sin(2 * math.pi * 220 * i / rate))
        for i in range(seconds * rate)
    )
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm.tobytes())
    return path


@pytest.fixture
def private_store(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("OCF_VOICE_ASSETS", str(tmp_path / "assets"))
    return tmp_path


def test_prepare_reference_selects_active_audio_and_preserves_source(private_store):
    source = tone(private_store / "input.wav", silence_prefix=1)
    original = source.read_bytes()
    prepared = voice_packs.prepare_reference(source)
    output = Path(prepared["path"])
    assert source.read_bytes() == original
    assert prepared["metadata"]["source_sha256"] == sha256_of_file(source)
    assert prepared["metadata"]["clip"]["start_s"] >= 0.9
    pack = voice_packs.create_pack(
        output,
        voice_id="OCF-VOICE-9893",
        name="Prepared synthetic fixture",
        locale="en-US",
        transcript="Synthetic fixture, not speech.",
        consent_declaration="Generated fixture for tests.",
    )
    assert pack["profile"]["creation_provenance"]["source_sha256"] == sha256_of_file(source)
    with wave.open(str(output), "rb") as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (24000, 1, 2)


def test_prepare_reference_rejects_corrupt_and_invalid_clip(private_store):
    corrupt = private_store / "corrupt.wav"
    corrupt.write_bytes(b"not wave")
    with pytest.raises(OCFError):
        voice_packs.prepare_reference(corrupt)
    source = tone(private_store / "input.wav")
    with pytest.raises(OCFError, match="extends beyond"):
        voice_packs.prepare_reference(source, start_s=1, duration_s=3)


def test_private_pack_registry_integrity_and_duplicate_id(private_store):
    source = tone(private_store / "reference.wav")
    result = voice_packs.create_pack(
        source,
        voice_id="OCF-VOICE-9891",
        name="Synthetic test fixture",
        locale="en-US",
        transcript="This is a synthetic fixture, not a speaker sample.",
        consent_declaration="Fixture generated for automated tests only.",
    )
    profile = result["profile"]
    assert profile["privacy"] == "private"
    assert profile["creation_provenance"]["source_sha256"] == sha256_of_file(source)
    assert validate_profile(profile)["valid"]
    assert voice_packs.inspect_pack("OCF-VOICE-9891")["pack_type"] == "reference-based-zero-shot"
    with pytest.raises(OCFError, match="already exists"):
        voice_packs.create_pack(
            source,
            voice_id="OCF-VOICE-9891",
            name="Duplicate",
            locale="en-US",
            transcript="Text",
            consent_declaration="Declared",
        )
    asset = asset_root() / profile["reference_audio"]["asset"]
    asset.write_bytes(b"tampered")
    with pytest.raises(OCFError, match="checksum"):
        validate_profile(profile)


def test_pack_requires_exact_transcript_and_consent(private_store):
    source = tone(private_store / "reference.wav")
    with pytest.raises(OCFError, match="transcript"):
        voice_packs.create_pack(
            source,
            voice_id="OCF-VOICE-9892",
            name="Fixture",
            locale="en-US",
            transcript=" ",
            consent_declaration="Declared",
        )
