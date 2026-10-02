"""Canonical Focus-state sequence guards.

The analyzed Human Plus / Focus 11 Access Channel source establishes the
background program as Focus 10 -> Focus 11 -> Focus 10. An earlier OCF-BG-0001
described a "focus-3 -> focus-10 -> focus-3" arc; that framing was wrong and is
superseded. These tests fail if Focus 3 returns to a canonical Focus-state
sequence, or if the recorded timings drift from the measured splice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from conftest import REPO_ROOT

CANONICAL_SEQUENCE = ("focus-10", "focus-11", "focus-10")

# Measured values from the OCF-BG-0011 splice: the access window opens at 6:31
# (391.0 s), closes at 12:50 (770.0 s), crossfaded over 30 s.
ACCESS_WINDOW = (391.0, 770.0)
ACCESS_CROSSFADE_S = 30


def _manifest(bg_id: str) -> dict:
    path = REPO_ROOT / "audio" / "background" / "manifests" / f"{bg_id}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_bg_0001_declares_the_canonical_focus_sequence():
    sequence = _manifest("OCF-BG-0001")["focus_sequence"]
    states = tuple(entry["state"] for entry in sequence)
    assert states == CANONICAL_SEQUENCE


def test_focus_3_is_never_part_of_a_canonical_focus_sequence():
    """No background may place Focus 3 inside a Focus-state program."""
    directory = REPO_ROOT / "audio" / "background" / "manifests"
    offenders = [
        path.name
        for path in sorted(directory.glob("OCF-BG-*.yaml"))
        for sequence in [
            yaml.safe_load(path.read_text(encoding="utf-8")).get("focus_sequence") or []
        ]
        if any("focus-3" in str(entry.get("state", "")) for entry in sequence)
    ]
    assert offenders == [], f"Focus 3 leaked into a Focus-state program: {offenders}"


def test_focus_sequence_roles_are_semantic():
    roles = [entry["role"] for entry in _manifest("OCF-BG-0001")["focus_sequence"]]
    assert roles == ["pre-access", "access-channel", "return"]


def test_focus_sequence_timings_match_the_measured_splice():
    sequence = _manifest("OCF-BG-0001")["focus_sequence"]
    access = sequence[1]
    assert access["start_s"] == pytest.approx(ACCESS_WINDOW[0])
    assert access["end_s"] == pytest.approx(ACCESS_WINDOW[1])
    assert access["crossfade_s"] == pytest.approx(ACCESS_CROSSFADE_S)
    # the program must open on Focus 10 and return to it
    assert sequence[0]["state"] == "focus-10"
    assert sequence[2]["state"] == "focus-10"
    assert sequence[2]["start_s"] == pytest.approx(ACCESS_WINDOW[1])


def test_bg_0001_provenance_timeline_assigns_no_focus_3_state():
    """Focus 3 may be named only to mark it superseded, never in the timeline."""
    import re

    notes = _manifest("OCF-BG-0001")["provenance"]["notes"]
    timeline = [line for line in notes.splitlines() if re.match(r"\s*\d+:\d+", line)]
    assert timeline, "expected a timeline in the provenance notes"
    assert not [line for line in timeline if "focus-3" in line.lower()]
    assert "superseded" in notes.lower()


def test_bg_0001_name_states_the_canonical_sequence():
    name = _manifest("OCF-BG-0001")["name"]
    assert "focus-3" not in name.lower()
    assert "Focus 10" in name and "Focus 11" in name


def test_focus_3_is_not_an_allowed_focus_sequence_state():
    schema = json.loads(
        (REPO_ROOT / "schemas" / "background-audio.schema.json").read_text(encoding="utf-8")
    )
    states = schema["properties"]["focus_sequence"]["items"]["properties"]["state"]["enum"]
    assert "focus-3" not in states
    assert {"focus-10", "focus-11"} <= set(states)


def test_sbagenx_arc_comment_carries_no_focus_3_framing():
    text = (REPO_ROOT / "audio" / "background" / "presets" / "attention-focus-arc.sbg").read_text(
        encoding="utf-8"
    )
    assert "focus-3 -> focus-10 -> focus-3" not in text


def test_focus_11_program_resolves_to_a_farfield_session():
    """OCF-BG-0001 names the combined session; OCF-BG-0011 carries the same program."""
    bg_0001 = _manifest("OCF-BG-0001")
    session = bg_0001["preset"]["file"]
    assert session == "audio/background/presets/attention-focus-10-11-10.yaml"

    # The declared path must actually exist and be a Farfield session.
    from ocf_tools import farfield as farfield_mod

    assert (REPO_ROOT / session).is_file()
    resolved = farfield_mod.resolve_preset(Path(session).stem)
    assert resolved is not None and resolved.is_file()

    bg_0011 = _manifest("OCF-BG-0011")
    assert bg_0011["engine"] == "reference-master"
    splice = bg_0011["reference"]["splices"][0]
    assert splice["target_start"] == pytest.approx(ACCESS_WINDOW[0])
    assert splice["slice_length"] == pytest.approx(ACCESS_WINDOW[1] - ACCESS_WINDOW[0])
    assert splice["crossfade"] == pytest.approx(ACCESS_CROSSFADE_S)
