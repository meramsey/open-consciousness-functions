"""Timed-transcript pipeline tests: parsing, resolution, export, CLI.

Covers the transcript toolchain shipped via ``ocf transcript …``:
LRC/SRT/VTT/plain parsing, canonical OCF timed-YAML output, timeline
resolution with cycle detection, timed exports, timing-only templates,
section segmentation, and CLI wiring.
"""

from __future__ import annotations

import yaml
from conftest import REPO_ROOT
from ocf_tools.cli import main
from ocf_tools.transcript import (
    apply_sections,
    detect_format,
    estimate_duration,
    export_lrc,
    export_srt,
    export_vtt,
    parse_lrc,
    parse_plain,
    parse_srt,
    parse_timestamp,
    parse_transcript,
    parse_vtt,
    resolve_timeline,
    suggest_boundaries,
    timed_yaml_doc,
)
from ocf_tools.validators import validate_against_schema, validate_timed_transcript

LRC = "[ti:Sample]\n[00:01.00]Breathe in.\n[00:03.50]Breathe out.\n"

SRT = (
    "1\n00:00:01,000 --> 00:00:02,500\nFirst cue\n\n2\n00:00:03,000 --> 00:00:04,000\nSecond cue\n"
)

VTT = (
    "WEBVTT\n\n"
    "cue-1\n00:01.000 --> 00:02.500\nOne\n\n"
    "NOTE comment\n\n"
    "00:03.000 --> 00:04.500\nTwo\n"
)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_lrc_events_and_metadata():
    parsed = parse_lrc(LRC)
    assert len(parsed.events) == 2
    assert parsed.events[0].at == 1.0
    assert parsed.events[1].at == 3.5
    assert parsed.metadata == {"ti": "Sample"}
    assert parsed.fmt == "lrc"


def test_parse_lrc_multiple_timestamps_expand():
    parsed = parse_lrc("[00:01.00][00:02.00]echo\n")
    assert [e.at for e in parsed.events] == [1.0, 2.0]
    assert [e.text for e in parsed.events] == ["echo", "echo"]


def test_parse_srt_blocks_and_ends():
    parsed = parse_srt(SRT)
    assert len(parsed.events) == 2
    assert parsed.events[0].at == 1.0
    assert parsed.events[0].ends_at == 2.5
    assert parsed.events[0].text.strip() == "First cue"
    assert parsed.events[1].text.strip() == "Second cue"


def test_parse_vtt_strips_header_and_keeps_cue_ids():
    parsed = parse_vtt(VTT)
    assert len(parsed.events) == 2
    assert parsed.events[0].cue_id == "cue-1"
    assert parsed.events[0].at == 1.0
    assert parsed.events[1].cue_id is None
    assert any("NOTE comment" in note for note in parsed.notes)


def test_parse_plain_paragraphs_untimed():
    parsed = parse_plain("One.\n\nTwo.\n\nThree.", "txt")
    assert [e.text for e in parsed.events] == ["One.", "Two.", "Three."]
    assert all(e.at is None for e in parsed.events)


def test_parse_timestamp_variants():
    assert parse_timestamp("00:01:02.500") == 62.5
    assert parse_timestamp("01:02,500") == 62.5
    assert parse_timestamp("3.5") == 3.5
    assert parse_timestamp("bogus") is None
    assert parse_timestamp(None) is None


def test_detect_format_from_content_and_argument():
    assert detect_format("sample.lrc", LRC) == "lrc"
    assert detect_format("sample.srt", SRT) == "srt"
    assert detect_format("sample.vtt", VTT) == "vtt"
    assert detect_format("sample.txt", "just words\n\nmore words\n") == "txt"
    assert detect_format("sample.lrc", "just words\n") == "lrc"
    assert detect_format("sample.txt", LRC) == "lrc"
    assert detect_format("sample.txt", LRC, explicit="md") == "md"


def test_parse_transcript_rejects_unknown_format():
    try:
        parse_transcript("x", fmt="nope")
    except Exception as exc:
        assert "not importable" in str(exc)
    else:
        raise AssertionError("expected OCFError")


# ---------------------------------------------------------------------------
# Canonical timed YAML
# ---------------------------------------------------------------------------


def _schema():
    import json

    with open(str(REPO_ROOT / "schemas" / "timed-transcript.schema.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_timed_yaml_doc_deterministic_and_verbatim_snapshot():
    parsed = parse_transcript(LRC, fmt="lrc", filename="sample.lrc", sha256="abc123")
    doc = timed_yaml_doc(parsed)
    again = timed_yaml_doc(parse_transcript(LRC, fmt="lrc", filename="sample.lrc", sha256="abc123"))
    assert doc == again
    assert doc["title"] == "Sample"
    assert doc["source"]["snapshot"] == LRC
    assert doc["source"]["sha256"] == "abc123"
    assert doc["timeline"][0] == {"id": "e001", "text": "Breathe in.", "at": "00:00:01.000"}


def test_timed_yaml_matches_schema():
    parsed = parse_srt(SRT)
    assert validate_against_schema(timed_yaml_doc(parsed), _schema()) == []


def test_untimed_import_matches_schema():
    parsed = parse_plain("Intro.\n\nBody.\n", "txt")
    assert validate_against_schema(timed_yaml_doc(parsed), _schema()) == []


# ---------------------------------------------------------------------------
# Timeline resolution
# ---------------------------------------------------------------------------


def test_resolve_after_offset():
    doc = {
        "schema_version": "1.0",
        "title": "t",
        "timeline": [
            {"id": "e001", "at": "00:00:10.000", "text": "a"},
            {"id": "e002", "after": "e001", "offset": 5.0, "text": "b"},
            {"id": "e003", "after": "e002", "text": "c"},
        ],
    }
    events, problems = resolve_timeline(doc)
    assert problems == []
    assert [e.at for e in events] == [10.0, 15.0, 15.0]


def test_resolve_sections_flat_mixed_is_a_problem():
    doc = {
        "schema_version": "1.0",
        "title": "t",
        "timeline": [{"id": "e001", "at": "00:00:01.000", "text": "a"}],
        "sections": [],
    }
    _events, problems = resolve_timeline(doc)
    assert any("both" in p for p in problems)


def test_resolve_unknown_after_and_cycle_flagged():
    doc = {
        "schema_version": "1.0",
        "title": "t",
        "timeline": [
            {"id": "e001", "after": "missing", "text": "a"},
            {"id": "e002", "after": "e003", "text": "b"},
            {"id": "e003", "after": "e002", "text": "c"},
        ],
    }
    _events, problems = resolve_timeline(doc)
    assert any("unknown 'after' target 'missing'" in p for p in problems)
    assert any("circular 'after' reference" in p for p in problems)


def test_validation_flags_timeline_problems():
    data = {
        "schema_version": "1.0",
        "title": "t",
        "timeline": [{"id": "e001", "after": "bogus", "text": "x"}],
    }
    result = validate_timed_transcript(data, REPO_ROOT / "none.yaml")
    assert any(i.code == "timed-timeline" for i in result.issues)


def test_validation_accepts_clean_doc(tmp_path):
    doc = timed_yaml_doc(parse_lrc(LRC))
    result = validate_timed_transcript(doc, tmp_path / "t.yaml")
    assert result.ok


# ---------------------------------------------------------------------------
# Estimates and segmentation
# ---------------------------------------------------------------------------


def test_estimate_duration_uses_ends_at_then_gap():
    _events, _problems = resolve_timeline(timed_yaml_doc(parse_srt(SRT)))
    assert estimate_duration([_events[0]], 0) == 1.5
    assert estimate_duration(_events, 0) == 1.5
    assert estimate_duration(_events, 1) == 1.0


def test_suggest_boundaries_long_pause():
    doc = {
        "schema_version": "1.0",
        "title": "t",
        "timeline": [
            {"id": "e001", "at": "00:00:01.000", "text": "start"},
            {"id": "e002", "at": "00:01:00.000", "text": "after a long gap"},
        ],
    }
    bounds = suggest_boundaries(resolve_timeline(doc)[0])
    assert bounds and any("long pause" in r for r in bounds[0]["reasons"])


def test_suggest_boundaries_countdown():
    doc = {
        "schema_version": "1.0",
        "title": "t",
        "timeline": [
            {"id": "e001", "at": "00:00:01.000", "text": "5, 4, 3, 2, 1"},
        ],
    }
    bounds = suggest_boundaries(resolve_timeline(doc)[0])
    assert bounds and any("countdown" in r for r in bounds[0]["reasons"])


def test_apply_sections_preserves_text_verbatim():
    parsed = parse_lrc("[00:01.00]One\n[00:55.00]Two\n[00:58.00]Three\n")
    doc = timed_yaml_doc(parsed)
    bounds = suggest_boundaries(resolve_timeline(doc)[0])
    updated = apply_sections(doc, [b["position"] for b in bounds])
    assert "timeline" not in updated
    flattened = [e["text"] for section in updated["sections"] for e in section["timeline"]]
    assert flattened == [e.text for e in parsed.events]


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


def test_export_srt_uses_comma_milliseconds():
    doc = timed_yaml_doc(parse_srt(SRT))
    text = export_srt(doc)
    assert "00:00:01,000 --> 00:00:02,500" in text
    assert "First cue" in text


def test_export_vtt_roundtrip_has_header():
    text = export_vtt(timed_yaml_doc(parse_srt(SRT)))
    assert text.startswith("WEBVTT")
    assert "00:00:01.000 --> " in text


def test_export_lrc_centiseconds():
    text = export_lrc(timed_yaml_doc(parse_srt(SRT)))
    assert text.splitlines()[0] == "[00:01.00]First cue"


def test_export_untimed_raises():
    doc = timed_yaml_doc(parse_plain("No times here.\n", "txt"))
    for exporter in (export_srt, export_vtt, export_lrc):
        try:
            exporter(doc)
        except Exception as exc:
            assert "no timestamp" in str(exc)
        else:
            raise AssertionError("expected OCFError")


def test_extract_timing_template_contains_no_text():
    from ocf_tools.transcript import extract_timing_template

    doc = timed_yaml_doc(parse_lrc(LRC))
    template = extract_timing_template(doc)
    if template["sections"]:
        assert all(section["text"] is None for section in template["sections"])
    assert "no transcript text is included" in str(template["source"]["notes"])


def test_extract_timing_template_matches_schema():
    from ocf_tools.transcript import extract_timing_template

    doc = timed_yaml_doc(parse_lrc(LRC))
    template = extract_timing_template(doc)
    assert validate_against_schema(template, _schema()) == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_import_writes_canonical_doc(tmp_path):
    lrc = tmp_path / "sample.lrc"
    lrc.write_text(LRC, encoding="utf-8")
    out = tmp_path / "audio" / "scripts" / "sample.yaml"
    status = main(["transcript", "import", str(lrc), "--output", str(out)])
    assert status == 0
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert data["source"]["snapshot"] == LRC
    assert len(data["timeline"]) == 2


def test_cli_import_refuses_overwrite_without_force(tmp_path):
    lrc = tmp_path / "sample.lrc"
    lrc.write_text(LRC, encoding="utf-8")
    out = tmp_path / "sample.yaml"
    assert main(["transcript", "import", str(lrc), "--output", str(out)]) == 0
    assert main(["transcript", "import", str(lrc), "--output", str(out)]) != 0
    assert main(["transcript", "import", str(lrc), "--output", str(out), "--force"]) == 0


def test_cli_export_writes_file(tmp_path):
    lrc = tmp_path / "sample.lrc"
    lrc.write_text(LRC, encoding="utf-8")
    yaml_path = tmp_path / "sample.yaml"
    assert main(["transcript", "import", str(lrc), "--output", str(yaml_path)]) == 0
    vtt_path = tmp_path / "sample.vtt"
    assert (
        main(["transcript", "export", str(yaml_path), "--format", "vtt", "--output", str(vtt_path)])
        == 0
    )
    assert vtt_path.read_text(encoding="utf-8").startswith("WEBVTT")


def test_cli_extract_template_requires_timing_only(tmp_path):
    lrc = tmp_path / "sample.lrc"
    lrc.write_text(LRC, encoding="utf-8")
    yaml_path = tmp_path / "sample.yaml"
    assert main(["transcript", "import", str(lrc), "--output", str(yaml_path)]) == 0
    out = tmp_path / "template.yaml"
    assert (
        main(
            [
                "transcript",
                "extract-template",
                str(yaml_path),
                "--timing-only",
                "--output",
                str(out),
            ]
        )
        == 0
    )
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert any("no transcript text" in note for note in data["source"]["notes"])


def test_cli_segment_apply_writes_sections(tmp_path):
    lrc = tmp_path / "gap.lrc"
    lrc.write_text("[00:01.00]One\n[01:00.00]Two\n[01:02.00]Three\n", encoding="utf-8")
    yaml_path = tmp_path / "gap.yaml"
    assert main(["transcript", "import", str(lrc), "--output", str(yaml_path)]) == 0
    assert main(["transcript", "segment", str(yaml_path), "--apply"]) == 0
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert "sections" in data and "timeline" not in data
    assert len(data["sections"]) >= 2


def test_cli_analyze_and_review_exit_zero(tmp_path):
    lrc = tmp_path / "sample.lrc"
    lrc.write_text(LRC, encoding="utf-8")
    yaml_path = tmp_path / "sample.yaml"
    assert main(["transcript", "import", str(lrc), "--output", str(yaml_path)]) == 0
    assert main(["transcript", "analyze", str(yaml_path)]) == 0
    assert main(["transcript", "review", str(yaml_path)]) == 0


def test_validate_all_counts_timed_documents():
    from ocf_tools.validators import validate_all

    result = validate_all()
    assert any(i.code == "timed-count" for i in result.issues)
