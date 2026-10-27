"""Explicit bounded bulk auditions with verified resumability and unique outputs."""

from __future__ import annotations

import errno
import json
import os
import shutil
import sys
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from functools import wraps
from pathlib import Path

from .complete_session import render_complete_session
from .indexes import load_all_functions
from .locale import LocaleCatalog
from .narration_first import _voice_profile
from .paths import REPO_ROOT, work_path, work_root
from .progress import observing, report
from .session_plans import digest, source_plan
from .speech_cache import STATS, enabled, voice_identity
from .utils import OCFError, sha256_of_file, verified_file_hashes, write_text_atomic

_MEMORY_RESERVE = 6 * 1024**3
_MEMORY_PER_JOB = 4 * 1024**3
_DISK_RESERVE = 8 * 1024**3
_DISK_PER_JOB = 3 * 1024**3


def _transient_failure(error):
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    if isinstance(error, OSError):
        return error.errno in {errno.EAGAIN, errno.EBUSY, errno.EINTR, errno.ETIMEDOUT}
    message = str(error).casefold()
    return "temporarily unavailable" in message or "timed out" in message


def _select_workers(requested, *, memory_bytes, disk_bytes, cpu_count, load_average=None):
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        raise OCFError("render worker limit must be a positive integer")
    if disk_bytes < _DISK_RESERVE + _DISK_PER_JOB:
        raise OCFError("insufficient free disk for one complete session plus safety reserve")
    if memory_bytes is not None and memory_bytes < _MEMORY_RESERVE + _MEMORY_PER_JOB:
        raise OCFError("insufficient available RAM for one complete session plus safety reserve")
    disk_workers = max(1, (disk_bytes - _DISK_RESERVE) // _DISK_PER_JOB)
    memory_workers = (
        1 if memory_bytes is None else max(1, (memory_bytes - _MEMORY_RESERVE) // _MEMORY_PER_JOB)
    )
    cores = max(1, int(cpu_count or 1))
    selected = min(requested, cores, int(disk_workers), int(memory_workers))
    if load_average is not None and load_average > cores * 0.75:
        selected = max(1, selected - 1)
    return selected


def _system_memory_available():
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            pass
    try:
        return int(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, OSError, ValueError):
        return None


def _batch_resource_state(requested):
    disk = shutil.disk_usage(work_root()).free
    try:
        load = os.getloadavg()[0]
    except (AttributeError, OSError):
        load = None
    selected = _select_workers(
        requested,
        memory_bytes=_system_memory_available(),
        disk_bytes=disk,
        cpu_count=os.cpu_count(),
        load_average=load,
    )
    return {
        "requested_workers": requested,
        "selected_workers": selected,
        "available_memory_bytes": _system_memory_available(),
        "available_disk_bytes": disk,
        "cpu_count": os.cpu_count(),
        "load_average_1m": load,
        "estimated_peak_memory_per_job_bytes": _MEMORY_PER_JOB,
        "estimated_temporary_and_output_bytes_per_job": _DISK_PER_JOB,
        "memory_reserve_bytes": _MEMORY_RESERVE,
        "disk_reserve_bytes": _DISK_RESERVE,
    }


def _publish_statuses(statuses, ids):
    write_text_atomic(
        work_path("logs", "bulk-render-latest.json"),
        json.dumps([statuses[owner] for owner in ids], indent=2) + "\n",
    )


def _renderer_fingerprint():
    return {
        name: sha256_of_file(Path(__file__).with_name(name))
        for name in (
            "bulk_render.py",
            "complete_session.py",
            "audio_build.py",
            "semantic_dsp.py",
            "narration_pacing.py",
            "narration_first.py",
        )
    }


def _git_worktree_identity():
    entry = REPO_ROOT / ".git"
    if entry.is_dir():
        git_dir = entry.resolve()
    elif entry.is_file():
        pointer = entry.read_text(encoding="utf-8").strip()
        if not pointer.startswith("gitdir:"):
            return {"verified": False, "worktree": str(REPO_ROOT.resolve())}
        git_dir = Path(pointer.partition(":")[2].strip())
        if not git_dir.is_absolute():
            git_dir = (REPO_ROOT / git_dir).resolve()
    else:
        return {"verified": False, "worktree": str(REPO_ROOT.resolve())}
    head = (git_dir / "HEAD").read_text(encoding="ascii").strip()
    branch = None
    if head.startswith("ref:"):
        ref = head.partition(":")[2].strip()
        branch = ref.removeprefix("refs/heads/")
        ref_path = git_dir / ref
        if not ref_path.is_file():
            common_file = git_dir / "commondir"
            common = (
                (git_dir / common_file.read_text().strip()).resolve()
                if common_file.is_file()
                else git_dir
            )
            ref_path = common / ref
        head = ref_path.read_text(encoding="ascii").strip()
    return {
        "verified": len(head) == 40 and all(char in "0123456789abcdef" for char in head),
        "head": head,
        "branch": branch,
        "worktree": str(REPO_ROOT.resolve()),
    }


def _render_job(
    owner,
    job,
    *,
    locale,
    voice,
    pacing,
    sample_rate,
    dsp_profile,
    force,
    fresh_synthesis,
    progress_sink,
):
    for attempt in (1, 2):
        try:
            with observing(progress_sink), enabled(not force and not fresh_synthesis):
                result = render_complete_session(
                    owner,
                    locale=locale,
                    voice=voice,
                    pacing=pacing,
                    sample_rate=sample_rate,
                    **({"dsp_profile": dsp_profile} if dsp_profile else {}),
                )
            root = Path(result["output_directory"])
            receipt = {
                "key": job["key"],
                "output_directory": str(root.resolve()),
                "manifest_sha256": sha256_of_file(root / "session-report.json"),
            }
            if not verified_output(receipt, job["key"]):
                raise OCFError(f"render artifact verification failed for {owner}")
            if job["resume_verified"]:
                write_text_atomic(job["receipt_path"], json.dumps(receipt, sort_keys=True) + "\n")
            return {
                "function_id": owner,
                "status": "rendered",
                "output_directory": str(root),
                "attempts": attempt,
                "resume_verification": "available"
                if job["resume_verified"]
                else "unavailable: background engine identity is unverified",
            }
        except (OCFError, OSError, ValueError, TimeoutError, ConnectionError) as exc:
            if attempt == 1 and _transient_failure(exc):
                report("function-retrying-transient", detail=f"{owner}: {exc}")
                continue
            return {
                "function_id": owner,
                "status": "failed",
                "attempts": attempt,
                "error": str(exc),
            }
    raise AssertionError("bounded render retry loop ended unexpectedly")


def _windows_process_is_alive(pid, *, kernel32=None, last_error=None):
    """Probe process state without sending a signal to the target process."""
    import ctypes
    from ctypes import wintypes

    if kernel32 is None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
    process = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not process:
        error = (last_error or ctypes.get_last_error)()
        if error == 5:  # ERROR_ACCESS_DENIED: conservatively regard the PID as live.
            return True
        if error in {87, 1168}:  # ERROR_INVALID_PARAMETER / ERROR_NOT_FOUND
            return False
        if hasattr(ctypes, "WinError"):
            raise ctypes.WinError(error)
        raise OSError(error, "OpenProcess failed")
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code)):
            error = (last_error or ctypes.get_last_error)()
            if hasattr(ctypes, "WinError"):
                raise ctypes.WinError(error)
            raise OSError(error, "GetExitCodeProcess failed")
        return exit_code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(process)


def _process_is_alive(pid):
    if os.name == "nt":
        return _windows_process_is_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _single_batch_owner(function):
    """Keep separate render-many invocations from racing shared receipts."""

    @wraps(function)
    def guarded(*args, **kwargs):
        if kwargs.get("dry_run"):
            return function(*args, **kwargs)
        lock = work_path("logs", "bulk-render.lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"pid": os.getpid(), "owner": "ocf.audio.render-many"}) + "\n"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            try:
                owner = json.loads(lock.read_text(encoding="utf-8"))
                pid = int(owner["pid"])
                if not _process_is_alive(pid):
                    raise ProcessLookupError(pid)
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                raise OCFError(
                    f"render batch lock is stale or unreadable; verify ownership before removing: {lock}"
                ) from exc
            raise OCFError(f"another render batch owns PID {pid}; refusing duplicate work") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            return function(*args, **kwargs)
        finally:
            try:
                if lock.read_text(encoding="utf-8") == payload:
                    lock.unlink()
            except OSError:
                pass

    return guarded


def verified_output(receipt: dict, key: str) -> bool:
    """Trust only the completed manifest plus every contained artifact checksum."""
    try:
        if receipt["key"] != key:
            return False
        root = Path(receipt["output_directory"]).resolve()
        manifest_path = root / "session-report.json"
        if sha256_of_file(manifest_path) != receipt["manifest_sha256"]:
            return False
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("artifacts") or "wav" not in manifest["artifacts"]:
            return False
        for artifact in manifest["artifacts"].values():
            path = (root / artifact["path"]).resolve()
            if not path.is_relative_to(root) or path.stat().st_size != artifact["size_bytes"]:
                return False
            if sha256_of_file(path) != artifact["sha256"]:
                return False
        return True
    except (OSError, KeyError, ValueError, TypeError):
        return False


@_single_batch_owner
@verified_file_hashes()
def render_many(
    function_ids: list[str] | None,
    *,
    voice: str,
    locale: str = "en-US",
    pacing: str = "sleep",
    dry_run: bool = False,
    force: bool = False,
    resume: bool = True,
    sample_rate: int = 44100,
    dsp_profile: str | None = None,
    fresh_synthesis: bool = False,
    workers: int = 1,
    progress_callback=None,
) -> dict:
    from .semantic_dsp import dependency_identity

    ids = sorted(
        set(function_ids if function_ids is not None else [r.id for r in load_all_functions()])
    )
    if not ids:
        raise OCFError("no functions selected")
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise OCFError("render worker limit must be a positive integer")

    statuses = {owner: {"function_id": owner, "status": "pending"} for owner in ids}
    jobs = {}

    def notify_external(event):
        if progress_callback is not None:
            try:
                progress_callback(event)
            except OSError:
                pass

    def notify(event):
        report(event["phase"], detail=event.get("detail"))
        notify_external(event)

    if not dry_run:
        # Missing voice/model or a broken shared reference profile blocks the batch,
        # rather than producing dozens of identical per-function failures.
        _, spec = _voice_profile(voice, locale, LocaleCatalog())
        identity_voice = voice_identity(spec)
        git_identity = _git_worktree_identity()
        if dsp_profile:
            shared_dsp_identity = dependency_identity(dsp_profile)
            if not shared_dsp_identity.get("verified"):
                raise OCFError("critical selected DSP/background profile identity is unverified")
        else:
            shared_dsp_identity = None
        renderer_identity = _renderer_fingerprint()

    for owner in ids:
        notify({"phase": "function-preflight", "function_id": owner, "detail": owner})
        try:
            plan, shared, expanded = source_plan(owner, locale)
            if dsp_profile:
                from .complete_session import build_complete_session_plan

                build_complete_session_plan(
                    owner, locale=locale, voice=voice, pacing=pacing, dsp_profile=dsp_profile
                )
            if dry_run:
                statuses[owner] = {
                    "function_id": owner,
                    "status": "planned",
                    "plan_sha256": digest(plan),
                }
                notify({"phase": "function-planned", "function_id": owner})
                continue
            dsp_identity = shared_dsp_identity or dependency_identity(
                expanded["resolved_dsp_profile"]
            )
            identity = {
                "plan": plan,
                "shared": shared,
                "voice": identity_voice,
                "pacing": pacing,
                "sample_rate": sample_rate,
                "fresh_synthesis_required": fresh_synthesis,
                "renderer": renderer_identity,
                "background": dsp_identity,
            }
            identity["git_worktree"] = git_identity
            key = digest(identity)
            receipt_path = work_path("cache", "bulk-renders", key + ".json")
            job = {
                "key": key,
                "receipt_path": receipt_path,
                "resume_verified": bool(dsp_identity["verified"] and git_identity["verified"]),
            }
            previous = {}
            if resume and not force and job["resume_verified"]:
                try:
                    previous = json.loads(receipt_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    pass
                if verified_output(previous, key):
                    statuses[owner] = {
                        "function_id": owner,
                        "status": "skipped-verified",
                        "output_directory": previous["output_directory"],
                        "plan_sha256": digest(plan),
                    }
                    notify({"phase": "function-skipped-verified", "function_id": owner})
                    continue
            jobs[owner] = job
            statuses[owner] = {
                "function_id": owner,
                "status": "pending",
                "plan_sha256": digest(plan),
            }
        except (OCFError, OSError, ValueError) as exc:
            statuses[owner] = {"function_id": owner, "status": "blocked", "error": str(exc)}
            notify({"phase": "function-blocked", "function_id": owner, "detail": str(exc)})

    ordered_statuses = [statuses[owner] for owner in ids]
    if dry_run:
        return {
            "workers": 1,
            "requested_workers": workers,
            "speech_cache": dict(STATS),
            "dry_run": True,
            "results": ordered_statuses,
            "failed": 0,
            "blocked": sum(row["status"] == "blocked" for row in ordered_statuses),
        }
    if not jobs:
        return {
            "workers": 0,
            "requested_workers": workers,
            "speech_cache": dict(STATS),
            "dry_run": False,
            "results": ordered_statuses,
            "failed": 0,
            "blocked": sum(row["status"] == "blocked" for row in ordered_statuses),
        }

    try:
        resource_state = _batch_resource_state(workers)
    except OCFError:
        raise
    selected_workers = resource_state["selected_workers"]
    dashboard_lock = threading.RLock()

    def publish():
        with dashboard_lock:
            _publish_statuses(statuses, ids)

    publish()
    pending = [owner for owner in ids if owner in jobs]
    active = {}
    max_active = 0
    with ThreadPoolExecutor(max_workers=selected_workers, thread_name_prefix="ocf-render") as pool:
        while pending or active:
            while pending and len(active) < selected_workers:
                try:
                    available_workers = _batch_resource_state(workers)["selected_workers"]
                    if len(active) >= available_workers:
                        break
                except OCFError:
                    if active:
                        break
                    for owner in pending:
                        statuses[owner] = {
                            "function_id": owner,
                            "status": "blocked",
                            "error": "insufficient resources before starting the next full session",
                        }
                    pending.clear()
                    publish()
                    for owner in ids:
                        if statuses[owner]["status"] == "blocked":
                            notify(
                                {
                                    "phase": "function-blocked",
                                    "function_id": owner,
                                    "detail": statuses[owner].get("error"),
                                }
                            )
                    break
                owner = pending.pop(0)
                statuses[owner] = {
                    **statuses[owner],
                    "status": "rendering",
                    "pid": os.getpid(),
                    "worker": len(active) + 1,
                }
                publish()
                notify({"phase": "function-start", "function_id": owner, "detail": owner})

                def progress_sink(event, owner=owner):
                    with dashboard_lock:
                        statuses[owner]["current_stage"] = event.get("phase", "rendering")
                        if event.get("detail"):
                            statuses[owner]["progress_detail"] = event["detail"]
                        publish()
                    notify_external({**event, "function_id": owner})

                future = pool.submit(
                    _render_job,
                    owner,
                    jobs[owner],
                    locale=locale,
                    voice=voice,
                    pacing=pacing,
                    sample_rate=sample_rate,
                    dsp_profile=dsp_profile,
                    force=force,
                    fresh_synthesis=fresh_synthesis,
                    progress_sink=progress_sink,
                )
                active[future] = owner
                max_active = max(max_active, len(active))
            if not active:
                continue
            completed, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in completed:
                owner = active.pop(future)
                try:
                    statuses[owner] = future.result()
                except Exception as exc:  # worker errors are isolated to this function
                    statuses[owner] = {
                        "function_id": owner,
                        "status": "failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                notify(
                    {
                        "phase": "function-" + statuses[owner]["status"],
                        "function_id": owner,
                        "detail": statuses[owner].get("error", owner),
                    }
                )
                publish()

    results = [statuses[owner] for owner in ids]
    return {
        "workers": max_active,
        "requested_workers": workers,
        "resource_decision": resource_state,
        "speech_cache": dict(STATS),
        "dry_run": False,
        "results": results,
        "failed": sum(row["status"] == "failed" for row in results),
        "blocked": sum(row["status"] == "blocked" for row in results),
    }
