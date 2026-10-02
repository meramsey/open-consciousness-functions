"""Regression coverage for the localization handoff's confirmed defects."""

from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from ocf_tools.cli import main
from ocf_tools.locale import LocaleCatalog, LocalePack, LocalizationError, resolve_document
from ocf_tools.transcript import measured_durations, resolve_timeline
from ocf_tools.validators import validate_narration_usage
from ocf_tools.voice import resolve_backend

KEY = "session.focus-cycle.opener"


def mixed_document():
    return {
        "schema_version": "1.0",
        "title": "Mixed",
        "locale": "en-US",
        "timeline": [
            {"id": "inline", "at": "00:00.000", "text": "Original English wording."},
            {"id": "keyed", "at": "00:10.000", "narration_key": KEY},
        ],
    }


def test_strict_resolution_refuses_cross_language_inline():
    with pytest.raises(LocalizationError, match="inline.*en-US.*es"):
        resolve_document(mixed_document(), "es")


def test_same_language_inline_is_preserved_and_fallback_is_explicit():
    assert (
        resolve_document(mixed_document(), "en-US")["timeline"][0]["text"]
        == "Original English wording."
    )
    resolved = resolve_document(mixed_document(), "es", strict=False)
    assert resolved["narration"]["resolved"][0]["locale"] == "en-US"


def test_piper_rejects_locale_incompatible_with_fixed_model():
    with pytest.raises(LocalizationError, match="model.*es"):
        resolve_backend(
            {"backend": "piper", "language": "en_US", "piper_model": "/not-needed.onnx"},
            [],
            locale="es",
        )


def test_piper_preserves_model_language_for_compatible_region():
    spec = resolve_backend({"backend": "piper", "language": "en_US"}, [], locale="en-GB")
    assert spec["language"] == "en_US"


def test_sparse_installed_regional_pack_inherits_same_language_only():
    catalog = LocaleCatalog()
    parent = catalog.require("es")
    catalog.packs["es-MX"] = LocalePack(dict(parent.manifest, locale="es-MX"), {})
    assert catalog.spoken(KEY, "es-MX") == catalog.spoken(KEY, "es")
    with pytest.raises(LocalizationError):
        catalog.spoken("focus.eleven.hold", "es-MX")


def test_regional_document_validation_agrees_with_resolution():
    doc = {"timeline": [{"id": "keyed", "narration_key": KEY}], "locale": "es-MX"}
    assert not validate_narration_usage(doc, Path("regional.yaml")).errors


def test_cosmetic_entry_revision_does_not_stale_translation():
    catalog = LocaleCatalog()
    source = catalog.canonical
    source.entries[KEY] = replace(source.entries[KEY], version="1.1.0")
    assert KEY not in catalog.stale_keys("es")
    source.entries[KEY] = replace(source.entries[KEY], version="2.0.0")
    assert KEY in catalog.stale_keys("es")


def test_default_cli_export_resolves_keyed_narration(tmp_path, capsys):
    doc = mixed_document()
    doc["timeline"] = doc["timeline"][1:]
    path = tmp_path / "keyed.yaml"
    path.write_text(yaml.safe_dump(doc))
    assert main(["transcript", "export", str(path), "--format", "srt"]) == 0
    assert LocaleCatalog().spoken(KEY, "en-US") in capsys.readouterr().out


def test_grouped_speech_measurement_maps_to_first_source_event():
    events, _ = resolve_timeline(
        {
            "timeline": [
                {"id": "e1", "at": "00:00.000", "text": "A sentence"},
                {"id": "e2", "at": "00:01.000", "text": "continued."},
            ]
        }
    )
    manifest = {"narration_timing": {"cues": [{"id": "e1+e2", "duration": 3.0}]}}
    assert measured_durations(manifest, events) == {"e1": 3.0}


def test_grouped_cli_subtitle_is_one_utterance_not_invented_word_timing(tmp_path, capsys):
    doc = {
        "schema_version": "1.0",
        "title": "Group",
        "timeline": [
            {"id": "e1", "at": "00:00.000", "text": "A sentence"},
            {"id": "e2", "at": "00:01.000", "text": "continued."},
        ],
    }
    path, timing = tmp_path / "group.yaml", tmp_path / "render.yaml"
    path.write_text(yaml.safe_dump(doc))
    timing.write_text(
        yaml.safe_dump(
            {
                "narration_timing": {
                    "cues": [
                        {"id": "e1+e2", "source_ids": ["e1", "e2"], "at": 0, "duration": 3},
                    ]
                }
            }
        )
    )
    assert (
        main(
            ["transcript", "export", str(path), "--format", "srt", "--render-manifest", str(timing)]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "00:00:00,000 --> 00:00:03,000\nA sentence continued." in output
    assert output.count(" --> ") == 1
