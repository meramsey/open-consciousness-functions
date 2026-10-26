import sys
import os
from types import SimpleNamespace

import pytest

from ocf_tools import environment


def _script(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _stub_python_probes(monkeypatch, version=None, *, import_ok=True):
    version = version or sys.version.split()[0]

    def run(command, **kwargs):
        if command[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout=f"Python {version}\n", stderr="")
        if "site.getusersitepackages()" in command[-1]:
            return SimpleNamespace(
                returncode=0,
                stdout=f"{version}\n{kwargs.get('env', {}).get('OCF_TEST_SITE', '')}\n",
                stderr="",
            )
        return SimpleNamespace(
            returncode=0 if import_ok else 1,
            stdout=f"{os.environ.get('OCF_TEST_PIPER_VERSION', '1.2.3')}\n" if import_ok else "",
            stderr="" if import_ok else "ModuleNotFoundError",
        )

    monkeypatch.setattr(environment.subprocess, "run", run)


@pytest.mark.unit
def test_project_python_prefers_valid_existing_venv_and_rejects_stale_candidate(
    tmp_path, monkeypatch
):
    root = tmp_path / "repo"
    _script(root / ".venv/bin/python", f"#!{sys.executable}\nimport sys\nprint('Python 3.12.3')\n")
    _stub_python_probes(monkeypatch, "3.12.3")
    result = environment.project_python(root)
    assert result["status"] == "ready"
    assert result["source"] == "project .venv"
    assert result["version"] == "3.12.3"

    _script(root / ".venv/bin/python", "#!/bin/sh\nexit 7\n")
    _stub_python_probes(monkeypatch, "3.10.0")
    monkeypatch.setenv("OCF_PYTHON", str(root / ".venv/bin/python"))
    assert environment.project_python(root)["status"] == "configured-python-invalid"


@pytest.mark.unit
def test_project_python_honors_pyenv_version_without_changing_global_selection(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".python-version").write_text("3.12.3\n", encoding="utf-8")
    pyenv = tmp_path / "pyenv"
    _script(pyenv / "versions/3.12.3/bin/python", "#!/bin/sh\nexit 0\n")
    monkeypatch.setenv("PYENV_ROOT", str(pyenv))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    _stub_python_probes(monkeypatch, "3.12.3")
    result = environment.project_python(root)
    assert result["status"] == "ready"
    assert result["source"] == "pyenv .python-version"
    assert result["executable"].endswith("/versions/3.12.3/bin/python")


@pytest.mark.unit
def test_piper_is_discovered_in_project_venv_without_global_path(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    pyver = f"{sys.version_info.major}.{sys.version_info.minor}"
    site = root / ".venv" / "lib" / f"python{pyver}" / "site-packages"
    _script(site / "piper/__init__.py", "")
    (site / "piper_tts-9.8.7.dist-info").mkdir(parents=True)
    (site / "piper_tts-9.8.7.dist-info/METADATA").write_text(
        "Metadata-Version: 2.1\nName: piper-tts\nVersion: 9.8.7\n", encoding="utf-8"
    )
    _script(root / ".venv/bin/piper", f"#!{sys.executable}\nraise SystemExit(0)\n")
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    monkeypatch.delenv("OCF_PIPER_EXECUTABLE", raising=False)
    monkeypatch.setattr(environment, "_user_home", lambda: tmp_path / "isolated-home")
    monkeypatch.setenv("OCF_TEST_SITE", str(site))
    monkeypatch.setenv("OCF_TEST_PIPER_VERSION", "9.8.7")
    _stub_python_probes(monkeypatch, sys.version.split()[0])
    result = environment.resolve_executable("piper", root=root)
    assert result["status"] == "ready"
    assert result["source"] == "existing local installation"
    assert result["runtime"]["package_version"] == "9.8.7"
    assert result["runtime"]["python_version"] == sys.version.split()[0]


@pytest.mark.unit
def test_piper_resolves_nondefault_user_local_installation_and_reports_broken_runtime(
    tmp_path, monkeypatch
):
    root = tmp_path / "repo"
    prefix = tmp_path / "user-install"
    pyver = f"{sys.version_info.major}.{sys.version_info.minor}"
    site = prefix / "lib" / f"python{pyver}" / "site-packages"
    _script(site / "piper/__init__.py", "")
    (site / "piper_tts-1.2.3.dist-info").mkdir(parents=True)
    (site / "piper_tts-1.2.3.dist-info/METADATA").write_text(
        "Metadata-Version: 2.1\nName: piper-tts\nVersion: 1.2.3\n", encoding="utf-8"
    )
    _script(prefix / "bin/piper", f"#!{sys.executable}\nraise SystemExit(0)\n")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setenv("OCF_PIPER_EXECUTABLE", str(prefix / "bin/piper"))
    monkeypatch.setattr(environment, "_user_home", lambda: tmp_path / "isolated-home")
    monkeypatch.setenv("OCF_TEST_SITE", str(site))
    monkeypatch.setenv("OCF_TEST_PIPER_VERSION", "1.2.3")
    _stub_python_probes(monkeypatch, sys.version.split()[0])
    result = environment.resolve_executable("piper", root=root)
    assert result["status"] == "ready"
    assert result["executable"] == str((prefix / "bin/piper").resolve())
    assert result["runtime"]["package_version"] == "1.2.3"

    _script(prefix / "bin/piper", "#!/missing/python\n")
    result = environment.resolve_executable("piper", root=root)
    assert result["status"] == "broken"
    assert result["reason"]


@pytest.mark.unit
def test_model_discovery_honors_explicit_nondefault_configured_path(tmp_path, monkeypatch):
    model = tmp_path / "models/amy/custom.onnx"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"onnx")
    (tmp_path / "models/amy/custom.onnx.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(environment.shutil, "which", lambda *_: None)
    monkeypatch.setattr(environment, "_user_home", lambda: tmp_path / "empty-home")
    monkeypatch.setenv("OCF_PIPER_EXECUTABLE", str(tmp_path / "no-piper"))
    result = environment.discover_environment(
        root=tmp_path / "repo",
        voice_profile={"backend": "piper", "piper_model": str(model)},
    )
    assert result["model"]["status"] == "ready"
    assert result["model"]["model_path"] == str(model.resolve())
    assert result["model"]["model_sha256"]
    assert result["tools"]["piper"]["status"] in {"not-found", "broken"}


@pytest.mark.unit
def test_missing_backend_is_reported_as_missing_not_as_a_download_or_install_attempt(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setenv("OCF_PIPER_EXECUTABLE", str(tmp_path / "missing-piper"))
    monkeypatch.setattr(environment, "_user_home", lambda: tmp_path / "empty-home")
    result = environment.resolve_executable("piper", root=tmp_path / "repo")
    assert result == environment.resolve_executable("piper", root=tmp_path / "repo")
    assert result["status"] == "not-found"
    assert "not on PATH" in result["reason"]
    assert not list(tmp_path.rglob("*.onnx"))
