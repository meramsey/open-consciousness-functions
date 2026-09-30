"""Tests for session-composition templates (spec 46 / 55 / 58)."""

from __future__ import annotations

from textwrap import dedent

import pytest
from ocf_tools import session
from ocf_tools.cli import main as cli_main
from ocf_tools.transcript import parse_timestamp
from ocf_tools.utils import OCFError
from ocf_tools.validators import _load_schema, validate_against_schema

TEMPLATE_ID = "OCF-TPL-SESSION-LEARN-001"

SLOTS = {
    "opener": dedent(
        """\
        Breathe in. Breathe out.
        [0:18]The channel opens now, count with me.
        Two.
        Three.
        """
    ).strip(),
    "focus11": dedent(
        """\
        At the focus eleven level, learn Attention.
        The command is PLUS-FOCUS.
        PLUS-FOCUS.
        """
    ).strip(),
    "sleep20": dedent(
        """\
        Resting in the twentieth state, the function holds.
        PLUS-FOCUS remains yours.
        """
    ).strip(),
    "closer": dedent(
        """\
        [29:00]        You are wide awake and refreshed.
        The function is yours, ready whenever you call it.
        Closed.
        """
    ).strip(),
}

ATTENTION_TEMPLATE_ID = "OCF-TPL-SESSION-ATTENTION-001"


def attention_slots() -> dict[str, str]:
    """Minimal prose for the single Attention slot (structure is what matters)."""
    return {
        "focus11": "The access channel opens.\nThe command is PLUS-FOCUS.",
    }


def test_list_templates_contains_learn_shell():
    rows = session.list_templates()
    ids = [row["id"] for row in rows]
    assert TEMPLATE_ID in ids
    row = next(r for r in rows if r["id"] == TEMPLATE_ID)
    assert row["origin"] == "original-ocf"


def test_load_template_missing_raises():
    with pytest.raises(OCFError, match="not found"):
        session.load_template("OCF-TPL-SESSION-NOPE-999")


def test_load_template_local_path(tmp_path):
    tpl = tmp_path / "local-template.yaml"
    tpl.write_text(
        dedent(
            """\
            schema_version: "1.0"
            id: "OCF-TPL-SESSION-LOCAL-001"
            name: "Local test shell"
            author: "tester"
            origin: "reference-derived"
            license: "pending-source-review"
            slots:
              required: ["opener"]
              optional: []
            defaults:
              line_seconds: 2.0
              duration: 60.0
            sections:
              - id: opening
                type: freeform
                role: opener
                slot: opener
                start: 0.0
                lines:
                  - at: 0.0
                    text: "Placeholder opener line."
            """
        )
    )
    loaded = session.load_template(str(tpl))
    assert loaded["id"] == "OCF-TPL-SESSION-LOCAL-001"
    assert loaded["origin"] == "reference-derived"


def test_load_template_rejects_bad_origin(tmp_path):
    tpl = tmp_path / "bad.yaml"
    tpl.write_text(
        dedent(
            """\
            schema_version: "1.0"
            id: "OCF-TPL-SESSION-BAD-001"
            name: "Bad"
            author: "tester"
            origin: "invented"
            license: "x"
            slots: {required: [], optional: []}
            sections: []
            """
        )
    )
    with pytest.raises(OCFError, match="schema"):
        session.load_template(str(tpl))


def test_compose_requires_declared_slots():
    tpl = session.load_template(TEMPLATE_ID)
    with pytest.raises(OCFError, match="missing required slot.*opener"):
        session.compose(
            tpl, {"focus11": "x", "sleep20": "y", "closer": "Done."}, title="t"
        )


def test_compose_lists_every_missing_slot():
    tpl = session.load_template(TEMPLATE_ID)
    with pytest.raises(OCFError, match="opener, focus11, sleep20, closer"):
        session.compose(tpl, {}, title="t")


def test_compose_rejects_unknown_slots():
    tpl = session.load_template(TEMPLATE_ID)
    with pytest.raises(OCFError, match="unknown slot"):
        session.compose(tpl, {**SLOTS, "bogus": "no"}, title="t")


def test_compose_focus11_slot_replaces_placeholder():
    tpl = session.load_template(TEMPLATE_ID)
    doc = session.compose(tpl, dict(SLOTS), title="t")
    focus = next(s for s in doc["sections"] if s["id"] == "focus11")
    assert focus["timeline"][0]["text"] == "At the focus eleven level, learn Attention."
    assert doc["slots"]["focus11"] == [
        "At the focus eleven level, learn Attention.",
        "The command is PLUS-FOCUS.",
        "PLUS-FOCUS.",
    ]


def test_compose_sleep20_spreads_across_sleep_hold():
    tpl = session.load_template(TEMPLATE_ID)
    doc = session.compose(tpl, dict(SLOTS), title="t")
    sleep = next(s for s in doc["sections"] if s["id"] == "sleep20")
    events = sleep["timeline"]
    assert events[0]["at"] == "00:20:13.880"  # 1014.32 + 598.68/3
    assert events[1]["at"] == "00:23:33.440"  # 1014.32 + 2*598.68/3
    assert events[0]["text"] == "Resting in the twentieth state, the function holds."
    assert doc["slots"]["sleep20"] == [
        "Resting in the twentieth state, the function holds.",
        "PLUS-FOCUS remains yours.",
    ]


def test_compose_lrc_timestamps_absolute_and_untimed_pacing():
    tpl = session.load_template(TEMPLATE_ID)
    doc = session.compose(tpl, dict(SLOTS), title="t")
    opening = doc["sections"][0]["timeline"]
    assert [e["at"] for e in opening] == [
        "00:00:00.000",
        "00:00:18.000",
        "00:00:21.000",
        "00:00:24.000",
    ]
    closing = doc["sections"][-1]["timeline"]
    assert closing[0]["at"] == "00:29:00.000"


def test_compose_bridge_wording_stays_untouched():
    tpl = session.load_template(TEMPLATE_ID)
    doc = session.compose(tpl, dict(SLOTS), title="t")
    authored = next(s for s in doc["sections"] if s["id"] == "access-open")
    assert authored["timeline"][0]["text"] == (
        "Your attention has settled into a calm, even rhythm."
    )


def test_compose_records_template_provenance_and_slots():
    tpl = session.load_template(TEMPLATE_ID)
    doc = session.compose(tpl, dict(SLOTS), title="t")
    assert doc["template"] == {
        "id": TEMPLATE_ID,
        "version": "1.0",
        "origin": "original-ocf",
    }
    assert doc["slots"]["opener"] == [
        "Breathe in. Breathe out.",
        "The channel opens now, count with me.",
        "Two.",
        "Three.",
    ]
    assert doc["slots"]["closer"] == [
        "You are wide awake and refreshed.",
        "The function is yours, ready whenever you call it.",
        "Closed.",
    ]


def test_compose_output_validates_against_timed_transcript_schema():
    tpl = session.load_template(TEMPLATE_ID)
    doc = session.compose(tpl, dict(SLOTS), title="t")
    schema = _load_schema("timed-transcript.schema.json")
    assert validate_against_schema(doc, schema) == []
    ids = [e["id"] for s in doc["sections"] for e in s["timeline"]]
    assert len(ids) == len(set(ids))


def test_compose_even_span_respects_lrc_timestamps():
    tpl = session.load_template(TEMPLATE_ID)
    sleep_text = "[20:00]Mid-sleep reinforcement.\nSecond drift line."
    doc = session.compose(tpl, {**SLOTS, "sleep20": sleep_text}, title="t")
    sleep = next(s for s in doc["sections"] if s["id"] == "sleep20")
    assert sleep["timeline"][0]["at"] == "00:20:00.000"
    assert sleep["timeline"][0]["text"] == "Mid-sleep reinforcement."


def test_compose_copies_template_source_provenance():
    tpl = session.load_template(ATTENTION_TEMPLATE_ID)
    doc = session.compose(tpl, attention_slots(), title="t")
    assert doc["source"]["format"] == "ocf-timed-yaml"
    assert doc["source"]["filename"] == "audio/scripts/attention.yaml"
    assert doc["source"]["sha256"] == (
        "f12e20c5ef3020bef08563ad305d5c34fac9e6285f85c4808fe12607da6f21b6"
    )
    assert any("adapted" in note.lower() for note in doc["source"]["notes"])
    assert any("citation-only" in note for note in doc["source"]["notes"])


def test_compose_without_template_source_has_no_source_block():
    tpl = session.load_template(TEMPLATE_ID)
    doc = session.compose(tpl, dict(SLOTS), title="t")
    assert "source" not in doc


def test_compose_from_slot_repeats_wording_across_window():
    """A from_slot section splits its window into `repeat` bands and even-spans
    the referenced slot's lines once per band."""
    tpl = session.load_template(ATTENTION_TEMPLATE_ID)
    focus_lines = [
        "From this moment on, focus with PLUS-FOCUS.",
        "Hold your breath and let it settle.",
    ]
    doc = session.compose(tpl, {"focus11": "\n".join(focus_lines)}, title="t")
    sleep = next(s for s in doc["sections"] if s["id"] == "sleep20")
    events = [(parse_timestamp(line["at"]), line["text"]) for line in sleep["timeline"]]
    times = [at for at, _ in events]
    assert times == sorted(times) and len(set(times)) == len(times)
    assert [text for _, text in events] == focus_lines * 2
    hold_start = next(s["start"] for s in tpl["sections"] if s["id"] == "sleep20")
    hold_end = next(s["start"] for s in tpl["sections"] if s["id"] == "return")
    midpoint = (hold_start + hold_end) / 2
    first_pass = [at for at, _ in events if at <= midpoint]
    second_pass = [at for at, _ in events if at > midpoint]
    assert len(first_pass) == len(second_pass) == len(focus_lines)
    assert hold_start <= first_pass[0] < first_pass[-1] < midpoint
    assert midpoint < second_pass[0] < second_pass[-1] < hold_end


def test_compose_from_slot_missing_raises():
    tpl = session.load_template(ATTENTION_TEMPLATE_ID)
    with pytest.raises(OCFError, match="missing required slot.*focus11"):
        session.compose(tpl, {}, title="t")


def test_attention_template_only_declares_focus11():
    tpl = session.load_template(ATTENTION_TEMPLATE_ID)
    legacy_extras = {
        "opener": "Settle the body.",
        "sleep20": "Resting at twenty.",
        "closer": "Wake up.",
    }
    with pytest.raises(OCFError, match="unknown slot"):
        session.compose(tpl, {**attention_slots(), **legacy_extras}, title="t")


def test_attention_template_has_quiet_reinforcement_section():
    tpl = session.load_template(ATTENTION_TEMPLATE_ID)
    doc = session.compose(tpl, attention_slots(), title="t")
    sleep = next(s for s in doc["sections"] if s["id"] == "sleep20")
    assert sleep["gain_db"] == -24.0
    # The reinforcement is real narration (the focus-11 wording repeated), not an empty hold.
    assert all(line["text"] for line in sleep["timeline"])
    assert len(sleep["timeline"]) == len(attention_slots()["focus11"].splitlines()) * 2


def test_attention_template_starts_match_legacy_arc():
    tpl = session.load_template(ATTENTION_TEMPLATE_ID)
    starts = {s["id"]: s["start"] for s in tpl["sections"]}
    assert starts["access-open"] == 391.0
    assert starts["focus11"] == 464.28
    assert starts["count-to-twenty"] == 834.32
    assert starts["sleep20"] == 1014.32
    assert starts["return"] == 1582.64
    assert starts["closing"] == 1748.24


class TestSessionCli:
    def test_list_templates(self, capsys):
        assert cli_main(["session", "list-templates"]) == 0
        assert TEMPLATE_ID in capsys.readouterr().out

    def test_compose_via_cli(self, tmp_path):
        files = {}
        for name, text in SLOTS.items():
            path = tmp_path / f"{name}.txt"
            path.write_text(text)
            files[name] = path
        out = tmp_path / "script.yaml"
        rc = cli_main(
            [
                "session",
                "compose",
                "--opener",
                str(files["opener"]),
                "--focus11",
                str(files["focus11"]),
                "--sleep20",
                str(files["sleep20"]),
                "--closer",
                str(files["closer"]),
                "--title",
                "Demo",
                "--output",
                str(out),
            ]
        )
        assert rc == 0
        assert out.is_file()
        text = out.read_text()
        assert "template:" in text
        assert "OCF-TPL-SESSION-LEARN-001" in text

    def test_compose_missing_opener_fails(self, tmp_path):
        files = {}
        for name, text in SLOTS.items():
            if name == "opener":
                continue
            path = tmp_path / f"{name}.txt"
            path.write_text(text)
            files[name] = path
        out = tmp_path / "script.yaml"
        args = ["session", "compose"]
        for name, path in files.items():
            args += [f"--{name}", str(path)]
        args += ["--output", str(out)]
        assert cli_main(args) == 1