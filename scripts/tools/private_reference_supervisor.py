"""Durable, single-owner supervisor for the private reference-V4 batch."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ocf_tools.process_status import process_is_alive

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(os.environ.get("OCF_WORK_DIR", ROOT / ".ocf-work")).expanduser().resolve()
STATE = WORK / "agent-continuity" / "private-reference-v4-supervisor.json"
LOG = WORK / "logs" / "private-reference-v4-supervisor.log"


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def alive(pid: int | None) -> bool:
    return process_is_alive(pid)


def command() -> list[str]:
    return [
        sys.executable,
        str(ROOT / "scripts/tools/render_private_reference_v4.py"),
        "--all",
        "--profile",
        str(
            WORK / "agent-continuity/corrective-reference-v4-v0.3.0/reference-v4-edition-0.3.0.yaml"
        ),
        "--voice",
        "OCF-VOICE-9003",
        "--version",
        "0.3.0",
        "--workers",
        "2",
        "--fresh-synthesis",
    ]


def start() -> int:
    previous = json.loads(STATE.read_text()) if STATE.is_file() else {}
    if alive(previous.get("pid")):
        print(f"supervisor already active: pid {previous['pid']}")
        return 2
    LOG.parent.mkdir(parents=True, exist_ok=True)
    started = now()
    args = command()
    with LOG.open("ab") as stream:
        stream.write(f"\n[{started}] supervisor start: {json.dumps(args)}\n".encode())
        stream.flush()
        child = subprocess.Popen(
            args,
            cwd=ROOT,
            env={
                **os.environ,
                "OCF_WORK_DIR": str(WORK),
                "PYTHONPATH": os.pathsep.join(
                    item
                    for item in (str(ROOT / "scripts"), os.environ.get("PYTHONPATH", ""))
                    if item
                ),
            },
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    state = {
        "status": "running",
        "pid": child.pid,
        "started_at": started,
        "command": args,
        "log": str(LOG),
        "worktree": str(ROOT),
    }
    write_atomic(STATE, state)
    print(json.dumps(state, indent=2), flush=True)
    exit_code = child.wait()
    state.update(
        {
            "status": "completed" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "finished_at": now(),
        }
    )
    write_atomic(STATE, state)
    return exit_code


def status() -> int:
    if not STATE.is_file():
        print(json.dumps({"status": "never-started"}, indent=2))
        return 1
    state = json.loads(STATE.read_text())
    state["live"] = alive(state.get("pid")) if state.get("status") == "running" else False
    print(json.dumps(state, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("start", "status"))
    args = parser.parse_args()
    return start() if args.action == "start" else status()


if __name__ == "__main__":
    raise SystemExit(main())
