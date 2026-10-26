"""Local reference selection preserves stereo precision and binds resume inputs."""

import json
import shutil
import wave

import pytest
import yaml
from ocf_tools import audio_build, semantic_dsp
from ocf_tools.utils import OCFError, sha256_of_file

pytestmark = pytest.mark.integration


def test_synthesis_profile_provenance_hash_is_not_an_active_reference_source():
    identity = semantic_dsp.dependency_identity("OCF-DSP-HPLUS-LOCKED-001")
    assert set(identity["inputs"]) == {"focus-10", "focus-11"}
    for row in identity["inputs"].values():
        assert row["manifest"]["engine"] == "farfield"
        assert set(row["sources"]) == {row["manifest"]["preset"]["file"]}


@pytest.fixture
def local_reference(tmp_path):
    source = tmp_path / "reference.wav"
    # Deliberately exercise low 24-bit precision and distinct left/right values.
    frame = (100001).to_bytes(3, "little", signed=True) + (-200003).to_bytes(
        3, "little", signed=True
    )
    with wave.open(str(source), "wb") as stream:
        stream.setparams((2, 3, 44100, 0, "NONE", "not compressed"))
        stream.writeframes(frame * 4410)
    manifest = {
        "schema_version": "1.0",
        "id": "OCF-BG-9001",
        "name": "local synthetic reference",
        "engine": "reference-master",
        "engine_source": {"repository": None, "version": None},
        "preset": {"file": None},
        "render": {"output": None, "seed": 0, "deterministic": True},
        "usage": {"functions": [], "audio_implementations": []},
        "provenance": {
            "design": "original-ocf",
            "notes": "Synthetic integration fixture",
            "reference_sha256": sha256_of_file(source),
        },
        "safety": {"headphone_notice": True, "driving_warning": True},
        "license": None,
        "reference": {"source": str(source), "splices": [], "preserve_precision": True},
    }
    path = tmp_path / "background.yaml"
    path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    profile = {
        "schema_version": "1.0",
        "id": "local-test",
        "version": "1.0.0",
        "initial_state": "focus-10",
        "seed": 0,
        "allow_static": True,
        "states": {"focus-10": {"mode": "preset", "preset": str(path)}},
        "transitions": {"curve": "equal-power", "fallback_seconds": 25},
    }
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(yaml.safe_dump(profile), encoding="utf-8")
    return source, path, profile_path, frame


def test_precision_preserving_reference_is_exact_stereo_and_source_is_immutable(
    local_reference, tmp_path
):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is optional")
    source, manifest, _, frame = local_reference
    original = sha256_of_file(source)
    stem, backend = audio_build._render_reference_master(
        str(manifest), "required", max_seconds=0.05, scratch_dir=tmp_path
    )
    assert backend == "reference-master"
    with wave.open(str(stem), "rb") as stream:
        assert (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) == (
            2,
            3,
            44100,
        )
        assert stream.readframes(stream.getnframes()) == frame * 2205
    assert sha256_of_file(source) == original


def test_reference_checksum_mismatch_blocks_resume_and_render(local_reference, tmp_path):
    source, manifest, profile, _ = local_reference
    first = semantic_dsp.dependency_identity(profile)
    assert first["inputs"]["focus-10"]["sources"][str(source)] == sha256_of_file(source)
    source.write_bytes(source.read_bytes() + b"changed")
    with pytest.raises(OCFError, match="checksum mismatch"):
        semantic_dsp.dependency_identity(profile)
    if shutil.which("ffmpeg"):
        with pytest.raises(OCFError, match="checksum mismatch"):
            audio_build._render_reference_master(str(manifest), "required", scratch_dir=tmp_path)


def test_explicit_manifest_path_is_validated_and_retained_in_state_selection(
    local_reference, tmp_path
):
    _, manifest, profile_path, _ = local_reference
    profile = semantic_dsp.load_profile(profile_path)
    plan = semantic_dsp.plan_program({"timeline": []}, [], 0.05, profile)
    selection = plan["selections"]["focus-10"]
    assert selection["manifest_reference"] == str(manifest)
    assert selection["manifest_sha256"] == sha256_of_file(manifest)
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps({"engine": "reference-master"}), encoding="utf-8")
    with pytest.raises(OCFError, match="background manifest"):
        audio_build._resolve_background_manifest(str(invalid))
