"""Checkout launchers must retain venv, environment, argv and stream boundaries."""

import os
import sys

import ocf_launch
import pytest
from ocf_tools import paths

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("windows,relative", [(False, "bin/python"), (True, "Scripts/python.exe")])
def test_virtualenv_paths_and_missing_interpreter_fail_without_system_fallback(
    tmp_path, windows, relative
):
    root = tmp_path / "checkout with spaces"
    with pytest.raises(RuntimeError, match="Python 3.11"):
        ocf_launch.venv_python(root, windows=windows)
    executable = root / ".venv" / relative
    executable.parent.mkdir(parents=True)
    executable.touch()
    assert ocf_launch.venv_python(root, windows=windows) == executable


def prepared(monkeypatch, tmp_path):
    root = tmp_path / "checkout with spaces"
    script = root / "scripts/start_ocf_lsp.py"
    interpreter = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()
    monkeypatch.setattr(sys, "prefix", str(root / ".venv"))
    monkeypatch.setattr(
        paths, "workspace_environment", lambda: {"PATH": "unchanged", "ROUTER": "keep"}
    )
    monkeypatch.setattr(paths, "work_path", lambda area, name: root / ".ocf-work" / area / name)
    monkeypatch.setattr(ocf_launch.os, "chdir", lambda path: None)
    return root, script, interpreter


def test_bootstrap_reexec_preserves_arguments_with_spaces(monkeypatch, tmp_path):
    root, script, interpreter = prepared(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "system"))
    calls = []
    monkeypatch.setattr(ocf_launch.os, "execv", lambda *args: calls.append(args))
    assert ocf_launch.launch("lsp", script, ["--workspace", str(root), "--stdio"]) == 0
    assert calls == [
        (str(interpreter), [str(interpreter), str(script), "--workspace", str(root), "--stdio"])
    ]


def test_missing_extra_and_unsupported_venv_only_report_to_stderr(monkeypatch, tmp_path, capsys):
    _root, script, _interpreter = prepared(monkeypatch, tmp_path)
    monkeypatch.setattr(ocf_launch.importlib.util, "find_spec", lambda name: None)
    assert ocf_launch.launch("lsp", script, []) == 1
    output = capsys.readouterr()
    assert output.out == "" and "pip install -e '.[lsp]'" in output.err
    monkeypatch.setattr(sys, "version_info", (3, 10))
    assert ocf_launch.launch("lsp", script, []) == 1
    assert "Python 3.11" in capsys.readouterr().err


@pytest.mark.parametrize("kind", ["lsp", "opencode"])
def test_final_exec_preserves_streams_exit_status_environment_and_arguments(
    monkeypatch, tmp_path, kind
):
    root, script, interpreter = prepared(monkeypatch, tmp_path)
    monkeypatch.setattr(ocf_launch.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(ocf_launch.shutil, "which", lambda name: "/installed path/opencode")
    calls, directories = [], []
    monkeypatch.setattr(ocf_launch.os, "execve", lambda *args: calls.append(args))
    monkeypatch.setattr(ocf_launch.os, "chdir", directories.append)
    assert ocf_launch.launch(kind, script, ["--example", "value with spaces"]) == 0
    executable, argv, env = calls[0]
    assert directories == [root]
    assert argv[-2:] == ["--example", "value with spaces"]
    assert env["PATH"] == "unchanged" and env["ROUTER"] == "keep"
    assert env["PIP_CACHE_DIR"] == str(root / ".ocf-work/cache/pip")
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(root / "scripts")
    if kind == "lsp":
        assert executable == str(interpreter)
        assert argv[:3] == [str(interpreter), "-m", "ocf_tools.lsp_server"]
        assert "OPENCODE_EXPERIMENTAL_LSP_TOOL" not in env
    else:
        assert executable == "/installed path/opencode"
        assert env["OPENCODE_EXPERIMENTAL_LSP_TOOL"] == "true"
        assert env["OPENCODE_DISABLE_LSP_DOWNLOAD"] == "true"
    # execve replaces this process: child exit/signal and stdin/out/err are inherited,
    # rather than mediated by a wrapper subprocess or a shell command string.


def test_exec_failure_is_nonzero_without_protocol_stdout(monkeypatch, tmp_path, capsys):
    _root, script, _interpreter = prepared(monkeypatch, tmp_path)
    monkeypatch.setattr(ocf_launch.shutil, "which", lambda name: "/missing/opencode")

    def failed(*args):
        raise OSError("cannot execute fixture")

    monkeypatch.setattr(ocf_launch.os, "execve", failed)
    assert ocf_launch.launch("opencode", script, []) == 1
    output = capsys.readouterr()
    assert not output.out and "cannot execute fixture" in output.err
    monkeypatch.setattr(ocf_launch.shutil, "which", lambda name: None)
    assert ocf_launch.launch("opencode", script, []) == 1
    assert "OpenCode is not on PATH" in capsys.readouterr().err
