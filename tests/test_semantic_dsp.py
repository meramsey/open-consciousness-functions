"""Configured state dispatch, source confidence and non-silent transition contracts."""

import shutil
import subprocess
import wave
from array import array
from copy import deepcopy

import pytest
from conftest import REPO_ROOT
from ocf_tools.indexes import load_yaml_file
from ocf_tools.semantic_dsp import gain_at, load_profile, plan_program
from ocf_tools.utils import OCFError


def state_doc():
    return {"timeline": [
        {"id": "ten", "at": "00:10.000", "semantic": "focus.ten.transition", "dsp": {"state": "focus-10"}},
        {"id": "eleven", "at": "00:30.000", "semantic": "focus.eleven.transition.open", "dsp": {"state": {"from": "focus-10", "to": "focus-11"}}},
        {"id": "eleven-ready", "after": "eleven", "offset": 0, "timing": {"anchor": "event-end"}, "semantic": "focus.eleven.ready"},
        {"id": "close", "at": "01:00.000", "semantic": "focus.eleven.transition.close", "dsp": {"state": {"from": "focus-11", "to": "focus-10"}}},
        {"id": "ten-return", "after": "close", "offset": 0, "timing": {"anchor": "event-end"}, "semantic": "focus.ten.ready"},
        {"id": "wake", "at": "01:30.000", "semantic": "session.return.complete", "dsp": {"state": "ordinary-waking"}},
        {"id": "end", "after": "wake", "offset": 0, "timing": {"anchor": "speech-end"}, "semantic": "session.complete"},
    ]}


TIMES = [{"id": key, "at": value} for key, value in [
    ("ten", 10), ("eleven", 30), ("eleven-ready", 40), ("close", 60), ("ten-return", 70), ("wake", 90), ("end", 98),
]]


def test_v4_candidate_resolution_and_provenance_not_universal_canonical():
    manifest = load_yaml_file(REPO_ROOT / "audio/background/manifests/OCF-BG-0012.yaml")
    assert manifest["provenance"]["status"] == "candidate"
    assert manifest["provenance"]["evidence_class"] == "measured directly from supplied V4-short reference excerpt"
    assert len(manifest["provenance"]["reference_sha256"]) == 64
    preset = load_yaml_file(REPO_ROOT / manifest["preset"]["file"])
    pairs = [group["pairs"][0] for group in preset["segments"][0]["groups"]]
    # Rounded structural measurements from the supplied excerpt, not arbitrary
    # theta/alpha lore; confidence and known modulation omissions live in report.
    assert pairs == [{"left": 39.75, "right": 40.25}, {"left": 79.25, "right": 80.75},
                     {"left": 158.05, "right": 161.95}, {"left": 198.0, "right": 202.0},
                     {"left": 317.95, "right": 322.05}]
    assert all(pair["right"] > pair["left"] for pair in pairs)
    assert all("tremolo" not in group and "sam" not in group for group in preset["segments"][0]["groups"])


def test_canonical_newer_f11_is_pure_sam_and_alternate_is_preserved():
    default = load_profile("OCF-DSP-DEFAULT-001")
    assert default["states"]["focus-11"]["preset"] == "OCF-BG-0006"
    pure = load_yaml_file(REPO_ROOT / "audio/background/presets/farfield/focus-11-b.yaml")
    alternate = load_yaml_file(REPO_ROOT / "audio/background/presets/farfield/focus-11-c.yaml")
    assert all("sam" in group for group in pure["segments"][0]["groups"])
    assert any(group.get("pairs") == [{"left": 175.0, "right": 179.0}] for group in alternate["segments"][0]["groups"])
    assert "alternate" in load_yaml_file(REPO_ROOT / "audio/background/manifests/OCF-BG-0007.yaml")["name"]


def test_measured_timing_resolves_backend_without_session_filenames():
    program = plan_program(state_doc(), TIMES, 100, load_profile("OCF-DSP-DEVELOPMENT-V4-001"))
    assert program["selections"]["focus-10"]["preset_id"] == "OCF-BG-0012"
    assert program["selections"]["focus-11"]["preset_id"] == "OCF-BG-0006"
    assert program["selections"]["focus-11"]["backend"] == "farfield"
    assert [(row["start_s"], row["end_s"]) for row in program["transitions"]] == [(10, 15), (30, 40), (60, 70), (90, 98)]
    assert program["transitions"][0]["envelope_provenance"].startswith("profile design-selected")


def test_continuous_equal_power_morph_without_an_intermediate_state():
    program = plan_program(state_doc(), TIMES, 100, load_profile("OCF-DSP-DEVELOPMENT-V4-001"))
    assert gain_at(program, "focus-10", 5) == 0
    assert gain_at(program, "focus-10", 20) == 1
    a, b = gain_at(program, "focus-10", 35), gain_at(program, "focus-11", 35)
    assert a > 0 and b > 0 and a*a+b*b == pytest.approx(1)
    assert gain_at(program, "focus-10", 50) == 0
    assert gain_at(program, "focus-11", 80) == 0
    assert gain_at(program, "focus-10", 99) == 0
    assert {row["to"] for row in program["transitions"]} == {"focus-10", "focus-11", "ordinary-waking"}


def test_missing_state_implementation_fails_or_must_be_explicitly_disabled():
    with pytest.raises(OCFError, match="required state DSP.*focus-10"):
        plan_program(state_doc(), TIMES, 100, load_profile("OCF-DSP-DEFAULT-001"))
    profile = load_profile("OCF-DSP-DEFAULT-001")
    profile["states"]["focus-10"] = {"mode": "disabled"}
    assert plan_program(state_doc(), TIMES, 100, profile)["selections"]["focus-10"]["explicit"]
    profile["states"]["focus-10"] = {"mode": "preset", "preset": "unrelated-name"}
    with pytest.raises(OCFError, match="unknown background"):
        plan_program(state_doc(), TIMES, 100, profile)


def test_unknown_timing_and_wrong_from_state_do_not_silently_fall_back():
    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    with pytest.raises(OCFError, match="no measured"):
        plan_program(state_doc(), TIMES[1:], 100, profile)
    doc = deepcopy(state_doc())
    doc["timeline"][1]["dsp"]["state"]["from"] = "focus-3"
    with pytest.raises(OCFError, match="disagrees"):
        plan_program(doc, TIMES, 100, profile)


def test_dispatch_plan_is_deterministic_and_does_not_mutate_source():
    doc, profile = state_doc(), load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    original = deepcopy(doc)
    assert plan_program(doc, TIMES, 100, profile) == plan_program(doc, TIMES, 100, profile)
    assert doc == original


def test_invalid_duration_duplicate_ledger_and_overlapping_windows():
    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    with pytest.raises(OCFError, match="positive session"):
        plan_program(state_doc(), TIMES, float("nan"), profile)
    with pytest.raises(OCFError, match="duplicate IDs"):
        plan_program(state_doc(), TIMES + TIMES[:1], 100, profile)
    doc = state_doc()
    doc["timeline"][0]["dsp"]["transition_s"] = 40
    with pytest.raises(OCFError, match="overlapping"):
        plan_program(doc, TIMES, 100, profile)


def test_repeated_state_is_noop_not_a_gain_swell():
    doc = state_doc()
    doc["timeline"][0]["dsp"]["state"] = "ordinary-waking"
    doc["timeline"][1]["dsp"]["state"]["from"] = "ordinary-waking"
    program = plan_program(doc, TIMES, 100, load_profile("OCF-DSP-DEVELOPMENT-V4-001"))
    assert gain_at(program, "ordinary-waking", 12) == 1


def test_actual_ffmpeg_envelopes_and_seeded_output(tmp_path):
    """Integration: independently check PCM, including both state morphs."""
    from ocf_tools.semantic_dsp import render_program

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe integration dependency unavailable")
    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    profile.pop("target_state_rms_dbfs")
    profile["transitions"]["fallback_seconds"] = .5
    times = [{**row, "at": row["at"]/10} for row in TIMES]
    stems = {}
    for state, level in [("focus-10", 3277), ("focus-11", 6554)]:
        path = tmp_path / f"{state}.wav"
        with wave.open(str(path), "wb") as writer:
            writer.setparams((2, 2, 8000, 0, "NONE", "not compressed"))
            writer.writeframes(array("h", [level, level]*80000).tobytes())
        stems[state] = path
    outputs = []
    for number in range(2):
        path = tmp_path / f"bed-{number}.wav"
        program = render_program(state_doc(), times, 10, profile, path,
                                 render_state=lambda state, selection, seed, duration: stems[state])
        outputs.append(program["output_sha256"])
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s24le", "-c:a", "pcm_s24le", "-"], capture_output=True, check=True).stdout
        assert len(raw) == 441000*6
        for time, expected in [(0,0), (2,3277/32768), (3.5, (3277+6554)/32768/2**.5), (5,6554/32768), (6.5,(3277+6554)/32768/2**.5), (8,3277/32768), (9.9,0)]:
            index = round(time*44100)*6
            sample = int.from_bytes(raw[index:index+3], "little", signed=True)/8388608
            assert sample == pytest.approx(expected, abs=3e-6)
    assert outputs[0] == outputs[1]


def test_cli_state_program_uses_existing_measured_ledger(monkeypatch, tmp_path):
    from ocf_tools import semantic_dsp
    from ocf_tools.cli import main
    from ocf_tools.utils import yaml_safe_dump

    doc = tmp_path / "session.yaml"
    doc.write_text(yaml_safe_dump({"schema_version": "1.0", "id": "test", "title": "Test", "source": {"format": "manual"}, **state_doc()}))
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(yaml_safe_dump({"event_timing": TIMES, "total_duration_s": 100}))
    captured = {}

    def render(document, timing, duration, profile, output):
        captured.update(timing=timing, duration=duration, profile=profile["id"])
        return {"profile_id": profile["id"]}

    monkeypatch.setattr(semantic_dsp, "render_program", render)
    assert main(["audio", "render-state-program", str(doc), "--render-manifest", str(ledger), "--dsp-profile", "OCF-DSP-DEVELOPMENT-V4-001", "--output", str(tmp_path / "bed.wav")]) == 0
    assert captured == {"timing": TIMES, "duration": 100, "profile": "OCF-DSP-DEVELOPMENT-V4-001"}
