"""Actual speech-end dependencies and fixed-vs-elastic localized timing."""

import io
import wave

import pytest
import yaml
from ocf_tools.cli import main
from ocf_tools.locale import LocaleCatalog
from ocf_tools.transcript import apply_render_timing, export_lrc, export_srt
from ocf_tools.utils import OCFError
from ocf_tools.voice import apply_pronunciation, render_narration

KEY = "session.focus-cycle.opener"


def test_pronunciation_override_replaces_instead_of_repeating_token():
    hint = "[[p l V s f oU k @ s]]"
    assert (
        apply_pronunciation("Say PLUS-FOCUS.", {"PLUS-FOCUS": {"espeak-ng": hint}}, "espeak-ng")
        == f"Say {hint}."
    )


def pcm(seconds):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(100)
        writer.writeframes(b"\x01\x00" * int(seconds * 100))
    return buffer.getvalue()


def render(doc, locale, path):
    english = LocaleCatalog().spoken(KEY, "en-US")
    return render_narration(
        doc,
        path,
        locale=locale,
        backend={"backend": "espeak-ng"},
        sample_rate=100,
        render_cue=lambda text: pcm(0.5 if text == english else 2),
    )


def test_long_translation_never_overwrites_next_fixed_speech(tmp_path):
    doc = {
        "schema_version": "1.0",
        "title": "Fixed",
        "timeline": [
            {"id": "a", "at": "00:00.000", "narration_key": KEY},
            {"id": "b", "at": "00:01.000", "narration_key": KEY},
        ],
    }
    with pytest.raises(OCFError, match="fixed.*overlap|overlap.*fixed"):
        render(doc, "es", tmp_path / "long.wav")
    assert not (tmp_path / "long.wav").exists()


def test_localized_speech_end_coordinates_dsp_and_ready_binding(tmp_path):
    doc = {
        "schema_version": "1.0",
        "title": "Dependent",
        "timeline": [
            {
                "id": "open",
                "at": "00:00.000",
                "semantic": "focus.eleven.open",
                "narration_key": KEY,
            },
            {
                "id": "transition",
                "after": "open",
                "offset": 0,
                "timing": {"anchor": "speech-end"},
                "semantic": "focus.eleven.transition.open",
                "dsp": {"state": {"from": "focus-10", "to": "focus-11"}, "transition_s": 3},
            },
            {
                "id": "ready",
                "after": "transition",
                "offset": 0,
                "timing": {"anchor": "event-end"},
                "semantic": "focus.eleven.ready",
                "auditory_cue": "focus.eleven.ready",
            },
        ],
    }
    english, spanish = (
        render(doc, "en-US", tmp_path / "en.wav"),
        render(doc, "es", tmp_path / "es.wav"),
    )
    en_times = {event["id"]: event["at"] for event in english["event_timing"]}
    es_times = {event["id"]: event["at"] for event in spanish["event_timing"]}
    assert en_times == {"open": 0, "transition": 0.5, "ready": 3.5}
    assert es_times == {"open": 0, "transition": 2, "ready": 5}
    assert spanish["auditory_cues"][0]["at"] == 5
    assert spanish["cue_stats"][0]["source_ids"] == ["open"]


def test_reflow_is_explicit_and_leaves_unrelated_fixed_anchor_intact(tmp_path):
    doc = {
        "schema_version": "1.0",
        "title": "Reflow",
        "timeline": [
            {"id": "a", "at": "00:00.000", "narration_key": KEY},
            {"id": "b", "at": "00:01.000", "narration_key": KEY, "timing": {"policy": "reflow"}},
            {"id": "fixed", "at": "00:10.000", "semantic": "session.fixed-anchor"},
        ],
    }
    meta = render(doc, "es", tmp_path / "reflow.wav")
    assert [cue["at"] for cue in meta["cue_stats"]] == [0, 2]
    assert {event["id"]: event["at"] for event in meta["event_timing"]}["fixed"] == 10
    assert not any(cue["cut_previous"] for cue in meta["cue_stats"])
    from ocf_tools.locale import resolve_document

    localized = resolve_document(doc, "es")
    view = apply_render_timing(localized, {"narration_timing": {"cues": meta["cue_stats"]}})
    assert "00:00:02,000 --> 00:00:04,000" in export_srt(view)
    assert "[00:02.00]" in export_lrc(view)


def test_pause_after_and_start_relative_anchor_keep_distinct_meanings(tmp_path):
    doc = {
        "schema_version": "1.0",
        "title": "Pause",
        "timeline": [
            {"id": "a", "at": "00:00.000", "narration_key": KEY, "timing": {"pause_after": 1}},
            {
                "id": "b",
                "after": "a",
                "offset": 1,
                "timing": {"anchor": "speech-end"},
                "narration_key": KEY,
            },
        ],
    }
    meta = render(doc, "es", tmp_path / "pause.wav")
    assert meta["cue_stats"][1]["at"] == 4


def test_split_count_speech_keeps_source_ids_and_exported_token_text(tmp_path):
    doc = {
        "schema_version": "1.0",
        "title": "Counts",
        "timeline": [
            {"id": "a", "at": "00:00.000", "text": "Ten. Eleven."},
            {"id": "b", "at": "00:02.000", "text": "Twelve."},
        ],
    }
    meta = render_narration(
        doc,
        tmp_path / "counts.wav",
        backend={"backend": "espeak-ng"},
        render_cue=lambda text: pcm(0.25),
        sample_rate=100,
        even_counts=True,
    )
    assert [cue["source_ids"] for cue in meta["cue_stats"]] == [["a"], ["a"], ["b"]]
    view = apply_render_timing(doc, {"narration_timing": {"cues": meta["cue_stats"]}})
    assert [event["text"] for event in view["timeline"]] == ["Ten.", "Eleven.", "Twelve."]
    assert len({event["id"] for event in view["timeline"]}) == 3
    assert meta["event_timing"][0]["at"] == 0
    assert meta["event_timing"][0]["end"] == 1.25


def test_cli_subtitles_follow_render_locale_and_actual_start(tmp_path, capsys):
    doc = {
        "schema_version": "1.0",
        "title": "Locale",
        "timeline": [{"id": "a", "at": "00:00.000", "narration_key": KEY}],
    }
    path, manifest = tmp_path / "source.yaml", tmp_path / "render.yaml"
    path.write_text(yaml.safe_dump(doc))
    spanish = LocaleCatalog().spoken(KEY, "es")
    manifest.write_text(
        yaml.safe_dump(
            {
                "voice": {"locale": "es"},
                "narration_timing": {
                    "cues": [
                        {
                            "id": "a",
                            "source_ids": ["a"],
                            "at": 2,
                            "duration": 3,
                            "display_text": spanish,
                        },
                    ]
                },
            }
        )
    )
    assert (
        main(
            [
                "transcript",
                "export",
                str(path),
                "--format",
                "lrc",
                "--render-manifest",
                str(manifest),
            ]
        )
        == 0
    )
    assert f"[00:02.00]{spanish}" in capsys.readouterr().out
    assert (
        main(
            [
                "transcript",
                "export",
                str(path),
                "--format",
                "srt",
                "--locale",
                "en-US",
                "--render-manifest",
                str(manifest),
            ]
        )
        == 1
    )
    assert "does not match" in capsys.readouterr().err


def test_end_dependent_subtitles_require_measured_render_data(tmp_path, capsys):
    doc = {
        "schema_version": "1.0",
        "title": "Dependent",
        "timeline": [
            {"id": "a", "at": "00:00.000", "narration_key": KEY},
            {
                "id": "b",
                "after": "a",
                "offset": 0,
                "timing": {"anchor": "speech-end"},
                "narration_key": KEY,
            },
        ],
    }
    path = tmp_path / "dependent.yaml"
    path.write_text(yaml.safe_dump(doc))
    assert main(["transcript", "export", str(path), "--format", "srt"]) == 1
    assert "require a render manifest" in capsys.readouterr().err


def test_section_gain_window_uses_actual_localized_boundaries():
    from ocf_tools.audio_build import _narration_gain_windows

    doc = {
        "sections": [
            {"id": "quiet", "gain_db": -24, "timeline": [{"id": "a", "at": "00:01.000"}]},
            {"id": "next", "timeline": [{"id": "b", "at": "00:04.000"}]},
        ]
    }
    assert _narration_gain_windows(doc, 12, [{"id": "a", "at": 5}, {"id": "b", "at": 9}]) == [
        (5, 9, -24)
    ]
