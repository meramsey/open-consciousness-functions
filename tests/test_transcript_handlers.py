"""Isolated transcript algorithms and handler boundaries; validators/I/O are injected."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from ocf_tools import transcript as t
from ocf_tools.utils import OCFError, OCFFileExistsError

pytestmark = pytest.mark.unit


def args(**kwargs):
    return SimpleNamespace(file="input.yaml", **kwargs)


def doc():
    return {
        "title": "Fixture",
        "timeline": [
            {"id": "a", "at": 0, "text": "start"},
            {"id": "b", "at": 20, "text": "open access"},
        ],
    }


@pytest.mark.parametrize("fraction,seconds", [("1", 0.1), ("12", 0.12), ("123", 0.123)])
def test_srt_fraction_precision_and_exact_snapshot(fraction, seconds):
    source = f"1\n00:00:01,{fraction} --> 00:00:02,{fraction}\nVerbatim words\n"
    parsed = t.parse_srt(source)
    assert parsed.events[0].at == pytest.approx(1 + seconds)
    assert parsed.events[0].ends_at == pytest.approx(2 + seconds)
    assert parsed.snapshot == source


@pytest.mark.parametrize("source", ["WEBVTT", "WEBVTT\n", "\ufeffWEBVTT\n\n", "", "\n\n"])
def test_empty_vtt_header_is_a_valid_empty_parse(source):
    parsed = t.parse_vtt(source)
    assert parsed.events == [] and parsed.snapshot == source


def test_invalid_blocks_diagnostics_and_vtt_without_header():
    srt = t.parse_srt("\n\n1\nwrong --> timing\nwords\n\n")
    assert not srt.events and any("unparsed timing" in note for note in srt.notes)
    vtt = t.parse_vtt("no timing\n\nwrong --> timing\nwords\n\n00:01.000 --> 00:02.000\nvalid")
    assert len(vtt.events) == 1 and len(vtt.notes) == 2
    assert t.detect_format(None, "00:00:01,000 --> 00:00:02,000") == "srt"
    assert t.detect_format(None, "00:01.000 --> 00:02.000") == "vtt"
    assert t.parse_lrc("[broken\n\n").events == []
    with pytest.raises(ValueError, match="unparseable"):
        t._vtt_time("bad")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("5, 4, 3", "state-transition"),
        ("open", "access-open"),
        ("command", "installation"),
        ("repeat", "rehearsal"),
        ("wake", "return"),
        ("settle", "preparation"),
        ("plain", "freeform"),
    ],
)
def test_section_suggestions_are_not_authoritative_semantic_identity(text, expected):
    assert t.guess_section_type(text) == expected


def test_empty_analysis_sections_and_duration_fallbacks():
    assert "no structural suggestions" in t.format_analysis(t.analyze_transcript({}))
    assert t.extract_timing_template({})["sections"] == []
    assert t.apply_sections({}, [0, -1])["sections"] == []
    assert (
        t.estimate_duration(
            [
                t.ResolvedEvent("a", "a", 0),
                t.ResolvedEvent("u", "", None),
                t.ResolvedEvent("b", "b", 8),
            ],
            0,
        )
        == 8
    )
    assert (
        t.estimate_duration([t.ResolvedEvent("a", "a", 0), t.ResolvedEvent("b", "b", 0.3)], 0) == 4
    )
    assert "timeline problems" in t.format_analysis(
        t.analyze_transcript({"timeline": [{"id": "a", "at": "invalid"}]})
    )
    with pytest.raises(OCFError, match="timeline problems"):
        t.export_srt({"timeline": [{"id": "a", "at": "invalid", "text": "bad anchor"}]})


def test_measured_cue_skip_conditions_keep_authored_document():
    original = {"timeline": [{"id": "a", "text": "untimed"}]}
    cues = [
        {"id": "unknown", "duration": 2},
        {"id": "a", "duration": "bad"},
        {"id": "a", "duration": 2},
    ]
    assert t.apply_render_timing(original, {"narration_timing": {"cues": cues}}) is original
    assert (
        t.measured_durations({"narration_timing": {"cues": [{"id": "a", "duration": "bad"}]}}, [])
        == {}
    )
    events, _ = t.resolve_timeline(doc())
    assert t._cue_duration(events[0], events, 0, {"other": 5}) == 20


def test_yaml_io_roundtrip_collision_and_nonmapping(tmp_path):
    path = tmp_path / "script.yaml"
    original = {"timeline": [{"id": "a", "at": 0, "text": "one\ntwo — café"}]}
    t.write_timed_doc(path, original, overwrite=False)
    assert t.load_timed_doc(path) == original
    assert "|" in path.read_text()
    with pytest.raises(OCFError, match="--force"):
        t.write_timed_doc(path, {}, overwrite=False)
    assert t.load_timed_doc(path) == original
    path.write_text("- list")
    with pytest.raises(OCFError, match="expected a mapping"):
        t.load_timed_doc(path)


@pytest.mark.parametrize(
    "handler", [t.run_analyze, t.run_segment, t.run_review, t.run_export, t.run_extract_template]
)
def test_handler_missing_input_returns_nonzero(monkeypatch, capsys, handler):
    def missing(path):
        raise OCFError("missing input")

    monkeypatch.setattr(t, "load_timed_doc", missing)
    assert handler(args()) == 1
    assert "missing input" in capsys.readouterr().err


@pytest.mark.parametrize("failure", ["read", "empty", "write", "validation"])
def test_import_failure_boundaries(monkeypatch, capsys, failure):
    def read(path):
        if failure == "read":
            raise OCFError("cannot read")
        return "" if failure == "empty" else "[00:01.00]unchanged wording"

    monkeypatch.setattr(t, "read_text", read)
    monkeypatch.setattr(t, "sha256_of_file", lambda path: "hash")
    monkeypatch.setattr(t, "_validate_file", lambda path: 1)
    written = []

    def write(path, value, **kw):
        if failure == "write":
            raise OCFError("cannot write")
        written.append(value)

    monkeypatch.setattr(t, "write_timed_doc", write)
    assert t.run_import(SimpleNamespace(file="source.lrc", output="output.yaml")) == 1
    if failure == "validation":
        assert written[0]["timeline"][0]["text"] == "unchanged wording"
        assert "Imported" not in capsys.readouterr().out


def test_import_existing_yaml_routes_validation_without_rewriting(monkeypatch, capsys):
    monkeypatch.setattr(t, "read_text", lambda path: "source text")
    monkeypatch.setattr(t, "_validate_file", lambda path: 7)
    assert t.run_import(args()) == 7
    assert "already canonical" in capsys.readouterr().out


def test_import_success_default_output_and_notes(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(t, "AUDIO_SCRIPTS_DIR", tmp_path)
    monkeypatch.setattr(t, "read_text", lambda path: "note\n[00:01.00]words")
    monkeypatch.setattr(t, "sha256_of_file", lambda path: "hash")
    monkeypatch.setattr(t, "_validate_file", lambda path: 0)
    written = []
    monkeypatch.setattr(
        t, "write_timed_doc", lambda path, value, **kw: written.append((path, value, kw))
    )
    assert t.run_import(SimpleNamespace(file="sample.lrc", title="Custom")) == 0
    assert written[0][0] == tmp_path / "sample.yaml"
    assert written[0][1]["title"] == "Custom"
    assert written[0][1]["source"]["snapshot"] == "note\n[00:01.00]words"
    text = capsys.readouterr().out
    assert "Imported 1 entry" in text and "import note" in text
    t._print_import_summary(t.parse_plain("one\n\ntwo", "txt"), tmp_path)
    assert "Imported 2 entries" in capsys.readouterr().out


def test_analysis_review_and_extract_dispatch(monkeypatch, capsys):
    original = doc()
    monkeypatch.setattr(t, "load_timed_doc", lambda path: deepcopy(original))
    monkeypatch.setattr(t, "_validate_file", lambda path: 0)
    monkeypatch.setattr(t, "_segment_interactive_flow", lambda *a, **kw: 8)
    assert t.run_analyze(args()) == 0
    assert t.run_analyze(args(interactive=True)) == 8
    assert t.run_segment(args()) == 8
    assert t.run_review(args()) == 0
    assert t.run_review(args(state_profile="fixture")) == 0
    assert "memory only" in capsys.readouterr().out
    writes = []
    monkeypatch.setattr(
        t, "write_timed_doc", lambda path, value, **kw: writes.append((path, value, kw))
    )
    assert t.run_review(args(state_profile="fixture", output="new.yaml", force=True)) == 0
    assert writes[-1][0] == Path("new.yaml") and writes[-1][1]["state_profile"] == "fixture"
    assert t.run_extract_template(args(output="template.yaml")) == 0
    assert writes[-1][1]["sections"][0]["text"] is None
    assert t.run_extract_template(args()) == 0
    assert "timing-only" in capsys.readouterr().out
    assert t.run_transcript(SimpleNamespace(transcript_kind="unknown")) == 0
    assert "Usage:" in capsys.readouterr().out


def test_apply_segments_validates_new_output_not_original(monkeypatch):
    monkeypatch.setattr(t, "load_timed_doc", lambda path: doc())
    writes, validates = [], []
    monkeypatch.setattr(
        t, "write_timed_doc", lambda path, value, **kw: writes.append((path, value, kw))
    )
    monkeypatch.setattr(t, "_validate_file", lambda path: validates.append(path) or 0)
    assert t.run_segment(args(apply=True, output="segmented.yaml", force=False)) == 0
    assert validates == ["segmented.yaml"]
    assert writes[0][0] == Path("segmented.yaml") and writes[0][2] == {"overwrite": False}
    assert t._segment_apply_flow("input.yaml", {}) == 0


@pytest.mark.parametrize(
    "answers,message,written",
    [
        (["n"], "nothing changed", False),
        (["yes", "n"], "discarded", False),
        (["yes", "yes"], "Wrote", True),
    ],
)
def test_interactive_segmentation_respects_human_decisions(
    monkeypatch, capsys, answers, message, written
):
    responses = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt: next(responses))
    writes = []
    monkeypatch.setattr(t, "write_timed_doc", lambda *a, **kw: writes.append(a))
    monkeypatch.setattr(t, "_validate_file", lambda path: 0)
    assert t._segment_interactive_flow("input.yaml", doc(), apply_all=False) == 0
    assert bool(writes) is written and message in capsys.readouterr().out
    assert t._segment_interactive_flow("input.yaml", {}, apply_all=False) == 0


@pytest.mark.parametrize(
    "failure", ["format", "untimed", "collision", "manifest", "empty-manifest"]
)
def test_export_failure_and_empty_manifest_boundaries(monkeypatch, capsys, failure):
    original = (
        doc() if failure != "untimed" else {"timeline": [{"id": "a", "text": "no timestamp"}]}
    )
    monkeypatch.setattr(t, "load_timed_doc", lambda path: original)

    def read_manifest(path):
        if failure == "manifest":
            raise OCFError("missing manifest")
        return {}

    monkeypatch.setattr(t, "load_yaml_file", read_manifest)

    def write(*a, **kw):
        raise OCFFileExistsError("already exists")

    monkeypatch.setattr(t, "write_text_atomic", write)
    request = args(
        format="bad" if failure == "format" else "srt",
        output="out.srt" if failure == "collision" else None,
        render_manifest="render.yaml" if "manifest" in failure else None,
    )
    assert t.run_export(request) == (0 if failure == "empty-manifest" else 1)
    text = capsys.readouterr()
    assert (
        "no usable cue timings" in text.err if failure == "empty-manifest" else "error:" in text.err
    )
