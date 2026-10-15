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
        "id": "OCF-TPL-SESSION-HPLUS-STANDARD-001",
        "version": "1.0.0",
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
    assert manifest["template"]["id"] == "OCF-TPL-SESSION-HPLUS-STANDARD-001"
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
