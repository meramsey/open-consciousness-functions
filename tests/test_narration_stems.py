"""Whole-stem identity, natural timing, PCM and safe-publication contracts."""

from __future__ import annotations

import hashlib
import io
import json
import os
import struct
import wave
from copy import deepcopy

import pytest
from ocf_tools import narration_stems as stems
from ocf_tools.recordings import session_fingerprint
from ocf_tools.utils import OCFError, OCFFileExistsError
from ocf_tools.validators import _load_schema, validate_against_schema

pytestmark = pytest.mark.unit


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixture(tmp_path, *, rate=8000, channels=1, duration=2.25):
    """Manual timestamps: speech/pause, DSP transition/pause, speech, return."""
    doc = {
        "id": "stem-session",
        "locale": "en-US",
        "narration": {"locale": "en-US", "resolved": []},
        "pacing_profile": {"id": "do-not-insert-these-pauses"},
        "timeline": [
            {
                "id": "intro.say",
                "at": 0.25,
                "text": "Exact words.  Même texte!",
                "timing": {"pause_after": 0.25},
            },
            {
                "id": "focus.enter",
                "after": "intro.say",
                "offset": 0.125,
                "semantic": "focus.ten.enter",
                "auditory_cue": "focus.ten.enter",
                "dsp": {"transition_s": 0.5},
                "timing": {"anchor": "event-end", "pause_after": 0.125},
            },
            {
                "id": "practice.say",
                "after": "focus.enter",
                "offset": 0,
                "text": "Exact words.  Même texte!",
                "timing": {"anchor": "event-end", "pause_after": 0.125},
            },
            {
                "id": "return.ready",
                "after": "practice.say",
                "offset": 0.125,
                "semantic": "session.complete",
                "auditory_cue": "session.complete",
                "timing": {"anchor": "speech-end"},
            },
        ],
    }
    frames = round(duration * rate)
    # Distinct channels and preserved quiet lead/tail; no content inference.
    pcm = b"".join(
        struct.pack("<" + "h" * channels, *([1000] if channels == 1 else [1000, -2000]))
        if rate // 8 <= frame < frames - rate // 8
        else b"\0\0" * channels
        for frame in range(frames)
    )
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
        writer.writeframes(pcm)
    source = tmp_path / "unhelpful-name-no-focus-information.wav"
    source.write_bytes(buffer.getvalue())
    spec = {
        "file": source.name,
        "sha256": sha(source.read_bytes()),
        "locale": "en-US",
        "speaker": "fixture-speaker",
        "version": "take-2",
        "rights": {"consent": "synthetic-fixture", "redistribution_permission": False},
        "approval": "pending",
        "markers": {
            "intro.say": {
                "at": 0.25,
                "speech_duration": 0.25,
                "end": 0.75,
                "text_sha256": sha(doc["timeline"][0]["text"].encode()),
            },
            "focus.enter": {"at": 0.875, "speech_duration": 0, "end": 1.5},
            "practice.say": {
                "at": 1.5,
                "speech_duration": 0.25,
                "end": 1.875,
                "text_sha256": sha(doc["timeline"][2]["text"].encode()),
            },
            "return.ready": {"at": 2, "speech_duration": 0, "end": 2},
        },
    }
    return doc, spec, source, pcm


def render(tmp_path, doc, spec, **kwargs):
    return stems.render_stem(
        doc, spec, tmp_path, tmp_path / "output.wav", locale="en-US", sample_rate=8000, **kwargs
    )


@pytest.mark.parametrize("channels", [1, 2])
def test_native_plan_and_render_preserve_entire_stem_and_contract(tmp_path, monkeypatch, channels):
    doc, spec, source, pcm = fixture(tmp_path, channels=channels)
    original = source.read_bytes()
    from ocf_tools import voice

    monkeypatch.setattr(voice, "resolve_backend", lambda *a, **k: pytest.fail("no TTS selection"))
    monkeypatch.setattr(voice, "render_cue_wav", lambda *a, **k: pytest.fail("no TTS synthesis"))
    before = deepcopy((doc, spec))
    plan = stems.plan_stem(doc, spec, tmp_path, locale="en-US")
    assert not (tmp_path / "output.wav").exists()
    result = render(tmp_path, doc, spec, channels=channels)
    assert result.keys() >= {
        "backend",
        "profile_id",
        "locale",
        "voice",
        "voice_options",
        "narration_source",
        "sample_rate",
        "channels",
        "duration",
        "cues",
        "cue_stats",
        "narration_pacing",
        "event_timing",
        "auditory_cues",
        "narration_resolution",
        "overlap_mode",
        "timing_mode",
        "locale_notes",
        "pronunciation_hints",
        "utterances",
        "even_counts",
    }
    assert result["backend"] == "prerecorded-stem"
    assert result["profile_id"] is None and result["voice_options"] == {}
    assert result["locale"] == result["voice"] == "en-US"
    assert result["pronunciation_hints"] == 0
    assert result["narration_pacing"]["profiles"] == {}
    assert result["duration"] == plan["duration"] == 2.25  # No tail or reassembled pauses.
    assert result["sample_rate"] == plan["sample_rate"] == 8000
    assert result["channels"] == plan["channels"] == channels
    assert result["cues"] == result["utterances"] == 2
    assert result["narration_resolution"] == doc["narration"]
    assert [row["at"] for row in result["event_timing"]] == [0.25, 0.875, 1.5, 2]
    assert [row["end"] for row in result["event_timing"]] == [0.75, 1.5, 1.875, 2]
    assert result["event_timing"][1]["dsp"] == {"transition_s": 0.5}
    assert [(b["event_id"], b["at"]) for b in result["auditory_cues"]] == [
        ("focus.enter", 0.875),
        ("return.ready", 2),
    ]
    assert source.read_bytes() == original
    assert (doc, spec) == before
    with wave.open(str(tmp_path / "output.wav"), "rb") as reader:
        assert reader.getnchannels() == channels
        assert reader.getsampwidth() == 2
        assert reader.readframes(reader.getnframes()) == pcm
    json.dumps(result, allow_nan=False)


def test_provenance_and_cue_rows_are_build_compatible_without_inferred_approval(tmp_path):
    doc, spec, _, _ = fixture(tmp_path)
    spec["approval"] = "approved"  # Preserve declaration, never infer content review.
    report = render(tmp_path, doc, spec)
    provenance = report["narration_source"]
    assert provenance["session_fingerprint"] == session_fingerprint(doc)
    assert provenance["preparation"]["original_preserved"] is True
    assert provenance["preparation"]["input_sha256"] == spec["sha256"]
    assert provenance["preparation"]["processed_sha256"] == sha(
        (tmp_path / "output.wav").read_bytes()
    )
    assert provenance["original"]["frames"] == provenance["processed"]["frames"] == 18000
    assert len(provenance["events"]) == 4
    assert provenance["approval"] == "approved"
    assert provenance["speech_content_review"] == "pending"
    assert provenance["content_verification"].startswith("pending;")
    for cue in report["cue_stats"]:
        row = cue["narration_source"]
        assert row["source"] == "recorded-stem"
        assert row["speaker"] == spec["speaker"] and row["version"] == "take-2"
        assert row["rights"] == spec["rights"]
        assert row["marker"] == spec["markers"][cue["id"]]
        assert row["checksum_sha256"] == spec["sha256"]
        assert row["speech_content_review"] == "pending"
        assert cue["samples"] == 2000  # Frames, not interleaved sample count.
        assert cue["pacing"] is None and cue["spoken_units"] == []
    # These are the nested fields copied by audio_build's final report.
    retained = {"narration_source": provenance, "cues": report["cue_stats"]}
    assert json.loads(json.dumps(retained))["cues"][0]["narration_source"]["marker"]["at"] == 0.25


def test_sections_and_optional_end_markers(tmp_path):
    doc, spec, _, _ = fixture(tmp_path)
    timeline = doc.pop("timeline")
    doc["sections"] = [
        {"id": "first", "timeline": timeline[:2]},
        {"id": "last", "timeline": timeline[2:]},
    ]
    for marker in spec["markers"].values():
        marker.pop("end")
    spec["session_fingerprint"] = session_fingerprint(doc)
    result = render(tmp_path, doc, spec)
    assert result["event_timing"][1]["end"] == 1.5
    assert {r["id"] for r in result["event_timing"]} == set(spec["markers"])


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("missing-boundary", "missing=.*focus.enter"),
        ("extra", "extra=.*unknown"),
        ("missing-spoken", "missing=.*intro.say"),
        ("missing-hash", "text_sha256"),
        ("stale-hash", "text_sha256"),
        ("whitespace-changed", "text_sha256"),
        ("missing-duration", "speech_duration"),
        ("nonspoken-duration", "nonspoken.*=0"),
        ("zero-spoken-duration", "positive speech_duration"),
        ("speech-end-not-structural-end", "structural event end"),
        ("dsp-end-not-structural-end", "structural event end"),
        ("guessed-focus-at", "scheduled anchor"),
        ("locale", "locale"),
        ("doc-locale", "locale"),
        ("event-locale", "locale"),
        ("session", "different session/version"),
        ("checksum", "checksum"),
        ("duplicate-id", "unique composed event IDs"),
        ("missing-id", "unique composed event IDs"),
        ("unresolved-key", "resolved narration"),
        ("unexpected-field", "Additional properties"),
        ("trim", "narration stem"),
        ("speed", "Additional properties"),
        ("negative-duration", "minimum"),
        ("nan", "finite JSON"),
        ("infinity", "finite JSON"),
        ("doc-nan", "finite JSON"),
    ],
)
def test_invalid_declarations_fail_before_publication(tmp_path, mutation, match):
    doc, spec, _, _ = fixture(tmp_path)
    markers = spec["markers"]
    if mutation == "missing-boundary":
        del markers["focus.enter"]
    elif mutation == "extra":
        markers["unknown"] = {"at": 0, "speech_duration": 0}
    elif mutation == "missing-spoken":
        del markers["intro.say"]
    elif mutation == "missing-hash":
        del markers["intro.say"]["text_sha256"]
    elif mutation == "stale-hash":
        markers["intro.say"]["text_sha256"] = "0" * 64
    elif mutation == "whitespace-changed":
        doc["timeline"][0]["text"] += " "
    elif mutation == "missing-duration":
        del markers["focus.enter"]["speech_duration"]
    elif mutation == "nonspoken-duration":
        markers["focus.enter"]["speech_duration"] = 0.1
    elif mutation == "zero-spoken-duration":
        markers["intro.say"]["speech_duration"] = 0
    elif mutation == "speech-end-not-structural-end":
        markers["intro.say"]["end"] = 0.5
    elif mutation == "dsp-end-not-structural-end":
        markers["focus.enter"]["end"] = 0.875
    elif mutation == "guessed-focus-at":
        markers["focus.enter"]["at"] = 1
    elif mutation == "locale":
        spec["locale"] = "fr"
    elif mutation == "doc-locale":
        doc["locale"] = "fr"
    elif mutation == "event-locale":
        doc["timeline"][0]["locale"] = "fr"
    elif mutation == "session":
        spec["session_fingerprint"] = "0" * 64
    elif mutation == "checksum":
        spec["sha256"] = "0" * 64
    elif mutation == "duplicate-id":
        doc["timeline"].append(deepcopy(doc["timeline"][0]))
    elif mutation == "missing-id":
        del doc["timeline"][0]["id"]
    elif mutation == "unresolved-key":
        doc["timeline"][0].update(narration_key="unresolved.key", text="")
    elif mutation == "unexpected-field":
        spec["infer_markers"] = True
    elif mutation == "trim":
        spec["processing"] = {"trim_silence": {}}
    elif mutation == "speed":
        spec["processing"] = {"speed": 1.2}
    elif mutation == "negative-duration":
        markers["intro.say"]["speech_duration"] = -1
    elif mutation == "nan":
        markers["focus.enter"]["at"] = float("nan")
    elif mutation == "infinity":
        markers["focus.enter"]["speech_duration"] = float("inf")
    else:
        doc["timeline"][1]["dsp"]["transition_s"] = float("nan")
    with pytest.raises(OCFError, match=match):
        render(tmp_path, doc, spec)
    assert not (tmp_path / "output.wav").exists()


@pytest.mark.parametrize("name", ["../outside.wav", "/absolute.wav", "C:/drive.wav", "a\\b.wav"])
def test_portable_contained_source_paths(tmp_path, name):
    doc, spec, _, _ = fixture(tmp_path)
    spec["file"] = name
    with pytest.raises(OCFError, match="portable relative"):
        render(tmp_path, doc, spec)


def test_symlink_escape_and_missing_file(tmp_path):
    doc, spec, source, _ = fixture(tmp_path)
    subdir = tmp_path / "manifest"
    subdir.mkdir()
    (subdir / source.name).symlink_to(source)
    with pytest.raises(OCFError, match="escapes"):
        stems.plan_stem(doc, spec, subdir, locale="en-US")
    source.unlink()
    with pytest.raises(OCFError, match="missing"):
        render(tmp_path, doc, spec)


@pytest.mark.parametrize("delta,accepted", [(1 / 8000, True), (2 / 8000, False), (0.019, False)])
def test_one_frame_marker_tolerance_preserves_manual_timestamp(tmp_path, delta, accepted):
    doc, spec, _, _ = fixture(tmp_path)
    spec["markers"]["focus.enter"]["at"] += delta
    spec["markers"]["focus.enter"]["end"] += delta
    if accepted:
        result = render(tmp_path, doc, spec)
        assert result["event_timing"][1]["at"] == 0.875 + delta
        assert result["event_timing"][1]["end"] == pytest.approx(1.5 + delta)
        assert result["auditory_cues"][0]["at"] == 0.875 + delta
    else:
        with pytest.raises(OCFError, match="scheduled anchor"):
            render(tmp_path, doc, spec)


@pytest.mark.parametrize("reflow", [False, True])
def test_overlaps_are_rejected_even_when_reflow_would_move_speech(tmp_path, reflow):
    doc, spec, _, _ = fixture(tmp_path)
    doc["timeline"][2].pop("after")
    doc["timeline"][2]["at"] = 0.375
    doc["timeline"][2]["timing"]["policy"] = "reflow" if reflow else "fixed"
    spec["markers"]["practice.say"].update(at=0.375, end=0.75)
    with pytest.raises(OCFError, match="overlap|scheduled anchor"):
        render(tmp_path, doc, spec)


def test_manual_overlap_inside_scheduler_tolerance_is_rejected(tmp_path):
    doc, spec, _, _ = fixture(tmp_path)
    # Remove nonspoken transition from the speech dependency, then start the
    # second speech half a frame before the first's explicitly required pause ends.
    doc["timeline"][2].update(after="intro.say", offset=0)
    spec["markers"]["practice.say"].update(at=0.75 - 0.5 / 8000, end=1.125 - 0.5 / 8000)
    spec["markers"]["return.ready"].update(at=1.25, end=1.25)
    with pytest.raises(OCFError, match="manual speech/pause overlap"):
        render(tmp_path, doc, spec)


@pytest.mark.parametrize("duration", [1.9, 1.999875])
def test_marker_beyond_audio_and_single_frame_truncation(tmp_path, duration):
    doc, spec, _, _ = fixture(tmp_path, duration=duration)
    with pytest.raises(OCFError, match="beyond audio|truncated audio"):
        render(tmp_path, doc, spec)


def test_optional_manual_end_beyond_audio_is_rejected_inside_alignment_tolerance(tmp_path):
    doc, spec, _, _ = fixture(tmp_path, duration=2)
    spec["markers"]["return.ready"]["end"] = 2 + 0.5 / 8000
    with pytest.raises(OCFError, match="beyond audio"):
        render(tmp_path, doc, spec)


def test_structural_end_uses_maximum_of_speech_and_transition_and_both_anchor_types(tmp_path):
    doc, spec, _, _ = fixture(tmp_path)
    text = doc["timeline"][0]["text"]
    doc["timeline"] = [
        {
            "id": "speech",
            "at": 0,
            "text": text,
            "dsp": {"transition_s": 0.5},
            "timing": {"pause_after": 0.1},
        },
        {"id": "speech-end", "after": "speech", "offset": 0, "timing": {"anchor": "speech-end"}},
        {"id": "event-end", "after": "speech", "offset": 0, "timing": {"anchor": "event-end"}},
    ]
    spec["markers"] = {
        "speech": {"at": 0, "speech_duration": 0.1, "end": 0.6, "text_sha256": sha(text.encode())},
        "speech-end": {"at": 0.2, "speech_duration": 0},
        "event-end": {"at": 0.6, "speech_duration": 0},
    }
    result = render(tmp_path, doc, spec)
    assert result["event_timing"][0]["end"] == pytest.approx(0.6)
    assert [row["at"] for row in result["event_timing"]] == [0, 0.2, 0.6]


@pytest.mark.parametrize("intentional_repeat", [False, True])
def test_duplicate_auditory_cues_require_explicit_repeat(tmp_path, intentional_repeat):
    doc, spec, _, _ = fixture(tmp_path)
    event = deepcopy(doc["timeline"][1])
    event.update(id="duplicate", intentional_repeat=intentional_repeat)
    doc["timeline"].append(event)
    spec["markers"]["duplicate"] = deepcopy(spec["markers"]["focus.enter"])
    if intentional_repeat:
        result = render(tmp_path, doc, spec)
        assert len(result["auditory_cues"]) == 3
    else:
        with pytest.raises(OCFError, match="duplicate auditory cue"):
            render(tmp_path, doc, spec)


def test_truncated_original_pcm_is_rejected(tmp_path):
    doc, spec, source, _ = fixture(tmp_path)
    source.write_bytes(source.read_bytes()[:-2])
    spec["sha256"] = sha(source.read_bytes())
    with pytest.raises(OCFError, match="truncated"):
        render(tmp_path, doc, spec)


@pytest.mark.parametrize(
    "mutation", ["frames", "duration", "checksum", "trim", "short-pcm", "format"]
)
def test_invalid_processing_receipts_or_frame_bytes_cannot_publish(tmp_path, monkeypatch, mutation):
    doc, spec, _, _ = fixture(tmp_path)
    real_process = stems.process_recording

    def broken(*args, **kwargs):
        data, receipt = real_process(*args, **kwargs)
        if mutation == "frames":
            receipt["processed"]["frames"] -= 1
        elif mutation == "duration":
            receipt["processed"]["duration_s"] += 0.01
        elif mutation == "checksum":
            receipt["processed_sha256"] = "0" * 64
        elif mutation == "trim":
            receipt["trimmed"]["leading_frames"] = 1
        elif mutation == "short-pcm":
            data = data[:-2]
        else:
            data = b"not a WAV file"
        return data, receipt

    monkeypatch.setattr(stems, "process_recording", broken)
    with pytest.raises(OCFError, match="frame|truncated|PCM WAV"):
        render(tmp_path, doc, spec)
    assert not (tmp_path / "output.wav").exists()


def test_only_explicit_processing_changes_samples_and_preserves_duration(tmp_path):
    doc, spec, source, _ = fixture(tmp_path, channels=2)
    original = source.read_bytes()
    spec["processing"] = {"gain_db": -6, "fade_in_s": 0.05}
    result = render(tmp_path, doc, spec, channels=2)
    receipt = result["narration_source"]["preparation"]
    assert receipt["processing"]["gain_db"] == -6
    assert receipt["processing"]["fade_out_s"] == 0
    assert receipt["channel_conversion"] == "unchanged"
    assert receipt["original"]["frames"] == receipt["processed"]["frames"]
    assert source.read_bytes() == original
    assert (tmp_path / "output.wav").read_bytes() != original


def test_explicit_mono_downmix_and_mono_to_stereo_duplication(tmp_path):
    doc, spec, _, _ = fixture(tmp_path, channels=2)
    result = render(tmp_path, doc, spec)
    assert result["narration_source"]["preparation"]["channel_conversion"] == "arithmetic_mean_L_R"
    doc, spec, _, _ = fixture(tmp_path)
    result = render(tmp_path, doc, spec, channels=2)
    assert result["narration_source"]["preparation"]["channel_conversion"] == "duplicate_mono"
    with wave.open(str(tmp_path / "output.wav"), "rb") as reader:
        values = struct.unpack(
            "<" + "h" * reader.getnframes() * 2, reader.readframes(reader.getnframes())
        )
    assert values[::2] == values[1::2]


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_original_cannot_be_overwritten_even_by_alias(tmp_path, alias):
    doc, spec, source, _ = fixture(tmp_path)
    original = source.read_bytes()
    target = source
    if alias != "same":
        target = tmp_path / "alias.wav"
        if alias == "symlink":
            target.symlink_to(source)
        else:
            os.link(source, target)
    with pytest.raises(OCFError, match="original source"):
        stems.render_stem(doc, spec, tmp_path, target, locale="en-US", sample_rate=8000)
    assert source.read_bytes() == original


def test_nooverwrite_and_atomic_overwrite(tmp_path):
    doc, spec, _, _ = fixture(tmp_path)
    target = tmp_path / "output.wav"
    target.write_bytes(b"existing")
    with pytest.raises(OCFFileExistsError):
        render(tmp_path, doc, spec, overwrite=False)
    assert target.read_bytes() == b"existing"
    render(tmp_path, doc, spec)
    assert target.read_bytes().startswith(b"RIFF")
    target.unlink()
    render(tmp_path, doc, spec, overwrite=False)
    assert target.read_bytes().startswith(b"RIFF")
    assert not list(tmp_path.glob(".output.wav.*.tmp"))


def test_nooverwrite_race_preserves_winner(tmp_path, monkeypatch):
    doc, spec, _, _ = fixture(tmp_path)
    target = tmp_path / "output.wav"
    real_link = stems.os.link

    def competing_link(source, destination):
        destination.write_bytes(b"race winner")
        return real_link(source, destination)

    monkeypatch.setattr(stems.os, "link", competing_link)
    with pytest.raises(OCFFileExistsError):
        render(tmp_path, doc, spec, overwrite=False)
    assert target.read_bytes() == b"race winner"
    assert not list(tmp_path.glob(".output.wav.*.tmp"))


def test_atomic_publication_failure_preserves_old_output(tmp_path, monkeypatch):
    doc, spec, _, _ = fixture(tmp_path)
    # Warm the recording cache so the injected replace fault targets publication.
    stems.plan_stem(doc, spec, tmp_path, locale="en-US")
    target = tmp_path / "output.wav"
    target.write_bytes(b"existing")

    def fail_replace(*args):
        raise OSError("publication failed")

    monkeypatch.setattr(stems.os, "replace", fail_replace)
    with pytest.raises(OSError, match="publication failed"):
        render(tmp_path, doc, spec)
    assert target.read_bytes() == b"existing"
    assert not list(tmp_path.glob(".output.wav.*.tmp"))


@pytest.mark.parametrize("sample_rate,channels", [(True, 1), (7999, 1), (8000, True), (8000, 3)])
def test_invalid_output_format(tmp_path, sample_rate, channels):
    doc, spec, _, _ = fixture(tmp_path)
    with pytest.raises(OCFError, match="sample_rate|channels"):
        stems.render_stem(
            doc,
            spec,
            tmp_path,
            tmp_path / "output.wav",
            locale="en-US",
            sample_rate=sample_rate,
            channels=channels,
        )


def test_default_render_format_is_pcm_44100_mono(tmp_path):
    doc, spec, _, _ = fixture(tmp_path, rate=44100)
    result = stems.render_stem(doc, spec, tmp_path, tmp_path / "output.wav", locale="en-US")
    assert result["sample_rate"] == 44100 and result["channels"] == 1


def test_schema_resolves_shared_processing_and_rejects_trim_and_unknown_keys(tmp_path):
    _, spec, _, _ = fixture(tmp_path)
    schema = _load_schema("narration-stem.schema.json")
    assert not validate_against_schema(spec, schema)
    spec["processing"] = {"gain_db": -3, "compression": {"ratio": 2}}
    assert not validate_against_schema(spec, schema)
    spec["processing"]["trim_silence"] = {"leading": False, "trailing": False}
    assert validate_against_schema(spec, schema)
