import json
import subprocess

import pytest
from tools import private_reference_supervisor as supervisor


@pytest.mark.unit
def test_supervisor_start_persists_owner_before_wait_and_terminal_state(
    monkeypatch, tmp_path, capsys
):
    root = tmp_path / "checkout"
    work = tmp_path / "private-work"
    state_path = work / "agent-continuity/state.json"
    log_path = work / "logs/supervisor.log"
    monkeypatch.setattr(supervisor, "ROOT", root)
    monkeypatch.setattr(supervisor, "WORK", work)
    monkeypatch.setattr(supervisor, "STATE", state_path)
    monkeypatch.setattr(supervisor, "LOG", log_path)
    monkeypatch.setattr(supervisor, "command", lambda: ["python", "render-fixture"])
    timestamps = iter(("started", "finished"))
    monkeypatch.setattr(supervisor, "now", lambda: next(timestamps))
    calls = []

    class Child:
        pid = 12345

        @staticmethod
        def wait():
            calls.append("wait")
            assert json.loads(state_path.read_text()) == {
                "status": "running",
                "pid": 12345,
                "started_at": "started",
                "command": ["python", "render-fixture"],
                "log": str(log_path),
                "worktree": str(root),
            }
            return 0

    def spawn(command, **kwargs):
        calls.append((command, kwargs))
        return Child()

    monkeypatch.setattr(supervisor.subprocess, "Popen", spawn)
    assert supervisor.start() == 0
    state = json.loads(state_path.read_text())
    assert state["status"] == "completed" and state["exit_code"] == 0
    assert state["finished_at"] == "finished"
    command, options = calls[0]
    assert command == ["python", "render-fixture"]
    assert options["cwd"] == root and options["start_new_session"] is True
    assert options["stdin"] == subprocess.DEVNULL
    assert options["stderr"] == subprocess.STDOUT
    assert options["stdout"].name == str(log_path)
    assert options["env"]["OCF_WORK_DIR"] == str(work)
    assert calls[1] == "wait"
    assert "supervisor start" in log_path.read_text()
    assert json.loads(capsys.readouterr().out)["status"] == "running"


@pytest.mark.unit
def test_supervisor_refuses_duplicate_owner_and_reports_missing_or_live_state(
    monkeypatch, tmp_path, capsys
):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(supervisor, "STATE", state_path)
    assert supervisor.status() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "never-started"

    state_path.write_text(json.dumps({"status": "running", "pid": 99}))
    monkeypatch.setattr(supervisor, "alive", lambda pid: pid == 99)
    monkeypatch.setattr(
        supervisor.subprocess, "Popen", lambda *_a, **_kw: pytest.fail("duplicate launch")
    )
    assert supervisor.start() == 2
    duplicate = json.loads(state_path.read_text())
    assert duplicate == {"status": "running", "pid": 99}
    assert "already active" in capsys.readouterr().out

    assert supervisor.status() == 0
    assert json.loads(capsys.readouterr().out)["live"] is True
    state_path.write_text(json.dumps({"status": "failed", "pid": 99, "exit_code": 1}))
    assert supervisor.status() == 0
    assert json.loads(capsys.readouterr().out)["live"] is False
