from __future__ import annotations

import io
import math
import os
import shutil
import wave
from array import array
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from ocf_tools import narration_first as nf
from ocf_tools.indexes import load_function_by_id, load_voice_profiles
from ocf_tools.locale import LocaleCatalog
from ocf_tools.timing import schedule_timeline
from ocf_tools.utils import OCFError


def _stub_voice(monkeypatch):
    profile = {
        "id": "OCF-VOICE-TEST",
        "slug": "test-piper",
        "name": "Test Piper",
        "backend": "piper",
        "language": "en_US",
        "words_per_min": None,
        "piper_model": "/not-used-in-fixture.onnx",
        "piper_length_scale": None,
    }
    resolved = {
        "profile_id": profile["id"],
        "name": "piper",
        "language": "en_US",
        "wpm": None,
        "piper_length_scale": None,
        "piper_sentence_silence_s": None,
    }
    monkeypatch.setattr(nf, "_voice_profile", lambda *_args: (profile, resolved))


def test_sleep_easy_plan_preserves_canonical_resources_and_four_pass_order(monkeypatch):
    _stub_voice(monkeypatch)
    plan = nf.plan_narration("OCF-SLP-005", locale="en-US", voice="OCF-VOICE-TEST", pacing="sleep")
    again = nf.plan_narration("OCF-SLP-005", locale="en-US", voice="OCF-VOICE-TEST", pacing="sleep")
    assert plan == again
    assert plan["function_id"] == "OCF-SLP-005"
    assert plan["approval_state"] == {
        "script_status": "approved",
        "function_review_status": "required",
        "resource_statuses": {
            "hplus.function.ocf-slp-005.opener": "reviewed",
            "hplus.function.ocf-slp-005.function-body": "reviewed",
            "hplus.function.ocf-slp-005.closer": "reviewed",
        },
        "tts_ready": True,
        "release_ready": False,
        "release_note": "Function-content human review remains required; this audition does not approve release.",
    }
    assert len(plan["segments"]) == 35
    body = [segment for segment in plan["segments"] if segment["role"] == "function-body"]
    assert [segment["playback"] for segment in body] == [n for n in range(1, 5) for _ in range(8)]
    catalog = LocaleCatalog()
    for resource in plan["narration_resources"]:
        entry, _ = catalog.resource(resource["key"], "en-US", domain="narration", fallback=False)
        for playback in range(1, int(resource["repetitions"]) + 1):
            pieces = [
                segment["canonical_text"]
                for segment in plan["segments"]
                if segment["resource_key"] == resource["key"] and segment["playback"] == playback
            ]
            assert "\n\n".join(pieces) == entry.text
    assert any('"Plus Sleep Easy."' in segment["canonical_text"] for segment in body)
    assert not any("Plus Quiet Sleep" in segment["canonical_text"] for segment in body)
    assert all("PLUS-SLEEP EASY" not in segment["spoken_text"] for segment in plan["segments"])
    assert plan["pacing"]["id"] == "sleep"
    assert plan["estimated_duration_seconds"] > plan["pacing"]["ending_silence_s"]


def test_same_language_region_records_resource_fallback(monkeypatch):
    _stub_voice(monkeypatch)
    plan = nf.plan_narration("OCF-SLP-005", locale="en-GB", voice="OCF-VOICE-TEST", pacing="normal")
    assert plan["requested_locale"] == "en-GB"
    assert {item["resolved_locale"] for item in plan["narration_resources"]} == {"en-US"}
    assert all(item["fallback"] is True for item in plan["narration_resources"])


def test_missing_locale_resource_and_invalid_locale_fail_before_render(monkeypatch):
    _stub_voice(monkeypatch)
    with pytest.raises(OCFError, match="unavailable|missing|does not exist|not found"):
        nf.plan_narration("OCF-SLP-005", locale="es", voice="OCF-VOICE-TEST")
    with pytest.raises(OCFError, match="invalid locale"):
        nf.plan_narration("OCF-SLP-005", locale="bad_tag", voice="OCF-VOICE-TEST")


def test_draft_function_script_blocks_tts_without_changing_approval(monkeypatch):
    record = load_function_by_id("OCF-SLP-005")
    changed = dict(record.data)
    changed["audio"] = {**changed["audio"], "script_status": "draft"}
    monkeypatch.setattr(
        nf, "load_function_by_id", lambda _function_id: SimpleNamespace(id=record.id, data=changed)
    )
    with pytest.raises(OCFError, match="not approved for TTS"):
        nf.plan_narration("OCF-SLP-005", locale="en-US", voice="test")
    assert record.data["audio"]["script_status"] == "approved"


def test_plan_requires_explicit_binding_and_reviewed_resources(monkeypatch):
    _stub_voice(monkeypatch)
    original_layers = nf.load_layers
    monkeypatch.setattr(
        nf, "load_layers", lambda _function_id: {"specifications": {}, "bindings": {}}
    )
    # Function YAML is authoritative even without the compatibility layer copy.
    assert nf.plan_narration("OCF-SLP-005", locale="en-US", voice="test")["segments"]
    original_loader = nf.load_function_by_id
    record = original_loader("OCF-SLP-005")
    record.data.pop("narration")
    monkeypatch.setattr(nf, "load_function_by_id", lambda _id: record)
    with pytest.raises(OCFError, match="no explicit.*narration_plan"):
        nf.plan_narration("OCF-SLP-005", locale="en-US", voice="test")
    monkeypatch.setattr(nf, "load_function_by_id", original_loader)

    original_resource = LocaleCatalog.resource

    def draft_resource(self, key, *args, **kwargs):
        entry, resolution = original_resource(self, key, *args, **kwargs)
        if key.endswith(".opener"):
            entry = replace(entry, status="draft")
        return entry, resolution

    monkeypatch.setattr(LocaleCatalog, "resource", draft_resource)
    monkeypatch.setattr(nf, "load_layers", original_layers)
    with pytest.raises(OCFError, match="not TTS-ready"):
        nf.plan_narration("OCF-SLP-005", locale="en-US", voice="test")


def test_dynamic_document_anchors_every_segment_to_measured_speech_end(monkeypatch):
    _stub_voice(monkeypatch)
    plan = nf.plan_narration("OCF-SLP-005", locale="en-US", voice="test", pacing="relaxed")
    doc = nf._dynamic_document(plan)
    events = doc["timeline"]
    from ocf_tools.transcript import parse_timestamp

    assert parse_timestamp(events[0]["at"]) == plan["pacing"]["leading_silence_s"]
    assert len(events) == len(plan["segments"])
    assert events[0]["timing"]["anchor"] == "start"
    assert all(event.get("timing", {}).get("anchor") == "speech-end" for event in events[1:])
    assert all("at" not in event for event in events[1:])
    durations = {event["id"]: 1.0 + index / 100 for index, event in enumerate(events)}
    scheduled = {item["id"]: item for item in schedule_timeline(doc, durations)}
    for previous, current in zip(events, events[1:], strict=False):
        expected = (
            scheduled[previous["id"]]["at"]
            + durations[previous["id"]]
            + previous["timing"]["pause_after"]
        )
        assert scheduled[current["id"]]["at"] == pytest.approx(expected)


def test_tts_headroom_precedes_pcm_assembly_and_keeps_valid_wav():
    source = io.BytesIO()
    with wave.open(source, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(array("h", [32767, -32768, 16384]).tobytes())
    adjusted, rail_count = nf._apply_tts_headroom(source.getvalue(), -3.0)
    assert rail_count == 2
    with wave.open(io.BytesIO(adjusted), "rb") as reader:
        assert reader.getframerate() == 8000
        assert reader.getnframes() == 3
        samples = array("h")
        samples.frombytes(reader.readframes(3))
    assert max(map(abs, samples)) < 32767


def _fixture_renderer(monkeypatch, rate: int = 8000):
    from ocf_tools import voice

    calls: list[dict] = []

    def render(doc, out_path, *, backend, sample_rate, **kwargs):
        events = doc["timeline"]
        durations = {event["id"]: 0.12 + index * 0.001 for index, event in enumerate(events)}
        scheduled_rows = schedule_timeline(doc, durations)
        scheduled = {row["id"]: row for row in scheduled_rows}
        frames = math.ceil(max(row["end"] for row in scheduled_rows) * sample_rate) + sample_rate
        samples = array("h", [0]) * frames
        cue_stats = []
        event_timing = []
        for event in events:
            row = scheduled[event["id"]]
            start = round(row["at"] * sample_rate)
            count = round(durations[event["id"]] * sample_rate)
            for offset in range(start, min(start + count, frames)):
                samples[offset] = 1800
            cue_stats.append(
                {
                    "id": event["id"],
                    "source_ids": [event["id"]],
                    "at": row["at"],
                    "text": event["text"],
                    "duration": durations[event["id"]],
                    "samples": count,
                }
            )
            event_timing.append({"id": event["id"], "at": row["at"], "end": row["end"]})
        with wave.open(str(out_path), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(sample_rate)
            writer.writeframes(samples.tobytes())
        calls.append({"doc": doc, "backend": backend, "sample_rate": sample_rate})
        return {
            "backend": backend["backend"],
            "profile_id": backend["id"],
            "voice_options": {"piper_length_scale": backend["piper_length_scale"]},
            "sample_rate": sample_rate,
            "channels": 1,
            "duration": round(frames / sample_rate, 3),
            "cue_stats": cue_stats,
            "event_timing": event_timing,
            "cues": len(cue_stats),
            "timing_mode": "explicit-at-timestamps",
        }

    monkeypatch.setattr(voice, "render_narration", render)
    monkeypatch.setattr(
        nf,
        "_voice_profile",
        lambda *_args: (
            {
                "id": "OCF-VOICE-TEST",
                "slug": "test-piper",
                "name": "Test Piper",
                "backend": "piper",
                "language": "en_US",
                "words_per_min": None,
                "piper_model": "/fixture/model.onnx",
                "piper_length_scale": None,
            },
            {"name": "piper", "profile_id": "OCF-VOICE-TEST", "language": "en_US"},
        ),
    )
    return calls


def test_narration_first_audition_writes_verified_dynamic_fixture_and_no_overwrite(
    tmp_path, monkeypatch
):
    calls = _fixture_renderer(monkeypatch)
    target = tmp_path / "sleep-easy-audition"
    result = nf.render_narration_first(
        "OCF-SLP-005",
        locale="en-US",
        voice="OCF-VOICE-TEST",
        pacing="sleep",
        output=target,
        sample_rate=8000,
        created_at=None,
    )
    assert result["output_directory"] == str(target.resolve())
    manifest = result["manifest"]
    assert manifest["approval_state"]["tts_ready"] is True
    assert manifest["release_ready"] is False
    assert manifest["measurements"]["spoken_segment_count"] == 35
    assert manifest["measurements"]["clipped_sample_count"] == 0
    audio_artifact = target / manifest["artifacts"]["wav"]["path"]
    transcript = target / manifest["artifacts"]["transcript"]["path"]
    assert audio_artifact.is_file() and audio_artifact.stat().st_size > 0
    assert transcript.read_text(encoding="utf-8").endswith("\n")
    assert sha256_file(audio_artifact) == manifest["artifacts"]["wav"]["sha256"]
    assert calls[0]["backend"]["piper_length_scale"] == pytest.approx(1.08)
    with pytest.raises(OCFError, match="refusing to overwrite"):
        nf.render_narration_first(
            "OCF-SLP-005", locale="en-US", voice="OCF-VOICE-TEST", pacing="sleep", output=target
        )


def test_audio_render_cli_routes_function_locale_voice_and_sleep_pacing(monkeypatch, capsys):
    from ocf_tools import cli

    calls = []
    monkeypatch.setattr(
        nf,
        "render_narration_first",
        lambda function_id, **kwargs: (
            calls.append((function_id, kwargs))
            or {"dry_run": True, "plan": {"function_id": function_id}}
        ),
    )
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
                "--pacing",
                "sleep",
                "--dry-run",
            ]
        )
        == 0
    )
    assert calls == [
        (
            "OCF-SLP-005",
            {
                "locale": "en-US",
                "voice": "OCF-VOICE-0002",
                "pacing": "sleep",
                "output": None,
                "dry_run": True,
                "sample_rate": 44100,
            },
        )
    ]
    assert '"function_id": "OCF-SLP-005"' in capsys.readouterr().out


def sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.integration
@pytest.mark.audio_integration
def test_optional_real_piper_sleep_easy_smoke(tmp_path):
    if os.environ.get("OCF_RUN_PIPER_SMOKE") != "1":
        pytest.skip("set OCF_RUN_PIPER_SMOKE=1 to run the full local Piper Sleep Easy synthesis")
    profile = next(
        profile for profile in load_voice_profiles() if profile.get("id") == "OCF-VOICE-0002"
    )
    model = Path(os.path.expanduser(os.path.expandvars(profile["piper_model"])))
    if shutil.which("piper") is None or not model.is_file():
        pytest.skip("configured Piper executable/model are not available")
    result = nf.render_narration_first(
        "OCF-SLP-005",
        locale="en-US",
        voice="OCF-VOICE-0002",
        pacing="sleep",
        output=tmp_path / "sleep-easy-real-piper",
    )
    wav = Path(result["output_directory"]) / result["manifest"]["artifacts"]["wav"]["path"]
    with wave.open(str(wav), "rb") as reader:
        assert reader.getnframes() > reader.getframerate() * 60
