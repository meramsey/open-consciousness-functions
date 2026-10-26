import hashlib
import io
import json
import threading
import wave
from contextlib import contextmanager

import pytest
from ocf_tools import bulk_render, speech_cache
from ocf_tools.utils import OCFError


def pcm():
    result = io.BytesIO()
    with wave.open(result, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(b"\0\0" * 80)
    return result.getvalue()


@pytest.mark.unit
def test_speech_cache_identity_corruption_and_failures(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    binary = tmp_path / "engine"
    model = tmp_path / "model.onnx"
    binary.write_bytes(b"binary")
    model.write_bytes(b"model-1")
    monkeypatch.setattr(speech_cache.shutil, "which", lambda _: str(binary))
    spec = {"binary": "fixture", "model": str(model), "locale": "en-US", "piper_length_scale": 1.0}
    calls = []

    def render():
        calls.append(1)
        return pcm()

    with speech_cache.enabled():
        assert speech_cache.cached_cue(spec, "Exact text.", render) == pcm()
        speech_cache.cached_cue(spec, "Exact text.", render)
        assert len(calls) == 1
        for changed in ({**spec, "locale": "fr"}, {**spec, "piper_length_scale": 1.2}):
            speech_cache.cached_cue(changed, "Exact text.", render)
        speech_cache.cached_cue(spec, "Changed text.", render)
        model.write_bytes(b"model-2")
        speech_cache.cached_cue(spec, "Exact text.", render)
        assert len(calls) == 5
        for path in (tmp_path / "work/cache/tts").glob("*/speech.wav"):
            path.write_bytes(b"corrupt")
        speech_cache.cached_cue(spec, "Exact text.", render)
        assert len(calls) == 6
        with pytest.raises(OCFError, match="invalid PCM"):
            speech_cache.cached_cue(spec, "Invalid output", lambda: b"bad")


@pytest.mark.unit
def test_bulk_resume_verifies_artifacts_force_preserves_history_and_failure_continues(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    from ocf_tools import semantic_dsp

    monkeypatch.setattr(
        bulk_render,
        "source_plan",
        lambda owner, locale: ({"id": owner}, {}, {"resolved_dsp_profile": {"id": "fixture"}}),
    )
    monkeypatch.setattr(semantic_dsp, "dependency_identity", lambda _: {"verified": True})
    from ocf_tools import complete_session

    monkeypatch.setattr(
        complete_session, "build_complete_session_plan", lambda *_args, **_kwargs: {}
    )
    monkeypatch.setattr(bulk_render, "LocaleCatalog", lambda: None)
    monkeypatch.setattr(bulk_render, "_voice_profile", lambda *_: ({}, {}))
    monkeypatch.setattr(bulk_render, "voice_identity", lambda _: {"fixture": True})
    outputs = []

    def render(owner, **kwargs):
        if owner == "failed":
            raise OCFError("deliberate failure")
        root = tmp_path / f"audition-{len(outputs)}"
        root.mkdir()
        data = pcm()
        (root / "master.wav").write_bytes(data)
        (root / "session-report.json").write_text(
            json.dumps(
                {
                    "artifacts": {
                        "wav": {
                            "path": "master.wav",
                            "size_bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                        }
                    }
                }
            )
        )
        outputs.append(root)
        return {"output_directory": str(root)}

    monkeypatch.setattr(bulk_render, "render_complete_session", render)
    first = bulk_render.render_many(["ok", "failed"], voice="fixture")
    assert first["failed"] == 1 and len(outputs) == 1
    assert (
        bulk_render.render_many(["ok"], voice="fixture")["results"][0]["status"]
        == "skipped-verified"
    )
    bulk_render.render_many(["ok"], voice="fixture", force=True)
    assert len(outputs) == 2 and outputs[0].exists()
    (outputs[1] / "master.wav").write_bytes(b"corrupt")
    bulk_render.render_many(["ok"], voice="fixture")
    assert len(outputs) == 3

    dependencies = {"profile": "reference-v4", "source_sha256": "first-source", "verified": True}
    monkeypatch.setattr(semantic_dsp, "dependency_identity", lambda _: dict(dependencies))
    selected = []

    def render_override(owner, **kwargs):
        selected.append(kwargs["dsp_profile"])
        return render(owner, **kwargs)

    monkeypatch.setattr(bulk_render, "render_complete_session", render_override)
    overridden = bulk_render.render_many(["ok"], voice="fixture", dsp_profile="private.yaml")
    assert overridden["results"][0]["status"] == "rendered"
    assert selected == ["private.yaml"]
    assert (
        bulk_render.render_many(["ok"], voice="fixture", dsp_profile="private.yaml")["results"][0][
            "status"
        ]
        == "skipped-verified"
    )
    dependencies["source_sha256"] = "changed-source"
    assert (
        bulk_render.render_many(["ok"], voice="fixture", dsp_profile="private.yaml")["results"][0][
            "status"
        ]
        == "rendered"
    )
    assert len(outputs) == 5


@pytest.mark.unit
def test_bulk_dry_run_needs_no_engine_and_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(bulk_render, "source_plan", lambda *args: ({}, {}, {}))
    monkeypatch.setattr(
        bulk_render, "_voice_profile", lambda *args: pytest.fail("dry-run resolved a backend")
    )
    result = bulk_render.render_many(["fixture"], voice="unavailable", dry_run=True)
    assert result["results"][0]["status"] == "planned"
    assert not (tmp_path / "work").exists()


@pytest.mark.unit
def test_render_batch_lease_blocks_duplicate_and_stale_owners(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    lease = bulk_render._single_batch_owner

    @lease
    def nested():
        @lease
        def duplicate():
            return None

        with pytest.raises(OCFError, match="another render batch owns PID"):
            duplicate()
        return "owned"

    assert nested() == "owned"
    lock = tmp_path / "work/logs/bulk-render.lock"
    assert not lock.exists()

    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text('{"pid": 2147483647, "owner": "interrupted"}\n')
    with pytest.raises(OCFError, match="stale or unreadable"):
        nested()
    assert lock.exists()


@pytest.mark.integration
def test_render_receipts_bind_to_current_worktree_head_and_branch():
    from ocf_tools.paths import REPO_ROOT

    identity = bulk_render._git_worktree_identity()
    assert identity["verified"] is True
    assert len(identity["head"]) == 40
    assert identity["branch"].startswith("engineering/")
    assert identity["branch"].endswith("20261025")
    assert identity["worktree"] == str(REPO_ROOT.resolve())


@pytest.mark.unit
def test_fresh_synthesis_skips_cache_and_publishes_durable_function_progress(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    from ocf_tools import semantic_dsp
    from ocf_tools.progress import observing

    monkeypatch.setattr(
        bulk_render,
        "source_plan",
        lambda owner, locale: ({"id": owner}, {}, {"resolved_dsp_profile": {"id": "fixture"}}),
    )
    monkeypatch.setattr(semantic_dsp, "dependency_identity", lambda _: {"verified": True})
    monkeypatch.setattr(bulk_render, "LocaleCatalog", lambda: None)
    monkeypatch.setattr(bulk_render, "_voice_profile", lambda *_: ({}, {}))
    monkeypatch.setattr(bulk_render, "voice_identity", lambda _: {"fixture": True})
    cache_states = []

    @contextmanager
    def record_cache_state(active=True):
        cache_states.append(active)
        yield

    monkeypatch.setattr(bulk_render, "enabled", record_cache_state)
    output = tmp_path / "audition"
    output.mkdir()
    data = pcm()
    (output / "master.wav").write_bytes(data)
    (output / "session-report.json").write_text(
        json.dumps(
            {
                "artifacts": {
                    "wav": {
                        "path": "master.wav",
                        "size_bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        bulk_render,
        "render_complete_session",
        lambda *_args, **_kwargs: {"output_directory": str(output)},
    )
    events = []
    with observing(events.append):
        result = bulk_render.render_many(["fresh"], voice="fixture", fresh_synthesis=True)
    assert result["failed"] == 0
    assert cache_states == [False]
    assert [(row["phase"], row.get("detail")) for row in events] == [
        ("function-preflight", "fresh"),
        ("function-start", "fresh"),
        ("function-rendered", "fresh"),
    ]


@pytest.mark.unit
def test_resource_worker_limit_reduces_for_memory_disk_cpu_and_load():
    gib = 1024**3
    assert (
        bulk_render._select_workers(
            2, memory_bytes=40 * gib, disk_bytes=100 * gib, cpu_count=16, load_average=0
        )
        == 2
    )
    assert (
        bulk_render._select_workers(
            2, memory_bytes=14 * gib, disk_bytes=100 * gib, cpu_count=16, load_average=0
        )
        == 2
    )
    assert (
        bulk_render._select_workers(
            2, memory_bytes=10 * gib, disk_bytes=100 * gib, cpu_count=16, load_average=0
        )
        == 1
    )
    assert (
        bulk_render._select_workers(
            2, memory_bytes=40 * gib, disk_bytes=100 * gib, cpu_count=1, load_average=0
        )
        == 1
    )
    assert (
        bulk_render._select_workers(
            2, memory_bytes=40 * gib, disk_bytes=100 * gib, cpu_count=8, load_average=7
        )
        == 1
    )
    with pytest.raises(OCFError, match="disk"):
        bulk_render._select_workers(
            2, memory_bytes=40 * gib, disk_bytes=10 * gib, cpu_count=8, load_average=0
        )


@pytest.mark.unit
def test_two_worker_batch_runs_distinct_functions_without_shared_output_races(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    from ocf_tools import semantic_dsp

    monkeypatch.setattr(
        bulk_render,
        "source_plan",
        lambda owner, locale: ({"id": owner}, {}, {"resolved_dsp_profile": {"id": "fixture"}}),
    )
    monkeypatch.setattr(semantic_dsp, "dependency_identity", lambda _: {"verified": True})
    monkeypatch.setattr(bulk_render, "LocaleCatalog", lambda: None)
    monkeypatch.setattr(bulk_render, "_voice_profile", lambda *_: ({}, {}))
    monkeypatch.setattr(bulk_render, "voice_identity", lambda _: {"fixture": True})
    monkeypatch.setattr(
        bulk_render,
        "_batch_resource_state",
        lambda requested: {"selected_workers": 2, "requested_workers": requested},
    )
    barrier = threading.Barrier(2)

    def render(owner, **kwargs):
        barrier.wait(timeout=2)
        root = tmp_path / f"audition-{owner}"
        root.mkdir()
        data = pcm()
        (root / "master.wav").write_bytes(data)
        (root / "session-report.json").write_text(
            json.dumps(
                {
                    "artifacts": {
                        "wav": {
                            "path": "master.wav",
                            "size_bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        return {"output_directory": str(root)}

    monkeypatch.setattr(bulk_render, "render_complete_session", render)
    result = bulk_render.render_many(
        ["one", "two"], voice="fixture", workers=2, fresh_synthesis=True
    )
    assert result["workers"] == 2
    assert {row["status"] for row in result["results"]} == {"rendered"}


@pytest.mark.unit
def test_render_job_retries_one_transient_error_but_not_deterministic_failure(
    monkeypatch, tmp_path
):
    import errno

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    calls = []
    monkeypatch.setattr(bulk_render, "verified_output", lambda *_: True)
    monkeypatch.setattr(bulk_render, "sha256_of_file", lambda *_: "a" * 64)

    def transient_then_success(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise OSError(errno.EAGAIN, "resource temporarily unavailable")
        return {"output_directory": str(tmp_path / "ready")}

    monkeypatch.setattr(bulk_render, "render_complete_session", transient_then_success)
    result = bulk_render._render_job(
        "transient",
        {"key": "key", "receipt_path": tmp_path / "receipt", "resume_verified": False},
        locale="en-US",
        voice="fixture",
        pacing="sleep",
        sample_rate=44100,
        dsp_profile=None,
        force=False,
        fresh_synthesis=True,
        progress_sink=lambda _event: None,
    )
    assert result["status"] == "rendered" and result["attempts"] == 2
    assert len(calls) == 2

    calls.clear()
    monkeypatch.setattr(
        bulk_render,
        "render_complete_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OCFError("invalid canonical plan")),
    )
    result = bulk_render._render_job(
        "deterministic",
        {"key": "key", "receipt_path": tmp_path / "receipt", "resume_verified": False},
        locale="en-US",
        voice="fixture",
        pacing="sleep",
        sample_rate=44100,
        dsp_profile=None,
        force=False,
        fresh_synthesis=True,
        progress_sink=lambda _event: None,
    )
    assert result["status"] == "failed" and result["attempts"] == 1


@pytest.mark.unit
def test_speech_quota_counts_abandoned_staging_and_preserves_pcm(monkeypatch, tmp_path):
    from ocf_tools.paths import work_path

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(speech_cache, "voice_identity", lambda spec: {})
    monkeypatch.setattr(speech_cache, "MAX_CACHE_BYTES", 100)
    abandoned = work_path("cache", "tts", "a" * 64)
    abandoned.mkdir(parents=True)
    (abandoned / ".ocf-cache-owned").write_text("a" * 64)
    (abandoned / ".abandoned.wav").write_bytes(b"x" * 100)
    with speech_cache.enabled():
        assert speech_cache.cached_cue({}, "fixture", pcm) == pcm()
    assert not list(work_path("cache", "tts").glob("*/speech.wav"))
    from ocf_tools.agent_api import cache_clean

    assert cache_clean(0, dry_run=False, confirmed=True)["selected_count"] == 1
    assert not abandoned.exists()


@pytest.mark.unit
def test_concurrent_cache_publish_reserves_capacity(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    from ocf_tools.paths import work_path

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(speech_cache, "MAX_CACHE_BYTES", 4400)

    def publish(key):
        try:
            speech_cache._publish(work_path("cache", "tts", key), key, b"x" * 200)
            return True
        except OCFError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, ["a" * 64, "b" * 64]))
    assert sorted(results) == [False, True]


@pytest.mark.unit
def test_piper_cache_tracks_backend_venv_instead_of_host_package_versions(monkeypatch, tmp_path):
    environment = tmp_path / "backend"
    executable = environment / "bin/piper"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"console wrapper")
    metadata = environment / "lib/python3.12/site-packages/piper_tts-1.dist-info/METADATA"
    metadata.parent.mkdir(parents=True)
    metadata.write_text("Version: 1\n")
    monkeypatch.setattr(speech_cache.shutil, "which", lambda _: str(executable))
    spec = {"binary": "piper", "name": "piper", "locale": "en-US"}
    first = speech_cache.voice_identity(spec)
    metadata.write_text("Version: 2\n")
    second = speech_cache.voice_identity(spec)
    assert first["assets"] == second["assets"]
    assert first["backend_environment"] != second["backend_environment"]
