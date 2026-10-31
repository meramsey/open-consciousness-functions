"""Deterministic worker lifecycle and recovery tests; all process boundaries are faked."""

import io
import queue
import subprocess
from types import SimpleNamespace

import pytest
from ocf_tools import voice_packs
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


class Stream:
    def __init__(self):
        self.closed = False
        self.writes = []

    def write(self, value):
        self.writes.append(value)

    def flush(self):
        pass

    def close(self):
        self.closed = True


class Process:
    def __init__(self, waits=()):
        self.stdin, self.stdout = Stream(), Stream()
        self.waits = list(waits)
        self.terminated = self.killed = False

    def poll(self):
        return None

    def wait(self, timeout=None):
        result = self.waits.pop(0) if self.waits else None
        if isinstance(result, BaseException):
            raise result
        return result

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def test_persistent_worker_selects_explicit_pack_and_restores_nested_context(monkeypatch):
    inherited = {"id": "OCF-VOICE-9890", "backend": "chatterbox-nano"}
    other = {"id": "OCF-VOICE-9891", "backend": "chatterbox-nano"}
    inspected = []
    stopped = []
    monkeypatch.setattr(voice_packs, "_worker_scopes", 0)
    monkeypatch.setattr(voice_packs, "_stop_worker", lambda: stopped.append(True))
    monkeypatch.setattr(
        voice_packs, "inspect_pack", lambda query: inspected.append(query) or {"profile": other}
    )
    token = voice_packs._active_voice_pack.set(inherited)
    try:
        with voice_packs.persistent_worker("OCF-VOICE-9890"):
            assert voice_packs._active_voice_pack.get() is inherited
            with voice_packs.persistent_worker("OCF-VOICE-9891"):
                assert voice_packs._active_voice_pack.get() is other
                assert voice_packs._worker_scopes == 2
            assert voice_packs._active_voice_pack.get() is inherited
        assert voice_packs._worker_scopes == 0
        assert inspected == ["OCF-VOICE-9891"]
        assert stopped == [True]
    finally:
        voice_packs._active_voice_pack.reset(token)


def test_persistent_worker_without_voice_preserves_inherited_selection(monkeypatch):
    inherited = {"id": "OCF-VOICE-9890", "backend": "chatterbox-nano"}
    stopped = []
    monkeypatch.setattr(voice_packs, "_worker_scopes", 0)
    monkeypatch.setattr(voice_packs, "_stop_worker", lambda: stopped.append(True))
    token = voice_packs._active_voice_pack.set(inherited)
    try:
        with voice_packs.persistent_worker():
            assert voice_packs._active_voice_pack.get() is inherited
        assert stopped == [True]
    finally:
        voice_packs._active_voice_pack.reset(token)


def test_persistent_worker_falls_back_for_unknown_or_non_chatterbox_pack(monkeypatch):
    inherited = {"id": "OCF-VOICE-9890", "backend": "chatterbox-nano"}
    monkeypatch.setattr(voice_packs, "_worker_scopes", 0)
    monkeypatch.setattr(voice_packs, "_stop_worker", lambda: None)
    token = voice_packs._active_voice_pack.set(inherited)
    try:
        monkeypatch.setattr(
            voice_packs, "inspect_pack", lambda _query: {"profile": {"backend": "piper"}}
        )
        with voice_packs.persistent_worker("piper-profile"):
            assert voice_packs._active_voice_pack.get() is inherited
        monkeypatch.setattr(
            voice_packs,
            "inspect_pack",
            lambda _query: (_ for _ in ()).throw(OCFError("unknown pack")),
        )
        with voice_packs.persistent_worker("unknown"):
            assert voice_packs._active_voice_pack.get() is inherited
    finally:
        voice_packs._active_voice_pack.reset(token)


def test_worker_stdout_forwards_lines_then_terminal_marker():
    responses = queue.Queue()
    process = SimpleNamespace(stdout=io.StringIO('{"ok":true}\n'))
    voice_packs._read_worker_stdout(process, responses)
    assert responses.get_nowait() == '{"ok":true}\n'
    assert responses.get_nowait() is None


def test_worker_startup_reuses_live_process_and_parses_response(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    process = Process()
    calls = []

    class Thread:
        def __init__(self, *, target, args, **kwargs):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    def start(argv, **kwargs):
        calls.append((argv, kwargs))
        return process

    monkeypatch.setattr(voice_packs, "_worker_process", None)
    monkeypatch.setattr(voice_packs, "_worker_responses", None)
    monkeypatch.setattr(voice_packs, "_worker_log_path", None)
    monkeypatch.setattr(voice_packs.subprocess, "Popen", start)
    monkeypatch.setattr(voice_packs.threading, "Thread", Thread)
    monkeypatch.setattr(
        voice_packs,
        "_read_worker_stdout",
        lambda _process, responses: responses.put('{"generation":1}'),
    )
    assert voice_packs._persistent_inference({"text": "one"}, tmp_path / "python", 1) == {
        "generation": 1
    }
    voice_packs._worker_responses.put('{"generation":2}')
    assert voice_packs._persistent_inference({"text": "two"}, tmp_path / "python", 1) == {
        "generation": 2
    }
    assert len(calls) == 1
    assert process.stdin.writes == ['{"text": "one"}\n', '{"text": "two"}\n']
    voice_packs._stop_worker()
    assert process.stdin.closed and process.stdout.closed


@pytest.mark.parametrize(
    "waits,terminated,killed",
    [
        ([], False, False),
        ([subprocess.TimeoutExpired("worker", 10), None], True, False),
        (
            [subprocess.TimeoutExpired("worker", 10), subprocess.TimeoutExpired("worker", 5), None],
            True,
            True,
        ),
    ],
)
def test_worker_stop_escalates_only_after_timeout(monkeypatch, waits, terminated, killed):
    process = Process(waits)
    monkeypatch.setattr(voice_packs, "_worker_process", process)
    monkeypatch.setattr(voice_packs, "_worker_responses", queue.Queue())
    monkeypatch.setattr(voice_packs, "_worker_log_path", None)
    voice_packs._stop_worker()
    assert process.stdin.closed and process.stdout.closed
    assert process.terminated is terminated
    assert process.killed is killed


def test_worker_eof_and_invalid_json_stop_the_worker(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    for response, message in [(None, "exited unexpectedly"), ("not json", "invalid JSON")]:
        process = Process()

        class Thread:
            def __init__(self, *, target, args, **kwargs):
                self.target, self.args = target, args

            def start(self):
                self.target(*self.args)

        monkeypatch.setattr(voice_packs, "_worker_process", None)
        monkeypatch.setattr(voice_packs, "_worker_responses", None)
        monkeypatch.setattr(voice_packs, "_worker_log_path", None)
        monkeypatch.setattr(voice_packs.subprocess, "Popen", lambda *a, **k: process)
        monkeypatch.setattr(voice_packs.threading, "Thread", Thread)
        monkeypatch.setattr(
            voice_packs,
            "_read_worker_stdout",
            lambda _process, responses, line=response: responses.put(line),
        )
        with pytest.raises(OCFError, match=message):
            voice_packs._persistent_inference({"text": "bad worker"}, tmp_path / "python", 1)
        assert voice_packs._worker_process is None
        assert process.stdin.closed


def test_worker_reentry_replaces_a_dead_process_before_sending(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    old, fresh = Process(), Process()
    old.poll = lambda: 1

    class Thread:
        def __init__(self, *, target, args, **kwargs):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    starts = []
    monkeypatch.setattr(voice_packs, "_worker_process", old)
    monkeypatch.setattr(voice_packs, "_worker_responses", queue.Queue())
    monkeypatch.setattr(voice_packs, "_worker_log_path", None)
    monkeypatch.setattr(voice_packs.subprocess, "Popen", lambda *a, **k: starts.append(a) or fresh)
    monkeypatch.setattr(voice_packs.threading, "Thread", Thread)
    monkeypatch.setattr(
        voice_packs,
        "_read_worker_stdout",
        lambda _process, responses: responses.put('{"restarted":true}'),
    )
    assert voice_packs._persistent_inference({"text": "after crash"}, tmp_path / "python", 1) == {
        "restarted": True
    }
    assert old.stdin.closed and old.stdout.closed
    assert len(starts) == 1
    voice_packs._stop_worker()


def test_worker_timeout_stops_process_and_reports_recovery_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    process = Process()

    class Thread:
        def __init__(self, **kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(voice_packs, "_worker_process", None)
    monkeypatch.setattr(voice_packs, "_worker_responses", None)
    monkeypatch.setattr(voice_packs, "_worker_log_path", None)
    monkeypatch.setattr(voice_packs.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(voice_packs.threading, "Thread", Thread)
    with pytest.raises(OCFError, match="worker failed or timed out"):
        voice_packs._persistent_inference({"text": "timeout"}, tmp_path / "python", 0.001)
    assert process.stdin.closed
    assert voice_packs._worker_process is None
