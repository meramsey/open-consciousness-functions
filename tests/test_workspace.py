from __future__ import annotations

import errno
import os
import subprocess
import time
from pathlib import Path

import pytest
from ocf_tools import paths
from ocf_tools.utils import write_text_atomic


def test_default_and_relative_override_are_resolved_from_repository(monkeypatch):
    monkeypatch.delenv("OCF_WORK_DIR", raising=False)
    assert paths.work_root() == paths.REPO_ROOT / ".ocf-work"
    monkeypatch.setenv("OCF_WORK_DIR", "private-work")
    assert paths.work_root() == (paths.REPO_ROOT / "private-work").resolve()
    assert paths.work_path("renders", "auditions").is_relative_to(paths.work_root())


def test_workspace_override_and_joined_paths_are_validated(monkeypatch):
    monkeypatch.setenv("OCF_WORK_DIR", str(paths.REPO_ROOT))
    with pytest.raises(RuntimeError, match="dedicated directory"):
        paths.work_root()
    monkeypatch.setenv("OCF_WORK_DIR", str(paths.REPO_ROOT / ".ocf-work-test"))
    with pytest.raises(ValueError, match="escapes"):
        paths.work_path("tmp", "..", "..", "outside")
    with pytest.raises(ValueError, match="unknown OCF work area"):
        paths.work_path("arbitrary")


def test_workspace_environment_is_subprocess_only_and_uses_all_temp_variables(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    original = {key: os.environ.get(key) for key in ("TMPDIR", "TMP", "TEMP")}
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(paths.subprocess, "run", fake_run)
    paths.workspace_run(["engine", "render"])
    env = captured["env"]
    temp_path = Path(env["TMPDIR"])
    assert env["TMP"] == env["TEMP"] == str(temp_path)
    assert temp_path.parent == (tmp_path / "ocf-work" / "tmp").resolve()
    assert temp_path.name.startswith("ocf-subprocess-") and not temp_path.exists()
    assert env["XDG_CACHE_HOME"] == str((tmp_path / "ocf-work" / "cache").resolve())
    assert {key: os.environ.get(key) for key in original} == original


def test_failed_subprocess_retains_only_its_marked_local_scratch(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    captured = {}

    def failed(command, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 2, b"", b"fixture error")

    monkeypatch.setattr(paths.subprocess, "run", failed)
    result = paths.workspace_run(["engine", "fail"])
    retained = Path(captured["env"]["TMPDIR"])
    assert result.returncode == 2
    assert (retained / ".ocf-owned").is_file()
    assert "fixture error" in paths.work_path("logs").joinpath(retained.name + ".log").read_text()


def test_temp_paths_are_marked_scoped_collision_safe_and_recoverable(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    first = paths.workspace_temp_directory(prefix="render-stage-")
    second = paths.workspace_temp_directory(prefix="render-stage-")
    assert first != second
    assert paths.unique_run_id("complete-session") != paths.unique_run_id("complete-session")
    assert first.is_relative_to(paths.work_path("tmp"))
    assert (first / ".ocf-owned").is_file()
    (first / "render-context.json").write_text('{"status":"interrupted"}\n')
    assert (first / "render-context.json").is_file()
    old_time = time.time() - 60
    for scratch in (first, second):
        os.utime(scratch, (old_time, old_time))
    preview = paths.cleanup_workspace(older_than_seconds=0, dry_run=True)
    assert first in preview and first.is_dir()
    removed = paths.cleanup_workspace(older_than_seconds=0)
    assert first in removed and second in removed
    assert not first.exists() and not second.exists()


def test_cleanup_rejects_unowned_files_and_respects_retention(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    scratch = paths.workspace_temp_directory()
    unrelated = paths.work_path("tmp") / "ocf-user-data"
    unrelated.mkdir()
    with pytest.raises(ValueError, match="unmarked"):
        paths.cleanup_workspace_temp(unrelated)
    monkeypatch.setenv("OCF_KEEP_WORK", "1")
    assert paths.cleanup_workspace_temp(scratch) is False
    assert scratch.is_dir()
    monkeypatch.delenv("OCF_KEEP_WORK")
    assert paths.cleanup_workspace_temp(scratch) is True
    assert unrelated.exists()


def test_workspace_temp_file_and_publish_preserve_collision_safety(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    descriptor, scratch_file = paths.workspace_temp_file(suffix=".wav")
    os.close(descriptor)
    assert scratch_file.is_relative_to(paths.work_path("tmp"))
    assert (scratch_file.parent / ".ocf-owned").is_file()
    scratch_file.write_bytes(b"audio")
    destination = tmp_path / "audition" / "run-1"
    paths.publish_workspace_temp_directory(scratch_file.parent, destination)
    assert (destination / scratch_file.name).read_bytes() == b"audio"
    assert not (destination / ".ocf-owned").exists()
    other = paths.workspace_temp_directory()
    with pytest.raises(FileExistsError, match="refusing to replace"):
        paths.publish_workspace_temp_directory(other, destination)
    assert other.exists()


def test_workspace_publish_falls_back_across_filesystems(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    scratch = paths.workspace_temp_directory()
    (scratch / "manifest.json").write_text("{}\n")
    original_replace = paths.os.replace

    def cross_device_once(source, destination):
        if Path(source) == scratch:
            raise OSError(errno.EXDEV, "cross-device link")
        return original_replace(source, destination)

    monkeypatch.setattr(paths.os, "replace", cross_device_once)
    target = tmp_path / "external-output" / "run"
    paths.publish_workspace_temp_directory(scratch, target)
    assert (target / "manifest.json").read_text() == "{}\n"
    assert not (target / ".ocf-owned").exists()
    assert not scratch.exists()


def test_atomic_writes_stage_in_workspace_and_keep_cross_device_outputs_atomic(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    target = tmp_path / "output" / "manifest.yaml"
    write_text_atomic(target, "value: local\n")
    assert target.read_text(encoding="utf-8") == "value: local\n"
    assert list(paths.work_path("tmp").iterdir()) == []

    original_replace = paths.os.replace
    failed_once = False

    def cross_device_once(source, destination):
        nonlocal failed_once
        if not failed_once and Path(source).is_relative_to(paths.work_path("tmp")):
            failed_once = True
            raise OSError(errno.EXDEV, "cross-device link")
        return original_replace(source, destination)

    monkeypatch.setattr(paths.os, "replace", cross_device_once)
    write_text_atomic(target, "value: cross-device\n")
    assert failed_once and target.read_text(encoding="utf-8") == "value: cross-device\n"
    assert list(paths.work_path("tmp").iterdir()) == []
    assert [path.name for path in target.parent.iterdir()] == ["manifest.yaml"]


def test_workspace_clean_cli_removes_only_old_marked_scratch(monkeypatch, tmp_path, capsys):
    from ocf_tools.cli import main

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    old = paths.workspace_temp_directory()
    unrelated = paths.work_path("tmp") / "ocf-unmarked"
    unrelated.mkdir()
    old_time = old.stat().st_mtime - 7200
    os.utime(old, (old_time, old_time))
    assert main(["workspace", "clean", "--older-than-hours", "1", "--dry-run"]) == 0
    assert old.exists() and unrelated.exists()
    assert main(["workspace", "clean", "--older-than-hours", "1"]) == 0
    assert not old.exists() and unrelated.exists()
    assert "Cleaned" in capsys.readouterr().out


def test_failed_workspace_run_keeps_error_in_caller_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "ocf-work"))
    log = paths.record_workspace_failure("run-123", "engine failed\ntraceback")
    assert log == paths.work_path("logs", "run-123.log")
    assert "engine failed\ntraceback" in log.read_text(encoding="utf-8")
