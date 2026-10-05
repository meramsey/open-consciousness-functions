"""Configured state dispatch, source confidence and non-silent transition contracts."""

import math
import shutil
import subprocess
import wave
from array import array
from copy import deepcopy

import pytest
from conftest import REPO_ROOT
from ocf_tools.indexes import load_yaml_file
from ocf_tools.semantic_dsp import _gain_expression, gain_at, load_profile, plan_program
from ocf_tools.utils import OCFError


def state_doc():
    return {
        "timeline": [
            {
                "id": "ten",
                "at": "00:10.000",
                "semantic": "focus.ten.transition",
                "dsp": {"state": "focus-10"},
            },
            {
                "id": "eleven",
                "at": "00:30.000",
                "semantic": "focus.eleven.transition.open",
                "dsp": {"state": {"from": "focus-10", "to": "focus-11"}},
            },
            {
                "id": "eleven-ready",
                "after": "eleven",
                "offset": 0,
                "timing": {"anchor": "event-end"},
                "semantic": "focus.eleven.ready",
            },
            {
                "id": "close",
                "at": "01:00.000",
                "semantic": "focus.eleven.transition.close",
                "dsp": {"state": {"from": "focus-11", "to": "focus-10"}},
            },
            {
                "id": "ten-return",
                "after": "close",
                "offset": 0,
                "timing": {"anchor": "event-end"},
                "semantic": "focus.ten.ready",
            },
            {
                "id": "wake",
                "at": "01:30.000",
                "semantic": "session.return.complete",
                "dsp": {"state": "ordinary-waking"},
            },
            {
                "id": "end",
                "after": "wake",
                "offset": 0,
                "timing": {"anchor": "speech-end"},
                "semantic": "session.complete",
            },
        ]
    }


TIMES = [
    {"id": key, "at": value}
    for key, value in [
        ("ten", 10),
        ("eleven", 30),
        ("eleven-ready", 40),
        ("close", 60),
        ("ten-return", 70),
        ("wake", 90),
        ("end", 98),
    ]
]


def test_v4_candidate_resolution_and_provenance_not_universal_canonical():
    manifest = load_yaml_file(REPO_ROOT / "audio/background/manifests/OCF-BG-0012.yaml")
    assert manifest["provenance"]["status"] == "candidate"
    assert (
        manifest["provenance"]["evidence_class"]
        == "measured directly from supplied V4-short reference excerpt"
    )
    assert len(manifest["provenance"]["reference_sha256"]) == 64
    preset = load_yaml_file(REPO_ROOT / manifest["preset"]["file"])
    pairs = [group["pairs"][0] for group in preset["segments"][0]["groups"]]
    # Rounded structural measurements from the supplied excerpt, not arbitrary
    # theta/alpha lore; confidence and known modulation omissions live in report.
    assert pairs == [
        {"left": 39.75, "right": 40.25},
        {"left": 79.25, "right": 80.75},
        {"left": 158.05, "right": 161.95},
        {"left": 198.0, "right": 202.0},
        {"left": 317.95, "right": 322.05},
    ]
    assert all(pair["right"] > pair["left"] for pair in pairs)
    assert all(
        "tremolo" not in group and "sam" not in group for group in preset["segments"][0]["groups"]
    )


def test_canonical_newer_f11_is_pure_sam_and_alternate_is_preserved():
    default = load_profile("OCF-DSP-DEFAULT-001")
    assert default["states"]["focus-11"]["preset"] == "OCF-BG-0006"
    pure = load_yaml_file(REPO_ROOT / "audio/background/presets/farfield/focus-11-b.yaml")
    alternate = load_yaml_file(REPO_ROOT / "audio/background/presets/farfield/focus-11-c.yaml")
    assert all("sam" in group for group in pure["segments"][0]["groups"])
    assert any(
        group.get("pairs") == [{"left": 175.0, "right": 179.0}]
        for group in alternate["segments"][0]["groups"]
    )
    assert (
        "alternate"
        in load_yaml_file(REPO_ROOT / "audio/background/manifests/OCF-BG-0007.yaml")["name"]
    )


def test_measured_timing_resolves_backend_without_session_filenames():
    program = plan_program(state_doc(), TIMES, 100, load_profile("OCF-DSP-DEVELOPMENT-V4-001"))
    assert program["selections"]["focus-10"]["preset_id"] == "OCF-BG-0012"
    assert program["selections"]["focus-11"]["preset_id"] == "OCF-BG-0006"
    assert program["selections"]["focus-11"]["backend"] == "farfield"
    assert [(row["start_s"], row["end_s"]) for row in program["transitions"]] == [
        (10, 15),
        (30, 40),
        (60, 70),
        (90, 98),
    ]
    assert program["transitions"][0]["envelope_provenance"].startswith("profile design-selected")


def test_continuous_equal_power_morph_without_an_intermediate_state():
    program = plan_program(state_doc(), TIMES, 100, load_profile("OCF-DSP-DEVELOPMENT-V4-001"))
    assert gain_at(program, "focus-10", 5) == 0
    assert gain_at(program, "focus-10", 20) == 1
    a, b = gain_at(program, "focus-10", 35), gain_at(program, "focus-11", 35)
    assert a > 0 and b > 0 and a * a + b * b == pytest.approx(1)
    assert gain_at(program, "focus-10", 50) == 0
    assert gain_at(program, "focus-11", 80) == 0
    assert gain_at(program, "focus-10", 99) == 0
    assert {row["to"] for row in program["transitions"]} == {
        "focus-10",
        "focus-11",
        "ordinary-waking",
    }


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
    profile["unexpected"] = True
    with pytest.raises(OCFError, match="semantic DSP profile:"):
        plan_program(state_doc(), TIMES, 100, profile)


def test_profile_load_and_declared_preset_file_failures_are_explicit(monkeypatch, tmp_path):
    from ocf_tools import audio_build, semantic_dsp

    with pytest.raises(OCFError, match="profile not found"):
        load_profile("missing-semantic-profile-for-test")

    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("{}\n")
    with pytest.raises(OCFError, match="semantic DSP profile:"):
        load_profile(invalid)

    monkeypatch.setattr(semantic_dsp, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        audio_build,
        "_resolve_background_manifest",
        lambda _preset: {
            "id": "TEST-PRESET",
            "engine": "farfield",
            "preset": {"file": "missing.preset"},
            "provenance": {},
        },
    )
    with pytest.raises(OCFError, match="preset file unavailable"):
        plan_program(state_doc(), TIMES, 100, load_profile("OCF-DSP-DEVELOPMENT-V4-001"))


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


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda doc, profile: doc["timeline"][0]["dsp"].update(transition_s=200), "window"),
        (lambda doc, profile: doc["timeline"][0]["dsp"].update(transition_s=-1), "window"),
        (
            lambda doc, profile: doc["timeline"][0]["dsp"].update(state={"from": "focus-10"}),
            "no target",
        ),
        (lambda doc, profile: profile["states"].pop("ordinary-waking"), "required state DSP"),
    ],
)
def test_transition_directive_boundaries_fail_closed(mutate, message):
    doc, profile = state_doc(), load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    mutate(doc, profile)
    with pytest.raises(OCFError, match=message):
        plan_program(doc, TIMES, 100, profile)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda doc, profile: doc["timeline"].clear(), "no state directives"),
        (lambda doc, profile: profile.update(initial_state="not-configured"), "required state DSP"),
        (
            lambda doc, profile: profile.update(
                approaches=[
                    {
                        "state_event": "ten",
                        "state": "focus-11",
                        "begin_event": "ten",
                        "established_event": "ten",
                        "curve": "raised-cosine",
                    }
                ]
            ),
            "distinct arrival directive",
        ),
    ],
)
def test_empty_or_invalid_approach_configuration_is_rejected(change, message):
    doc, profile = state_doc(), load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    change(doc, profile)
    with pytest.raises(OCFError, match=message):
        plan_program(doc, TIMES, 100, profile)


def test_linear_gain_and_ffmpeg_expression_cover_transition_shapes():
    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    profile["transitions"]["curve"] = "linear"
    program = plan_program(state_doc(), TIMES, 100, profile)
    assert gain_at(program, "focus-10", 35) == pytest.approx(0.5)
    assert gain_at(program, "focus-11", 35) == pytest.approx(0.5)
    expression = _gain_expression(program, "focus-10")
    assert "clip(" in expression and "cos(PI/2*" not in expression
    equal_power = plan_program(state_doc(), TIMES, 100, load_profile("OCF-DSP-DEVELOPMENT-V4-001"))
    assert "cos(PI/2*" in _gain_expression(equal_power, "focus-10")


def test_repeated_state_is_noop_not_a_gain_swell():
    doc = state_doc()
    doc["timeline"][0]["dsp"]["state"] = "ordinary-waking"
    doc["timeline"][1]["dsp"]["state"]["from"] = "ordinary-waking"
    program = plan_program(doc, TIMES, 100, load_profile("OCF-DSP-DEVELOPMENT-V4-001"))
    assert gain_at(program, "ordinary-waking", 12) == 1
    assert "(t-10.000000000)" not in _gain_expression(program, "ordinary-waking")


def constant_stem(directory, state, level):
    """A flat calibrated probe stem; output level then reads out the envelope."""
    path = directory / f"{state}.wav"
    with wave.open(str(path), "wb") as writer:
        writer.setparams((2, 2, 8000, 0, "NONE", "not compressed"))
        writer.writeframes(array("h", [level, level] * 80000).tobytes())
    return path


def approach_doc():
    doc = state_doc()
    doc["timeline"][:0] = [
        {"id": "preparation", "at": 1, "semantic": "preparation.relaxation.begin"},
        {"id": "arrival-word", "at": 8, "semantic": "focus.ten.enter"},
    ]
    return doc


def approach_profile():
    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    profile.pop("target_state_rms_dbfs")
    profile["transitions"]["fallback_seconds"] = 0.5
    profile["approaches"] = [
        {
            "state": "focus-10",
            "begin_event": "preparation",
            "established_event": "arrival-word",
            "state_event": "ten",
            "curve": "raised-cosine",
        }
    ]
    return profile


def test_measured_approach_ownership_and_anchor_failures_are_unit_contracts():
    doc = approach_doc()
    times = [{"id": "preparation", "at": 1}, {"id": "arrival-word", "at": 8}]
    times += TIMES
    program = plan_program(doc, times, 100, approach_profile())
    assert program["transitions"][0]["end_s"] == program["transitions"][0]["start_s"]
    assert program["approaches"][0]["arrival_s"] == 10
    assert gain_at(program, "focus-10", 5) == pytest.approx((1 - math.cos(4 * math.pi / 7)) / 2)
    assert gain_at(program, "focus-11", 35) > 0
    assert "(1-cos(PI*" in _gain_expression(program, "focus-10")

    for bad_times, message in [
        ([row for row in times if row["id"] != "preparation"], "anchor missing"),
        (
            [dict(row, at=0) if row["id"] == "ten" else row for row in times],
            "invalid DSP approach window",
        ),
        (
            [dict(row, at="bad") if row["id"] == "arrival-word" else row for row in times],
            "numeric times",
        ),
    ]:
        with pytest.raises(OCFError, match=message):
            plan_program(doc, bad_times, 100, approach_profile())

    disabled = approach_profile()
    disabled["states"]["focus-10"] = {"mode": "disabled"}
    with pytest.raises(OCFError, match="explicitly selected program"):
        plan_program(doc, times, 100, disabled)

    duplicate = approach_profile()
    duplicate["approaches"].append(dict(duplicate["approaches"][0]))
    with pytest.raises(OCFError, match="duplicate DSP approach"):
        plan_program(doc, times, 100, duplicate)

    interleaved = approach_doc()
    interleaved["timeline"].insert(
        2,
        {"id": "intermediate", "at": 5, "dsp": {"state": "focus-11"}},
    )
    interleaved_times = times + [{"id": "intermediate", "at": 5}]
    with pytest.raises(OCFError, match="approach overlaps another state transition"):
        plan_program(interleaved, interleaved_times, 100, approach_profile())

    overlapping_doc = {
        "timeline": [
            {"id": "preparation", "at": 1},
            {"id": "arrival-word", "at": 8},
            {"id": "arrival-ten", "at": 10, "dsp": {"state": "focus-10"}},
            {"id": "arrival-eleven", "at": 10, "dsp": {"state": "focus-11"}},
        ]
    }
    overlapping_times = [
        {"id": "preparation", "at": 1},
        {"id": "arrival-word", "at": 8},
        {"id": "arrival-ten", "at": 10},
        {"id": "arrival-eleven", "at": 10},
    ]
    overlapping = approach_profile()
    overlapping["approaches"][0]["state_event"] = "arrival-ten"
    overlapping["approaches"].append(
        {
            "state": "focus-11",
            "begin_event": "preparation",
            "established_event": "arrival-word",
            "state_event": "arrival-eleven",
            "curve": "raised-cosine",
        }
    )
    with pytest.raises(OCFError, match="overlapping DSP approaches"):
        plan_program(overlapping_doc, overlapping_times, 100, overlapping)

    double_ramp = approach_profile()
    doc_with_ramp = approach_doc()
    doc_with_ramp["timeline"][2]["dsp"]["transition_s"] = 1
    with pytest.raises(OCFError, match="second nonzero DSP ramp"):
        plan_program(doc_with_ramp, times, 100, double_ramp)


@pytest.mark.parametrize(
    ("available", "message"),
    [
        ({"ffprobe": "/usr/bin/ffprobe"}, "requires ffmpeg"),
        ({"ffmpeg": "/usr/bin/ffmpeg"}, "requires ffprobe"),
    ],
)
def test_renderer_requires_both_verification_tools(monkeypatch, tmp_path, available, message):
    from ocf_tools import semantic_dsp

    monkeypatch.setattr(semantic_dsp.shutil, "which", lambda name: available.get(name))
    with pytest.raises(OCFError, match=message):
        semantic_dsp.render_program(
            state_doc(),
            TIMES,
            100,
            load_profile("OCF-DSP-DEVELOPMENT-V4-001"),
            tmp_path / "bed.wav",
        )


def test_disabled_renderer_emits_deterministic_silence_without_state_sources(monkeypatch, tmp_path):
    from ocf_tools import semantic_dsp

    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    profile["states"] = {state: {"mode": "disabled"} for state in profile["states"]}
    commands = []
    monkeypatch.setattr(semantic_dsp.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        semantic_dsp,
        "_command",
        lambda command: commands.append(command) or subprocess.CompletedProcess(command, 0, "", ""),
    )
    monkeypatch.setattr(semantic_dsp, "_sha", lambda path: "a" * 64)

    output = tmp_path / "nested" / "silence.wav"
    program = semantic_dsp.render_program(state_doc(), TIMES, 100, profile, output)

    assert output.parent.is_dir()
    assert program["output_sha256"] == "a" * 64
    assert len(program["external_commands"]) == 1
    assert "anullsrc=r=44100:cl=stereo" in commands[0]
    assert commands[0][-1] == str(output)


def test_renderer_verifies_rendered_state_duration_before_mixing(monkeypatch, tmp_path):
    import json

    from ocf_tools import semantic_dsp

    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    profile.pop("target_state_rms_dbfs", None)
    commands = []
    monkeypatch.setattr(semantic_dsp.shutil, "which", lambda name: f"/usr/bin/{name}")

    def command(args):
        commands.append(args)
        stdout = json.dumps({"format": {"duration": "100"}}) if "ffprobe" in args[0] else ""
        return subprocess.CompletedProcess(args, 0, stdout, "")

    monkeypatch.setattr(semantic_dsp, "_command", command)
    monkeypatch.setattr(semantic_dsp, "_sha", lambda _path: "b" * 64)
    stem = tmp_path / "rendered.wav"

    def render_state(_state, _selection, _seed, _duration):
        stem.touch()
        return stem

    result = semantic_dsp.render_program(
        state_doc(), TIMES, 100, profile, tmp_path / "mix.wav", render_state=render_state
    )
    assert len([args for args in commands if "ffprobe" in args[0]]) == sum(
        choice["mode"] == "preset" for choice in result["selections"].values()
    )
    assert any("-filter_complex" in args for args in commands)
    assert all(
        selection["stem_sha256"] == "b" * 64
        for selection in result["selections"].values()
        if selection["mode"] == "preset"
    )


def test_renderer_rejects_short_state_stem_without_silent_extension(monkeypatch, tmp_path):
    import json

    from ocf_tools import semantic_dsp

    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    monkeypatch.setattr(semantic_dsp.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        semantic_dsp,
        "_command",
        lambda args: subprocess.CompletedProcess(
            args, 0, json.dumps({"format": {"duration": "1"}}), ""
        ),
    )
    stem = tmp_path / "short.wav"
    stem.touch()
    with pytest.raises(OCFError, match="shorter than the session"):
        semantic_dsp.render_program(
            state_doc(),
            TIMES,
            100,
            profile,
            tmp_path / "mix.wav",
            render_state=lambda *_args: stem,
        )


def test_farfield_render_boundary_records_commands_and_validates_outputs(monkeypatch, tmp_path):
    import json

    from ocf_tools import farfield, semantic_dsp

    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    profile.pop("target_state_rms_dbfs", None)
    monkeypatch.setattr(semantic_dsp.shutil, "which", lambda name: f"/usr/bin/{name}")

    def render(args):
        output = Path(args[args.index("--output") + 1])
        output.touch()
        return subprocess.CompletedProcess(args, 0, "", "")

    from pathlib import Path

    monkeypatch.setattr(farfield, "run_farfield", render)
    monkeypatch.setattr(
        semantic_dsp,
        "_command",
        lambda args: subprocess.CompletedProcess(
            args, 0, json.dumps({"format": {"duration": "100"}}) if "ffprobe" in args[0] else "", ""
        ),
    )
    monkeypatch.setattr(semantic_dsp, "_sha", lambda _path: "c" * 64)
    output = tmp_path / "bed.wav"
    result = semantic_dsp.render_program(state_doc(), TIMES, 100, profile, output)
    assert (
        len([command for command in result["external_commands"] if command[0] == "farfield"]) == 2
    )
    assert all(
        selection["stem_sha256"] == "c" * 64
        for selection in result["selections"].values()
        if selection["mode"] == "preset"
    )


@pytest.mark.parametrize("outcome", ["failure", "missing-output", "missing-engine"])
def test_farfield_render_boundary_fails_closed(monkeypatch, tmp_path, outcome):
    from ocf_tools import farfield, semantic_dsp

    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    monkeypatch.setattr(semantic_dsp.shutil, "which", lambda name: f"/usr/bin/{name}")

    def render(args):
        if outcome == "missing-engine":
            raise farfield.OCFFarfieldMissing("install Farfield")
        if outcome == "missing-output":
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 1, "", "render failed")

    monkeypatch.setattr(farfield, "run_farfield", render)
    with pytest.raises(
        OCFError, match="required state focus-10: (install Farfield|Farfield render failed)"
    ):
        semantic_dsp.render_program(state_doc(), TIMES, 100, profile, tmp_path / "bed.wav")


def test_other_backend_render_and_calibration_are_validated(monkeypatch, tmp_path):
    import json

    from ocf_tools import audio_build, semantic_dsp

    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    preset = {
        "id": "TEST-REFERENCE-MASTER",
        "engine": "reference-master",
        "preset": {},
        "provenance": {},
    }
    monkeypatch.setattr(audio_build, "_resolve_background_manifest", lambda _reference: preset)
    monkeypatch.setattr(semantic_dsp.shutil, "which", lambda name: f"/usr/bin/{name}")
    stem = tmp_path / "reference-master.wav"
    stem.touch()
    monkeypatch.setattr(audio_build, "_render_background", lambda *_args, **_kwargs: (stem, None))
    commands = []

    def command(args):
        commands.append(args)
        if "ffprobe" in args[0]:
            stdout, stderr = json.dumps({"format": {"duration": "100"}}), ""
        elif "volumedetect" in args:
            stdout, stderr = "", "mean_volume: -20.0 dB"
        else:
            stdout, stderr = "", ""
        return subprocess.CompletedProcess(args, 0, stdout, stderr)

    monkeypatch.setattr(semantic_dsp, "_command", command)
    monkeypatch.setattr(semantic_dsp, "_sha", lambda _path: "d" * 64)
    result = semantic_dsp.render_program(state_doc(), TIMES, 100, profile, tmp_path / "mix.wav")
    preset_selection = result["selections"]["focus-10"]
    expected_gain = 10 ** ((profile["target_state_rms_dbfs"] - (-20.0)) / 20)
    assert preset_selection["raw_rms_dbfs"] == -20
    assert preset_selection["renderer_gain"] == pytest.approx(expected_gain)
    assert any("volumedetect" in args for args in commands)


def test_other_backend_missing_output_and_unparseable_calibration_fail(monkeypatch, tmp_path):
    from ocf_tools import audio_build, semantic_dsp

    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    preset = {
        "id": "TEST",
        "engine": "reference-master",
        "preset": {},
        "provenance": {},
    }
    monkeypatch.setattr(audio_build, "_resolve_background_manifest", lambda _reference: preset)
    monkeypatch.setattr(semantic_dsp.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        audio_build, "_render_background", lambda *_args, **_kwargs: (None, "engine failed")
    )
    with pytest.raises(OCFError, match="required state focus-10: engine failed"):
        semantic_dsp.render_program(state_doc(), TIMES, 100, profile, tmp_path / "mix.wav")

    stem = tmp_path / "bed.wav"
    stem.touch()
    monkeypatch.setattr(audio_build, "_render_background", lambda *_args, **_kwargs: (stem, None))

    def uncalibratable(args):
        stdout = '{"format":{"duration":"100"}}' if "ffprobe" in args[0] else ""
        return subprocess.CompletedProcess(args, 0, stdout, "no volume measurement")

    monkeypatch.setattr(semantic_dsp, "_command", uncalibratable)
    with pytest.raises(OCFError, match="cannot calibrate state focus-10 RMS"):
        semantic_dsp.render_program(state_doc(), TIMES, 100, profile, tmp_path / "mix.wav")


def test_external_command_errors_include_command_and_stderr(monkeypatch):
    from ocf_tools import semantic_dsp

    monkeypatch.setattr(
        semantic_dsp.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 9, "", "engine detail"),
    )
    with pytest.raises(OCFError, match=r"semantic DSP engine failed: engine --flag\nengine detail"):
        semantic_dsp._command(["engine", "--flag"])

    success = subprocess.CompletedProcess(["engine"], 0, "ok", "")
    monkeypatch.setattr(semantic_dsp.subprocess, "run", lambda *_args, **_kwargs: success)
    assert semantic_dsp._command(["engine"]) is success


def test_render_command_refuses_overwrite_before_loading_inputs(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from ocf_tools import semantic_dsp

    output = tmp_path / "existing.wav"
    output.touch()
    monkeypatch.setattr(
        semantic_dsp, "load_profile", lambda _reference: pytest.fail("loaded profile")
    )
    args = SimpleNamespace(output=output, force=False)
    with pytest.raises(OCFError, match="refusing to overwrite"):
        semantic_dsp.run_render_program(args)


def test_render_command_requires_measured_timing_ledger(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from ocf_tools import semantic_dsp, transcript

    monkeypatch.setattr(transcript, "load_timed_doc", lambda _path: state_doc())
    monkeypatch.setattr(semantic_dsp, "load_yaml_file", lambda _path: {})
    args = SimpleNamespace(
        output=tmp_path / "bed.wav",
        force=False,
        file=tmp_path / "session.yaml",
        render_manifest=tmp_path / "ledger.yaml",
        dsp_profile="profile",
    )
    with pytest.raises(OCFError, match="measured event_timing ledger"):
        semantic_dsp.run_render_program(args)


def test_actual_ffmpeg_envelopes_and_seeded_output(tmp_path):
    """Integration: independently check PCM, including both state morphs."""
    from ocf_tools.semantic_dsp import render_program

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe integration dependency unavailable")
    profile = load_profile("OCF-DSP-DEVELOPMENT-V4-001")
    profile.pop("target_state_rms_dbfs")
    profile["transitions"]["fallback_seconds"] = 0.5
    times = [{**row, "at": row["at"] / 10} for row in TIMES]
    stems = {
        state: constant_stem(tmp_path, state, level)
        for state, level in [("focus-10", 3277), ("focus-11", 6554)]
    }
    outputs = []
    for number in range(2):
        path = tmp_path / f"bed-{number}.wav"
        program = render_program(
            state_doc(),
            times,
            10,
            profile,
            path,
            render_state=lambda state, selection, seed, duration: stems[state],
        )
        outputs.append(program["output_sha256"])
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s24le", "-c:a", "pcm_s24le", "-"],
            capture_output=True,
            check=True,
        ).stdout
        assert len(raw) == 441000 * 6
        for time, expected in [
            (0, 0),
            (2, 3277 / 32768),
            (3.5, (3277 + 6554) / 32768 / 2**0.5),
            (5, 6554 / 32768),
            (6.5, (3277 + 6554) / 32768 / 2**0.5),
            (8, 3277 / 32768),
            (9.9, 0),
        ]:
            index = round(time * 44100) * 6
            sample = int.from_bytes(raw[index : index + 3], "little", signed=True) / 8388608
            assert sample == pytest.approx(expected, abs=3e-6)
    assert outputs[0] == outputs[1]


def test_actual_ffmpeg_approach_envelope_matches_planned_gain(tmp_path):
    """Integration: rendered PCM follows the pre-arrival approach envelope."""
    from ocf_tools.semantic_dsp import render_program

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe integration dependency unavailable")
    times = [{"id": "preparation", "at": 0.1}, {"id": "arrival-word", "at": 0.9}]
    times += [{**row, "at": row["at"] / 10} for row in TIMES]
    stems = {
        state: constant_stem(tmp_path, state, level)
        for state, level in [("focus-10", 3277), ("focus-11", 6554)]
    }
    path = tmp_path / "approach-bed.wav"
    program = render_program(
        approach_doc(),
        times,
        10,
        approach_profile(),
        path,
        render_state=lambda state, selection, seed, duration: stems[state],
    )
    assert program["transitions"][0]["end_s"] == 1.0
    assert program["approaches"][0]["start_s"] == 0.1
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s24le", "-c:a", "pcm_s24le", "-"],
        capture_output=True,
        check=True,
    ).stdout
    assert len(raw) == 441000 * 6
    for time in [0.05, 0.1, 0.2, 0.5, 0.7, 0.9, 0.99, 1.0, 1.4, 2.5, 3.5, 5.0, 6.5, 8.0, 9.5]:
        index = round(time * 44100) * 6
        sample = int.from_bytes(raw[index : index + 3], "little", signed=True) / 8388608
        expected = (
            3277 * gain_at(program, "focus-10", time) + 6554 * gain_at(program, "focus-11", time)
        ) / 32768
        assert sample == pytest.approx(expected, abs=3e-6)
    # Nothing before induction, full F10 well before arrival, silence after exit.
    assert int.from_bytes(raw[0:3], "little", signed=True) == 0
    assert int.from_bytes(
        raw[round(1.4 * 44100) * 6 : round(1.4 * 44100) * 6 + 3], "little", signed=True
    ) == pytest.approx(3277 * 256, abs=1)
    assert (
        int.from_bytes(
            raw[round(9.99 * 44100) * 6 : round(9.99 * 44100) * 6 + 3], "little", signed=True
        )
        == 0
    )


def test_cli_state_program_uses_existing_measured_ledger(monkeypatch, tmp_path):
    from ocf_tools import semantic_dsp
    from ocf_tools.cli import main
    from ocf_tools.utils import yaml_safe_dump

    doc = tmp_path / "session.yaml"
    doc.write_text(
        yaml_safe_dump(
            {
                "schema_version": "1.0",
                "id": "test",
                "title": "Test",
                "source": {"format": "manual"},
                **state_doc(),
            }
        )
    )
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(yaml_safe_dump({"event_timing": TIMES, "total_duration_s": 100}))
    captured = {}

    def render(document, timing, duration, profile, output):
        captured.update(timing=timing, duration=duration, profile=profile["id"])
        return {"profile_id": profile["id"]}

    monkeypatch.setattr(semantic_dsp, "render_program", render)
    assert (
        main(
            [
                "audio",
                "render-state-program",
                str(doc),
                "--render-manifest",
                str(ledger),
                "--dsp-profile",
                "OCF-DSP-DEVELOPMENT-V4-001",
                "--output",
                str(tmp_path / "bed.wav"),
            ]
        )
        == 0
    )
    assert captured == {"timing": TIMES, "duration": 100, "profile": "OCF-DSP-DEVELOPMENT-V4-001"}
