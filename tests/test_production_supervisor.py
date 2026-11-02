"""Synthetic supervision boundaries; no production assets or real renderers."""

import os
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from ocf_tools import production_supervisor as supervisor


def identity(pid):
    return {
        "pid": pid,
        "start_ticks": str(pid),
        "boot_id": "fixture",
        "cgroup": "0::/app.slice/ocf-test.service",
        "command_sha256": "fixture",
    }


@pytest.mark.unit
def test_watchdog_rate_limit_allows_routine_timer_cadence():
    root = Path(__file__).resolve().parents[1]
    unit = root / "deploy/systemd/ocf-production-watchdog.service.in"
    timer = root / "deploy/systemd/ocf-production-watchdog.timer.in"
    settings = dict(
        line.split("=", 1)
        for line in unit.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    assert "OnCalendar=" in timer.read_text()
    # Three nominal 20-second checks per minute leave no headroom for the
    # documented five-second failure restart; this formerly caused start-limit-hit.
    assert int(settings["StartLimitBurst"]) >= 12
    assert int(settings["StartLimitIntervalSec"]) == 60


@pytest.fixture
def config(tmp_path):
    status = tmp_path / "status.json"
    supervisor.write_json(status, {"sessions": {"fixture": {"state": "pending"}}})
    return {
        "state_directory": str(tmp_path / "supervision"),
        "batch_status": str(status),
        "worker_log": str(tmp_path / "worker.log"),
        "working_directory": str(tmp_path),
        "worker_command": [sys.executable, "-c", "pass"],
        "reconcile_command": ["synthetic"],
        "owner_unit": "ocf-test.service",
        "heartbeat_interval": 0.01,
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "change,expected",
    [
        ("none", "healthy"),
        ("missing", "missing-heartbeat"),
        ("dead-controller", "dead-or-reused-controller"),
        ("reused-controller", "dead-or-reused-controller"),
        ("controller-cgroup", "wrong-controller-cgroup"),
        ("heartbeat", "stale-heartbeat"),
        ("dead-worker", "dead-or-reused-worker"),
        ("reused-worker", "dead-or-reused-worker"),
        ("worker-cgroup", "wrong-worker-cgroup"),
        ("stalled", "stalled-progress"),
        ("reconciling", "healthy-reconciliation"),
        ("reconcile-timeout", "reconciliation-timeout"),
        ("paused", "paused"),
    ],
)
def test_health_is_not_just_pid_or_cpu(change, expected):
    controller, worker = identity(1), identity(2)
    heartbeat = {
        "controller": deepcopy(controller),
        "worker": deepcopy(worker),
        "phase": "running",
        "at": 100,
        "last_progress_at": 100,
        "phase_deadline": 300,
    }
    if change == "missing":
        heartbeat = None
    elif change == "dead-controller":
        controller = None
    elif change == "reused-controller":
        controller["start_ticks"] = "different"
    elif change == "controller-cgroup":
        controller["cgroup"] = "0::/opencode-v2-server.service"
        heartbeat["controller"] = deepcopy(controller)
    elif change == "heartbeat":
        heartbeat["at"] = 0
    elif change == "dead-worker":
        worker = None
    elif change == "reused-worker":
        worker["command_sha256"] = "unrelated"
    elif change == "worker-cgroup":
        worker["cgroup"] = "0::/unrelated.service"
        heartbeat["worker"] = deepcopy(worker)
    elif change == "stalled":
        heartbeat["last_progress_at"] = 0
    elif change in {"reconciling", "reconcile-timeout"}:
        heartbeat["phase"] = "reconciling"
        heartbeat["phase_deadline"] = 300 if change == "reconciling" else 10
    elif change == "paused":
        heartbeat["phase"] = "paused"
    assert (
        supervisor.classify_health(
            heartbeat,
            controller,
            worker,
            now=120,
            heartbeat_timeout=75,
            progress_timeout=100,
            expected_unit="ocf-test.service",
        )
        == expected
    )


@pytest.mark.unit
def test_process_identity_handles_spaces_zombies_and_pid_reuse(tmp_path):
    p = tmp_path / "123"
    p.mkdir()
    values = ["S", "1"] + ["0"] * 17 + ["original-start"]
    (p / "stat").write_text("123 (name with spaces) " + " ".join(values))
    (p / "cgroup").write_text("0::/ocf-test.service")
    (p / "cmdline").write_bytes(b"worker\0fixture")
    boot = tmp_path / "sys/kernel/random/boot_id"
    boot.parent.mkdir(parents=True)
    boot.write_text("boot-fixture")
    original = supervisor.process_identity(123, tmp_path)
    assert original["start_ticks"] == "original-start"
    (p / "cmdline").write_bytes(b"unrelated")
    assert supervisor.process_identity(123, tmp_path) != original
    (p / "stat").write_text("123 (name) Z " + " ".join(values[1:]))
    assert supervisor.process_identity(123, tmp_path) is None
    assert supervisor.process_identity(999, tmp_path) is None


@pytest.mark.unit
def test_atomic_json_rejects_nonfinite_and_nonregular_files(tmp_path):
    path = tmp_path / "state.json"
    supervisor.write_json(path, {"verified": 1})
    assert supervisor.read_json(path) == {"verified": 1}
    path.write_text('{"at":NaN}')
    with pytest.raises(ValueError):
        supervisor.read_json(path)
    with pytest.raises((ValueError, OSError)):
        supervisor.read_json(tmp_path)


@pytest.mark.unit
def test_changed_or_missing_frozen_input_is_detected(config, tmp_path):
    import hashlib

    path = tmp_path / "frozen.fixture"
    path.write_bytes(b"original")
    config["frozen_files"] = {str(path): hashlib.sha256(b"original").hexdigest()}
    assert supervisor.changed_inputs(config) == []
    path.write_bytes(b"changed")
    assert supervisor.changed_inputs(config) == [str(path)]
    path.unlink()
    assert supervisor.changed_inputs(config) == [str(path)]


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "linux", reason="Linux systemd process leases")
def test_duplicate_lease_fifo_and_recovery_budget(config, tmp_path):
    with supervisor.lease(tmp_path / "owner.lock") as first:
        assert first
        with supervisor.lease(tmp_path / "owner.lock") as duplicate:
            assert not duplicate
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError):
        supervisor.read_json(fifo)
    assert all(supervisor.budget(config, "fixture crash", "fixture") for _ in range(3))
    assert not supervisor.budget(config, "fixture crash", "fixture")


class FakeChild:
    pid = 222

    def __init__(self, code):
        self.code = code

    def poll(self):
        return self.code

    def wait(self, timeout=None):
        return self.code


@pytest.mark.unit
@pytest.mark.parametrize(
    "code,terminal,allowed,expected",
    [
        (0, True, True, 0),
        (0, False, True, 1),
        (7, False, True, 1),
        (-9, False, True, 1),
        (0, False, False, 0),
    ],
)
def test_worker_exit_and_unfinished_success_are_not_completion(
    config, monkeypatch, code, terminal, allowed, expected
):
    from contextlib import contextmanager

    @contextmanager
    def lease(_path):
        yield True

    monkeypatch.setattr(supervisor, "lease", lease)
    monkeypatch.setattr(supervisor, "process_identity", identity)
    replies = iter(
        [
            {"safe_to_run": True},
            {"terminal": terminal, "safe_to_run": allowed, "active_identity": "fixture"},
        ]
    )
    monkeypatch.setattr(supervisor, "execute", lambda *args, **kwargs: next(replies))
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *args, **kwargs: FakeChild(code))
    monkeypatch.setattr(supervisor, "emit", lambda *args: None)
    assert supervisor.run(config) == expected
    exit_receipt = supervisor.read_json(Path(config["state_directory"]) / "worker-exit.json")
    assert exit_receipt["exit_code"] == code


@pytest.mark.unit
def test_reconciliation_block_and_controller_errors_do_not_dispatch(config, monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def lease(_path):
        yield True

    monkeypatch.setattr(supervisor, "lease", lease)
    monkeypatch.setattr(supervisor, "process_identity", identity)
    monkeypatch.setattr(supervisor, "emit", lambda *args: None)
    monkeypatch.setattr(
        supervisor,
        "execute",
        lambda *args, **kwargs: {"safe_to_run": False, "reason": "corrupt output"},
    )
    monkeypatch.setattr(
        supervisor.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("must not dispatch")
    )
    assert supervisor.run(config) == 0
    assert (
        supervisor.read_json(Path(config["state_directory"]) / "paused.json")["reason"]
        == "reconciliation-blocked"
    )


@pytest.mark.unit
def test_escalation_reservation_deduplicates_denial(config, monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def lease(_path):
        yield True

    calls = []
    config["escalation_command"] = ["fixture-bridge"]
    monkeypatch.setattr(supervisor, "lease", lease)

    def denied(*args, **kwargs):
        calls.append(args)
        raise RuntimeError("router denied")

    monkeypatch.setattr(supervisor, "execute", denied)
    supervisor.emit(config, "engineering-required", "fixture")
    supervisor.emit(config, "engineering-required", "fixture")
    assert len(calls) == 1
    receipts = supervisor.read_json(Path(config["state_directory"]) / "events.json")
    assert next(iter(receipts.values()))["delivery"] == "uncertain-or-denied"


@pytest.mark.unit
@pytest.mark.parametrize(
    "case,expected_action",
    [
        ("healthy", None),
        ("dead", "restart"),
        ("heartbeat", "restart"),
        ("worker", "restart"),
        ("stalled", "restart"),
        ("disk", "stop"),
        ("paused", None),
        ("terminal", None),
        ("duplicate", None),
    ],
)
def test_watchdog_failure_paths_are_bounded_and_unit_scoped(
    config, monkeypatch, case, expected_action
):
    from contextlib import contextmanager
    from types import SimpleNamespace

    root = Path(config["state_directory"])
    config["worker_exit_grace"] = 0
    supervisor.write_json(
        root / "heartbeat.json",
        {
            "controller": identity(1),
            "worker": identity(2),
            "phase": "running",
            "at": 100,
            "last_progress_at": 100,
        },
    )

    @contextmanager
    def lease(_path):
        yield case != "duplicate"

    monkeypatch.setattr(supervisor, "lease", lease)
    monkeypatch.setattr(supervisor.time, "time", lambda: 120)
    monkeypatch.setattr(
        supervisor.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=0 if case == "disk" else 100 * 1024**3),
    )
    monkeypatch.setattr(
        supervisor,
        "process_identity",
        lambda pid: None if case == "dead" or (case == "worker" and pid == 2) else identity(pid),
    )
    monkeypatch.setattr(
        supervisor.subprocess,
        "check_output",
        lambda *args, **kwargs: "ActiveState=active\nMainPID=1\nControlGroup=/ocf-test.service\n",
    )
    calls = []
    monkeypatch.setattr(supervisor.subprocess, "run", lambda args, **kwargs: calls.append(args))
    monkeypatch.setattr(supervisor, "emit", lambda *args: None)
    if case in {"heartbeat", "stalled"}:
        data = supervisor.read_json(root / "heartbeat.json")
        data["at" if case == "heartbeat" else "last_progress_at"] = -10000
        supervisor.write_json(root / "heartbeat.json", data)
    if case == "paused":
        supervisor.write_json(root / "paused.json", {"reason": "operator pause"})
    if case == "terminal":
        supervisor.write_json(root / "reconciliation.json", {"terminal": True})
    assert supervisor.watchdog(config) == 0
    if expected_action:
        assert calls[0] == [
            "systemctl",
            "--user",
            "--no-block",
            expected_action,
            "ocf-test.service",
        ]
    else:
        assert calls == []
