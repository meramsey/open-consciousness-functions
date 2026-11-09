"""Cache identity follows the selected private runtime, not disposable leftovers."""

from pathlib import Path

import pytest
from ocf_tools import speech_cache, voice_packs

pytestmark = pytest.mark.unit
PACKAGES = ("chatterbox_tts", "torch", "torchaudio", "transformers", "resemble_perth")
SPEC = {"name": "chatterbox-nano", "reference_sha256": "a" * 64, "reference_text_sha256": "b" * 64}


def runtime(tmp_path, monkeypatch, library):
    selected = tmp_path / "durable-runtime"
    interpreter = selected / ("Scripts/python.exe" if library.startswith("Lib/") else "bin/python")
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"synthetic interpreter; never executed")
    monkeypatch.setenv("OCF_CHATTERBOX_PYTHON", str(interpreter))
    for package in PACKAGES:
        folder = selected / library / (package + "-1.0.dist-info")
        folder.mkdir(parents=True)
        for name in ("METADATA", "RECORD", "direct_url.json"):
            (folder / name).write_text(package + ":" + name)
    return selected, interpreter


@pytest.mark.parametrize("library", ["lib/python3.12/site-packages", "Lib/site-packages"])
@pytest.mark.parametrize("package", PACKAGES)
@pytest.mark.parametrize("record", ["METADATA", "RECORD", "direct_url.json"])
def test_each_selected_package_record_independently_invalidates_identity(
    tmp_path, monkeypatch, library, package, record
):
    selected, _ = runtime(tmp_path, monkeypatch, library)
    before = speech_cache.voice_identity(SPEC)
    assert len([key for key in before["assets"] if key.endswith("/METADATA")]) == len(PACKAGES)
    path = selected / library / (package + "-1.0.dist-info") / record
    path.write_text("changed installed dependency")
    assert speech_cache.voice_identity(SPEC) != before


def test_old_disposable_runtime_cannot_affect_selected_identity(tmp_path, monkeypatch):
    runtime(tmp_path, monkeypatch, "lib/python3.12/site-packages")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "workspace"))
    old = (
        tmp_path
        / "workspace/voice-envs/chatterbox/lib/python3.12/site-packages/torch-1.0.dist-info/METADATA"
    )
    old.parent.mkdir(parents=True)
    old.write_text("old")
    before = speech_cache.voice_identity(SPEC)
    old.write_text("unrelated update")
    assert speech_cache.voice_identity(SPEC) == before
    old.unlink()
    assert speech_cache.voice_identity(SPEC) == before


def test_selected_interpreter_change_invalidates_identity(tmp_path, monkeypatch):
    _, interpreter = runtime(tmp_path, monkeypatch, "lib/python3.12/site-packages")
    before = speech_cache.voice_identity(SPEC)
    interpreter.write_bytes(b"updated interpreter")
    assert speech_cache.voice_identity(SPEC) != before


def test_selected_venv_entrypoint_is_not_resolved_to_base(tmp_path, monkeypatch):
    _, interpreter = runtime(tmp_path, monkeypatch, "lib/python3.12/site-packages")
    original = Path.resolve
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda path, *a, **k: (
            tmp_path / "base/bin/python" if path == interpreter else original(path, *a, **k)
        ),
    )
    assert voice_packs.runtime_interpreter() == interpreter
    assert len(
        [key for key in speech_cache.voice_identity(SPEC)["assets"] if key.endswith("/METADATA")]
    ) == len(PACKAGES)


@pytest.mark.parametrize(
    "platform,suffix", [("win32", "Scripts/python.exe"), ("linux", "bin/python")]
)
def test_unconfigured_runtime_retains_platform_default(tmp_path, monkeypatch, platform, suffix):
    monkeypatch.delenv("OCF_CHATTERBOX_PYTHON", raising=False)
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    monkeypatch.setattr(voice_packs.sys, "platform", platform)
    assert voice_packs.runtime_interpreter() == tmp_path / "voice-envs/chatterbox" / suffix


def test_relative_interpreter_is_anchored_without_following_symlinks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OCF_CHATTERBOX_PYTHON", "runtime/bin/python")
    assert voice_packs.runtime_interpreter() == tmp_path / "runtime/bin/python"


def test_live_worker_rejects_runtime_change_before_sending_request(tmp_path, monkeypatch):
    from ocf_tools.utils import OCFError

    class Live:
        def poll(self):
            return None

    monkeypatch.setattr(voice_packs, "_worker_process", Live())
    monkeypatch.setattr(voice_packs, "_worker_interpreter", tmp_path / "first/bin/python")
    with pytest.raises(OCFError, match="runtime changed"):
        voice_packs._persistent_inference({}, tmp_path / "second/bin/python", 1)
