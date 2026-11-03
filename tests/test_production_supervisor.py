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


@pytest.mark.unit
@pytest.mark.parametrize("reply", ["", '{"safe_to_run": true}'])
def test_execute_preserves_scoped_environment_and_timeout(config, monkeypatch, reply):
    from types import SimpleNamespace

    config["environment"] = {"OCF_SYNTHETIC": "fixture"}
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=reply, stderr="")

    monkeypatch.setattr(supervisor.subprocess, "run", run)
    assert supervisor.execute(["fixture"], config, timeout=9) == (
        {"safe_to_run": True} if reply else {}
    )
    assert calls[0][1]["env"]["OCF_SYNTHETIC"] == "fixture"
    assert calls[0][1]["timeout"] == 9
    assert calls[0][1]["cwd"] == config["working_directory"]


@pytest.mark.unit
def test_execute_failed_operation_never_looks_successful(config, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        supervisor.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=7, stdout="{}", stderr="synthetic error"),
    )
    with pytest.raises(RuntimeError, match="exited 7"):
        supervisor.execute(["fixture"], config)


@pytest.mark.unit
@pytest.mark.parametrize("action", ["pause", "resume", "status", "run", "watchdog"])
def test_cli_controls_only_its_explicit_unit(config, tmp_path, monkeypatch, capsys, action):
    path = tmp_path / "config.json"
    supervisor.write_json(path, config)
    monkeypatch.setattr(supervisor.sys, "platform", "linux")
    monkeypatch.setattr(supervisor.sys, "argv", ["supervisor", action, "--config", str(path)])
    calls = []
    monkeypatch.setattr(
        supervisor.subprocess, "run", lambda command, **kwargs: calls.append(command)
    )
    monkeypatch.setattr(supervisor, "run", lambda value: 21)
    monkeypatch.setattr(supervisor, "watchdog", lambda value: 22)
    root = Path(config["state_directory"])
    supervisor.write_json(root / "paused.json", {"reason": "fixture"})
    result = supervisor.main()
    if action == "pause":
        assert supervisor.read_json(root / "paused.json")["reason"] == "explicit operator pause"
        assert calls == [["systemctl", "--user", "stop", "ocf-test.service"]]
    elif action == "resume":
        assert not (root / "paused.json").exists()
        assert calls == [["systemctl", "--user", "start", "ocf-test.service"]]
    elif action == "status":
        assert capsys.readouterr().out.strip() == "{}"
        assert calls == []
    else:
        assert result == (21 if action == "run" else 22)


@pytest.mark.unit
@pytest.mark.parametrize(
    "platform,unit", [("win32", "ocf-test.service"), ("linux", "unrelated.service")]
)
def test_cli_rejects_unsupported_platform_and_unscoped_unit(
    config, tmp_path, monkeypatch, platform, unit
):
    config["owner_unit"] = unit
    path = tmp_path / "config.json"
    supervisor.write_json(path, config)
    monkeypatch.setattr(supervisor.sys, "platform", platform)
    monkeypatch.setattr(supervisor.sys, "argv", ["supervisor", "run", "--config", str(path)])
    with pytest.raises(SystemExit) as error:
        supervisor.main()
    assert error.value.code == 2


@pytest.fixture
def watched(config, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    @contextmanager
    def lease(path):
        yield True

    root = Path(config["state_directory"])
    heartbeat = {
        "controller": identity(1),
        "worker": identity(2),
        "phase": "running",
        "at": 100,
        "last_progress_at": 100,
        "worker_started_at": 100,
        "active_reservations": 1,
        "batch_owner_pid": 2,
        "input_sha256": "a" * 64,
    }
    supervisor.write_json(root / "heartbeat.json", heartbeat)
    now = [120]
    properties = ["ActiveState=active\nMainPID=1\nControlGroup=/ocf-test.service\n"]
    calls, events = [], []
    monkeypatch.setattr(supervisor, "lease", lease)
    monkeypatch.setattr(supervisor.time, "time", lambda: now[0])
    monkeypatch.setattr(
        supervisor.shutil, "disk_usage", lambda path: SimpleNamespace(free=100 * 1024**3)
    )
    monkeypatch.setattr(supervisor, "process_identity", identity)
    monkeypatch.setattr(supervisor.subprocess, "check_output", lambda *a, **k: properties[0])
    monkeypatch.setattr(supervisor.subprocess, "run", lambda args, **k: calls.append(args))
    monkeypatch.setattr(supervisor, "emit", lambda *args: events.append(args))
    return config, root, heartbeat, now, properties, calls, events


@pytest.mark.unit
@pytest.mark.parametrize(
    "kind",
    ["batch-status", "duplicates", "reservation", "ownership", "main-pid", "budget", "integrity"],
)
def test_watchdog_protects_reservations_integrity_and_budgets(watched, kind):
    config, root, heartbeat, now, properties, calls, events = watched
    if kind == "batch-status":
        heartbeat["batch_status_error"] = "invalid fixture"
    elif kind == "duplicates":
        heartbeat["active_reservations"] = 2
    elif kind == "reservation":
        config["verify_batch_owner"] = True
        heartbeat["input_sha256"] = "invalid"
    elif kind == "ownership":
        config["verify_batch_owner"] = True
        heartbeat["worker_started_at"] = 0
        heartbeat["batch_owner_pid"] = 999
    elif kind == "main-pid":
        properties[0] = "ActiveState=active\nMainPID=999\n"
    elif kind == "budget":
        heartbeat["at"] = 0
        config["max_recoveries_per_job"] = 0
    elif kind == "integrity":
        config["frozen_files"] = {str(root / "missing-frozen.fixture"): "0" * 64}
    supervisor.write_json(root / "heartbeat.json", heartbeat)
    assert supervisor.watchdog(config) == 0
    if kind in {"integrity", "budget"}:
        assert (root / "paused.json").exists()
        assert events
        assert calls == (
            [["systemctl", "--user", "--no-block", "stop", "ocf-test.service"]]
            if kind == "integrity"
            else []
        )
    else:
        assert calls == [["systemctl", "--user", "--no-block", "restart", "ocf-test.service"]]


@pytest.mark.unit
def test_service_transition_is_tolerated_only_until_its_deadline(watched):
    config, root, heartbeat, now, properties, calls, events = watched
    properties[0] = "ActiveState=deactivating\nMainPID=1\n"
    config["transition_timeout"] = 30
    assert supervisor.watchdog(config) == 0
    assert calls == []
    assert supervisor.read_json(root / "watchdog.json")["health"] == "healthy-service-transition"
    now[0] += 31
    assert supervisor.watchdog(config) == 0
    assert calls == [["systemctl", "--user", "--no-block", "restart", "ocf-test.service"]]


@pytest.mark.unit
def test_worker_exit_reconciliation_has_bounded_grace(watched, monkeypatch):
    config, root, heartbeat, now, properties, calls, events = watched
    monkeypatch.setattr(
        supervisor, "process_identity", lambda pid: None if pid == 2 else identity(pid)
    )
    assert supervisor.watchdog(config) == 0
    assert calls == []
    assert (
        supervisor.read_json(root / "watchdog.json")["health"]
        == "healthy-worker-exit-reconciliation"
    )
    now[0] += 11
    assert supervisor.watchdog(config) == 0
    assert calls == [["systemctl", "--user", "--no-block", "restart", "ocf-test.service"]]


@pytest.mark.unit
def test_disk_pause_recovers_only_after_reserve_returns(watched):
    config, root, heartbeat, now, properties, calls, events = watched
    supervisor.write_json(root / "paused.json", {"reason": "disk-safeguard"})
    assert supervisor.watchdog(config) == 0
    assert not (root / "paused.json").exists()
    assert calls == []


@pytest.mark.unit
def test_progress_observes_descendant_io_not_cpu(config, tmp_path, monkeypatch):
    proc = tmp_path / "synthetic-proc"
    proc.mkdir()
    for pid, parent in [(1, 0), (2, 1), (3, 2)]:
        folder = proc / str(pid)
        folder.mkdir()
        (folder / "stat").write_text(f"{pid} (fixture process) S {parent}")
    (proc / "1/io").write_text("read_bytes: 0")
    (proc / "2/io").write_text("write_bytes: 10")
    (proc / "nonnumeric").mkdir()
    (proc / "4").mkdir()
    (proc / "4/stat").write_text("invalid")

    def path(value):
        value = str(value)
        return (
            proc / value.removeprefix("/proc/")
            if value.startswith("/proc/")
            else proc
            if value == "/proc"
            else Path(value)
        )

    monkeypatch.setattr(supervisor, "Path", path)
    first = supervisor.progress_token(config, identity(1))
    (proc / "2/io").write_text("write_bytes: 11")
    assert supervisor.progress_token(config, identity(1)) != first
    assert supervisor.progress_token(config, None)


@pytest.mark.unit
@pytest.mark.parametrize("case", ["terminal", "frozen-input", "paused", "budget-exhausted"])
def test_owner_preflight_and_exhausted_recovery_never_dispatch_duplicates(
    watched, monkeypatch, case
):
    config, root, heartbeat, now, properties, calls, events = watched
    monkeypatch.setattr(supervisor, "progress_token", lambda *args: "synthetic")
    monkeypatch.setattr(
        supervisor, "execute", lambda *a, **k: {"terminal": case == "terminal", "safe_to_run": True}
    )
    if case == "budget-exhausted":
        config["max_recoveries_per_job"] = 0
        monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *a, **k: FakeChild(7))
    else:
        monkeypatch.setattr(
            supervisor.subprocess, "Popen", lambda *a, **k: pytest.fail("must not dispatch")
        )
    if case == "frozen-input":
        config["frozen_files"] = {str(root / "missing.fixture"): "0" * 64}
    elif case == "paused":
        supervisor.write_json(root / "paused.json", {"reason": "operator"})
    assert supervisor.run(config) == 0
    if case == "terminal":
        assert events[-1][1] == "completed"
        assert not (root / "worker-exit.json").exists()
    elif case != "paused":
        pause = supervisor.read_json(root / "paused.json")
        assert pause["reason"] == (
            "controller-error" if case == "frozen-input" else "worker recovery budget exhausted"
        )


@pytest.mark.unit
@pytest.mark.parametrize("timeout", [False, True])
def test_owner_shutdown_is_bounded_without_real_signals(watched, monkeypatch, timeout):
    config, root, heartbeat, now, properties, calls, events = watched
    handlers = {}

    def register(sig, handler):
        handlers[sig] = handler

    class Child:
        pid = 222

        def poll(self):
            handlers[supervisor.signal.SIGINT](None, None)
            return None

        def send_signal(self, value):
            calls.append(("signal", value))

        def wait(self, timeout=None):
            if timeout == 45 and self.timeout:
                raise supervisor.subprocess.TimeoutExpired("synthetic", timeout)
            return 130

        def terminate(self):
            calls.append(("terminate",))

    child = Child()
    child.timeout = timeout
    monkeypatch.setattr(supervisor.signal, "signal", register)
    monkeypatch.setattr(supervisor, "progress_token", lambda *a: "synthetic")
    monkeypatch.setattr(supervisor, "execute", lambda *a, **k: {"safe_to_run": True})
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *a, **k: child)
    assert supervisor.run(config) == 0
    assert ("signal", supervisor.signal.SIGINT) in calls
    assert (("terminate",) in calls) == timeout
    assert supervisor.read_json(root / "worker-exit.json")["stop_requested"] is True


@pytest.mark.unit
def test_escalation_acceptance_and_unreadable_state_are_recorded_once(config, monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def lease(path):
        yield True

    monkeypatch.setattr(supervisor, "lease", lease)
    Path(config["batch_status"]).unlink()
    config["escalation_command"] = ["synthetic-bridge"]
    calls = []

    def execute(*args, **kwargs):
        calls.append(args)
        return {"acknowledged": True}

    monkeypatch.setattr(supervisor, "execute", execute)
    supervisor.emit(config, "engineering-required", "unreadable synthetic state")
    supervisor.emit(config, "engineering-required", "unreadable synthetic state")
    assert len(calls) == 1
    receipt = next(
        iter(supervisor.read_json(Path(config["state_directory"]) / "events.json").values())
    )
    assert receipt["identity"] == "unreadable-state"
    assert receipt["delivery"] == "accepted"
    assert receipt["result"] == {"acknowledged": True}
