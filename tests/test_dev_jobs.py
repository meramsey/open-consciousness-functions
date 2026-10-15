import json
import time

import pytest
from ocf_tools import dev_jobs as jobs
from ocf_tools.utils import OCFError


def wait(job_id, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = jobs.status(job_id)
        if state["state"] in jobs.TERMINAL:
            return state
        time.sleep(0.1)
    jobs.cancel(job_id)
    pytest.fail("job did not finish within test deadline")


def test_persistent_test_job_idempotency_counts_and_results(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    first = jobs.start(
        "tests",
        {"paths": ["tests/test_loader_contracts.py"], "full": False, "workers": 1},
        "fixture",
    )
    same = jobs.start(
        "tests",
        {"paths": ["tests/test_loader_contracts.py"], "full": False, "workers": 1},
        "fixture",
    )
    assert same["job_id"] == first["job_id"]
    with pytest.raises(OCFError, match="different inputs"):
        jobs.start("tests", {"paths": ["tests/test_workspace.py"], "full": False}, "fixture")
    finished = wait(first["job_id"])
    assert finished["state"] == "completed", finished
    result = jobs.job_result(first["job_id"])
    assert result["data"]["passed"] > 0 and result["data"]["errors"] == 0
    assert not jobs.cancel(first["job_id"])["cancel_requested"]


def test_queued_cancellation_and_stale_recovery(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    with jobs.lock("executor") as acquired:
        assert acquired
        first = jobs.start("tests", {"paths": ["tests/test_loader_contracts.py"], "full": False})
        assert jobs.cancel(first["job_id"])["cancel_requested"]
        assert wait(first["job_id"])["state"] == "canceled"
    path = jobs.directory(first["job_id"]) / "state.json"
    state = json.loads(path.read_text())
    state.update(state="running", heartbeat=0)
    jobs.save(path, state)
    recovered = jobs.status(first["job_id"])
    assert recovered["state"] == "failed" and "interrupted" in recovered["error"]


def test_running_job_cancellation_and_concurrent_duplicate_prevention(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    with jobs.lock("executor"):
        with ThreadPoolExecutor(max_workers=2) as pool:
            records = list(
                pool.map(lambda _: jobs.start("tests", {"paths": [], "full": True}), range(2))
            )
        assert records[0]["job_id"] == records[1]["job_id"]
    identifier = records[0]["job_id"]
    deadline = time.monotonic() + 30
    while jobs.status(identifier)["state"] == "queued" and time.monotonic() < deadline:
        time.sleep(0.1)
    assert jobs.status(identifier)["state"] == "running"
    jobs.cancel(identifier)
    assert wait(identifier)["state"] == "canceled"


def test_incomplete_historical_job_does_not_break_new_starts(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    incomplete = jobs.directory("a" * 32)
    incomplete.mkdir(parents=True)
    (incomplete / "request.json").write_text('{"request_hash":"incomplete"}')
    with jobs.lock("executor"):
        job = jobs.start("tests", {"paths": ["tests/test_loader_contracts.py"], "full": False})
        jobs.cancel(job["job_id"])
        assert wait(job["job_id"])["state"] == "canceled"
    assert (incomplete / "request.json").exists()


@pytest.mark.unit
def test_log_capture_drains_but_bounds_retained_bytes(tmp_path):
    import io

    metrics = {}
    jobs.capture_log(io.BytesIO(b"x" * 10000), tmp_path / "log", metrics, limit=100)
    assert (tmp_path / "log").stat().st_size == 100
    assert metrics == {"log_truncated": True, "log_bytes": 100}


@pytest.mark.unit
def test_queued_input_change_fails_explicitly_before_execution(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    root = jobs.directory("c" * 32)
    root.mkdir(parents=True)
    jobs.save(
        root / "request.json",
        {"operation": "tests", "arguments": {"paths": [], "full": True}, "input_sha256": "old"},
    )
    monkeypatch.setattr(jobs, "input_identity", lambda *args: {"changed": True})
    assert jobs.execute("c" * 32) == 1
    assert "inputs changed" in json.loads((root / "result.json").read_text())["message"]


@pytest.mark.unit
def test_execution_owns_lease_and_recovers_without_supervisor(monkeypatch, tmp_path):
    import threading

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    identifier = "b" * 32
    root = jobs.directory(identifier)
    root.mkdir(parents=True)
    jobs.save(
        root / "state.json", {"job_id": identifier, "state": "queued", "heartbeat": time.time()}
    )
    entered = threading.Event()
    finish = threading.Event()

    def execute(_):
        entered.set()
        assert finish.wait(5)
        return 0

    monkeypatch.setattr(jobs, "execute", execute)
    thread = threading.Thread(target=jobs.managed_execute, args=(identifier,))
    thread.start()
    try:
        assert entered.wait(5)
        with jobs.lock("executor") as acquired:
            assert not acquired
        jobs.cancel(identifier)
        assert jobs.status(identifier)["state"] == "running"
    finally:
        finish.set()
        thread.join(5)
    assert jobs.status(identifier)["state"] == "canceled"


@pytest.mark.skipif(
    __import__("os").name == "nt", reason="POSIX process-group regression; Windows uses taskkill /T"
)
def test_cancel_kills_descendant_that_ignores_termination():
    import subprocess
    import sys

    child = "import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print(os.getpid(),flush=True); time.sleep(60)"
    parent = f"import subprocess,sys; p=subprocess.Popen([sys.executable,'-c',{child!r}]); p.wait()"
    process = subprocess.Popen(
        [sys.executable, "-c", parent], start_new_session=True, stdout=subprocess.PIPE, text=True
    )
    try:
        pid = int(process.stdout.readline())
        jobs._kill_tree(process)
        state = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True, check=False
        ).stdout.strip()
        assert not state or state.startswith("Z")
    finally:
        if process.poll() is None:
            jobs._kill_tree(process)
