"""Small checkout launch helpers; bootstrap Python never runs the actual service."""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


def venv_python(root, *, windows=None):
    windows = os.name == "nt" if windows is None else windows
    interpreter = root / ".venv" / ("Scripts/python.exe" if windows else "bin/python")
    if not interpreter.is_file():
        raise RuntimeError(
            "Create this checkout's .venv with Python 3.11+ and install -e '.[lsp]': "
            + str(interpreter)
        )
    return interpreter


def python_lsp_command(argv):
    """Use the installed JS distribution directly; never bootstrap/download Node."""
    spec = importlib.util.find_spec("pyright")
    if spec is None or not spec.origin:
        raise RuntimeError(
            "Install the optional Python LSP in .venv: python -m pip install -e '.[python-lsp]'"
        )
    server = Path(spec.origin).parent / "dist" / "langserver.index.js"
    if not server.is_file():
        raise RuntimeError(
            "Pyright's bundled server is missing; reinstall the pinned .[python-lsp] extra."
        )
    node = shutil.which("node")
    if not node:
        raise RuntimeError(
            "Pyright requires Node >=14 on OpenCode's startup PATH; install Node explicitly. No runtime download was attempted."
        )
    return [node, str(server), *argv]


def handoff(command, env=None, *, windows=None):
    """POSIX replaces the process; Windows waits with inherited protocol handles.

    CRT exec through Windows venv redirectors can lose redirected stdio and
    report success before the child exits. Popen preserves those handles and
    lets this launcher propagate the actual child's exit status instead.
    """
    windows = os.name == "nt" if windows is None else windows
    if not windows:
        if env is None:
            os.execv(command[0], command)
        else:
            os.execve(command[0], command, env)
        return 0
    child = subprocess.Popen(command, env=env)
    try:
        return child.wait()
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait()


def launch(kind, script, argv=None):
    """Re-exec into the project venv, then preserve protocol/terminal streams."""
    script = Path(script).resolve()
    root = script.parents[1]
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        interpreter = venv_python(root)
        if Path(sys.prefix).resolve() != (root / ".venv").resolve():
            return handoff([str(interpreter), str(script), *argv])
        if sys.version_info < (3, 11):  # noqa: UP036 — bootstrap may be older than the venv
            raise RuntimeError("The checkout's .venv requires Python 3.11 or newer.")

        from ocf_tools.paths import work_path, workspace_environment

        env = workspace_environment()
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(root / "scripts"), env.get("PYTHONPATH")) if part
        )
        env["PIP_CACHE_DIR"] = str(work_path("cache", "pip"))
        env["UV_CACHE_DIR"] = str(work_path("cache", "uv"))
        if kind == "lsp":
            if any(importlib.util.find_spec(name) is None for name in ("pygls", "lsprotocol")):
                raise RuntimeError(
                    "OCF LSP extra is missing from this .venv; run its Python with "
                    "-m pip install -e '.[lsp]' from the checkout."
                )
            command = [str(interpreter), "-m", "ocf_tools.lsp_server", *argv]
        elif kind == "python-lsp":
            command = python_lsp_command(argv)
        elif kind == "opencode":
            executable = shutil.which("opencode")
            if not executable:
                raise RuntimeError(
                    "OpenCode is not on PATH; add your existing installation to PATH."
                )
            env["OPENCODE_EXPERIMENTAL_LSP_TOOL"] = "true"
            # Keep local/explicit servers available without incidental built-in downloads.
            env["OPENCODE_DISABLE_LSP_DOWNLOAD"] = "true"
            command = [executable, *argv]
        else:
            raise ValueError("unknown checkout launcher")
        os.chdir(root)
        return handoff(command, env)
    except (RuntimeError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
