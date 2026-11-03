"""Linux/systemd outer supervision for an existing deterministic job owner.

This module never generates audio. A configured reconciler proves safe resume;
the existing worker retains its own output reservations and content checks.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4


def read_json(path):
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 16 * 1024**2:
            raise ValueError("supervision requires a bounded regular JSON file")
        with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as stream:

            def invalid_constant(value):
                raise ValueError("non-finite JSON constant: " + value)

            return json.load(stream, parse_constant=invalid_constant)
    finally:
        os.close(fd)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(0o600)
    temporary.replace(path)


@contextlib.contextmanager
def lease(path):
    """Nonblocking process lease; subprocess exec must not inherit its descriptor."""
    import fcntl

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    acquired = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            pass
        yield acquired
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def process_identity(pid, proc=Path("/proc")):
    try:
        directory = proc / str(int(pid))
        raw = (directory / "stat").read_text()
        fields = raw.rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return {
            "pid": int(pid),
            "start_ticks": fields[19],
            "boot_id": (proc / "sys/kernel/random/boot_id").read_text().strip(),
            "cgroup": (directory / "cgroup").read_text().strip(),
            "command_sha256": hashlib.sha256((directory / "cmdline").read_bytes()).hexdigest(),
        }
    except (OSError, ValueError, IndexError):
        return None


def classify_health(
    heartbeat, controller, worker, *, now, heartbeat_timeout, progress_timeout, expected_unit
):
    if not heartbeat:
        return "missing-heartbeat"
    if not controller or controller != heartbeat.get("controller"):
        return "dead-or-reused-controller"
    if expected_unit not in controller["cgroup"].split("/"):
        return "wrong-controller-cgroup"
    if now - heartbeat["at"] > heartbeat_timeout:
        return "stale-heartbeat"
    if heartbeat["phase"] in {"reconciling", "finishing"}:
        return (
            "reconciliation-timeout"
            if now > heartbeat["phase_deadline"]
            else "healthy-reconciliation"
        )
    if heartbeat["phase"] != "running":
        return heartbeat["phase"]
    if not worker or worker != heartbeat.get("worker"):
        return "dead-or-reused-worker"
    if expected_unit not in worker["cgroup"].split("/"):
        return "wrong-worker-cgroup"
    if now - heartbeat["last_progress_at"] > progress_timeout:
        return "stalled-progress"
    if heartbeat.get("job_started_at") and now - heartbeat["job_started_at"] > 1800:
        return "healthy-long-job"
    return "healthy"


def progress_token(config, worker):
    """Receipts/log writes and process IO are evidence; CPU alone is not health."""
    values = []
    for name in [config["batch_status"], config["worker_log"]]:
        try:
            info = Path(name).stat()
            values.append((name, info.st_size, info.st_mtime_ns))
        except OSError:
            values.append((name, None))
    if worker and Path("/proc").is_dir():
        children = {worker["pid"]}
        table = {}
        for directory in Path("/proc").iterdir():
            if not directory.name.isdecimal():
                continue
            try:
                fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
                table[int(directory.name)] = int(fields[1])
            except (OSError, ValueError, IndexError):
                continue
        while True:
            expanded = children | {pid for pid, parent in table.items() if parent in children}
            if expanded == children:
                break
            children = expanded
        for pid in sorted(children):
            try:
                values.append((pid, Path(f"/proc/{pid}/io").read_text()))
            except OSError:
                continue
    return hashlib.sha256(repr(values).encode()).hexdigest()


def execute(command, config, *, timeout=600):
    environment = os.environ.copy()
    environment.update(config.get("environment", {}))
    result = subprocess.run(
        command,
        cwd=config["working_directory"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"configured operation exited {result.returncode}: {result.stderr[-2000:]}"
        )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def changed_inputs(config):
    changed = []
    for name, expected in config.get("frozen_files", {}).items():
        try:
            actual = hashlib.sha256(Path(name).read_bytes()).hexdigest()
        except OSError:
            actual = None
        if actual != expected:
            changed.append(name)
    return changed


def emit(config, kind, reason):
    root = Path(config["state_directory"])
    event = {"kind": kind, "reason": reason, "at": time.time()}
    try:
        status = read_json(config["batch_status"])
        identity = next(
            (
                key
                for key, row in status.get("sessions", {}).items()
                if row["state"] in {"running", "failed"}
            ),
            "collection",
        )
        source = status.get("source_sha", "unspecified")
    except (OSError, ValueError, KeyError):
        identity, source = "unreadable-state", "unknown"
    event.update(identity=identity, source_sha=source)
    event_id = hashlib.sha256(
        json.dumps(
            {"kind": kind, "reason": reason, "identity": identity, "source": source}, sort_keys=True
        ).encode()
    ).hexdigest()
    with lease(root / "events.lock") as acquired:
        if not acquired:
            return
        receipts = read_json(root / "events.json") if (root / "events.json").exists() else {}
        if event_id in receipts:
            return
        # Write-ahead: ambiguous delivery never becomes an automatic redispatch.
        receipts[event_id] = {**event, "delivery": "reserved"}
        write_json(root / "events.json", receipts)
        write_json(root / "latest-event.json", {**event, "event_id": event_id})
        if config.get("escalation_command"):
            try:
                result = execute(
                    [*config["escalation_command"], str(root / "latest-event.json")],
                    config,
                    timeout=60,
                )
                receipts[event_id].update(delivery="accepted", result=result)
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
                receipts[event_id].update(delivery="uncertain-or-denied", error=str(error))
            write_json(root / "events.json", receipts)


def budget(config, reason, identity):
    root = Path(config["state_directory"])
    with lease(root / "budget.lock") as acquired:
        if not acquired:
            return False
        path = root / "recoveries.json"
        data = read_json(path) if path.exists() else {"attempts": []}
        recent = [item for item in data["attempts"] if time.time() - item["at"] < 86400]
        count = sum(item["identity"] == identity for item in recent)
        allowed = count < config.get("max_recoveries_per_job", 3) and len(recent) < config.get(
            "max_recoveries_per_day", 10
        )
        if allowed:
            recent.append({"at": time.time(), "identity": identity, "reason": reason})
            write_json(path, {"attempts": recent})
        return allowed


def run(config):
    root = Path(config["state_directory"])
    with lease(root / "controller.lock") as acquired:
        if not acquired:
            return 0
        if (root / "paused.json").exists():
            return 0
        stop = threading.Event()
        record = {
            "controller": process_identity(os.getpid()),
            "worker": None,
            "phase": "reconciling",
            "phase_deadline": time.time() + config.get("reconcile_timeout", 600),
            "last_progress_at": time.time(),
        }
        guard = threading.Lock()

        def pulse():
            token = None
            while not stop.is_set():
                with guard:
                    snapshot = dict(record)
                current = progress_token(config, snapshot["worker"])
                if current != token:
                    token = current
                    with guard:
                        record["last_progress_at"] = time.time()
                        snapshot["last_progress_at"] = record["last_progress_at"]
                snapshot["at"] = time.time()
                try:
                    status = read_json(config["batch_status"])
                    active = [
                        (key, row)
                        for key, row in status.get("sessions", {}).items()
                        if row["state"] == "running"
                    ]
                    snapshot["batch_owner_pid"] = status.get("owner_pid")
                    snapshot["active_reservations"] = len(active)
                    if active:
                        key, row = active[0]
                        snapshot["job_identity"] = key
                        snapshot["input_sha256"] = row.get("input_sha256")
                        if row.get("started_at"):
                            snapshot["job_started_at"] = datetime.fromisoformat(
                                row["started_at"]
                            ).timestamp()
                except (OSError, ValueError, KeyError) as error:
                    snapshot["batch_status_error"] = type(error).__name__
                write_json(root / "heartbeat.json", snapshot)
                stop.wait(config.get("heartbeat_interval", 10))

        thread = threading.Thread(target=pulse, daemon=True)
        thread.start()
        child = None
        previous_handlers = {
            sig: signal.signal(sig, lambda *_args: stop.set())
            for sig in [signal.SIGTERM, signal.SIGINT]
        }
        try:
            if changed_inputs(config):
                raise ValueError("frozen production input changed")
            reconciled = execute(
                config["reconcile_command"], config, timeout=config.get("reconcile_timeout", 600)
            )
            write_json(root / "reconciliation.json", reconciled)
            if reconciled.get("terminal"):
                with guard:
                    record["phase"] = "completed"
                emit(config, "completed", "collection terminal and all receipts verified")
                return 0
            if not reconciled.get("safe_to_run"):
                write_json(
                    root / "paused.json", {"reason": "reconciliation-blocked", "detail": reconciled}
                )
                emit(
                    config,
                    "engineering-required",
                    "reconciliation blocked: " + reconciled.get("reason", "unknown"),
                )
                return 0
            if stop.is_set():
                return 0
            environment = os.environ.copy()
            environment.update(config.get("environment", {}))
            Path(config["worker_log"]).parent.mkdir(parents=True, exist_ok=True)
            with open(config["worker_log"], "a", encoding="utf-8") as output:
                child = subprocess.Popen(
                    config["worker_command"],
                    cwd=config["working_directory"],
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    close_fds=True,
                )
                with guard:
                    record.update(
                        worker=process_identity(child.pid),
                        phase="running",
                        worker_started_at=time.time(),
                        last_progress_at=time.time(),
                    )
                while child.poll() is None and not stop.wait(1):
                    pass
                if stop.is_set() and child.poll() is None:
                    child.send_signal(signal.SIGINT)
                    try:
                        child.wait(timeout=45)
                    except subprocess.TimeoutExpired:
                        child.terminate()
                        child.wait(timeout=15)
                code = child.wait()
            with guard:
                record.update(
                    phase="finishing",
                    phase_deadline=time.time() + config.get("reconcile_timeout", 600),
                )
            write_json(
                root / "worker-exit.json",
                {
                    "at": time.time(),
                    "exit_code": code,
                    "worker": record["worker"],
                    "stop_requested": stop.is_set(),
                },
            )
            if stop.is_set():
                return 0  # systemd cleans the whole dedicated cgroup before a later resume.
            if code:
                status = read_json(config["batch_status"])
                identity = next(
                    (
                        key
                        for key, row in status.get("sessions", {}).items()
                        if row["state"] in {"running", "failed"}
                    ),
                    "collection",
                )
                if budget(config, f"worker exited {code}", identity):
                    return 1  # Clean orphaned worker descendants before reconciliation.
                write_json(
                    root / "paused.json",
                    {"reason": "worker recovery budget exhausted", "exit_code": code},
                )
                emit(
                    config, "engineering-required", "worker recovery budget exhausted: " + identity
                )
                return 0
            final = execute(
                config["reconcile_command"], config, timeout=config.get("reconcile_timeout", 600)
            )
            write_json(root / "reconciliation.json", final)
            if final.get("terminal"):
                with guard:
                    record["phase"] = "completed"
                emit(config, "completed", "collection terminal and all receipts verified")
                return 0
            if stop.is_set():
                return 0
            identity = final.get("active_identity", "collection")
            if final.get("safe_to_run") and budget(
                config, f"worker exited {code} before terminal queue", identity
            ):
                return 1  # systemd restarts only after this owner and its children exit.
            write_json(
                root / "paused.json", {"reason": "recovery-blocked-or-exhausted", "detail": final}
            )
            emit(config, "engineering-required", "unfinished queue needs engineering: " + identity)
            return 0
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            write_json(root / "paused.json", {"reason": "controller-error", "error": str(error)})
            emit(config, "engineering-required", "controller error: " + type(error).__name__)
            return 0
        finally:
            stop.set()
            thread.join(timeout=15)
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
            write_json(root / "heartbeat.json", {**record, "at": time.time(), "owner_exited": True})


def watchdog(config):
    root = Path(config["state_directory"])
    with lease(root / "watchdog.lock") as acquired:
        if not acquired:
            return 0
        if changed_inputs(config):
            write_json(root / "paused.json", {"reason": "frozen-input-changed"})
            subprocess.run(
                ["systemctl", "--user", "--no-block", "stop", config["owner_unit"]],
                check=True,
                timeout=15,
            )
            emit(config, "integrity-blocked", "frozen production input changed")
            return 0
        free = shutil.disk_usage(config["working_directory"]).free
        minimum = config.get("min_disk_free_bytes", 16 * 1024**3)
        if (root / "paused.json").exists():
            paused = read_json(root / "paused.json")
            if paused.get("reason") == "disk-safeguard" and free >= minimum + 1024**3:
                (root / "paused.json").unlink()
            else:
                return 0
        if free < minimum:
            write_json(root / "paused.json", {"reason": "disk-safeguard", "free_bytes": free})
            subprocess.run(
                ["systemctl", "--user", "--no-block", "stop", config["owner_unit"]],
                check=True,
                timeout=15,
            )
            emit(config, "resource-blocked", "disk safety reserve reached")
            return 0
        reconciled = (
            read_json(root / "reconciliation.json")
            if (root / "reconciliation.json").exists()
            else {}
        )
        if reconciled.get("terminal"):
            return 0
        heartbeat = (
            read_json(root / "heartbeat.json") if (root / "heartbeat.json").exists() else None
        )
        controller = (
            process_identity(heartbeat["controller"]["pid"])
            if heartbeat and heartbeat.get("controller")
            else None
        )
        worker = (
            process_identity(heartbeat["worker"]["pid"])
            if heartbeat and heartbeat.get("worker")
            else None
        )
        health = classify_health(
            heartbeat,
            controller,
            worker,
            now=time.time(),
            heartbeat_timeout=config.get("heartbeat_timeout", 75),
            progress_timeout=config.get("progress_timeout", 5400),
            expected_unit=config["owner_unit"],
        )
        worker_gone_since = None
        if health == "dead-or-reused-worker" and controller:
            previous = (
                read_json(root / "watchdog.json") if (root / "watchdog.json").exists() else {}
            )
            worker_gone_since = previous.get("worker_gone_since") or time.time()
            if time.time() - worker_gone_since < config.get("worker_exit_grace", 10):
                health = "healthy-worker-exit-reconciliation"
        if heartbeat and health.startswith("healthy") and heartbeat.get("phase") == "running":
            if heartbeat.get("batch_status_error"):
                health = "invalid-batch-status"
            elif heartbeat.get("active_reservations", 0) > 1:
                health = "duplicate-output-reservations"
            elif (
                config.get("verify_batch_owner")
                and heartbeat.get("active_reservations") == 1
                and len(str(heartbeat.get("input_sha256", ""))) != 64
            ):
                health = "invalid-output-reservation"
            elif (
                config.get("verify_batch_owner")
                and worker
                and time.time() - heartbeat.get("worker_started_at", 0) > 30
                and heartbeat.get("batch_owner_pid") != worker["pid"]
            ):
                health = "lost-batch-ownership"
        service = subprocess.check_output(
            [
                "systemctl",
                "--user",
                "show",
                config["owner_unit"],
                "-p",
                "ActiveState",
                "-p",
                "MainPID",
                "-p",
                "ControlGroup",
            ],
            text=True,
            timeout=15,
        )
        properties = dict(line.split("=", 1) for line in service.splitlines() if "=" in line)
        transition_since = None
        if properties.get("ActiveState") in {"activating", "deactivating"}:
            previous = (
                read_json(root / "watchdog.json") if (root / "watchdog.json").exists() else {}
            )
            transition_since = previous.get("transition_since") or time.time()
            health = (
                "healthy-service-transition"
                if time.time() - transition_since < config.get("transition_timeout", 720)
                else "service-transition-timeout"
            )
        elif controller and int(properties.get("MainPID", 0)) != controller["pid"]:
            health = "wrong-service-main-pid"
        write_json(
            root / "watchdog.json",
            {
                "at": time.time(),
                "health": health,
                "transition_since": transition_since,
                "worker_gone_since": worker_gone_since,
                "watchdog": process_identity(os.getpid()),
            },
        )
        if health.startswith("healthy"):
            return 0
        status = read_json(config["batch_status"])
        identity = next(
            (key for key, row in status.get("sessions", {}).items() if row["state"] == "running"),
            "collection",
        )
        if (
            heartbeat
            and time.time() - heartbeat["at"] < config.get("restart_delay", 30)
            and heartbeat.get("owner_exited")
        ):
            return 0
        if budget(config, health, identity):
            subprocess.run(
                ["systemctl", "--user", "--no-block", "restart", config["owner_unit"]],
                check=True,
                timeout=15,
            )
        else:
            write_json(
                root / "paused.json",
                {"reason": "watchdog recovery budget exhausted", "health": health},
            )
            emit(config, "engineering-required", "watchdog recovery budget exhausted: " + identity)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["run", "watchdog", "pause", "resume", "status"])
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("systemd production supervision requires Linux")
    config = read_json(args.config)
    if not re.fullmatch(r"ocf-[A-Za-z0-9_.@-]+\.service", config["owner_unit"]):
        parser.error("supervision can control only explicitly configured ocf-*.service units")
    root = Path(config["state_directory"])
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.action == "pause":
        write_json(root / "paused.json", {"reason": "explicit operator pause", "at": time.time()})
        subprocess.run(["systemctl", "--user", "stop", config["owner_unit"]], check=True)
        return 0
    if args.action == "resume":
        (root / "paused.json").unlink(missing_ok=True)
        subprocess.run(["systemctl", "--user", "start", config["owner_unit"]], check=True)
        return 0
    if args.action == "status":
        print(
            json.dumps(
                {
                    name: read_json(root / name)
                    for name in ["heartbeat.json", "watchdog.json", "reconciliation.json"]
                    if (root / name).exists()
                },
                indent=2,
            )
        )
        return 0
    return run(config) if args.action == "run" else watchdog(config)


if __name__ == "__main__":
    raise SystemExit(main())
