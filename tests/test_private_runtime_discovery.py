"""Capability discovery must follow the same runtime as synthesis and caching."""

import builtins

import pytest
from ocf_tools import voice_capabilities, voice_packs

pytestmark = pytest.mark.unit


def installed(root, library):
    interpreter = root / ("Scripts/python.exe" if library.startswith("Lib/") else "bin/python")
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"synthetic interpreter; never executed")
    package = root / library / "chatterbox/__init__.py"
    package.parent.mkdir(parents=True)
    package.write_text('raise AssertionError("must never import backend during discovery")')
    metadata = root / library / "chatterbox_tts-0.1.7.dist-info/METADATA"
    metadata.parent.mkdir(parents=True)
    metadata.write_text("Name: chatterbox-tts\nVersion: 0.1.7\n")
    return interpreter, package


@pytest.mark.parametrize("library", ["lib/python3.12/site-packages", "Lib/site-packages"])
def test_selected_runtime_discovery_survives_absent_scratch(tmp_path, monkeypatch, library):
    interpreter, package = installed(tmp_path / "durable", library)
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "absent-scratch"))
    monkeypatch.setenv("OCF_CHATTERBOX_PYTHON", str(interpreter))
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert name.split(".")[0] not in {"torch", "chatterbox"}
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    result = voice_capabilities.backend_capability("chatterbox-nano")
    assert result["available"]
    assert result["installation"]["package_found"]
    assert result["installation"]["discovery"]["runtime"]["package_version"] == "0.1.7"
    assert result["installation"]["discovery"]["source"] == "selected optional environment"
    monkeypatch.setattr(voice_packs, "inference_verified", lambda profile: False)
    profile = {
        "id": "OCF-VOICE-9899",
        "backend": "chatterbox-nano",
        "customization_method": "reference-audio",
    }
    assert voice_capabilities.profile_capability(profile)["available"]
    package.unlink()
    assert not voice_capabilities.backend_capability("chatterbox-nano")["available"]
    missing = voice_capabilities.profile_capability(profile)
    assert not missing["available"]
    assert any("package is unavailable" in item for item in missing["blockers"])


def test_missing_selected_runtime_never_falls_back_to_scratch(tmp_path, monkeypatch):
    installed(tmp_path / "scratch/voice-envs/chatterbox", "lib/python3.12/site-packages")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "scratch"))
    monkeypatch.setenv("OCF_CHATTERBOX_PYTHON", str(tmp_path / "missing/bin/python"))
    result = voice_capabilities.backend_capability("chatterbox-nano")
    assert not result["available"]
    assert not result["installation"]["executable_found"]
    assert not result["installation"]["package_found"]


def test_disposable_runtime_changes_do_not_change_selected_discovery(tmp_path, monkeypatch):
    interpreter, _ = installed(tmp_path / "durable", "lib/python3.12/site-packages")
    old_interpreter, old_package = installed(
        tmp_path / "scratch/voice-envs/chatterbox", "lib/python3.12/site-packages"
    )
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "scratch"))
    monkeypatch.setenv("OCF_CHATTERBOX_PYTHON", str(interpreter))
    before = voice_capabilities.backend_capability("chatterbox-nano")
    old_interpreter.unlink()
    old_package.unlink()
    assert voice_capabilities.backend_capability("chatterbox-nano") == before
