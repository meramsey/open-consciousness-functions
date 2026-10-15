"""Progress observers never change source audio, scheduling or job ownership."""

import json
import time

import pytest
from ocf_tools import dev_jobs, progress, speech_cache

pytestmark = pytest.mark.unit


def test_nested_observers_restore_counts_and_do_not_leak_text():
    outer, inner = [], []
    progress.advance("ignored")
    with progress.observing(outer.append):
        progress.advance("synthesis-cues", detail="OCF-VOICE-0002")
        with progress.observing(inner.append):
            progress.advance("recording-preparation", detail="source-hash")
        progress.advance("synthesis-cues", detail="OCF-VOICE-0002")
    progress.advance("ignored")
    assert [row["completed"] for row in outer] == [1, 2]
    assert inner == [{"phase": "recording-preparation", "completed": 1, "detail": "source-hash"}]


def test_observer_io_failure_cannot_interrupt_audio_or_change_cache_counters():
    def broken(_row):
        raise OSError("observer unavailable")

    before = speech_cache.STATS["bypassed"]
    data = b"exact engine bytes"
    with progress.observing(broken):
        result = speech_cache.cached_cue({"name": "fixture"}, "private spoken text", lambda: data)
    assert result is data and speech_cache.STATS["bypassed"] == before + 1


def test_job_execution_publishes_separate_progress_and_terminal_state_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    job_id = "b" * 32
    root = dev_jobs.directory(job_id)
    root.mkdir(parents=True)
    state = {
        "job_id": job_id,
        "state": "running",
        "heartbeat": time.time(),
        "progress": "executing canonical service",
    }
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")

    def work(_job_id):
        progress.report("background-dsp", completed=1, total=2)
        live = dev_jobs.status(job_id)
        assert live["progress"] == "background-dsp"
        assert live["progress_detail"]["completed"] == 1
        return 0

    monkeypatch.setattr(dev_jobs, "_execute", work)
    assert dev_jobs.execute(job_id) == 0
    state.update(state="completed", progress="verified result available")
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    final = dev_jobs.status(job_id)
    assert final["progress"] == "verified result available" and "progress_detail" not in final
    state.update(state="running")
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (root / "progress.json").write_text("interrupted", encoding="utf-8")
    assert dev_jobs.status(job_id)["progress"] == "verified result available"
