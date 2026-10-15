"""Source-neutral scheduling uses measured PCM, with explicit fallback and identity."""

import io
import json
import wave
from copy import deepcopy

import pytest
from ocf_tools import locale, voice
from ocf_tools.narration_sources import SourceResolver, text_fingerprint
from ocf_tools.utils import OCFError, sha256_of_file


def wav(path, *, frames=8000, stereo=False):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setparams((2 if stereo else 1, 2, 8000, 0, "NONE", "not compressed"))
        writer.writeframes((b"\xe8\x03\x18\xfc" if stereo else b"\xe8\x03") * frames)
    path.write_bytes(buffer.getvalue())
    return buffer.getvalue()


def fixture(tmp_path, mode="hybrid", stereo=False):
    doc = {
        "schema_version": "1.0",
        "id": "source-test",
        "title": "Original technical fixture",
        "locale": "en-US",
        "source": {"format": "manual"},
        "timeline": [
            {
                "id": "first",
                "at": 0,
                "text": "Original first instruction.",
                "timing": {"pause_after": 1},
            },
            {
                "id": "second",
                "after": "first",
                "offset": 0,
                "text": "Original second instruction.",
                "timing": {"anchor": "speech-end"},
            },
        ],
    }
    wav(tmp_path / "take.wav", stereo=stereo)
    config = {
        "schema_version": "2.0",
        "id": "sources",
        "locale": "en-US",
        "mode": mode,
        "fallback": "tts",
        "default_voice": "espeak-ng",
        "output_channels": 2 if stereo else 1,
        "recordings": {
            "take": {
                "file": "take.wav",
                "sha256": sha256_of_file(tmp_path / "take.wav"),
                "text_sha256": text_fingerprint(doc["timeline"][0]["text"]),
                "locale": "en-US",
                "speaker": "synthetic-fixture",
                "version": "1",
                "target": {"event_id": "first"},
                "rights": {"consent": "synthetic-fixture", "redistribution_permission": False},
            }
        },
    }
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return doc, config, path


def test_hybrid_measured_sources_gain_and_stereo_preservation(tmp_path):
    doc, config, path = fixture(tmp_path, stereo=True)
    config["recordings"]["take"]["gain_db"] = -6
    path.write_text(json.dumps(config), encoding="utf-8")
    seen = []
    original = (tmp_path / "take.wav").read_bytes()
    result = voice.render_narration(
        doc,
        tmp_path / "out.wav",
        narration_sources=path,
        sample_rate=8000,
        render_cue_with_profile=lambda text, spec: seen.append((text, spec)) or original,
    )
    assert len(seen) == 1 and seen[0][0] == doc["timeline"][1]["text"]
    assert result["channels"] == 2 and result["duration"] == 4
    assert [cue["at"] for cue in result["cue_stats"]] == [0, 2]
    assert result["cue_stats"][0]["narration_source"]["source"] == "recording"
    assert result["cue_stats"][1]["narration_source"]["fallback_reason"]
    with wave.open(str(tmp_path / "out.wav")) as reader:
        left = int.from_bytes(reader.readframes(1)[:2], "little", signed=True)
        reader.rewind()
        right = int.from_bytes(reader.readframes(1)[2:], "little", signed=True)
        assert left == -right and left == pytest.approx(501, abs=1)
    assert (tmp_path / "take.wav").read_bytes() == original


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("missing", "recorded-only"),
        ("hash", "checksum"),
        ("text", "fingerprint"),
        ("fallback", "fallback=error"),
        ("silence", "cannot suppress"),
        ("locale", "locale"),
        ("unknown", "unknown narration event"),
        ("escape", "relative"),
        ("speaker", "single declared speaker"),
    ],
)
def test_source_preflight_failures_never_fall_back(tmp_path, mutation, match):
    doc, config, path = fixture(tmp_path)
    if mutation == "missing":
        config["mode"] = "recording"
    elif mutation == "hash":
        config["recordings"]["take"]["sha256"] = "0" * 64
    elif mutation == "text":
        doc["timeline"][0]["text"] += " Changed."
    elif mutation == "fallback":
        config["fallback"] = "error"
    elif mutation == "silence":
        config["events"] = {"first": {"source": "silence"}}
    elif mutation == "locale":
        config["locale"] = "es"
    elif mutation == "unknown":
        config["events"] = {"typo": {"source": "tts"}}
    elif mutation == "escape":
        config["recordings"]["take"]["file"] = "C:\\private\\take.wav"
    else:
        config["speaker_consistency"] = "require-single"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(OCFError, match=match):
        SourceResolver(doc, path)


def test_recorded_only_never_resolves_tts_and_semantic_pauses_not_duplicated(tmp_path, monkeypatch):
    doc, config, path = fixture(tmp_path, "recording")
    config["recordings"]["second"] = {
        **config["recordings"]["take"],
        "text_sha256": text_fingerprint(doc["timeline"][1]["text"]),
        "target": {"event_id": "second"},
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(voice, "resolve_backend", lambda *_a, **_k: pytest.fail("no TTS required"))
    result = voice.render_narration(
        doc, tmp_path / "recorded.wav", narration_sources=path, sample_rate=8000
    )
    assert result["duration"] == 4 and result["cue_stats"][1]["at"] == 2


def test_resource_specificity_event_override_and_ambiguity(tmp_path):
    doc, config, path = fixture(tmp_path)
    doc["timeline"][0]["narration_key"] = "fixture.resource"
    config["recordings"]["shared"] = {
        **config["recordings"]["take"],
        "target": {"narration_key": "fixture.resource"},
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    assert SourceResolver(doc, path).rows["first"]["recording_id"] == "take"
    config["events"] = {"first": {"source": "tts", "voice": "espeak-ng"}}
    path.write_text(json.dumps(config), encoding="utf-8")
    assert SourceResolver(doc, path).rows["first"]["source"] == "tts"
    config.pop("events")
    config["recordings"]["duplicate"] = config["recordings"]["take"]
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(OCFError, match="ambiguous"):
        SourceResolver(doc, path)


def test_semantic_unit_hybrid_inserts_internal_gap_once_and_whole_recording_none(
    tmp_path, monkeypatch
):
    doc, config, path = fixture(tmp_path)
    doc["timeline"] = [
        {
            "id": "first",
            "at": 0,
            "text": "Alpha. Omega.",
            "narration_key": "fixture.guidance",
            "timing": {"pause_after": 2, "narration_pacing_units": ["instruction", "landing"]},
        }
    ]
    doc["narration_pacing"] = {
        "entries": {"fixture.guidance": "guided"},
        "profiles": {
            "guided": {
                "rate_scale": 0.9,
                "default_unit": "instruction",
                "pauses": {"sentence": 2, "instruction": 3, "landing": 5},
            }
        },
    }
    entry = config["recordings"]["take"]
    entry.update(
        target={"event_id": "first", "unit_index": 1}, text_sha256=text_fingerprint("Alpha.")
    )
    path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(locale, "resolve_document", lambda document, *_a, **_k: deepcopy(document))
    monkeypatch.setattr(voice, "_pronunciation_hints", lambda *_a: {})
    from ocf_tools import validators

    monkeypatch.setattr(
        validators, "validate_narration_hygiene", lambda *_: validators.ValidationResult()
    )
    result = voice.render_narration(
        doc,
        tmp_path / "units.wav",
        narration_sources=path,
        sample_rate=8000,
        render_cue_with_profile=lambda *_: (tmp_path / "take.wav").read_bytes(),
    )
    cue = result["cue_stats"][0]
    assert cue["duration"] == 5 and cue["pacing"]["internal_pause_s"] == 3
    assert [unit["narration_source"]["source"] for unit in cue["spoken_units"]] == [
        "recording",
        "tts",
    ]
    entry.update(target={"event_id": "first"}, text_sha256=text_fingerprint("Alpha. Omega."))
    path.write_text(json.dumps(config), encoding="utf-8")
    whole = voice.render_narration(
        doc, tmp_path / "whole.wav", narration_sources=path, sample_rate=8000
    )
    assert whole["cue_stats"][0]["duration"] == 1
    assert whole["cue_stats"][0]["spoken_units"] == []


def test_complete_take_is_not_displaced_by_partial_units(tmp_path):
    doc, config, path = fixture(tmp_path)
    doc["timeline"] = [
        {"id": "first", "at": 0, "text": "Alpha. Omega.", "narration_key": "fixture.guidance"}
    ]
    doc["narration_pacing"] = {
        "entries": {"fixture.guidance": "guided"},
        "profiles": {
            "guided": {"rate_scale": 1, "default_unit": "sentence", "pauses": {"sentence": 1}}
        },
    }
    config["recordings"]["take"]["text_sha256"] = text_fingerprint("Alpha. Omega.")
    config["recordings"]["unit"] = {
        **config["recordings"]["take"],
        "text_sha256": text_fingerprint("Alpha."),
        "target": {"event_id": "first", "unit_index": 1},
    }
    config["mode"] = "recording"
    path.write_text(json.dumps(config), encoding="utf-8")
    assert SourceResolver(doc, path).rows["first"]["recording_id"] == "take"


def test_no_background_build_preserves_stereo_and_source_receipts(tmp_path):
    from ocf_tools import audio_build
    from ocf_tools.indexes import load_yaml_file

    doc, config, path = fixture(tmp_path, "recording", stereo=True)
    config["recordings"]["second"] = {
        **config["recordings"]["take"],
        "text_sha256": text_fingerprint(doc["timeline"][1]["text"]),
        "target": {"event_id": "second"},
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    output = tmp_path / "build"
    report = audio_build.build(
        "synthetic",
        manifest_override={"title": "Original fixture", "background_audio": {"strategy": "none"}},
        document_override=doc,
        render_label="source-fixture",
        out_root=output,
        formats=["wav"],
        narration_sources=path,
        sample_rate=8000,
    )
    with wave.open(str(output / report["master"]["file"])) as reader:
        assert reader.getnchannels() == 2
        assert reader.readframes(1) == b"\xe8\x03\x18\xfc"
    saved = load_yaml_file(output / "OCF-RENDER-fixture.yaml")
    cue = saved["narration_timing"]["cues"][0]["narration_source"]
    assert cue["recording_id"] == "take"
    assert cue["recording"]["rights"]["consent"] == "synthetic-fixture"
    assert cue["recording"]["version"] == "1" and cue["preparation"]


def test_event_voice_rate_gain_and_processing_are_executed(tmp_path):
    doc, _config, _path = fixture(tmp_path)
    doc["timeline"][0]["voice"] = {"profile": "espeak-ng", "rate": 0.8, "gain_db": -6}
    doc["timeline"][1]["voice"] = {"profile": "espeak-ng", "rate": 1.2}
    original = (tmp_path / "take.wav").read_bytes()
    seen = []
    metadata = voice.render_narration(
        doc,
        tmp_path / "voices.wav",
        sample_rate=8000,
        render_cue_with_profile=lambda text, spec: seen.append((text, spec)) or original,
    )
    assert seen[0][1]["wpm"] < seen[1][1]["wpm"]
    assert metadata["cue_stats"][0]["narration_source"]["gain_db"] == -6
    source = {
        "schema_version": "2.0",
        "id": "processed-tts",
        "locale": "en-US",
        "mode": "tts",
        "default_voice": "espeak-ng",
        "events": {"first": {"source": "tts", "processing": {"gain_db": -6}}},
    }
    result = voice.render_narration(
        doc,
        tmp_path / "processed.wav",
        sample_rate=8000,
        narration_sources=source,
        render_cue_with_profile=lambda *_: original,
    )
    assert result["cue_stats"][0]["narration_source"]["preparation"]["processing"]["gain_db"] == -6


def test_pcm_negative_endpoint_and_real_overflow():
    assert voice._source_gain([-32768, 32767], 0) == [-32768, 32767]
    with pytest.raises(OCFError, match="clip"):
        voice._source_gain([-32768], 1)
    with pytest.raises(OCFError, match="clip"):
        voice._source_gain([32767], 1)


@pytest.mark.parametrize("mode", ["silence", "typo"])
def test_complete_session_rejects_invalid_source_modes_before_voice_resolution(mode):
    from ocf_tools.complete_session import render_complete_session

    with pytest.raises(OCFError, match="silence|unknown narration"):
        render_complete_session("OCF-SLP-005", narration_source=mode, dry_run=True)


@pytest.mark.parametrize("backend", ["espeak-ng", "piper"])
def test_reference_conditioning_is_never_silently_ignored(backend):
    with pytest.raises(OCFError, match="unsupported voice customization"):
        voice.resolve_backend(
            {"backend": backend, "customization_method": "reference-audio"}, profiles=[]
        )


def test_profile_defaults_apply_without_source_manifest_and_nullable_controls(tmp_path):
    doc, _config, _path = fixture(tmp_path)
    doc["timeline"][0]["voice"] = {"gain_db": None, "rate": None}
    audio = (tmp_path / "take.wav").read_bytes()
    profile = {"backend": "espeak-ng", "gain_db": -6, "processing_defaults": {"gain_db": -6}}
    implicit = voice.render_narration(
        doc,
        tmp_path / "nullable.wav",
        backend=profile,
        sample_rate=8000,
        render_cue_with_profile=lambda *_: audio,
    )
    assert implicit["cue_stats"][0]["narration_source"]["rate_scale"] == 1
    doc["timeline"][0].pop("voice")
    ordinary = voice.render_narration(
        doc,
        tmp_path / "ordinary.wav",
        backend=profile,
        sample_rate=8000,
        render_cue_with_profile=lambda *_: audio,
    )
    assert (tmp_path / "nullable.wav").read_bytes() == (tmp_path / "ordinary.wav").read_bytes()
    assert ordinary["cue_stats"][0]["narration_source"]["preparation"]
    assert implicit["duration"] == ordinary["duration"]
    profile["processing_defaults"] = {"denoise": True}
    with pytest.raises(OCFError, match="denoising is unsupported"):
        voice.render_narration(
            doc,
            tmp_path / "unsupported.wav",
            backend=profile,
            sample_rate=8000,
            render_cue_with_profile=lambda *_: audio,
        )


@pytest.mark.parametrize("backend", ["piper", "espeak-ng"])
def test_nested_rate_defaults_precede_session_pacing_and_preserve_padding(backend):
    from ocf_tools.narration_first import _adjusted_profile

    profile = {
        "backend": backend,
        "rate_defaults": {
            "piper_length_scale": 1.1,
            "words_per_min": 180,
            "speed": 1.0,
            "sentence_silence_s": 0.7,
        },
    }
    adjusted = _adjusted_profile(
        {"pacing": {"speech_rate_scale": 1.2}, "voice_profile": {"backend": backend}}, profile
    )
    resolved = voice.resolve_backend(adjusted, profiles=[])
    if backend == "piper":
        assert resolved["piper_length_scale"] == pytest.approx(1.32)
        assert resolved["piper_sentence_silence_s"] == 0.7
        paced, _ = voice._paced_voice_spec(resolved, 0.8)
        assert paced["piper_sentence_silence_s"] == 0
    else:
        assert resolved["wpm"] == 150


def test_synth_processing_input_cache_repairs_interrupted_generation(tmp_path):
    import hashlib

    from ocf_tools.paths import work_path

    audio = wav(tmp_path / "take.wav")
    checksum = hashlib.sha256(audio).hexdigest()
    path = work_path("cache", "narration-processing-inputs", checksum + ".wav")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"interrupted")
    row = {"processing": {"gain_db": -6}}
    first, _ = voice._source_processing(audio, row, {}, 8000, 1)
    repeated, receipt = voice._source_processing(audio, row, {}, 8000, 1)
    assert first == repeated and receipt["cache_hit"] is True
    assert path.read_bytes() == audio


def test_marked_complete_stem_integrates_without_tts_or_added_silence(tmp_path, monkeypatch):
    doc, _config, path = fixture(tmp_path)
    wav(tmp_path / "stem.wav", frames=24000, stereo=True)
    source = {
        "schema_version": "2.0",
        "id": "complete-stem",
        "locale": "en-US",
        "mode": "recording",
        "output_channels": 2,
        "session_stem": {
            "file": "stem.wav",
            "sha256": sha256_of_file(tmp_path / "stem.wav"),
            "locale": "en-US",
            "speaker": "synthetic-fixture",
            "version": "1",
            "markers": {
                "first": {
                    "at": 0,
                    "speech_duration": 1,
                    "end": 2,
                    "text_sha256": text_fingerprint(doc["timeline"][0]["text"]),
                },
                "second": {
                    "at": 2,
                    "speech_duration": 1,
                    "end": 3,
                    "text_sha256": text_fingerprint(doc["timeline"][1]["text"]),
                },
            },
        },
    }
    path.write_text(json.dumps(source), encoding="utf-8")
    monkeypatch.setattr(
        voice, "resolve_backend", lambda *_a, **_k: pytest.fail("stem needs no TTS")
    )
    output = tmp_path / "complete-stem.wav"
    result = voice.render_narration(doc, output, narration_sources=path, sample_rate=8000)
    assert result["duration"] == 3 and result["channels"] == 2
    assert result["narration_source"]["mode"] == "recording"
    assert result["cue_stats"][1]["narration_source"]["marker"]["at"] == 2
    assert output.read_bytes() == (tmp_path / "stem.wav").read_bytes()


def test_stage_recording_can_use_explicit_per_event_segments(tmp_path):
    doc, config, path = fixture(tmp_path, "recording")
    wav(tmp_path / "take.wav", frames=48000)
    entry = config["recordings"]["take"]
    entry["sha256"] = sha256_of_file(tmp_path / "take.wav")
    entry["segment"] = {"start_s": 0, "end_s": 1}
    config["recordings"]["second"] = {
        **entry,
        "text_sha256": text_fingerprint(doc["timeline"][1]["text"]),
        "target": {"event_id": "second"},
        "segment": {"start_s": 2, "end_s": 4},
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    result = voice.render_narration(
        doc, tmp_path / "segments.wav", narration_sources=path, sample_rate=8000
    )
    assert result["duration"] == 5
    assert result["cue_stats"][1]["at"] == 2
    assert result["cue_stats"][1]["duration"] == 2
    receipt = result["cue_stats"][1]["narration_source"]["preparation"]
    assert receipt["selected_segment"]["duration_s"] == 2


def test_strict_speaker_consistency_rejects_unidentified_default_tts(tmp_path):
    doc, config, path = fixture(tmp_path)
    config.pop("default_voice")
    config["speaker_consistency"] = "require-single"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(OCFError, match="declared speaker"):
        SourceResolver(doc, path)
