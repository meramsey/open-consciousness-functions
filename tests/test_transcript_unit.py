"""Isolated transcript parsing, timing, and structural-analysis contracts."""

from __future__ import annotations

import pytest

from ocf_tools.transcript import (
    ResolvedEvent,
    TranscriptEvent,
    apply_render_timing,
    apply_sections,
    analyze_transcript,
    detect_format,
    estimate_duration,
    export_lrc,
    export_srt,
    export_vtt,
    extract_timing_template,
    flatten_event_dicts,
    format_analysis,
    format_lrc_ts,
    format_timestamp,
    is_countdown,
    parse_lrc,
    parse_plain,
    parse_srt,
    parse_timestamp,
    parse_vtt,
    resolve_timeline,
    state_cue_score,
    suggest_boundaries,
    timed_yaml_doc,
)

pytestmark = pytest.mark.unit


def test_timestamp_and_format_edge_cases():
    assert parse_timestamp("") is None
    assert parse_timestamp("1:2:3.5") == 3723.5
    assert parse_timestamp("1:2:3:4") is None
    assert format_timestamp(3661.2345) == "01:01:01.234"
    assert format_timestamp(None) is None
    assert format_lrc_ts(61.239) == "01:01.23"


def test_lrc_records_notes_and_combines_metadata():
    parsed = parse_lrc("[ar:one][ar:two]\n[bad]text\nplain\n")
    assert parsed.metadata["ar"] == "one; two"
    assert len(parsed.notes) == 3


def test_srt_skips_invalid_blocks_and_vtt_handles_bom_and_notes():
    srt = parse_srt("bad block\n\n1\nnot a timing line\ntext\n")
    assert not srt.events and any("skipped" in note for note in srt.notes)
    vtt = parse_vtt("\ufeffWEBVTT\n\nSTYLE\nfoo\n\n1\n00:00.000 --> bad\ntext\n")
    assert any("STYLE" in note for note in vtt.notes)
    assert any("unparsed" in note for note in vtt.notes)


def test_detection_and_plain_normalization():
    assert detect_format("x.yaml", "") == "ocf-timed-yaml"
    assert detect_format("x.unknown", "WEBVTT\n") == "vtt"
    assert detect_format("x.unknown", "words") == "txt"
    assert [event.text for event in parse_plain(" a \r\n\r\n b ", "md").events] == ["a", "b"]


def test_timeline_resolves_speech_end_event_end_and_overrides():
    doc = {
        "timeline": [
            {"id": "a", "at": 1, "text": "a"},
            {"id": "b", "after": "a", "timing": {"anchor": "speech-end"}},
        ]
    }
    events, problems = resolve_timeline(doc, speech_durations={"a": 2}, start_overrides={"b": 8})
    assert [event.at for event in events] == [1, 8]
    assert problems == []

    sections = {"sections": [{"id": "one", "timeline": [{"id": "a", "at": 1}]}]}
    section_events, section_problems = resolve_timeline(sections)
    assert section_events[0].section == "one"
    assert section_problems == []


def test_timeline_event_end_uses_dsp_transition_and_pause():
    doc = {
        "timeline": [
            {"id": "a", "at": 1, "text": "a", "timing": {"pause_after": 2}, "dsp": {"transition_s": 4}},
            {"id": "duplicate", "at": 3, "text": "duplicate"},
            {"id": "b", "after": "a", "timing": {"anchor": "event-end"}},
        ]
    }
    events, problems = resolve_timeline(doc, speech_durations={"a": 1})
    assert events[-1].at == 7
    assert problems == []


def test_estimate_duration_covers_untimed_preferred_and_short_gap():
    events = [
        ResolvedEvent("a", "a", None),
        ResolvedEvent("b", "b", 2, preferred_duration=0.1),
        ResolvedEvent("c", "c", 2.2),
    ]
    assert estimate_duration(events, 0) == 3.0
    assert estimate_duration(events, 1) == 0.2
    assert estimate_duration(events, 2) == 4.0


def test_measured_render_timing_preserves_unconsumed_events():
    doc = {"timeline": [{"id": "a", "at": "00:01.000", "text": "one"}, {"id": "b", "at": "00:03.000", "text": "two"}]}
    unchanged = apply_render_timing(doc, {"narration_timing": {"cues": []}})
    assert unchanged == doc
    view = apply_render_timing(
        doc,
        {"narration_timing": {"cues": [{"id": "a#1", "source_ids": ["a"], "at": 2, "duration": 1.5, "display_text": "ONE"}]}},
    )
    assert [event["id"] for event in view["timeline"]] == ["a#1", "b"]
    assert view["timeline"][0]["ends_at"] == "00:00:03.500"


def test_structural_analysis_and_formatting_cover_suggestions():
    assert is_countdown("5 4 3 2 1")
    assert not is_countdown("5 3 9")
    assert state_cue_score("Enter focus and return to the state") >= 2
    doc = {"timeline": [
        {"id": "a", "at": 1, "ends_at": 2, "text": "5 4 3 2 1"},
        {"id": "b", "at": 20, "text": "Enter focus and practice"},
        {"id": "c", "at": 21, "text": "repeat this phrase"},
        {"id": "d", "at": 22, "text": "repeat this phrase"},
    ]}
    analysis = analyze_transcript(doc)
    rendered = format_analysis(analysis)
    assert analysis["silence_count"] == 1
    assert analysis["repeated"]
    assert "possible countdowns" in rendered
    assert "longest pauses" in rendered


def test_sections_and_timing_template_keep_text_out_of_template():
    doc = {"title": "Demo", "source": {"filename": "demo.yaml", "sha256": "hash"}, "timeline": [
        {"id": "a", "at": 1, "text": "relax"},
        {"id": "b", "at": 20, "text": "open access"},
    ]}
    updated = apply_sections(doc, [-1, 1, 999])
    assert "timeline" not in updated and len(flatten_event_dicts(updated)) == 2
    template = extract_timing_template(doc, title="Custom")
    assert template["title"] == "Custom"
    assert all(section["text"] is None for section in template["sections"])


def test_exports_use_measured_duration_and_reject_unresolved_content():
    parsed = parse_lrc("[00:01.00]hello\n")
    doc = timed_yaml_doc(parsed)
    assert "00:00:01,000 --> 00:00:03,500" in export_srt(doc, measured={"e001": 2.5})
    assert "WEBVTT" in export_vtt(doc)
    assert export_lrc(doc).startswith("[00:01.00]")
    with pytest.raises(Exception, match="no timestamp"):
        export_srt(timed_yaml_doc(parse_plain("untimed", "txt")))


def test_export_rejects_timeline_problems():
    with pytest.raises(Exception, match="no timestamp"):
        export_lrc({"timeline": [{"id": "a", "after": "missing", "text": "x"}]})


def test_timed_yaml_keeps_multiline_source_and_cue_metadata():
    parsed = parse_vtt("WEBVTT\n\ncue\n00:01.000 --> 00:02.000\nline one\nline two\n")
    doc = timed_yaml_doc(parsed)
    assert doc["timeline"][0]["cue_id"] == "cue"
    assert doc["timeline"][0]["ends_at"] == "00:00:02.000"
    assert doc["source"]["snapshot"].startswith("WEBVTT")
