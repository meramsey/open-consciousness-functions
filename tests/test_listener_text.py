"""Measured listener text contracts and synthetic native-metadata integration."""

import copy
import json
import sys
from types import ModuleType, SimpleNamespace

import pytest
from ocf_tools import listener_text as lt
from ocf_tools.transcript import parse_lrc, parse_srt, parse_vtt
from ocf_tools.utils import OCFError


def _render():
    return {
        "narration_timing": {
            "cues": [
                {
                    "id": "a",
                    "at": 0.0,
                    "duration": 1.5,
                    "spoken_text": "Hello. Café.",
                    "spoken_units": [
                        {"text": "Hello.", "start_seconds": 0.0, "end_seconds": 0.05},
                        {"text": "Café.", "start_seconds": 1.0, "end_seconds": 1.5},
                    ],
                },
                {"id": "repeat", "at": 3600.123, "duration": 1.0, "spoken_text": "Hello. Café."},
            ]
        }
    }


@pytest.mark.unit
def test_measured_sidecars_preserve_repeats_unicode_and_short_intervals(tmp_path):
    audio = tmp_path / "session.mp3"
    receipt = lt.write_listener_text(_render(), 3602, audio)
    assert audio.with_suffix(".txt").read_bytes() == "Hello. Café.\n\nHello. Café.\n".encode()
    srt = parse_srt(audio.with_suffix(".srt").read_text(encoding="utf-8"))
    vtt = parse_vtt(audio.with_suffix(".vtt").read_text(encoding="utf-8"))
    lrc = parse_lrc(audio.with_suffix(".lrc").read_text(encoding="utf-8"))
    assert [e.text.rstrip("\n") for e in srt.events] == ["Hello.", "Café.", "Hello. Café."]
    assert srt.events[0].ends_at == 0.05
    assert srt.events[-1].at == vtt.events[-1].at == 3600.123
    assert lrc.events[-1].at == 3600.12
    assert receipt["spoken_intervals"] == 3
    assert "not word alignment" in receipt["granularity"]
    assert (
        json.loads(audio.with_suffix(".timing.json").read_text(encoding="utf-8"))["artifacts"]
        == receipt["artifacts"]
    )
    with pytest.raises(OCFError):
        lt.write_listener_text(_render(), 3602, audio)


@pytest.mark.unit
def test_whole_utterance_paragraphs_remain_one_complete_measured_subtitle(tmp_path):
    text = "First paragraph.\n\nSecond paragraph."
    render = {
        "narration_timing": {
            "cues": [
                {
                    "id": "recorded",
                    "at": 0.1,
                    "duration": 0.8,
                    "spoken_text": text,
                }
            ]
        }
    }
    audio = tmp_path / "session.wav"
    lt.write_listener_text(render, 1.0, audio)
    assert audio.with_suffix(".txt").read_text(encoding="utf-8") == text + "\n"
    for parser, extension in ((parse_srt, "srt"), (parse_vtt, "vtt"), (parse_lrc, "lrc")):
        events = parser(audio.with_suffix("." + extension).read_text(encoding="utf-8")).events
        assert len(events) == 1
        assert events[0].text.rstrip("\n") == "First paragraph. Second paragraph."
        assert events[0].at == 0.1
        if extension != "lrc":
            assert events[0].ends_at == 0.9


@pytest.mark.unit
def test_timing_manifest_preserves_all_four_body_passes_and_sections(tmp_path):
    cues = []
    for event_id, start in (
        ("focus11-body.pass-1", 0),
        ("focus11-body.pass-2", 3),
        ("sleep20-body.pass-1", 6),
        ("sleep20-body.pass-2", 9),
    ):
        cues.append(
            {
                "id": event_id,
                "source_ids": [event_id],
                "at": start,
                "duration": 2,
                "spoken_text": "First sentence. Second sentence.",
                "spoken_units": [
                    {"text": "First sentence.", "start_seconds": start, "end_seconds": start + 1},
                    {
                        "text": "Second sentence.",
                        "start_seconds": start + 1,
                        "end_seconds": start + 2,
                    },
                ],
            }
        )
    audio = tmp_path / "session.mp3"
    receipt = lt.write_listener_text({"narration_timing": {"cues": cues}}, 12, audio)
    manifest = json.loads(audio.with_suffix(".timing.json").read_text(encoding="utf-8"))
    assert receipt["body_pass_coverage"] == {
        "programming": [1, 2],
        "sleep_reinforcement": [1, 2],
    }
    assert len(manifest["timeline"]) == 8
    assert manifest["timeline"][0]["semantic_section"] == "focus11-body"
    assert manifest["timeline"][0]["pass_type"] == "programming"
    assert manifest["timeline"][0]["pass_index"] == 1
    assert manifest["timeline"][6]["pass_type"] == "sleep_reinforcement"
    assert manifest["timeline"][6]["pass_index"] == 2
    assert all(row["granularity"] == "measured_speech_unit" for row in manifest["timeline"])


@pytest.mark.unit
def test_tied_onsets_use_the_same_canonical_plain_and_subtitle_order(tmp_path):
    from ocf_tools.release import transcript_from_render

    render = {
        "narration_timing": {
            "cues": [
                {"id": "b", "at": 0, "duration": 0.5, "spoken_text": "Second."},
                {"id": "a", "at": 0, "duration": 0.5, "spoken_text": "First."},
            ]
        }
    }
    audio = tmp_path / "session.wav"
    lt.write_listener_text(render, 1, audio)
    assert (
        audio.with_suffix(".txt").read_text(encoding="utf-8")
        == transcript_from_render(render)
        == "First.\n\nSecond.\n"
    )
    assert [
        row.text.rstrip("\n")
        for row in parse_srt(audio.with_suffix(".srt").read_text(encoding="utf-8")).events
    ] == ["First.", "Second."]


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutation",
    [
        "missing-text",
        "missing-duration",
        "nan",
        "negative",
        "outside",
        "unordered",
        "unit-mismatch",
        "unit-outside",
        "zero",
        "no-cues",
    ],
)
def test_invalid_ledgers_fail_closed(mutation):
    render = copy.deepcopy(_render())
    cues = render["narration_timing"]["cues"]
    if mutation == "missing-text":
        del cues[0]["spoken_text"]
    elif mutation == "missing-duration":
        del cues[0]["duration"]
    elif mutation in ("nan", "negative", "outside"):
        cues[0]["at"] = {"nan": float("nan"), "negative": -1, "outside": 4000}[mutation]
    elif mutation == "unordered":
        cues[0]["spoken_units"].reverse()
    elif mutation == "unit-mismatch":
        cues[0]["spoken_units"][0]["text"] = "Invented"
    elif mutation == "unit-outside":
        cues[0]["spoken_units"][0]["end_seconds"] = 4
    elif mutation == "zero":
        cues[0]["spoken_units"][0]["end_seconds"] = 0
    else:
        cues.clear()
    with pytest.raises(OCFError):
        lt.measured_document(render, 3602)


@pytest.mark.unit
def test_missing_optional_native_lyrics_dependency_fails_explicitly(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "mutagen.flac", None)
    with pytest.raises(OCFError, match="optional 'listener' extra"):
        lt.embed_listener_text(tmp_path / "copy.mp3", _render(), 3602, "en-US")


@pytest.mark.unit
@pytest.mark.parametrize(
    "render",
    [
        None,
        {"narration_timing": None},
        {"narration_timing": {"cues": None}},
        {"narration_timing": {"cues": ["not an object"]}},
        {"narration_timing": {"cues": [{"at": "not a time"}]}},
    ],
)
def test_malformed_narration_objects_fail_before_any_sidecar_write(tmp_path, render):
    with pytest.raises(OCFError):
        lt.write_listener_text(render, 1, tmp_path / "session.wav")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.unit
@pytest.mark.parametrize("duration", [True, "not a duration", 0, -1, float("nan")])
def test_invalid_media_duration_is_rejected(duration):
    with pytest.raises(OCFError, match="finite positive"):
        lt.measured_document(_render(), duration)


@pytest.mark.unit
@pytest.mark.parametrize("corrupt", ["plain", "timed", "version", "flac", "unsupported"])
def test_native_tag_readback_errors_are_not_silently_accepted(monkeypatch, tmp_path, corrupt):
    extension = "flac" if corrupt == "flac" else "wav" if corrupt == "unsupported" else "mp3"
    audio = tmp_path / ("staged." + extension)
    lt.write_listener_text(_render(), 3602, audio)
    plain = audio.with_suffix(".txt").read_text(encoding="utf-8")
    description = "OCF spoken-session transcript"
    synced = [("Hello.", 0), ("Café.", 1000), ("Hello. Café.", 3600123)]

    class Tags(dict):
        version = (2, 4, 0) if corrupt == "version" else (2, 3, 0)

        def add(self, frame):
            pass

        def save(self, *args, **kwargs):
            pass

    tags = Tags(
        {
            f"USLT:{description}:eng": SimpleNamespace(
                text="wrong" if corrupt == "plain" else plain
            ),
            f"SYLT:{description}:eng": SimpleNamespace(text=[] if corrupt == "timed" else synced),
        }
    )
    parent, id3, flac = ModuleType("mutagen"), ModuleType("mutagen.id3"), ModuleType("mutagen.flac")
    parent.__path__ = []
    id3.ID3 = lambda _: tags
    id3.USLT = id3.SYLT = lambda **kwargs: SimpleNamespace(**kwargs)
    flac_calls = []

    def read_flac(_):
        flac_calls.append(1)
        return Tags() if len(flac_calls) == 1 else Tags(LYRICS=["wrong"], UNSYNCEDLYRICS=[plain])

    flac.FLAC = read_flac
    for module in (parent, id3, flac):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    expected = "support only" if corrupt == "unsupported" else "read-back failed"
    with pytest.raises(OCFError, match=expected):
        lt.embed_listener_text(audio, _render(), 3602, "en-US")


@pytest.mark.integration
@pytest.mark.audio_integration
@pytest.mark.external_tool
def test_native_lyrics_preserve_audio_artwork_and_tags(tmp_path):
    pytest.importorskip("mutagen")
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3
    from ocf_tools import audio_build, audition_exports
    from PIL import Image
    from test_audition_exports import _session, _tools

    _tools()
    _, master, _ = _session(tmp_path)
    cover = tmp_path / "cover.png"
    Image.new("RGB", (64, 64), "navy").save(cover)
    render = {
        "narration_timing": {
            "cues": [{"id": "a", "at": 0, "duration": 0.75, "spoken_text": "Café."}]
        }
    }
    for fmt in ("mp3", "flac"):
        audio = tmp_path / (fmt + "." + fmt)
        audio_build._encode(
            master, fmt, audio, {"title": "Test", "track": "3/7", "OCF_LOCALE": "en-US"}, cover
        )
        before = {
            "packets": audition_exports.audio_hash(audio, packets=True),
            "pcm": audition_exports.audio_hash(audio),
        }
        lt.write_listener_text(render, 1.0, audio)
        lt.embed_listener_text(audio, render, 1.0, "en-US")
        assert before == {
            "packets": audition_exports.audio_hash(audio, packets=True),
            "pcm": audition_exports.audio_hash(audio),
        }
        assert audition_exports.front_cover_type(audio) == 3
        tags = audition_exports._probe(audio)["tags"]
        assert tags["title"] == "Test" and tags["track"] == "3/7" and tags["ocf_locale"] == "en-US"
        if fmt == "mp3":
            parsed = ID3(audio)
            assert parsed.getall("USLT")[0].text == "Café.\n"
            assert parsed.getall("SYLT")[0].text == [("Café.", 0)]
            assert parsed.getall("SYLT")[0].format == 2
            assert parsed.getall("APIC")[0].data == cover.read_bytes()
        else:
            parsed = FLAC(audio)
            assert parsed["LYRICS"] == ["[00:00.00]Café.\n"]
            assert parsed["UNSYNCEDLYRICS"] == ["Café.\n"]
            assert parsed.pictures[0].data == cover.read_bytes()
