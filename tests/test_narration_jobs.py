"""Narration MCP adapters reuse source resolution and the persistent executor."""

import json
import time
import wave

import pytest
from ocf_tools import agent_api as api
from ocf_tools import complete_session, narration_cli
from ocf_tools import dev_jobs as jobs
from ocf_tools.locale import iter_events
from ocf_tools.narration_sources import text_fingerprint
from ocf_tools.utils import OCFError, sha256_of_file

FUNCTION = "OCF-FND-002"


def wav(path, value=1000, rate=8000):
    with wave.open(str(path), "wb") as writer:
        writer.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        writer.writeframes(value.to_bytes(2, "little", signed=True) * (rate // 10))


@pytest.fixture
def sources(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    doc = narration_cli.session_document(FUNCTION)
    for i in range(2):
        wav(tmp_path / f"take{i}.wav", value=1000 + i)
    data = {
        "schema_version": "2.0",
        "id": "test-sources",
        "mode": "recording",
        "locale": "en-US",
        "recordings": {},
    }
    for i, event in enumerate(iter_events(doc)):
        if event.get("text", "").strip():
            name = f"take{i % 2}.wav"
            data["recordings"][f"event-{i}"] = {
                "file": name,
                "sha256": sha256_of_file(tmp_path / name),
                "text_sha256": text_fingerprint(event["text"]),
                "locale": "en-US",
                "speaker": "synthetic-fixture",
                "version": "1",
                "target": {"event_id": event["id"]},
            }
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def wait(job_id):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        state = jobs.status(job_id)
        if state["state"] in jobs.TERMINAL:
            return state
        time.sleep(0.1)
    jobs.cancel(job_id)
    pytest.fail("narration job exceeded the test deadline")


def test_inspect_source_coverage_parity_pagination_and_no_writes(sources):
    path, _ = sources
    original = {p.name: sha256_of_file(p) for p in path.parent.iterdir()}
    coverage = narration_cli.coverage(FUNCTION, sources=path)
    first = api.dispatch(
        "ocf_inspect_narration_sources",
        {
            "function_id": FUNCTION,
            "manifest": path.name,
            "limit": 2,
        },
    )
    second = api.inspect_narration_sources(FUNCTION, path.name, offset=2, limit=2)
    assert first["events"]["total"] == len(coverage["events"])
    assert first["events"]["items"] == [api.compact_source_event(r) for r in coverage["events"][:2]]
    assert first["events"]["next_offset"] == 2
    assert second["events"]["items"][0]["event_id"] == coverage["events"][2]["event_id"]
    assert '"text"' not in json.dumps(first)
    assert len(json.dumps(first)) < 4000
    assert original == {p.name: sha256_of_file(p) for p in path.parent.iterdir()}
    assert api.inspect_narration_sources(FUNCTION, path.name, limit=51)["status"] == "failed"
    assert api.inspect_narration_sources(FUNCTION, path.name, locale="es")["status"] == "failed"


@pytest.mark.unit
@pytest.mark.parametrize(
    "reference", ["../take.wav", "/etc/passwd", "C:/take.wav", "C:\\take.wav", "\\\\host\\take.wav"]
)
def test_private_manifest_references_are_sandboxed(monkeypatch, tmp_path, reference):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    for dataset, data in (
        (False, {"recordings": {"take": {"file": reference}}}),
        (False, {"session_stem": {"file": reference}}),
        (True, {"records": [{"audio": reference}]}),
        (True, {"consent_record": reference}),
    ):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(data))
        with pytest.raises(OCFError):
            api.workspace_manifest(path.name, dataset=dataset)


@pytest.mark.unit
def test_manifest_limits_malformed_data_and_symlink_escape(monkeypatch, tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("OCF_WORK_DIR", str(root))
    path = root / "sources.json"
    path.write_bytes(b" " * (2 * 1024**2 + 1))
    with pytest.raises(OCFError, match="2 MiB"):
        api.workspace_manifest(path.name)
    for data in ([], {"recordings": []}, {"session_stem": "invalid"}, {"mode": float("nan")}):
        path.write_text(json.dumps(data))
        with pytest.raises((OCFError, ValueError)):
            api.workspace_manifest(path.name)
    outside = tmp_path / "take.wav"
    wav(outside)
    (root / "take.wav").symlink_to(outside)
    path.write_text(json.dumps({"recordings": {"take": {"file": "take.wav"}}}))
    with pytest.raises(OCFError, match="outside"):
        api.workspace_manifest(path.name)
    (root / "external.json").symlink_to(outside)
    with pytest.raises(OCFError, match="outside"):
        api.workspace_manifest("external.json")


def test_persistent_recording_validation_metrics_results_and_idempotency(sources):
    path, data = sources
    first = api.dispatch(
        "ocf_validate_recordings",
        {
            "function_id": FUNCTION,
            "manifest": path.name,
            "idempotency_key": "validation",
        },
    )
    assert wait(first["job_id"])["state"] == "completed"
    same = api.validate_recordings(FUNCTION, path.name, idempotency_key="validation")
    assert same.get("job_id") == first["job_id"] and same.get("reused"), same
    result = api.get_job_result(first["job_id"], limit=1)["data"]
    assert result["status"] == "passed" and result["errors"] == 0
    assert result["sources"]["recording"] == len(data["recordings"])
    assert result["selected_originals"] == result["measured_originals"] == 2
    assert result["duration_s"] == pytest.approx(0.2)
    assert result["diagnostics"]["total"] == 2
    assert result["diagnostics"]["next_offset"] == 1
    metrics = result["diagnostics"]["items"][0]["metrics"]
    assert metrics["sample_rate"] == 8000 and metrics["duration_s"] == pytest.approx(0.1)
    assert metrics["sample_peak"] > 0
    assert not result["originals_modified"] and not result["transcript_verified"]
    wav(path.parent / "take0.wav", value=1500)
    changed = api.validate_recordings(FUNCTION, path.name, idempotency_key="validation")
    assert changed["status"] == "failed" and "different inputs" in changed["message"]


@pytest.mark.parametrize("operation", ["narration-validate", "narration-render"])
def test_real_queued_audio_change_refuses_execution(sources, operation):
    path, _ = sources
    with jobs.lock("executor"):
        job = jobs.start(operation, {"function_id": FUNCTION, "manifest": path.name})
        wav(path.parent / "take0.wav", value=2000)
    assert wait(job["job_id"])["state"] == "failed"
    result = jobs.job_result(job["job_id"])["data"]
    assert "inputs changed" in result["message"]
    assert result["diagnostics"]["items"][0]["severity"] == "error"
    assert not (path.parent / "renders/jobs" / job["job_id"]).exists()
    assert not list((path.parent / "renders").rglob("*.*"))


def test_validation_checks_unselected_catalog_and_inspects_only_selected(sources):
    path, data = sources
    entry = next(iter(data["recordings"].values()))
    data["recordings"]["unselected"] = {
        **entry,
        "file": "extra.wav",
        "target": {"function_id": "OCF-SLP-005"},
    }
    wav(path.parent / "extra.wav", value=1234)
    path.write_text(json.dumps(data))
    job = api.validate_recordings(FUNCTION, path.name)
    assert wait(job["job_id"])["state"] == "failed"
    result = jobs.job_result(job["job_id"])["data"]
    assert "checksum mismatch" in result["message"]
    data["recordings"]["unselected"]["sha256"] = sha256_of_file(path.parent / "extra.wav")
    path.write_text(json.dumps(data))
    job = api.validate_recordings(FUNCTION, path.name)
    assert wait(job["job_id"])["state"] == "completed"
    assert jobs.job_result(job["job_id"])["data"]["selected_originals"] == 2


def test_render_dispatch_uses_canonical_service_unique_job_output_and_optional_voice(
    sources, monkeypatch
):
    path, _ = sources
    monkeypatch.setattr(jobs.subprocess, "Popen", lambda *args, **kwargs: None)
    calls = []

    def render(function_id, **kwargs):
        calls.append((function_id, kwargs))
        assert kwargs["narration_sources"] == path
        assert kwargs["pacing"] == "relaxed" and kwargs["voice"] is None
        return {"dry_run": False}

    monkeypatch.setattr(complete_session, "render_complete_session", render)
    outputs = []
    for key in ("one", "two"):
        job = api.dispatch(
            "ocf_start_narration_render",
            {
                "function_id": FUNCTION,
                "manifest": path.name,
                "pacing": "relaxed",
                "idempotency_key": key,
            },
        )
        assert jobs.managed_execute(job["job_id"]) == 0
        result = jobs.job_result(job["job_id"])["data"]
        assert result["status"] == "passed" and result["listening_approval"] is None
        assert result["output_directory"] == f"renders/jobs/{job['job_id']}"
        outputs.append(calls[-1][1]["output"])
    assert outputs[0] != outputs[1]


def test_narration_mix_profile_is_sandboxed_fingerprinted_and_forwarded(sources, monkeypatch):
    path, _ = sources
    profile = path.parent / "mix.json"
    profile.write_text("{}", encoding="utf-8")
    arguments = {
        "function_id": FUNCTION,
        "manifest": path.name,
        "locale": "en-US",
        "mix_profile": profile.name,
    }
    before = jobs.input_identity("narration-render", arguments)
    profile.write_text('{"output_headroom_db":3}', encoding="utf-8")
    after = jobs.input_identity("narration-render", arguments)
    assert before["mix_profile"] != after["mix_profile"]
    monkeypatch.setattr(jobs.subprocess, "Popen", lambda *_a, **_k: None)
    captured = []
    monkeypatch.setattr(
        complete_session,
        "render_complete_session",
        lambda *_a, **kwargs: captured.append(kwargs) or {"dry_run": False},
    )
    started = api.start_narration_render(FUNCTION, path.name, mix_profile=profile.name)
    assert jobs.managed_execute(started["job_id"]) == 0
    assert captured[0]["mix_profile"] == {"output_headroom_db": 3}
    rejected = api.start_narration_render(FUNCTION, path.name, mix_profile="/outside.json")
    assert rejected["status"] == "failed"
    assert "relative" in rejected["message"] or "contained" in rejected["message"]


def test_narration_job_uses_existing_queued_cancellation(sources):
    path, _ = sources
    with jobs.lock("executor"):
        job = api.start_narration_render(FUNCTION, path.name)
        assert job["operation"] == "narration-render"
        assert api.cancel_job(job["job_id"])["cancel_requested"]
        assert wait(job["job_id"])["state"] == "canceled"
    assert not (path.parent / "renders/jobs" / job["job_id"]).exists()


def test_hybrid_render_identity_tracks_effective_voices_and_model_bytes(sources, monkeypatch):
    from ocf_tools import speech_cache, voice

    path, data = sources
    entries = list(data["recordings"])
    data["mode"] = "hybrid"
    data["fallback"] = "tts"
    data["default_voice"] = "manifest-voice"
    first = data["recordings"].pop(entries[0])
    second = data["recordings"].pop(entries[1])
    data["events"] = {first["target"]["event_id"]: {"source": "tts", "voice": "event-voice"}}
    path.write_text(json.dumps(data))
    models = {}
    for name in ("cli-voice", "event-voice"):
        model = path.parent / (name + ".onnx")
        model.write_bytes(name.encode())
        models[name] = model
    monkeypatch.setattr(voice, "resolve_backend", lambda name, **kwargs: {"id": name})
    monkeypatch.setattr(
        speech_cache, "voice_identity", lambda spec: sha256_of_file(models[spec["id"]])
    )
    args = {"function_id": FUNCTION, "manifest": path.name, "locale": "en-US", "voice": "cli-voice"}
    before = jobs.input_identity("narration-render", args)
    assert set(before["voices"]) == set(models)
    assert second["target"]["event_id"] not in data["events"]
    models["event-voice"].write_bytes(b"updated model")
    after = jobs.input_identity("narration-render", args)
    assert before["voices"]["event-voice"] != after["voices"]["event-voice"]


def test_source_validation_inspection_failure_is_diagnostic_and_continues(sources, monkeypatch):
    from ocf_tools import recording_audio

    path, _ = sources
    original = recording_audio.inspect_recording

    def inspect(asset):
        if asset.name == "take0.wav":
            raise OCFError("synthetic decoder failure")
        return original(asset)

    monkeypatch.setattr(recording_audio, "inspect_recording", inspect)
    result = jobs.validate_narration_recordings(FUNCTION, path.name)
    assert result["errors"] == 1 and result["measured_originals"] == 1
    assert {d["severity"] for d in result["diagnostics"]} == {"info", "error"}


def test_session_stem_bytes_are_identity_inputs_before_schema_extension(sources):
    path, data = sources
    stem = path.parent / "stem.wav"
    wav(stem)
    data["session_stem"] = {"file": stem.name, "sha256": sha256_of_file(stem)}
    path.write_text(json.dumps(data))
    args = {"function_id": FUNCTION, "manifest": path.name, "locale": "en-US"}
    before = jobs.input_identity("narration-validate", args)
    wav(stem, value=3000)
    after = jobs.input_identity("narration-validate", args)
    assert before["narration_manifest"] == after["narration_manifest"]
    assert before["referenced_assets"]["session_stem"] != after["referenced_assets"]["session_stem"]


@pytest.mark.parametrize("mutation", ["edit", "create"])
def test_dataset_wav_identity_and_real_queued_change(monkeypatch, tmp_path, mutation):
    from ocf_tools.voice_datasets import initialize

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    initialize(tmp_path / "dataset")
    manifest = tmp_path / "dataset/dataset.json"
    data = json.loads(manifest.read_text())
    asset = manifest.parent / data["records"][0]["audio"]
    if mutation == "edit":
        wav(asset, rate=data["sample_rate"])
    args = {"manifest": "dataset/dataset.json"}
    before = jobs.input_identity("voice-dataset", args)
    with jobs.lock("executor"):
        job = api.validate_voice_dataset(args["manifest"])
        wav(asset, value=2000, rate=data["sample_rate"])
    after = jobs.input_identity("voice-dataset", args)
    assert before["dataset_manifest"] == after["dataset_manifest"]
    assert before["referenced_assets"] != after["referenced_assets"]
    assert wait(job["job_id"])["state"] == "failed"
    assert "inputs changed" in jobs.job_result(job["job_id"])["data"]["message"]


def test_dataset_training_plan_is_safe_compact_and_backend_compatible(monkeypatch, tmp_path):
    from ocf_tools.voice_datasets import initialize, training_plan

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    assert api.plan_voice_training("espeak") == training_plan(backend="espeak")
    initialize(tmp_path / "dataset")
    report = api.dispatch(
        "ocf_plan_voice_training",
        {
            "backend": "piper",
            "dataset": "dataset/dataset.json",
        },
    )
    assert not report["training_supported"] and not report["ready"]
    assert report["dataset"]["errors"] > 0
    assert "measurements" not in report["dataset"] and "diagnostics" not in report["dataset"]
    assert report["resources"]["gpu_probe"] == "not-requested"
    assert api.plan_voice_training(dataset="../dataset.json")["status"] == "failed"


@pytest.mark.unit
def test_voice_capabilities_default_no_process_and_explicit_bounded_probe(monkeypatch):
    from types import SimpleNamespace

    from ocf_tools import voice_capabilities, voice_engine_cli

    assert api.inspect_voice_capabilities() == voice_engine_cli.capabilities_report()
    assert api.inspect_voice_capabilities()["resources"]["gpu_probe"] == "not-requested"
    monkeypatch.setattr(voice_capabilities.shutil, "which", lambda name: "/fake/" + name)
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="8192, 4096\n")

    monkeypatch.setattr(voice_capabilities, "workspace_run", run)
    report = api.dispatch("ocf_inspect_voice_capabilities", {"probe_gpu": True})
    assert report["resources"]["gpus"] == [{"total_mib": 8192, "free_mib": 4096}]
    assert len(calls) == 1 and calls[0][1]["timeout"] == 2.0
    assert not report["training_supported"] and not report["inference_verified"]
