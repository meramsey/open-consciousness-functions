from __future__ import annotations

import json
from pathlib import Path

import pytest
from ocf_tools import cli
from ocf_tools.complete_session import build_complete_session_plan


def test_sleep_easy_complete_template_expands_existing_focus_and_sleep_sequence(monkeypatch):
    from ocf_tools import narration_first

    monkeypatch.setattr(
        narration_first,
        "_voice_profile",
        lambda query, locale, catalog: (
            {
                "id": "OCF-VOICE-0002",
                "slug": "piper-lessac",
                "name": "Piper en_US lessac medium",
                "backend": "piper",
                "piper_length_scale": 1.0,
            },
            {"name": "piper", "language": "en_US", "binary": "piper", "wpm": None},
        ),
    )
    plan = build_complete_session_plan(
        "OCF-SLP-005", locale="en-US", voice="OCF-VOICE-0002", pacing="sleep"
    )
    assert plan["session_completeness"] == "complete"
    assert plan["template"] == {
        "id": "OCF-TPL-SESSION-HPLUS-LOCKED-005",
        "version": "5.0.0",
        "origin": "reference-derived",
        "content_status": "draft",
    }
    assert [stage["id"] for stage in plan["stages"]] == [
        "function-opener",
        "body-comfort",
        "transmutation-box",
        "relaxation",
        "focus-ten",
        "open",
        "focus11-body",
        "close",
        "focus10-hold",
        "focus20-enter",
        "sleep20-body",
        "focus20-close",
        "return",
        "function-closer",
        "session-complete",
    ]
    assert [row["to"] for row in plan["state_directives"]] == [
        "focus-10",
        "focus-11",
        "focus-10",
        "focus-20",
        "focus-10",
        "ordinary-waking",
    ]
    assert [row["to"] for row in plan["effective_state_directives"]] == [
        "focus-11",
        "focus-10",
    ]
    assert {row["event_id"] for row in plan["ignored_state_directives"]} == {
        "focus-ten.transition",
        "focus20-enter.transition",
        "focus20-close.transition",
        "return.complete",
    }
    state_choices = plan["dsp_profile"]["states"]
    assert state_choices["focus-10"] == {"mode": "preset", "preset": "OCF-BG-0012"}
    assert state_choices["focus-11"] == {"mode": "preset", "preset": "OCF-BG-0006"}
    assert "focus-20" not in state_choices
    assert plan["dsp_profile"]["default_background_state"] == "focus-10"
    stages = {stage["id"]: stage for stage in plan["stages"]}
    assert stages["function-opener"]["background_policy_states"] == ["focus-10"]
    assert stages["open"]["background_policy_states"] == ["focus-10", "focus-11"]
    assert stages["focus11-body"]["background_policy_states"] == ["focus-11"]
    assert stages["sleep20-body"]["background_policy_states"] == ["focus-10"]
    assert stages["function-closer"]["background_policy_states"] == ["focus-10"]
    assert len(plan["dsp_profile"]["ignored_state_events"]) == 4
    assert plan["approval_state"]["function_review_status"] == "required"
    assert plan["approval_state"]["release_ready"] is False
    sleep_stage = next(stage for stage in plan["stages"] if stage["id"] == "sleep20-body")
    assert len(sleep_stage["event_ids"]) == 2
    assert set(plan["pacing_auditions"]) == {
        "relaxation-1-to-10",
        "focus20-countdown-10-to-20",
        "waking-countdown-20-to-1",
    }
    paced = {item["event_id"]: item for item in plan["narration_pacing_plan"]}
    relaxation_counts = [
        unit["text"]
        for item in plan["narration_pacing_plan"]
        if item["narration_key"].startswith("hplus.shared.relaxation.")
        for unit in item["units"]
        if unit["kind"] == "count"
    ]
    assert relaxation_counts == [
        "One.",
        "Two.",
        "Three.",
        "Four.",
        "Five.",
        "Six.",
        "Seven.",
        "Eight.",
        "Nine.",
        "Ten.",
    ]
    torso = next(
        item
        for item in plan["narration_pacing_plan"]
        if item["narration_key"] == "hplus.shared.relaxation.torso"
    )
    sleep_landings = [unit for unit in torso["units"] if unit["text"] == "Sleep."]
    assert [unit["kind"] for unit in sleep_landings] == ["landing"] * 4
    assert [unit["pause_after_s"] for unit in sleep_landings] == [5.0, 5.0, 5.0, 6.0]
    focus20 = paced["focus20-enter.enter"]["units"]
    assert [unit["text"] for unit in focus20[4:]] == [
        "Ten.",
        "Eleven.",
        "Twelve.",
        "Thirteen.",
        "Fourteen.",
        "Fifteen.",
        "Sixteen.",
        "Seventeen.",
        "Eighteen.",
        "Nineteen.",
        "Twenty.",
        "Twenty.",
    ]
    assert all(unit["pause_after_s"] == 5 for unit in focus20[4:-1])
    assert all(unit["rate_scale"] == 0.88 for unit in focus20)
    waking = paced["return.begin"]["units"]
    assert [unit["text"] for unit in waking[4:24]] == [
        "Twenty.",
        "Nineteen.",
        "Eighteen.",
        "Seventeen.",
        "Sixteen.",
        "Fifteen.",
        "Fourteen.",
        "Thirteen.",
        "Twelve.",
        "Eleven.",
        "Ten.",
        "Nine.",
        "Eight.",
        "Seven.",
        "Six.",
        "Five.",
        "Four.",
        "Three.",
        "Two.",
        "One.",
    ]
    assert [unit["pause_after_s"] for unit in waking[4:23]] == [3] * 19
    assert waking[23]["pause_after_s"] == 4
    assert waking[4]["rate_scale"] == 0.9 and waking[23]["rate_scale"] == 0.97
    assert all(
        left["rate_scale"] <= right["rate_scale"]
        for left, right in zip(waking[4:23], waking[5:24], strict=True)
    )


def test_audio_render_defaults_to_complete_session_and_narration_only_is_explicit(
    monkeypatch, capsys
):
    from ocf_tools import complete_session, narration_first

    calls = []
    monkeypatch.setattr(
        complete_session,
        "render_complete_session",
        lambda function_id, **kwargs: (
            calls.append(("session", function_id, kwargs))
            or {"dry_run": True, "session_plan": {"function_id": function_id}}
        ),
    )
    monkeypatch.setattr(
        narration_first,
        "render_narration_first",
        lambda function_id, **kwargs: (
            calls.append(("narration", function_id, kwargs))
            or {"dry_run": True, "plan": {"function_id": function_id}}
        ),
    )
    assert (
        cli.main(
            [
                "audio",
                "render",
                "OCF-SLP-005",
                "--locale",
                "en-US",
                "--voice",
                "OCF-VOICE-0002",
                "--dry-run",
            ]
        )
        == 0
    )
    assert calls[-1][0] == "session"
    assert calls[-1][2]["template"] is None
    assert calls[-1][2]["dsp_profile"] is None
    assert (
        cli.main(
            [
                "audio",
                "render",
                "OCF-SLP-005",
                "--mode",
                "narration-only",
                "--locale",
                "en-US",
                "--voice",
                "OCF-VOICE-0002",
                "--dry-run",
            ]
        )
        == 0
    )
    assert calls[-1][0] == "narration"
    assert "session_plan" in capsys.readouterr().out


def test_background_activity_requires_each_selected_binaural_state(tmp_path):
    import wave

    from ocf_tools.complete_session import _background_activity
    from ocf_tools.utils import OCFError

    path = tmp_path / "background.wav"
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(2)
        writer.setsampwidth(2)
        writer.setframerate(10)
        writer.writeframes(b"\xe8\x03\x84\x03" * 100)
    stages = [
        {
            "id": "focus-eleven",
            "start_seconds": 0,
            "duration_seconds": 10,
            "background_at_midpoint": [{"state": "focus-11", "gain": 1.0}],
        }
    ]
    checks = _background_activity(path, stages, {"focus-11": {"mode": "preset"}})
    assert checks[0]["status"] == "non-silent"
    assert checks[0]["different_channel_frames"] > 0
    with pytest.raises(OCFError, match="were not measured"):
        _background_activity(
            path,
            stages,
            {"focus-10": {"mode": "preset"}, "focus-11": {"mode": "preset"}},
        )

    for frame, message in ((b"\xe8\x03\xe8\x03", "independent L/R"), (b"\0\0\0\0", "is silent")):
        with wave.open(str(path), "wb") as writer:
            writer.setnchannels(2)
            writer.setsampwidth(2)
            writer.setframerate(10)
            writer.writeframes(frame * 100)
        with pytest.raises(OCFError, match=message):
            _background_activity(path, stages, {"focus-11": {"mode": "preset"}})


@pytest.mark.unit
def test_ffprobe_inspection_is_required_and_rejects_failed_or_silent_streams(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from ocf_tools import complete_session
    from ocf_tools.utils import OCFError

    path = tmp_path / "synthetic.wav"
    monkeypatch.setattr(complete_session.shutil, "which", lambda _name: "ffprobe")
    probe = {
        "streams": [
            {
                "codec_type": "audio",
                "codec_name": "pcm_s16le",
                "sample_rate": "8000",
                "channels": 2,
                "channel_layout": "stereo",
                "sample_fmt": "s16",
            }
        ],
        "format": {"duration": "1.25", "bit_rate": "256000"},
    }
    monkeypatch.setattr(
        complete_session,
        "workspace_run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps(probe), stderr=""
        ),
    )
    result = complete_session._probe_audio(path)
    assert result["codec"] == "pcm_s16le"
    assert result["sample_rate"] == 8000 and result["channels"] == 2
    assert result["duration_seconds"] == 1.25 and result["bit_rate"] == 256000

    monkeypatch.setattr(complete_session.shutil, "which", lambda _name: None)
    with pytest.raises(OCFError, match="ffprobe is required"):
        complete_session._probe_audio(path)
    monkeypatch.setattr(complete_session.shutil, "which", lambda _name: "ffprobe")
    monkeypatch.setattr(
        complete_session,
        "workspace_run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="decode failed"),
    )
    with pytest.raises(OCFError, match="ffprobe could not inspect"):
        complete_session._probe_audio(path)
    monkeypatch.setattr(
        complete_session,
        "workspace_run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps({"streams": [{"codec_type": "video"}]}), stderr=""
        ),
    )
    with pytest.raises(OCFError, match="no audio stream"):
        complete_session._probe_audio(path)


@pytest.mark.unit
def test_ffmpeg_decode_verification_has_explicit_success_and_failure_paths(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from ocf_tools import complete_session
    from ocf_tools.utils import OCFError

    path = tmp_path / "synthetic.wav"
    monkeypatch.setattr(complete_session.shutil, "which", lambda _name: None)
    with pytest.raises(OCFError, match="ffmpeg is required"):
        complete_session._verify_decode(path)

    monkeypatch.setattr(complete_session.shutil, "which", lambda _name: "ffmpeg")
    results = iter(
        [
            SimpleNamespace(returncode=0, stderr=""),
            SimpleNamespace(returncode=1, stderr="bad frame"),
        ]
    )
    monkeypatch.setattr(complete_session, "workspace_run", lambda *_a, **_k: next(results))
    complete_session._verify_decode(path)
    with pytest.raises(OCFError, match="audio decode failed"):
        complete_session._verify_decode(path)


@pytest.mark.unit
@pytest.mark.parametrize(
    "case", ["stereo", "mono", "rate", "width", "empty", "identical", "silent"]
)
def test_stereo_measurement_validates_format_frames_and_channels(tmp_path, case):
    import wave

    from ocf_tools import complete_session
    from ocf_tools.utils import OCFError

    path = tmp_path / "synthetic.wav"
    channels = 1 if case == "mono" else 2
    sample_rate = 16000 if case == "rate" else 8000
    sample_width = 1 if case == "width" else 2
    frames = 0 if case == "empty" else 16
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(sample_width)
        writer.setframerate(sample_rate)
        if case == "identical":
            writer.writeframes(
                b"".join((1000).to_bytes(2, "little", signed=True) * 2 for _ in range(frames))
            )
        elif case == "silent":
            writer.writeframes(
                b"".join(
                    (0).to_bytes(2, "little", signed=True)
                    + (1000).to_bytes(2, "little", signed=True)
                    for _ in range(frames)
                )
            )
        elif sample_width == 1:
            writer.writeframes(bytes([128, 129] * frames))
        elif channels == 1:
            writer.writeframes(b"\x01\x00" * frames)
        else:
            writer.writeframes(b"\x01\x00\xff\xff" * frames)

    if case == "stereo":
        metrics = complete_session._stereo_metrics(path, 8000)
        assert metrics["channels"] == 2 and metrics["different_channel_frames"] == 16
        assert metrics["left_peak_int16"] > 0 and metrics["right_peak_int16"] > 0
    else:
        with pytest.raises(OCFError):
            complete_session._stereo_metrics(path, 8000)


@pytest.mark.unit
def test_session_structure_guard_accepts_complete_contract_and_rejects_drift():
    from copy import deepcopy

    from ocf_tools.complete_session import (
        EXPECTED_STATE_TARGETS,
        _verify_session_structure,
    )
    from ocf_tools.utils import OCFError

    stage_semantics = [
        "focus.ten.enter",
        "focus.ten.transition",
        "focus.eleven.transition.open",
        "focus.eleven.transition.close",
        "focus.twenty.enter",
        "focus.twenty.transition.close",
    ]
    doc = {
        "timeline": [
            {
                "id": f"state-{index}",
                "semantic": semantic,
                "dsp": {"state": target},
            }
            for index, (semantic, target) in enumerate(
                zip(stage_semantics, EXPECTED_STATE_TARGETS, strict=True)
            )
        ]
        + [{"id": "return-complete", "semantic": "session.return.complete"}]
        + [{"id": "complete", "semantic": "session.complete"}]
        + [{"id": f"body-{index}", "narration_key": "function.body"} for index in range(4)]
    }
    binding = {"narration_plan": {"sequence": [{"key": "function.body", "role": "function-body"}]}}
    profile = {
        "initial_state": "focus-10",
        "states": {"focus-10": {"mode": "preset"}, "focus-11": {"mode": "preset"}},
    }

    _verify_session_structure(doc, binding, profile)
    incomplete = deepcopy(doc)
    incomplete["timeline"] = [
        event for event in incomplete["timeline"] if event.get("semantic") != "session.complete"
    ]
    with pytest.raises(OCFError, match="missing required semantic stage"):
        _verify_session_structure(incomplete, binding, profile)
    with pytest.raises(OCFError, match="exactly 5 bound function-body passes"):
        _verify_session_structure(doc, binding, profile, body_passes=5)
    changed_state = deepcopy(doc)
    changed_state["timeline"][0]["dsp"]["state"] = "focus-20"
    with pytest.raises(OCFError, match="Focus progression differs"):
        _verify_session_structure(changed_state, binding, profile)
    with pytest.raises(OCFError, match="lacks required session state"):
        _verify_session_structure(
            doc,
            binding,
            {"initial_state": "focus-10", "states": {"focus-10": {"mode": "preset"}}},
        )


@pytest.mark.unit
def test_template_resolution_requires_a_bound_declared_complete_template(monkeypatch):
    from ocf_tools import complete_session, session
    from ocf_tools.utils import OCFError

    binding = {"session_templates": ["template.complete"], "default_session_template": None}
    monkeypatch.setattr(complete_session, "load_layers", lambda _identity: {"bindings": binding})
    monkeypatch.setattr(
        session, "load_template", lambda name: {"id": name, "session_completeness": "complete"}
    )

    with pytest.raises(OCFError, match="no complete default session template"):
        complete_session._resolve_template("OCF-FND-004", None)
    with pytest.raises(OCFError, match="not bound to OCF-FND-004"):
        complete_session._resolve_template("OCF-FND-004", "template.unbound")

    monkeypatch.setattr(
        session,
        "load_template",
        lambda name: {"id": name, "session_completeness": "draft"},
    )
    with pytest.raises(OCFError, match="not declared complete"):
        complete_session._resolve_template("OCF-FND-004", "template.complete")

    monkeypatch.setattr(
        session,
        "load_template",
        lambda name: {"id": name, "session_completeness": "complete"},
    )
    template, returned_binding = complete_session._resolve_template(
        "OCF-FND-004", "template.complete"
    )
    assert template["id"] == "template.complete" and returned_binding is binding


@pytest.mark.unit
def test_slot_key_projection_rejects_duplicate_and_missing_required_roles():
    from ocf_tools.complete_session import _slot_keys
    from ocf_tools.utils import OCFError

    plan = {"narration_plan": {"sequence": [{"role": "function-body", "key": "body"}]}}
    with pytest.raises(OCFError, match="not bound"):
        _slot_keys(plan, {"slots": {"required": ["opener", "function_body"]}})

    duplicate = {
        "narration_plan": {
            "sequence": [
                {"role": "function-body", "key": "body.one"},
                {"role": "function-body", "key": "body.two"},
            ]
        }
    }
    with pytest.raises(OCFError, match="duplicate block role"):
        _slot_keys(duplicate, {"slots": {"required": ["function_body"]}})

    assert _slot_keys(
        {
            "narration_plan": {
                "sequence": [
                    {"role": "opener", "key": "open"},
                    {"role": "function-body", "key": "body"},
                    {"role": "closer", "key": "close"},
                    {"role": "unused", "key": "ignored"},
                ]
            }
        },
        {"slots": {"required": ["opener", "function_body", "closer"]}},
    ) == {"opener": "open", "function_body": "body", "closer": "close"}


@pytest.mark.unit
@pytest.mark.parametrize(
    "case,message",
    [
        ("default", "default background must be active"),
        ("unknown-section", "unknown section"),
        ("default-mode", "default background state must select"),
        ("ignored-event", "ignores state event"),
        ("missing-stage-state", "selects unconfigured DSP state"),
        ("disabled-stage", "expects disabled background state"),
        ("incoming-state", "does not preserve its incoming background state"),
        ("transition-source", "logical DSP transition from"),
        ("transition-target", "transitions to unconfigured stage background"),
    ],
)
def test_stage_background_policy_rejects_inconsistent_transitions(case, message):

    from ocf_tools.complete_session import _verify_stage_background_policy
    from ocf_tools.utils import OCFError

    doc = {
        "sections": [
            {
                "id": "body",
                "timeline": [{"id": "switch", "dsp": {"state": "focus-11"}}],
            }
        ]
    }
    profile = {
        "initial_state": "focus-10",
        "default_background_state": "focus-10",
        "states": {"focus-10": {"mode": "preset"}, "focus-11": {"mode": "preset"}},
        "stage_backgrounds": {"body": ["focus-10", "focus-11"]},
        "ignored_state_events": [],
    }
    if case == "default":
        profile["default_background_state"] = "focus-11"
    elif case == "unknown-section":
        profile["stage_backgrounds"] = {"missing": ["focus-10"]}
    elif case == "default-mode":
        profile["states"]["focus-10"]["mode"] = "off"
    elif case == "ignored-event":
        profile["ignored_state_events"] = ["absent"]
    elif case == "missing-stage-state":
        profile["stage_backgrounds"]["body"] = ["unconfigured"]
    elif case == "disabled-stage":
        profile["states"]["focus-11"]["mode"] = "off"
    elif case == "incoming-state":
        profile["stage_backgrounds"]["body"] = ["focus-11"]
    elif case == "transition-source":
        doc["sections"][0]["timeline"][0]["dsp"]["state"] = {
            "from": "focus-11",
            "to": "focus-11",
        }
    elif case == "transition-target":
        doc["sections"][0]["timeline"][0]["dsp"]["state"] = "unconfigured"

    with pytest.raises(OCFError, match=message):
        _verify_stage_background_policy(doc, profile)


@pytest.mark.unit
def test_stage_background_policy_accepts_explicit_state_continuity():
    from ocf_tools.complete_session import _verify_stage_background_policy

    _verify_stage_background_policy(
        {
            "sections": [
                {
                    "id": "body",
                    "timeline": [{"id": "switch", "dsp": {"state": "focus-11"}}],
                }
            ]
        },
        {
            "initial_state": "focus-10",
            "default_background_state": "focus-10",
            "states": {"focus-10": {"mode": "preset"}, "focus-11": {"mode": "preset"}},
            "stage_backgrounds": {"body": ["focus-10", "focus-11"]},
            "ignored_state_events": [],
        },
    )


@pytest.mark.integration
@pytest.mark.audio_integration
def test_optional_complete_farfield_piper_session():
    import os
    import shutil

    if os.environ.get("OCF_RUN_COMPLETE_SESSION_SMOKE") != "1":
        pytest.skip("set OCF_RUN_COMPLETE_SESSION_SMOKE=1 to run complete Piper/Farfield rendering")
    if not all(shutil.which(name) for name in ("piper", "farfield", "ffmpeg", "ffprobe")):
        pytest.skip("Piper, Farfield, ffmpeg, and ffprobe are required for complete-session smoke")
    from ocf_tools.complete_session import _stereo_metrics, _verify_decode, render_complete_session
    from ocf_tools.paths import AUDIO_RENDERED_DIR, unique_run_id

    output = os.environ.get("OCF_COMPLETE_SESSION_OUTPUT")
    if output:
        output_directory = Path(output).expanduser().resolve()
        manifest = json.loads(
            (output_directory / "session-report.json").read_text(encoding="utf-8")
        )
    else:
        result = render_complete_session(
            "OCF-SLP-005",
            locale="en-US",
            voice="OCF-VOICE-0002",
            pacing="sleep",
            output=AUDIO_RENDERED_DIR
            / "integration"
            / unique_run_id("sleep-easy-complete-session"),
        )
        output_directory = Path(result["output_directory"])
        manifest = result["manifest"]
    wav = output_directory / manifest["artifacts"]["wav"]["path"]
    _verify_decode(wav)
    metrics = _stereo_metrics(wav, sample_rate=44100)
    assert manifest["template"]["id"] == "OCF-TPL-SESSION-HPLUS-LOCKED-004"
    assert metrics["channels"] == 2 and metrics["clipped_sample_count"] == 0
    checks = manifest["background_activity_checks"]
    assert {layer["state"] for check in checks for layer in check["layers"]} == {
        "focus-10",
        "focus-11",
    }
    assert len(manifest["state_transitions"]) == 2
    assert {row["to"] for row in manifest["state_transitions"]} == {
        "focus-10",
        "focus-11",
    }
    assert {row["checkpoint"] for row in manifest["representative_audio_analysis"]} >= {
        "opening-first-10-seconds",
        "sleep-function-body-midpoint",
        "function-closer-midpoint",
        "ending-fade-end",
    }
    assert set(manifest["pacing_auditions"]) == {
        "relaxation-1-to-10",
        "focus20-countdown-10-to-20",
        "waking-countdown-20-to-1",
    }
    for audition in manifest["pacing_auditions"].values():
        wav_artifact = audition["wav"]
        report_artifact = audition["timing_report"]
        assert (output_directory / wav_artifact["path"]).stat().st_size == wav_artifact[
            "size_bytes"
        ]
        timing = json.loads((output_directory / report_artifact["path"]).read_text())
        assert timing["total_duration_seconds"] == audition["duration_seconds"]
        assert timing["segments"]
