"""Audio/background manifest tests: determinism, schema conformance, IDs."""

from __future__ import annotations

import json

from conftest import REPO_ROOT
from ocf_tools.prompts import audio_manifest_yaml, background_manifest_yaml
from ocf_tools.validators import validate_against_schema


def _schema(name: str) -> dict:
    with open(str(REPO_ROOT / "schemas" / name), encoding="utf-8") as handle:
        return json.load(handle)


def test_background_manifest_is_deterministic():
    kwargs = dict(
        bg_id="OCF-BG-0001",
        name="Neutral focus bed",
        author="Ada",
        engine="farfield",
        preset_file="audio/background/presets/example.yaml",
        provenance="original-ocf",
        notes="seed 12345",
        intended="training use",
        functions=["OCF-FND-002"],
        seed="12345",
        fmt="wav",
        render_notes="none",
        headphone=True,
        driving=True,
        safety_notes=["volume low"],
        license_="CC-BY-4.0",
    )
    first = background_manifest_yaml(**kwargs)
    second = background_manifest_yaml(**kwargs)
    assert first == second
    assert first["id"] == "OCF-BG-0001"
    assert first["render"]["seed"] == 12345
    assert first["render"]["deterministic"] is True


def test_background_manifest_matches_schema():
    data = background_manifest_yaml(
        bg_id="OCF-BG-0002",
        name="Bed",
        author="Ada",
        engine="farfield",
        preset_file="audio/background/presets/example.yaml",
        provenance="original-ocf",
        notes="",
        intended="",
        functions=[],
        seed="",
        fmt="wav",
        render_notes="",
        headphone=True,
        driving=True,
        safety_notes=[],
        license_="CC-BY-4.0",
    )
    assert validate_against_schema(data, _schema("background-audio.schema.json")) == []


def test_audio_manifest_matches_schema():
    data = audio_manifest_yaml(
        audio_id="OCF-AUDIO-0001",
        function_id="OCF-FND-002",
        title="Attention training",
        author="Ada",
        narrator="",
        language="en",
        license_="CC-BY-4.0",
        training_type="training",
        duration="12.5",
        transcript="audio/scripts/attention.md",
        induction="settle",
        bg_strategy="optional",
        preset="OCF-BG-0001",
        lang_rehearsal="PLUS-FOCUS",
        legacy_rehearsal="",
        compat_mode="standard",
        release_seq="release now",
        safety_lang="not medical advice",
        sample_rate="44100",
        channels="2",
        fmt="wav",
        loudness="-16 LUFS target",
        accessibility="transcript provided",
        test_notes="listened on headphones",
    )
    assert data["id"] == "OCF-AUDIO-0001"
    assert data["function_id"] == "OCF-FND-002"
    assert data["duration_minutes"] == 12.5
    assert data["technical"]["sample_rate"] == 44100
    assert validate_against_schema(data, _schema("audio-implementation.schema.json")) == []


def test_sample_background_fixture_valid(sample_background_path):
    from ocf_tools.indexes import load_yaml_file

    data = load_yaml_file(sample_background_path)
    assert validate_against_schema(data, _schema("background-audio.schema.json")) == []


def test_deprecated_magnitude_review_targets_use_more_less():
    from ocf_tools.indexes import load_all_functions

    for record in load_all_functions():
        text = " ".join([record.canonical_command or ""] + record.command_modes)
        if "GREATER" in text or "LESSER" in text:
            raise AssertionError(
                f"{record.id} still uses GREATER/LESSER vocabulary in canonical commands"
            )
