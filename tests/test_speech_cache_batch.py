"""Shared synthesis cache policy, single-flight and immutable refresh history."""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event, Lock

import pytest
from ocf_tools import speech_cache


def pcm(value: int) -> bytes:
    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24000)
        output.writeframes(value.to_bytes(2, "little", signed=True) * 32)
    return stream.getvalue()


@pytest.fixture
def cache_root(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(speech_cache, "voice_identity", lambda spec: spec)
    return tmp_path / "work" / "cache" / "tts"


def test_auto_reuses_refresh_generates_once_per_scope_and_preserves_history(cache_root):
    calls = []

    def synthesize():
        calls.append(len(calls) + 1)
        return pcm(calls[-1] * 100)

    with speech_cache.policy("auto", function_id="OCF-A") as (stats, events, _scope):
        first = speech_cache.cached_cue(
            {"profile_id": "voice-a"}, "Shared exact words.", synthesize
        )
        assert (
            speech_cache.cached_cue({"profile_id": "voice-a"}, "Shared exact words.", synthesize)
            == first
        )
    assert len(calls) == 1 and stats["miss"] == 1 and stats["hit"] == 1
    assert events[0]["action"] == "miss" and events[1]["action"] == "hit"
    first_sha = events[0]["audio_sha256"]

    with speech_cache.policy("refresh", refresh_scope="batch-one") as (stats, events, scope):
        assert scope == "batch-one"
        refreshed = speech_cache.cached_cue(
            {"profile_id": "voice-a"}, "Shared exact words.", synthesize
        )
        assert (
            speech_cache.cached_cue({"profile_id": "voice-a"}, "Shared exact words.", synthesize)
            == refreshed
        )
    key = events[0]["cache_key"]
    root = cache_root / key
    assert len(calls) == 2 and stats["refreshed"] == 1 and stats["hit"] == 1
    history = list((root / "history").glob("*.wav"))
    assert len(history) == 1 and hashlib.sha256(history[0].read_bytes()).hexdigest() == first_sha
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["refresh_scope"] == "batch-one"
    assert manifest["sample_rate"] == 24000 and manifest["channels"] == 1
    if os.name == "posix":
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert stat.S_IMODE((root / "speech.wav").stat().st_mode) == 0o600
        assert stat.S_IMODE((root / "manifest.json").stat().st_mode) == 0o600

    with speech_cache.policy("off") as (stats, _events, _scope):
        speech_cache.cached_cue({"profile_id": "voice-a"}, "Shared exact words.", synthesize)
        speech_cache.cached_cue({"profile_id": "voice-a"}, "Shared exact words.", synthesize)
    assert stats["bypassed"] == 2 and len(calls) == 4
    assert len(list((root / "history").glob("*.wav"))) == 1


def test_concurrent_identical_requests_are_single_flight(cache_root):
    ready = Barrier(2)
    started = Event()
    release = Event()
    call_lock = Lock()
    calls = []

    def render():
        with call_lock:
            calls.append(True)
        started.set()
        assert release.wait(5)
        return pcm(700)

    def request():
        ready.wait()
        with speech_cache.policy("auto"):
            return speech_cache.cached_cue({"profile_id": "same"}, "One shared unit.", render)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(request)
        second = pool.submit(request)
        assert started.wait(5)
        release.set()
        assert first.result() == second.result() == pcm(700)
    assert len(calls) == 1


def test_interrupted_publish_is_not_reused_and_retry_recovers(cache_root, monkeypatch):
    from ocf_tools import speech_cache

    real_replace = speech_cache.os.replace
    failed = {"once": False}

    def interrupt_manifest(source, destination):
        if Path(destination).name == "manifest.json" and not failed["once"]:
            failed["once"] = True
            raise OSError("simulated interruption before cache pointer commit")
        return real_replace(source, destination)

    monkeypatch.setattr(speech_cache.os, "replace", interrupt_manifest)
    calls = []

    def synthesize():
        calls.append(True)
        return pcm(500)

    with speech_cache.policy("auto") as (first_stats, _events, _scope):
        first = speech_cache.cached_cue({"profile_id": "interrupted"}, "Retry this.", synthesize)
    assert first == pcm(500) and first_stats["bypassed"] == 1
    monkeypatch.setattr(speech_cache.os, "replace", real_replace)
    with speech_cache.policy("auto") as (retry_stats, _events, _scope):
        second = speech_cache.cached_cue({"profile_id": "interrupted"}, "Retry this.", synthesize)
    assert second == first and len(calls) == 2 and retry_stats["miss"] == 1
    root = next(cache_root.iterdir())
    assert speech_cache._read_verified(root, root.name) is not None


@pytest.mark.parametrize("mode", ["auto", "off", "refresh"])
def test_render_cli_accepts_explicit_speech_cache_mode(mode):
    from ocf_tools.cli import _build_parser

    parser = _build_parser()
    many = parser.parse_args(
        ["audio", "render-many", "OCF-SEN-001", "--voice", "OCF-VOICE-9003", "--speech-cache", mode]
    )
    session = parser.parse_args(
        ["audio", "render", "OCF-SEN-001", "--voice", "OCF-VOICE-9003", "--speech-cache", mode]
    )
    assert many.speech_cache == session.speech_cache == mode


def test_representative_session_plan_identifies_shared_resources_and_four_body_passes(monkeypatch):
    from ocf_tools import bulk_render
    from ocf_tools.session_plans import source_plan

    monkeypatch.setattr(bulk_render, "voice_identity", lambda _spec: {"fixture": "piper"})

    plans = []
    for function_id in ("OCF-SEN-001", "OCF-SEN-002", "OCF-BOD-006"):
        _plan, shared, expanded = source_plan(function_id, "en-US")
        plans.append((function_id, shared, expanded))
    summary = bulk_render._candidate_speech_plan(plans)
    compatible_summary = bulk_render._candidate_speech_plan(
        plans, {"name": "piper", "language": "en_US", "binary": "piper", "wpm": None}
    )
    shared_keys = {
        item["resource_key"] for item in summary["template_resources_shared_across_functions"]
    }
    assert "hplus.shared.body-comfort" in shared_keys
    assert "hplus.shared.focus10.count" in shared_keys
    assert summary["candidate_four_pass_body_units"] > 0
    assert summary["candidate_unique_spoken_units"] > 0
    assert compatible_summary["compatible_unit_fingerprints"]


def test_four_identical_body_passes_synthesize_once_and_keep_reinforcement_outside_cache(
    cache_root,
):
    calls = []

    def synthesize():
        calls.append(True)
        return pcm(900)

    with speech_cache.policy("auto", function_id="OCF-BOD-006") as (stats, events, _scope):
        passes = [
            speech_cache.cached_cue(
                {"profile_id": "piper-fixture"}, "Exact function-body text.", synthesize
            )
            for _ in range(4)
        ]
    assert calls == [True]
    assert passes == [passes[0]] * 4
    assert stats["hit"] == 3 and stats["miss"] == 1
    assert len({event["audio_sha256"] for event in events}) == 1


@pytest.mark.skipif(
    not os.environ.get("OCF_CHATTERBOX_INTEGRATION_VOICE_ID"),
    reason="needs an explicitly supplied local synthetic/authorized Chatterbox voice pack",
)
def test_opt_in_representative_shared_narration_cache_benchmark(monkeypatch):
    """Real speech cache comparison on three sessions, without background mixing."""
    from ocf_tools.complete_session import build_complete_session_plan
    from ocf_tools.locale import LocaleCatalog, iter_events, resolve_document
    from ocf_tools.narration_pacing import event_pacing, split_speech_units
    from ocf_tools.paths import REPO_ROOT, work_path
    from ocf_tools.speech_cache import policy
    from ocf_tools.voice import (
        _paced_voice_spec,
        _pronunciation_hints,
        apply_pronunciation,
        render_cue_wav,
        resolve_backend,
    )
    from ocf_tools.voice_packs import inspect_pack, persistent_worker

    monkeypatch.setenv("OCF_WORK_DIR", str(REPO_ROOT / ".ocf-work"))
    voice_id = os.environ["OCF_CHATTERBOX_INTEGRATION_VOICE_ID"]
    profile = inspect_pack(voice_id)["profile"]
    locale = "en-US"
    voice = resolve_backend(voice_id, locale=locale, catalog=LocaleCatalog())
    selected_shared = {
        "hplus.shared.body-comfort",
        "hplus.shared.focus10.count",
        "hplus.shared.focus11.open.prepare",
    }
    requests = []
    for function_id in ("OCF-SEN-001", "OCF-SEN-002", "OCF-BOD-006"):
        plan = build_complete_session_plan(
            function_id, locale=locale, voice=voice_id, pacing="sleep"
        )
        doc = resolve_document(plan["template_plan"], locale, catalog=LocaleCatalog(), strict=True)
        hints = _pronunciation_hints(doc, locale, LocaleCatalog(), voice["name"])
        body_pass = 0
        for event in iter_events(doc):
            is_body = event.get("slot_ref") == "function_body"
            if not is_body and event.get("narration_key") not in selected_shared:
                continue
            text = str(event.get("text") or "").strip()
            if not text:
                continue
            units = split_speech_units(text)
            pacing = event_pacing(doc, event, len(units))
            rate_scales = pacing["unit_rate_scales"] if pacing else [1.0] * len(units)
            if is_body:
                body_pass += 1
                units, rate_scales = units[:1], rate_scales[:1]
            for unit, rate_scale in zip(units, rate_scales, strict=True):
                event_hints = {
                    **hints.get(event["id"], {}),
                    **(voice.get("pronunciation") or {}),
                }
                spoken = (
                    apply_pronunciation(unit["text"], event_hints, voice["name"])
                    if event_hints
                    else unit["text"]
                )
                effective, _ = _paced_voice_spec(voice, rate_scale)
                requests.append((function_id, effective, spoken, is_body))
        assert body_pass == 4

    assert len(requests) >= 20  # shared prep/count/open plus four body playback passes per function
    body_request_counts = {}
    for function_id, _spec, spoken, is_body in requests:
        if is_body:
            key = (function_id, hashlib.sha256(spoken.encode("utf-8")).hexdigest())
            body_request_counts[key] = body_request_counts.get(key, 0) + 1

    def execute(mode: str, *, repeat_first_uncached=False):
        started = time.perf_counter()
        events = []
        outputs = []
        scope = f"benchmark-{mode}" if mode == "refresh" else None
        with persistent_worker():
            if repeat_first_uncached:
                fid, spec, text, _ = requests[0]
                with policy("off", function_id=fid) as (_stats, rows, _scope):
                    for _ in range(2):
                        raw = render_cue_wav(spec, text)
                        rate, samples = __import__(
                            "ocf_tools.voice", fromlist=["_read_pcm_from_bytes"]
                        )._read_pcm_from_bytes(raw)
                        assert rate > 0 and samples
                        outputs.append(hashlib.sha256(raw).hexdigest())
                    events.extend(rows)
            offset = 1 if repeat_first_uncached else 0
            index = offset
            while index < len(requests):
                fid = requests[index][0]
                group = []
                while index < len(requests) and requests[index][0] == fid:
                    group.append(requests[index])
                    index += 1
                with policy(mode, refresh_scope=scope, function_id=fid) as (_stats, rows, _scope):
                    for _owner, spec, text, _body in group:
                        raw = render_cue_wav(spec, text)
                        rate, samples = __import__(
                            "ocf_tools.voice", fromlist=["_read_pcm_from_bytes"]
                        )._read_pcm_from_bytes(raw)
                        assert rate > 0 and samples
                        outputs.append(hashlib.sha256(raw).hexdigest())
                    events.extend(rows)
        return {
            "elapsed_seconds": time.perf_counter() - started,
            "outputs": outputs,
            "events": events,
        }

    uncached = execute("off", repeat_first_uncached=True)
    cold = execute("refresh")
    warm = execute("auto")
    uncached_events = uncached["events"]
    cold_events = cold["events"]
    warm_events = warm["events"]
    assert len(uncached["outputs"]) == len(requests) + 1
    assert all(event["action"] == "bypassed" for event in uncached_events)
    assert len(cold["outputs"]) == len(requests)
    assert len(warm["outputs"]) == len(requests)
    assert all(event["action"] == "hit" for event in warm_events)
    for (function_id, text_hash), count in body_request_counts.items():
        body_rows = [
            event
            for event in cold_events
            if event.get("function_id") == function_id and event["text_sha256"] == text_hash
        ]
        assert len(body_rows) == count
        assert sum(event["action"] in {"refreshed", "miss"} for event in body_rows) == 1
        assert sum(event["action"] == "hit" for event in body_rows) == count - 1
    cold_audio = {
        event["cache_key"]: event["audio_sha256"] for event in cold_events if event.get("cache_key")
    }
    assert all(
        cold_audio.get(event.get("cache_key")) == event.get("audio_sha256") for event in warm_events
    )
    unique_cold = {
        event["cache_key"]
        for event in cold_events
        if event.get("cache_key") and event["action"] == "refreshed"
    }
    assert len(unique_cold) < len(requests)
    assert uncached_events[0]["inference"]["model_reused"] is False
    assert uncached_events[1]["inference"]["model_reused"] is True

    shared_owners = {}
    for event in cold_events:
        if event.get("cache_key"):
            shared_owners.setdefault(event["cache_key"], set()).add(event.get("function_id"))
    body_events = [
        event
        for event in cold_events
        if event.get("function_id")
        and event.get("text_sha256")
        in {hashlib.sha256(request[2].encode()).hexdigest() for request in requests if request[3]}
    ]
    report = {
        "schema_version": "1.0",
        "voice_id": voice_id,
        "reference_sha256": profile["reference_audio"]["sha256"],
        "model_identity": voice["model_identity"],
        "functions": ["OCF-SEN-001", "OCF-SEN-002", "OCF-BOD-006"],
        "requested_units": len(requests),
        "unique_cold_units": len(unique_cold),
        "shared_units_across_functions": sum(len(owners) > 1 for owners in shared_owners.values()),
        "four_pass_body_requested_units": sum(request[3] for request in requests),
        "four_pass_body_events": len(body_events),
        "uncached": {
            "elapsed_seconds": uncached["elapsed_seconds"],
            "calls": len(uncached["outputs"]),
        },
        "shared_cache_cold": {
            "elapsed_seconds": cold["elapsed_seconds"],
            "requests": len(cold_events),
            "generated_unique": len(unique_cold),
            "cache_hits": sum(event["action"] == "hit" for event in cold_events),
        },
        "warm_cache": {
            "elapsed_seconds": warm["elapsed_seconds"],
            "cache_hits": sum(event["action"] == "hit" for event in warm_events),
            "reused_clip_hashes": sorted(set(warm["outputs"])),
        },
        "speedup_vs_uncached": {
            "shared_cache_cold": round(uncached["elapsed_seconds"] / cold["elapsed_seconds"], 3),
            "warm_cache": round(uncached["elapsed_seconds"] / warm["elapsed_seconds"], 3),
        },
        "warm_worker": {
            "first_generation_seconds": uncached_events[0]["inference"].get("generation_seconds"),
            "second_generation_seconds": uncached_events[1]["inference"].get("generation_seconds"),
            "second_model_reused": uncached_events[1]["inference"].get("model_reused"),
            "second_conditioning_reused": uncached_events[1]["inference"].get(
                "speaker_conditioning_reused"
            ),
        },
        "complete_mix_rendered": False,
        "limitation": "HPLUS Focus 10 complete-session mix requires Farfield, unavailable locally; this benchmark covers actual measured TTS unit synthesis only.",
    }
    report_path = work_path("logs", "voice-cache-benchmark", voice_id, f"{int(time.time())}.json")
    report_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    report_path.parent.chmod(0o700)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_path.chmod(0o600)
    assert report_path.is_relative_to(work_path("logs"))
