"""Persistent local allowlisted jobs; one executor, explicit starts, no shell API."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .paths import REPO_ROOT, work_path, work_root, workspace_environment
from .utils import OCFError, sha256_of_file, write_text_atomic

TERMINAL = {"completed", "failed", "canceled"}
MAX_QUEUED = 8
MAX_RECORDS = 256
MAX_LOG_BYTES = 4 * 1024**2
TIMEOUT = 6 * 3600


def now() -> str:
    return datetime.now(UTC).isoformat()


def directory(job_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise OCFError("invalid job ID")
    return work_path("logs", "jobs", job_id)


def save(path: Path, data: dict):
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


@contextmanager
def lock(name: str, *, wait: bool = False):
    root = work_path("logs", "jobs")
    root.mkdir(parents=True, exist_ok=True)
    with (root / (name + ".lock")).open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        acquired = False
        deadline = time.monotonic() + 10
        while not acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if not wait:
                    break
                if time.monotonic() >= deadline:
                    raise OCFError("job scheduler is busy; retry shortly") from None
                time.sleep(0.05)
        try:
            yield acquired
        finally:
            if acquired:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)


def validate_request(operation: str, arguments: dict) -> dict:
    from .agent_api import owner, safe_path
    from .locale import normalize_tag

    allowed = {
        "artwork": {"function_id", "locale", "theme", "resolution"},
        "voice-audition": {"voices", "locale"},
        "voice-dataset": {"manifest"},
        "tests": {"paths", "full", "workers"},
        "plans": {"function_id", "locale", "generate"},
        "render": {"function_id", "locale", "voice", "pacing", "force"},
        "release": {"function_id", "locale", "voice", "artwork", "artwork_theme", "dry_run"},
        "validate": set(),
    }
    if operation not in allowed or set(arguments) - allowed[operation]:
        raise OCFError("operation or argument is not allowlisted")
    args = dict(arguments)
    if operation == "voice-dataset":
        manifest = safe_path(args["manifest"], work_root())
        if manifest.suffix != ".json" or manifest.stat().st_size > 2 * 1024**2:
            raise OCFError("dataset manifest must be JSON, at most 2 MiB")
        return args
    if operation == "voice-audition":
        from .indexes import load_voice_profiles

        known = {p["id"] for p in load_voice_profiles()}
        voices = args.get("voices")
        if (
            not isinstance(voices, list)
            or not 1 <= len(voices) <= 4
            or any(v not in known for v in voices)
        ):
            raise OCFError("select 1..4 installed voice profile IDs")
        if args.get("locale", "en-US") != "en-US":
            raise OCFError("the original audition script is currently en-US only")
        return args
    if operation == "artwork":
        from .artwork import BRAND

        owner(args["function_id"])
        args["locale"] = normalize_tag(args.get("locale", "en-US"))
        if args.get("theme") not in {p.stem for p in (BRAND / "themes").glob("*.json")}:
            raise OCFError(
                "MCP artwork jobs select registered themes; custom file rendering is an explicit CLI workflow"
            )
        if type(args.get("resolution")) is not int or not 256 <= args["resolution"] <= 4096:
            raise OCFError("artwork resolution must be 256..4096")
        from .artwork import load_theme

        if load_theme(args["theme"]).get("brand_revision") == "0.2.0" and args["resolution"] < 320:
            raise OCFError("refined covers require at least 320 pixels for legible typography")
        return args
    for key in ("full", "generate", "force", "dry_run"):
        if key in args and not isinstance(args[key], bool):
            raise OCFError(f"{key} must be a boolean")
    if operation == "tests":
        paths = args.get("paths", [])
        if not isinstance(paths, list) or bool(paths) == bool(args.get("full")):
            raise OCFError("select explicit test paths or full=true")
        if type(args.get("workers", 1)) is not int or args.get("workers", 1) not in (1, 2):
            raise OCFError("test workers must be 1 or 2")
        for name in paths:
            if not isinstance(name, str) or not re.fullmatch(
                r"tests/[A-Za-z0-9_/.-]+\.py(?:::[A-Za-z0-9_]+)*", name
            ):
                raise OCFError("tests must be repository test paths/node IDs, never pytest options")
            safe_path(name.split("::")[0], REPO_ROOT)
    elif operation != "validate":
        args["locale"] = normalize_tag(args.get("locale", "en-US"))
        if args.get("function_id"):
            owner(args["function_id"])
        elif operation != "plans":
            raise OCFError("a single function ID is required")
        if operation == "render":
            if not args.get("voice") or args.get("pacing") not in ("normal", "relaxed", "sleep"):
                raise OCFError("voice and valid pacing are required")
        if operation == "release":
            if args.get("artwork"):
                safe_path(args["artwork"], work_root())
            else:
                from .artwork import BRAND

                if args.get("artwork_theme") not in {
                    p.stem for p in (BRAND / "themes").glob("*.json")
                }:
                    raise OCFError(
                        "select explicit workspace artwork or a registered artwork theme"
                    )
    return args


def status(job_id: str) -> dict:
    root = directory(job_id)
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    if state["state"] not in TERMINAL and time.time() - state.get("heartbeat", 0) > 30:
        state = {
            **state,
            "state": "failed",
            "error": "worker interrupted; inspect retained artifacts; explicit new start required",
        }
    return {key: value for key, value in state.items() if key not in {"heartbeat", "worker_pid"}}


def input_identity(operation: str, args: dict) -> dict:
    """Content snapshot, checked again at execution, including collection/data inputs."""
    sources = {}
    for directory_name in (
        "scripts",
        "schemas",
        "tests",
        "functions",
        "function-content",
        "locales",
        "audio/templates",
        "audio/defaults",
        "audio/session-plans",
        "audio/background/manifests",
        "audio/background/presets",
        "audio/background/state-profiles",
        "audio/voices/profiles",
        "brand",
        "audio/voices",
    ):
        for path in sorted((REPO_ROOT / directory_name).rglob("*")):
            if (
                path.is_file()
                and not path.is_symlink()
                and path.suffix in {".py", ".json", ".yaml", ".yml", ".sbg"}
            ):
                sources[path.relative_to(REPO_ROOT).as_posix()] = sha256_of_file(path)
    for name in ("pyproject.toml", "requirements-dev.txt", "function-index.json"):
        sources[name] = sha256_of_file(REPO_ROOT / name)
    if operation == "release" and args.get("artwork"):
        from .agent_api import safe_path

        sources["artwork"] = sha256_of_file(safe_path(args["artwork"], work_root()))
    if operation == "render":
        from .locale import LocaleCatalog
        from .narration_first import _voice_profile
        from .speech_cache import voice_identity

        _, spec = _voice_profile(args["voice"], args["locale"], LocaleCatalog())
        sources["voice"] = voice_identity(spec)
    if operation == "voice-audition":
        from .locale import LocaleCatalog
        from .narration_first import _voice_profile
        from .speech_cache import voice_identity

        sources["voices"] = {
            name: voice_identity(_voice_profile(name, "en-US", LocaleCatalog())[1])
            for name in args["voices"]
        }
    if operation == "voice-dataset":
        from .agent_api import safe_path

        manifest = safe_path(args["manifest"], work_root())
        sources["dataset_manifest"] = sha256_of_file(manifest)
    return sources


def start(operation: str, arguments: dict, idempotency_key: str | None = None) -> dict:
    from .session_plans import digest

    args = validate_request(operation, arguments)
    if idempotency_key is not None and not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", idempotency_key):
        raise OCFError("idempotency key must be 1..100 letters/digits/dot/underscore/hyphen")
    sources = input_identity(operation, args)
    request_hash = digest({"operation": operation, "arguments": args, "sources": sources})
    with lock("scheduler", wait=True):
        active = 0
        records = sorted(work_path("logs", "jobs").glob("*/request.json"))
        if len(records) >= MAX_RECORDS:
            raise OCFError(
                "job record limit reached; archive reviewed local job records before starting more"
            )
        for path in records:
            try:
                request = json.loads(path.read_text(encoding="utf-8"))
                previous = status(path.parent.name)
                if "request_hash" not in request:
                    continue
            except (OSError, ValueError, KeyError, TypeError):
                # Incomplete publication never spawned a worker; retain it for
                # diagnostics without disabling unrelated jobs.
                continue
            same_key = (
                idempotency_key is not None and request.get("idempotency_key") == idempotency_key
            )
            same_work = request["request_hash"] == request_hash
            if same_key:
                if not same_work:
                    raise OCFError("idempotency key already belongs to different inputs")
                return {**previous, "reused": True}
            if previous["state"] not in TERMINAL:
                active += 1
                if same_work:
                    return {**previous, "reused": True}
        if active >= MAX_QUEUED:
            raise OCFError("job queue is full (8 active/queued maximum)")
        job_id = uuid4().hex
        root = directory(job_id)
        root.mkdir(parents=True)
        save(
            root / "request.json",
            {
                "operation": operation,
                "arguments": args,
                "request_hash": request_hash,
                "input_sha256": digest(sources),
                "idempotency_key": idempotency_key,
            },
        )
        state = {
            "job_id": job_id,
            "operation": operation,
            "state": "queued",
            "created_at": now(),
            "started_at": None,
            "completed_at": None,
            "progress": "waiting for the single executor",
            "heartbeat": time.time(),
            "log": str((root / "job.log").relative_to(work_root())),
            "result": str((root / "result.json").relative_to(work_root())),
        }
        save(root / "state.json", state)
        env = workspace_environment()
        env["PYTHONPATH"] = str(REPO_ROOT / "scripts")
        command = [sys.executable, "-m", "ocf_tools.dev_jobs", "--worker", job_id]
        try:
            with (root / "worker.log").open("ab") as log:
                subprocess.Popen(
                    command,
                    cwd=REPO_ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    **(
                        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                        if os.name == "nt"
                        else {"start_new_session": True}
                    ),
                )
        except OSError as exc:
            save(
                root / "state.json",
                {**state, "state": "failed", "completed_at": now(), "error": str(exc)},
            )
            raise
    return status(job_id)


def cancel(job_id: str) -> dict:
    current = status(job_id)
    if current["state"] not in TERMINAL:
        (directory(job_id) / "cancel").touch()
    return {
        **current,
        "cancel_requested": current["state"] not in TERMINAL,
        "note": "canceled is reported only after the worker stops the owned process tree",
    }


def job_result(job_id: str, *, offset: int = 0, limit: int = 20) -> dict:
    from .agent_api import page

    current = status(job_id)
    path = directory(job_id) / "result.json"
    if current["state"] not in TERMINAL or not path.is_file():
        return current
    result = json.loads(path.read_text(encoding="utf-8"))
    if "diagnostics" in result:
        result["diagnostics"] = page(result["diagnostics"], offset, limit)
    if len(json.dumps(result)) > 16000:
        result = {
            "status": result.get("status"),
            "truncated": True,
            "artifact": current["result"],
            "message": "Detailed result retained locally; request targeted scope for smaller output.",
        }
    return {**current, "data": result}


def _kill_tree(process):
    if os.name == "nt":
        if process.poll() is not None:
            return
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            # Do not reap the leader before escalation: its reserved PID also
            # reserves the owned process-group identity while descendants exit.
            time.sleep(0.2)
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Darwin may return EPERM, rather than ESRCH, when only zombies
            # remain in the group. Never swallow a real live-process failure.
            if not _finished(process) or _group_has_live_members(process.pid):
                raise
    process.wait(timeout=10)


def _group_has_live_members(group_id: int) -> bool:
    result = subprocess.run(
        ["ps", "-A", "-o", "pgid=", "-o", "stat="], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise OCFError("could not verify process-group termination")
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == str(group_id) and not fields[1].startswith("Z"):
            return True
    return False


def _finished(process):
    if os.name != "nt" and hasattr(os, "waitid"):
        return os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
    return process.poll() is not None


def capture_log(stream, path: Path, metrics: dict, limit: int = MAX_LOG_BYTES):
    kept = 0
    with path.open("wb") as target:
        while chunk := stream.read(65536):
            remaining = max(0, limit - kept)
            target.write(chunk[:remaining])
            kept += min(len(chunk), remaining)
            if len(chunk) > remaining:
                metrics["log_truncated"] = True
    metrics["log_bytes"] = kept


def worker(job_id: str):
    root = directory(job_id)
    env = workspace_environment()
    env["PYTHONPATH"] = str(REPO_ROOT / "scripts")
    child = subprocess.Popen(
        [sys.executable, "-m", "ocf_tools.dev_jobs", "--execute", job_id],
        cwd=REPO_ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **(
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if os.name == "nt"
            else {"start_new_session": True}
        ),
    )
    metrics = {"log_truncated": False}
    reader = threading.Thread(
        target=capture_log, args=(child.stdout, root / "job.log", metrics), daemon=True
    )
    reader.start()
    started = time.monotonic()
    stopped = None
    try:
        while not _finished(child):
            if (root / "cancel").exists() or time.monotonic() - started > TIMEOUT:
                stopped = "canceled" if (root / "cancel").exists() else "failed"
                break
            time.sleep(0.2)
    finally:
        cleanup_error = None
        try:
            _kill_tree(child)
        except (OSError, OCFError, subprocess.SubprocessError) as exc:
            cleanup_error = str(exc)
        reader.join(timeout=10)
        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
        if cleanup_error:
            state.update(
                state="failed",
                progress="process cleanup could not be verified",
                error=cleanup_error,
            )
        elif stopped:
            state.update(state=stopped, progress="owned process tree stopped")
        elif state["state"] not in TERMINAL:
            state.update(
                state="failed", progress="execution process exited without a verified result"
            )
        state.update(completed_at=now(), heartbeat=time.time(), **metrics)
        save(root / "state.json", state)


def managed_execute(job_id: str):
    """Execution owns the lease, so supervisor failure cannot release capacity."""
    root = directory(job_id)
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    while True:
        state["heartbeat"] = time.time()
        save(root / "state.json", state)
        if (root / "cancel").exists():
            state.update(state="canceled", completed_at=now(), progress="canceled before execution")
            save(root / "state.json", state)
            return
        with lock("executor") as acquired:
            if not acquired:
                time.sleep(0.2)
                continue
            state.update(
                state="running",
                started_at=now(),
                progress="executing canonical service",
                worker_pid=os.getpid(),
            )
            save(root / "state.json", state)
            stop = threading.Event()

            def pulse():
                while not stop.wait(1):
                    state["heartbeat"] = time.time()
                    save(root / "state.json", state)

            heartbeat = threading.Thread(target=pulse, daemon=True)
            heartbeat.start()
            try:
                code = execute(job_id)
            finally:
                stop.set()
                heartbeat.join()
            state.update(
                state="completed" if code == 0 else "failed", progress="verified result available"
            )
            if (root / "cancel").exists():
                state.update(
                    state="canceled", progress="cancellation completed at service boundary"
                )
            state.update(completed_at=now(), heartbeat=time.time())
            save(root / "state.json", state)
            return code


def execute(job_id: str) -> int:
    root = directory(job_id)
    request = json.loads((root / "request.json").read_text(encoding="utf-8"))
    operation = request["operation"]
    args = validate_request(operation, request["arguments"])
    try:
        from .session_plans import digest

        if digest(input_identity(operation, args)) != request["input_sha256"]:
            raise OCFError("inputs changed since enqueue; explicit new job required")
        if operation == "artwork":
            from .artwork import generate_cover

            result = generate_cover(**args)
            result = {
                k: result[k]
                for k in (
                    "path",
                    "sha256",
                    "fingerprint",
                    "review_status",
                    "human_approval",
                    "cache",
                    "title_lines",
                )
            }
            passed = True
        elif operation == "voice-audition":
            from .custom_voices import audition

            generated = audition(**args)
            result = {
                "output_directory": generated["output_directory"],
                "outputs": [
                    {k: v for k, v in row.items() if k != "segments"}
                    for row in generated["report"]["outputs"]
                ],
                "listening_approval": None,
            }
            passed = True
        elif operation == "voice-dataset":
            from .agent_api import safe_path
            from .voice_datasets import validate_dataset

            result = validate_dataset(safe_path(args["manifest"], work_root()))
            passed = result["errors"] == 0
        elif operation == "render":
            from .bulk_render import render_many

            result = render_many([args.pop("function_id")], **args)
            passed = result["failed"] == 0
        elif operation == "plans":
            from .generators import indexes_are_fresh
            from .session_plans import generate_plans

            result = generate_plans(
                [args["function_id"]] if args.get("function_id") else None,
                locale=args["locale"],
                check=not args["generate"],
            )
            result.pop("files", None)
            passed = True
            if not args["generate"]:
                fresh = indexes_are_fresh()
                result["indexes"] = fresh
                passed = fresh[0] if isinstance(fresh, tuple) else bool(fresh)
        elif operation == "validate":
            from dataclasses import asdict

            from .validators import validate_all

            validation = validate_all()
            result = {
                "errors": len(validation.errors),
                "warnings": len(validation.warnings),
                "diagnostics": [asdict(i) for i in validation.issues],
            }
            passed = validation.ok
        elif operation == "release":
            from .agent_api import safe_path
            from .release import package_release

            result = package_release(
                args["function_id"],
                artwork=safe_path(args["artwork"], work_root()) if args.get("artwork") else None,
                artwork_theme=args.get("artwork_theme"),
                locale=args["locale"],
                voice=args.get("voice"),
                dry_run=args["dry_run"],
                output=work_path("renders", "releases", job_id),
            )
            passed = True
        else:
            command = [
                sys.executable,
                "-m",
                "pytest",
                *args["paths"],
                "--junitxml",
                str(root / "tests.xml"),
                "-q",
            ]
            if args.get("workers", 1) == 2:
                command.extend(["-n", "2", "--dist", "loadfile"])
            completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
            passed = completed.returncode == 0
            suites = (
                list(ET.parse(root / "tests.xml").getroot().iter("testsuite"))
                if (root / "tests.xml").exists()
                else []
            )
            counts = {
                key: sum(int(s.get(key, 0)) for s in suites)
                for key in ("tests", "failures", "errors", "skipped")
            }
            counts["passed"] = (
                counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
            )
            diagnostics = [
                {
                    "test": case.get("classname", "") + "::" + case.get("name", ""),
                    "message": failure.get("message", "")[:1000],
                }
                for suite in suites
                for case in suite.findall("testcase")
                for failure in case
                if failure.tag in {"failure", "error"}
            ]
            result = {**counts, "exit_code": completed.returncode, "diagnostics": diagnostics}
        result["status"] = "passed" if passed else "failed"
    except Exception as exc:
        result = {"status": "failed", "code": "operation-failed", "message": str(exc)[:1500]}
        passed = False
    save(root / "result.json", result)
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--worker")
    group.add_argument("--execute")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return 0
    return managed_execute(args.execute)


if __name__ == "__main__":
    raise SystemExit(main())
