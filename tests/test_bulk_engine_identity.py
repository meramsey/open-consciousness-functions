"""Resume requires both matching engine inputs and verified output bytes."""

import io
import json
import wave
from pathlib import Path

import pytest
from ocf_tools import (
    audio_build,
    bulk_render,
    complete_session,
    farfield,
    semantic_dsp,
    speech_cache,
    utils,
    voice,
)
from ocf_tools.utils import sha256_of_file

pytestmark = pytest.mark.unit


@pytest.fixture
def bulk(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    engine = tmp_path / "engine.py"
    engine.write_text("implementation = 1\n")
    preset = tmp_path / "preset.yaml"
    preset.write_text("preset: one\n")
    source = tmp_path / "private.flac"
    source.write_bytes(b"synthetic source one")
    processor = tmp_path / "processor"
    processor.write_bytes(b"ffmpeg/ffprobe fixture implementation one")
    manifest = {"engine": "farfield", "preset": {"file": str(preset)}}
    profile = {"seed": 1, "states": {"one": {"mode": "preset", "preset": "fixture"}}}
    monkeypatch.setattr(audio_build, "_resolve_background_manifest", lambda _: manifest)
    monkeypatch.setattr(
        farfield, "engine_identity", lambda: {"implementation": sha256_of_file(engine)}
    )
    monkeypatch.setattr(semantic_dsp.shutil, "which", lambda _: str(processor))
    monkeypatch.setattr(
        bulk_render,
        "source_plan",
        lambda owner, locale: ({"id": owner}, {}, {"resolved_dsp_profile": profile}),
    )
    monkeypatch.setattr(complete_session, "build_complete_session_plan", lambda *_a, **_k: {})
    monkeypatch.setattr(semantic_dsp, "load_profile", lambda _: profile)
    monkeypatch.setattr(bulk_render, "LocaleCatalog", lambda: None)
    monkeypatch.setattr(bulk_render, "_voice_profile", lambda *_: ({}, {}))
    monkeypatch.setattr(bulk_render, "voice_identity", lambda _: {"tts": "unchanged"})
    monkeypatch.setattr(speech_cache, "voice_identity", lambda spec: spec)
    synthesis, outputs = [], []
    pcm = io.BytesIO()
    with wave.open(pcm, "wb") as writer:
        writer.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        writer.writeframes(b"\xe8\x03" * 80)
    monkeypatch.setattr(
        voice, "_render_cue_wav", lambda *args: synthesis.append(args) or pcm.getvalue()
    )

    def render(owner, **kwargs):
        with speech_cache.enabled():
            data = voice.render_cue_wav({}, "Unchanged speech.")
        root = tmp_path / f"output-{len(outputs)}"
        root.mkdir()
        (root / "master.wav").write_bytes(data)
        (root / "session-report.json").write_text(
            json.dumps(
                {
                    "artifacts": {
                        "wav": {
                            "path": "master.wav",
                            "size_bytes": len(data),
                            "sha256": sha256_of_file(root / "master.wav"),
                        }
                    }
                }
            )
        )
        outputs.append(root)
        return {"output_directory": str(root)}

    monkeypatch.setattr(bulk_render, "render_complete_session", render)
    return engine, preset, source, manifest, profile, synthesis, outputs


def run(**kwargs):
    return bulk_render.render_many(["fixture"], voice="fixture", **kwargs)["results"][0]


def test_implicit_engine_change_invalidates_same_audio_without_invalidating_speech(bulk):
    engine, _, _, _, _, synthesis, outputs = bulk
    assert run()["status"] == "rendered"
    assert run()["status"] == "skipped-verified"
    engine.write_text("implementation = 2\n")
    assert run()["status"] == "rendered"
    assert sha256_of_file(outputs[0] / "master.wav") == sha256_of_file(outputs[1] / "master.wav")
    assert len(synthesis) == 1
    (outputs[1] / "master.wav").write_bytes(b"corrupt")
    assert run()["status"] == "rendered"


def test_preset_and_experimental_profile_changes_invalidate_resume(bulk):
    _, preset, _, _, profile, _, _ = bulk
    assert run(dsp_profile="experimental.yaml")["status"] == "rendered"
    assert run(dsp_profile="experimental.yaml")["status"] == "skipped-verified"
    preset.write_text("preset: two\n")
    assert run(dsp_profile="experimental.yaml")["status"] == "rendered"
    profile["seed"] = 2
    assert run(dsp_profile="experimental.yaml")["status"] == "rendered"


def test_changed_common_processor_invalidates_farfield_backed_resume(bulk):
    engine = bulk[0]
    assert run()["status"] == "rendered"
    assert run()["status"] == "skipped-verified"
    (engine.parent / "processor").write_bytes(b"changed processing implementation")
    assert run()["status"] == "rendered"


def test_reference_source_identity_needs_no_farfield(bulk, monkeypatch):
    _, _, source, manifest, _, synthesis, _ = bulk
    manifest.update(engine="reference-master", preset={}, reference={"source": str(source)})
    monkeypatch.setattr(
        farfield, "engine_identity", lambda: pytest.fail("reference requires no Farfield")
    )
    assert run()["status"] == "rendered"
    assert run()["status"] == "skipped-verified"
    source.write_bytes(b"synthetic source two")
    assert run()["status"] == "rendered"
    assert len(synthesis) == 1


def test_unknown_engine_cannot_read_or_publish_trusted_resume_receipts(bulk, monkeypatch, tmp_path):
    run()
    monkeypatch.setattr(farfield, "engine_identity", lambda: None)
    for _ in range(2):
        result = run()
        assert result["status"] == "rendered"
        assert "unverified" in result["resume_verification"]
    assert len(list((tmp_path / "work/cache/bulk-renders").glob("*.json"))) == 1


def test_forced_sequential_functions_bypass_synthesis_cache_then_restore(bulk):
    *_, synthesis, outputs = bulk
    bulk_render.render_many(["first", "second"], voice="fixture")
    assert len(synthesis) == 1
    before = dict(speech_cache.STATS)
    result = bulk_render.render_many(["first", "second"], voice="fixture", force=True)
    assert all(row["status"] == "rendered" for row in result["results"])
    assert len(synthesis) == 3 and len(outputs) == 4
    assert speech_cache.STATS["bypassed"] - before["bypassed"] == 2
    run(resume=False)
    assert len(synthesis) == 3


def test_explicit_profile_dry_run_never_probes_or_hashes_backgrounds(bulk, monkeypatch):
    monkeypatch.setattr(
        semantic_dsp, "dependency_identity", lambda _: pytest.fail("dry-run fingerprinted inputs")
    )
    monkeypatch.setattr(complete_session, "build_complete_session_plan", lambda *args, **kwargs: {})
    assert run(dsp_profile="experimental.yaml", dry_run=True)["status"] == "planned"


def test_shared_reference_is_measured_once_per_batch_not_once_per_state_or_function(
    bulk, monkeypatch
):
    _, _, source, manifest, profile, _, _ = bulk
    manifest.update(engine="reference-master", preset={}, reference={"source": str(source)})
    profile["states"]["two"] = {"mode": "preset", "preset": "fixture"}
    reads = []
    original_open = open

    def counted(path, *args, **kwargs):
        if Path(path) == source and args == ("rb",):
            reads.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(utils, "open", counted, raising=False)
    result = bulk_render.render_many(["first", "second"], voice="fixture")
    assert result["failed"] == 0 and len(reads) == 1
    run()
    assert len(reads) == 2
