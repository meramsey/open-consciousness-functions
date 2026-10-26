"""Synthetic metadata/audio fixtures verify services, never inference or training."""

import json
import math
import subprocess
import wave
from array import array
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from ocf_tools import custom_voices as voices
from ocf_tools import voice_capabilities as capabilities
from ocf_tools import voice_datasets as datasets
from ocf_tools.indexes import load_voice_profiles
from ocf_tools.utils import OCFError, sha256_of_file


def synthetic_wav(path, *, rate=22050, channels=1, width=2, frequency=210, amplitude=8000):
    """A tone is not a speaker recording or an inference result."""
    pcm = array(
        "h",
        [
            round(amplitude * math.sin(2 * math.pi * frequency * i / rate))
            for i in range(rate // 10)
        ],
    )
    import sys

    if sys.byteorder != "little":
        pcm.byteswap()
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(width)
        output.setframerate(rate)
        output.writeframes(pcm.tobytes())
    return path


@pytest.fixture
def private_store(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("OCF_VOICE_ASSETS", str(tmp_path / "models"))
    return tmp_path


def synthetic_model(tmp_path, *, voice_id="OCF-VOICE-9801"):
    model = tmp_path / "fixture.onnx"
    model.write_bytes(b"synthetic weight fixture; NOT an inference model")
    Path(str(model) + ".json").write_text(
        json.dumps(
            {"language": {"code": "en_US"}, "audio": {"sample_rate": 22050}, "num_speakers": 1}
        )
    )
    return voices.import_model(model, voice_id=voice_id, name="Synthetic test only")["profile"]


def minimal_dataset(tmp_path):
    root = tmp_path / "dataset"
    datasets.initialize(root)
    manifest = root / "dataset.json"
    data = json.loads(manifest.read_text())
    data["records"] = [
        next(r for r in data["records"] if r["split"] == split)
        for split in ("train", "validation", "test")
    ]
    manifest.write_text(json.dumps(data))
    return manifest, data


def test_registry_distinguishes_installed_from_supported(monkeypatch):
    from ocf_tools import environment

    monkeypatch.setattr(capabilities.shutil, "which", lambda name: f"/local/{name}")
    monkeypatch.setattr(
        environment,
        "resolve_executable",
        lambda name: {
            "status": "ready",
            "binary": name,
            "executable": f"/local/{name}",
            "source": "PATH",
            "runtime": {
                "status": "ready",
                "python_version": "3.12.0",
                "package_version": "1.0.0",
                "package_metadata_found": True,
                "inference_verified": False,
            },
        },
    )
    monkeypatch.setattr(capabilities, "_package_present", lambda name: True)
    f5 = capabilities.backend_capability("f5-tts")
    assert f5["upstream"]["reference_inference"] and f5["upstream"]["training"]
    assert f5["installation"]["package_found"]
    assert not f5["available"] and not f5["ocf"]["inference_supported"]
    for backend in ("piper", "espeak", "espeak-ng"):
        report = capabilities.backend_capability(backend)
        assert report["ocf"]["cpu_tts"] and report["available"]
        assert not report["ocf"]["training_supported"]
    registry = capabilities.capability_registry()
    registry["f5-tts"]["ocf"]["inference_supported"] = True
    assert not capabilities.capability_registry()["f5-tts"]["ocf"]["inference_supported"]
    with pytest.raises(OCFError, match="unknown"):
        capabilities.backend_capability("imaginary")


def test_discovery_does_not_import_torch_or_launch_gpu_by_default(monkeypatch):
    requested = []
    monkeypatch.setattr(
        capabilities.importlib.util, "find_spec", lambda name: requested.append(name)
    )
    monkeypatch.setattr(
        capabilities, "workspace_run", lambda *a, **k: pytest.fail("unexpected process")
    )
    result = capabilities.local_preflight()
    assert requested == ["torch"]
    assert not result["torch_installed"] and result["gpu_probe"] == "not-requested"
    assert not result["training_resources_verified"]


def test_optional_gpu_query_is_bounded_and_does_not_claim_training_readiness(monkeypatch):
    monkeypatch.setattr(capabilities, "_package_present", lambda name: True)
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "/local/nvidia-smi")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="6144, 4096\n")

    monkeypatch.setattr(capabilities, "workspace_run", run)
    report = capabilities.local_preflight(probe_gpu=True, timeout=1000)
    assert report["gpus"] == [{"total_mib": 6144, "free_mib": 4096}]
    assert calls[0][1]["timeout"] == 5.0 and calls[0][1]["check"] is False
    assert "--query-gpu=memory.total,memory.free" in calls[0][0]
    assert not report["training_resources_verified"]


@pytest.mark.parametrize("failure", ["timeout", "invalid", "exit"])
def test_gpu_probe_failure_is_reported_without_capability_promotion(monkeypatch, failure):
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "nvidia-smi")

    def run(*args, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired("nvidia-smi", 2)
        return SimpleNamespace(returncode=1 if failure == "exit" else 0, stdout="invalid")

    monkeypatch.setattr(capabilities, "workspace_run", run)
    report = capabilities.local_preflight(probe_gpu=True)
    assert report["gpu_probe"] == "failed" and not report["gpus"]


def reference_profile(tmp_path):
    root = voices.asset_root()
    root.mkdir(parents=True, exist_ok=True)
    audio = synthetic_wav(root / "reference.wav")
    (root / "private").mkdir(exist_ok=True)
    (root / "private/consent.txt").write_text(
        "Synthetic fixture declaration; not independently verified consent."
    )
    return {
        "schema_version": "1.0",
        "id": "OCF-VOICE-9810",
        "slug": "reference-fixture",
        "name": "Synthetic reference fixture",
        "backend": "f5-tts",
        "locale": "en-US",
        "customization_method": "reference-audio",
        "reference_audio": {
            "asset": audio.name,
            "sha256": sha256_of_file(audio),
            "reference_text": "Synthetic tone, not spoken text or inference.",
            "locale": "en-US",
            "speaker": "synthetic-test-only",
            "consent_status": "self-recorded",
            "consent_record": "private/consent.txt",
        },
    }


def test_reference_profile_is_valid_metadata_but_unavailable(private_store, monkeypatch):
    monkeypatch.setattr(capabilities, "_package_present", lambda name: True)
    profile = reference_profile(private_store)
    result = voices.validate_profile(profile)
    assert result["valid"] and not result["available"] and not result["inference_supported"]
    assert not voices.profile_availability(profile)["available"]
    profile["reference_audio"]["consent_status"] = "unknown"
    with pytest.raises(OCFError, match="authorization"):
        voices.validate_profile(profile, assets=False)


def test_reference_checksum_config_and_locale_are_checked(private_store):
    profile = reference_profile(private_store)
    reference = profile["reference_audio"]
    config = voices.asset_root() / "reference.json"
    config.write_text("{}")
    reference.update(config_asset=config.name, config_sha256=sha256_of_file(config))
    voices.validate_profile(profile)
    config.write_text('{"changed": true}')
    with pytest.raises(OCFError, match="checksum"):
        voices.validate_profile(profile)
    reference["locale"] = "fr-FR"
    with pytest.raises(OCFError, match="locale"):
        voices.validate_profile(profile, assets=False)


def test_metadata_export_import_without_weights_is_redacted_and_unavailable(
    private_store, monkeypatch
):
    profile = synthetic_model(private_store)
    profile["notes"] = f"private {private_store}/notes"
    profile["attribution"] = f"Operator file {private_store}/speaker.txt"
    profile["consent_record"] = "private/consent.txt"
    profile["processing_defaults"] = {"gain_db": -1, "denoise": False}
    profile["rate_defaults"] = {"speed": 0.9}
    output = private_store / "portable.json"
    exported = voices.export_profile(profile, output)
    assert exported["assets_included"] == 0
    text = output.read_text()
    assert str(private_store) not in text and 'consent_record"' not in text
    assert "piper_model" not in text and not (private_store / "portable-assets").exists()
    monkeypatch.setenv("OCF_VOICE_ASSETS", str(private_store / "other-models"))
    result = voices.import_profile(output, voice_id="OCF-VOICE-9802")
    assert not result["availability"]["available"] and not result["inference_verified"]
    assert result["assets_copied"] == 0
    assert result["profile"]["rate_defaults"] == {"speed": 0.9}
    assert result["profile"]["processing_defaults"]["denoise"] is False


def test_opt_in_asset_roundtrip_and_existing_model_reuse(private_store, monkeypatch):
    profile = synthetic_model(private_store)
    output = private_store / "portable.json"
    voices.export_profile(profile["id"], output, include_assets=True)
    monkeypatch.setenv("OCF_VOICE_ASSETS", str(private_store / "destination-models"))
    result = voices.import_profile(output, include_assets=True, voice_id="OCF-VOICE-9802")
    assert result["assets_copied"] == 2 and not result["inference_verified"]
    model = Path(voices.model_path(result["profile"]))
    assert model.read_bytes() == b"synthetic weight fixture; NOT an inference model"
    second = voices.import_profile(output, include_assets=True, voice_id="OCF-VOICE-9803")
    assert second["profile"]["model"] == result["profile"]["model"]
    assert second["assets_copied"] == 0 and second["assets_reused"] == 2
    with pytest.raises(OCFError, match="already exists"):
        voices.import_profile(output, include_assets=True, voice_id="OCF-VOICE-9802")
    model.write_bytes(b"changed local model")
    with pytest.raises(OCFError, match="refusing replacement"):
        voices.import_profile(output, include_assets=True, voice_id="OCF-VOICE-9804")


def test_reference_bundle_requires_local_consent_reattachment(private_store, monkeypatch):
    profile = reference_profile(private_store)
    output = private_store / "reference.json"
    voices.export_profile(profile, output, include_assets=True)
    assert "private/consent.txt" not in output.read_text()
    monkeypatch.setenv("OCF_VOICE_ASSETS", str(private_store / "new-models"))
    with pytest.raises(OCFError, match="authorization"):
        voices.import_profile(output, include_assets=True)
    voices.asset_root().mkdir(parents=True)
    (voices.asset_root() / "local-consent.txt").write_text(
        "Local synthetic fixture declaration only."
    )
    result = voices.import_profile(output, include_assets=True, consent_record="local-consent.txt")
    assert result["assets_copied"] == 1 and not result["availability"]["available"]
    assert not result["inference_verified"]


@pytest.mark.parametrize(
    "unsafe",
    ["../outside.onnx", "/tmp/outside.onnx", "C:/private/model.onnx", "C:\\private\\model.onnx"],
)
@pytest.mark.parametrize("include_assets", [False, True])
def test_bundle_paths_reject_cross_platform_escape_before_publication(
    private_store, unsafe, include_assets
):
    profile = synthetic_model(private_store)
    output = private_store / "bundle.json"
    voices.export_profile(profile, output, include_assets=True)
    bundle = json.loads(output.read_text())
    bundle["assets"][0]["path"] = unsafe
    output.write_text(json.dumps(bundle))
    with pytest.raises(OCFError, match="contained|portable"):
        voices.import_profile(output, include_assets=include_assets, voice_id="OCF-VOICE-9802")
    assert not any(p["id"] == "OCF-VOICE-9802" for p in load_voice_profiles())


def test_tampered_bundle_and_symlink_escape_are_rejected(private_store):
    profile = synthetic_model(private_store)
    output = private_store / "bundle.json"
    voices.export_profile(profile, output, include_assets=True)
    bundle = json.loads(output.read_text())
    model = private_store / bundle["assets"][0]["path"]
    model.write_bytes(b"tampered bundle")
    with pytest.raises(OCFError, match="checksum"):
        voices.import_profile(output, include_assets=True, voice_id="OCF-VOICE-9802")
    model.unlink()
    model.symlink_to(private_store / "fixture.onnx")
    # Link is inside the bundle parent, so construct an actual parent escape.
    bundle["assets"][0]["path"] = "link/model.onnx"
    (private_store / "link").symlink_to(private_store.parent, target_is_directory=True)
    output.write_text(json.dumps(bundle))
    with pytest.raises(OCFError, match="escapes"):
        voices.import_profile(output, include_assets=True, voice_id="OCF-VOICE-9802")


def test_export_legacy_model_preserves_original_profile(private_store):
    synthetic_model(private_store)
    profile = {
        "schema_version": "1.0",
        "id": "OCF-VOICE-9890",
        "slug": "legacy-test",
        "name": "Legacy synthetic fixture",
        "backend": "piper",
        "piper_model": str(private_store / "fixture.onnx"),
    }
    original = deepcopy(profile)
    result = voices.export_profile(profile, private_store / "legacy.json", include_assets=True)
    assert profile == original and "piper_model" not in result["profile"]
    assert result["assets_included"] == 2 and not result["inference_verified"]


def test_trained_profile_requires_real_provenance_and_authorization(private_store):
    profile = synthetic_model(private_store)
    profile["customization_method"] = "trained-adapted"
    with pytest.raises(OCFError, match="training_provenance"):
        voices.validate_profile(profile, assets=False)
    profile["training_provenance"] = {
        "dataset_id": "synthetic-test-only",
        "dataset_sha256": "a" * 64,
        "backend_version": "test-only",
        "training_config_sha256": "b" * 64,
    }
    with pytest.raises(OCFError, match="authorization"):
        voices.validate_profile(profile, assets=False)
    profile.update(consent_status="self-recorded", consent_record="local-consent.txt")
    (voices.asset_root() / "local-consent.txt").write_text("Synthetic fixture declaration only.")
    assert not voices.validate_profile(profile)["inference_verified"]


def test_import_prompt_multiple_sessions_and_deterministic_split_report(private_store):
    manifest, original = minimal_dataset(private_store)
    prompt = original["records"][0]
    first_source = synthetic_wav(private_store / "first.wav")
    first = datasets.import_recording(
        manifest,
        prompt["id"],
        first_source,
        session_id="day-one",
        speaker="fixture",
        transcript=prompt["text"],
        session_metadata={
            "room_notes": "synthetic test; no room measurement",
            "gain_notes": "test only",
        },
    )
    assert first["record"]["sha256"] == sha256_of_file(first_source)
    assert first["record"]["text_sha256"] == datasets.text_fingerprint(prompt["text"])
    assert not first["converted"] and not first["microphone_captured"]
    second_source = synthetic_wav(private_store / "second.wav", frequency=310)
    second = datasets.import_recording(
        manifest, prompt["id"], second_source, session_id="day-two", speaker="fixture"
    )
    assert second["record"]["split"] == prompt["split"]
    assert second["record"]["prompt_id"] == prompt["id"]
    data = json.loads(manifest.read_text())
    assert len(data["sessions"]) == 2
    assert str(private_store) not in json.dumps(data)
    shuffled = deepcopy(data)
    shuffled["records"].reverse()
    assert datasets.split_report(data) == datasets.split_report(shuffled)
    before = manifest.read_bytes()
    with pytest.raises(OCFError, match="already imported"):
        datasets.import_recording(
            manifest, prompt["id"], second_source, session_id="day-two", speaker="fixture"
        )
    assert manifest.read_bytes() == before and first_source.exists()


@pytest.mark.parametrize("format_kwargs", [{"rate": 24000}, {"channels": 2}, {"width": 1}])
def test_recording_import_rejects_format_without_conversion_or_manifest_changes(
    private_store, format_kwargs
):
    manifest, data = minimal_dataset(private_store)
    source = synthetic_wav(private_store / "wrong-format.wav", **format_kwargs)
    before = manifest.read_bytes()
    with pytest.raises(OCFError, match="PCM16"):
        datasets.import_recording(
            manifest, data["records"][0]["id"], source, session_id="session", speaker="fixture"
        )
    assert manifest.read_bytes() == before


@pytest.mark.parametrize("session", ["../outside", "C:/private", "bad\\session"])
def test_recording_import_rejects_session_path_escape(private_store, session):
    manifest, data = minimal_dataset(private_store)
    source = synthetic_wav(private_store / "take.wav")
    before = manifest.read_bytes()
    with pytest.raises(OCFError, match="contained|metadata"):
        datasets.import_recording(
            manifest, data["records"][0]["id"], source, session_id=session, speaker="fixture"
        )
    assert manifest.read_bytes() == before


def test_recording_import_rejects_transcript_mismatch_and_session_speaker_change(private_store):
    manifest, data = minimal_dataset(private_store)
    source = synthetic_wav(private_store / "take.wav")
    prompt = data["records"][0]
    with pytest.raises(OCFError, match="exactly match"):
        datasets.import_recording(
            manifest,
            prompt["id"],
            source,
            session_id="session",
            speaker="fixture",
            transcript="Different text",
        )
    datasets.import_recording(
        manifest, prompt["id"], source, session_id="session", speaker="fixture"
    )
    with pytest.raises(OCFError, match="different speaker"):
        datasets.import_recording(
            manifest, data["records"][1]["id"], source, session_id="session", speaker="other"
        )


def test_dataset_readiness_and_training_blockers_remain_honest(private_store, monkeypatch):
    manifest, data = minimal_dataset(private_store)
    for index, prompt in enumerate(data["records"]):
        source = synthetic_wav(private_store / f"take-{index}.wav", frequency=200 + index * 60)
        datasets.import_recording(
            manifest, prompt["id"], source, session_id="session", speaker="synthetic-test-only"
        )
    report = datasets.validate_dataset(manifest)
    assert report["status"] == "passed" and not report["readiness"]["dataset_ready"]
    assert (
        not report["authorization_verified"] and report["quality_summary"]["measured_records"] == 3
    )
    data = json.loads(manifest.read_text())
    data.update(consent_status="self-recorded", consent_record="consent.txt")
    (manifest.parent / "consent.txt").write_text(
        "Synthetic fixture declaration only, not speaker authorization."
    )
    manifest.write_text(json.dumps(data))
    report = datasets.validate_dataset(manifest)
    assert report["readiness"]["dataset_ready"] and not report["authorization_verified"]
    monkeypatch.setattr(capabilities, "_package_present", lambda name: False)
    plan = datasets.training_plan(manifest, backend="f5-tts")
    assert not plan["ready"] and not plan["model_produced"] and not plan["training_supported"]
    assert not plan["inference_supported"] and any(
        "torch" in blocker for blocker in plan["blockers"]
    )
    assert any("memory" in blocker for blocker in plan["blockers"])
    assert plan["resources"]["gpu_probe"] == "not-requested"
    workflow = datasets.recording_workflow(manifest)
    assert workflow["workflow"] == "import-first" and not workflow["capture_supported"]
    data["records"][0]["text"] += " changed"
    manifest.write_text(json.dumps(data))
    assert any(
        d["code"] == "transcript-changed"
        for d in datasets.validate_dataset(manifest)["diagnostics"]
    )


def test_dataset_tampering_duplicate_takes_and_split_leakage_are_detected(private_store):
    manifest, data = minimal_dataset(private_store)
    source = synthetic_wav(private_store / "take.wav")
    prompt = data["records"][0]
    datasets.import_recording(manifest, prompt["id"], source, session_id="first", speaker="fixture")
    second = datasets.import_recording(
        manifest, prompt["id"], source, session_id="second", speaker="fixture"
    )
    data = json.loads(manifest.read_text())
    data["records"][-1]["split"] = "test" if prompt["split"] != "test" else "train"
    manifest.write_text(json.dumps(data))
    codes = {d["code"] for d in datasets.validate_dataset(manifest)["diagnostics"]}
    assert {"duplicate-audio", "prompt-split-leakage"} <= codes
    target = manifest.parent / second["record"]["audio"]
    target.write_bytes(b"invalid wav")
    codes = {d["code"] for d in datasets.validate_dataset(manifest)["diagnostics"]}
    assert {"checksum-mismatch", "decode"} <= codes


def test_room_gain_guidance_is_actionable_without_noise_measurement_claim():
    guidance = " ".join(
        datasets.recording_guidance(
            [{"code": "clipping"}, {"code": "low-level"}, {"code": "excessive-silence"}]
        )
    )
    assert "Lower input gain" in guidance and "re-record" in guidance
    assert "not a measured noise floor" in guidance and "room tone" in guidance


def test_existing_profiles_stay_schema_valid_and_unmodified():
    for profile in load_voice_profiles():
        original = deepcopy(profile)
        assert voices.validate_profile(profile, assets=False)["valid"]
        assert profile == original


def test_missing_binary_and_unsupported_method_are_unavailable(monkeypatch):
    from ocf_tools import environment

    monkeypatch.setattr(capabilities, "_package_present", lambda name: True)
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: None)
    monkeypatch.setattr(environment, "_user_home", lambda: Path("/nonexistent/ocf-test-home"))
    monkeypatch.setenv("OCF_PIPER_EXECUTABLE", "/nonexistent/ocf-test-piper")
    monkeypatch.setattr(
        environment,
        "resolve_executable",
        lambda name: {"status": "not-found", "reason": "not on PATH"},
    )
    assert not capabilities.backend_capability("piper")["available"]
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: "/local/piper")
    report = capabilities.profile_capability(
        {"backend": "piper", "customization_method": "reference-audio"}
    )
    assert not report["available"] and any("method" in reason for reason in report["blockers"])


def test_reference_configuration_requires_an_explicit_matching_method(private_store):
    profile = reference_profile(private_store)
    del profile["customization_method"]
    with pytest.raises(OCFError, match="customization_method"):
        voices.validate_profile(profile, assets=False)
    profile["customization_method"] = "installed-model"
    with pytest.raises(OCFError, match="reference-audio"):
        voices.validate_profile(profile, assets=False)


def test_dataset_consent_and_audio_symlink_escapes_block_readiness(private_store):
    manifest, data = minimal_dataset(private_store)
    data.update(consent_status="self-recorded", consent_record="../consent.txt")
    outside = synthetic_wav(private_store / "outside.wav")
    record = data["records"][0]
    (manifest.parent / record["audio"]).symlink_to(outside)
    manifest.write_text(json.dumps(data))
    report = datasets.validate_dataset(manifest)
    assert not report["readiness"]["dataset_ready"]
    codes = {d["code"] for d in report["diagnostics"]}
    assert {"unsafe-path", "unsafe-consent-path"} <= codes


def test_dataset_scaffold_has_deterministic_complete_split_coverage(private_store):
    datasets.initialize(private_store / "first")
    datasets.initialize(private_store / "second")
    first = json.loads((private_store / "first/dataset.json").read_text())
    second = json.loads((private_store / "second/dataset.json").read_text())
    assert datasets.split_report(first) == datasets.split_report(second)
    assert {r["split"] for r in first["records"]} == {"train", "validation", "test"}


def test_export_redacts_embedded_paths_and_preserves_public_attribution_urls(private_store):
    profile = synthetic_model(private_store)
    profile["attribution"] = (
        "source:/home/private/model file:C:\\Users\\Private\\voice https://example.org/attribution"
    )
    output = private_store / "redacted.json"
    exported = voices.export_profile(profile, output)
    attribution = exported["profile"]["attribution"]
    assert "/home/private" not in attribution and "Users" not in attribution
    assert "https://example.org/attribution" in attribution
    profile["pronunciation"] = {"/home/private/secret": {"piper": "hint"}}
    with pytest.raises(OCFError, match="metadata keys"):
        voices.export_profile(profile, private_store / "unsafe-keys.json")
    assert not (private_store / "unsafe-keys.json").exists()


def test_export_never_rewrites_reference_transcript_to_hide_paths(private_store):
    profile = reference_profile(private_store)
    profile["reference_audio"]["reference_text"] = "Say /home/private exactly."
    with pytest.raises(OCFError, match="cannot rewrite source wording"):
        voices.export_profile(profile, private_store / "unsafe-transcript.json")
    assert profile["reference_audio"]["reference_text"] == "Say /home/private exactly."


def test_malformed_portable_reference_has_schema_error_before_consent_injection(private_store):
    profile = reference_profile(private_store)
    output = private_store / "malformed.json"
    voices.export_profile(profile, output)
    bundle = json.loads(output.read_text())
    bundle["profile"]["reference_audio"] = "not-an-object"
    output.write_text(json.dumps(bundle))
    with pytest.raises(OCFError, match="schema"):
        voices.import_profile(output, consent_record="local-consent.txt")


def test_recording_import_contention_fails_safely_then_retry_preserves_both_updates(
    private_store, monkeypatch
):
    manifest, data = minimal_dataset(private_store)
    first_source = synthetic_wav(private_store / "first.wav")
    second_source = synthetic_wav(private_store / "second.wav", frequency=310)
    started, release = Event(), Event()
    original_copy = datasets.shutil.copyfileobj

    def paused_copy(incoming, out):
        if not started.is_set():
            started.set()
            assert release.wait(5), "test failed to release the first importer"
        return original_copy(incoming, out)

    monkeypatch.setattr(datasets.shutil, "copyfileobj", paused_copy)
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(
            datasets.import_recording,
            manifest,
            data["records"][0]["id"],
            first_source,
            session_id="first",
            speaker="fixture",
        )
        try:
            assert started.wait(5), "first importer never entered its transaction"
            with pytest.raises(OCFError, match="busy.*retry"):
                datasets.import_recording(
                    manifest,
                    data["records"][1]["id"],
                    second_source,
                    session_id="second",
                    speaker="fixture",
                )
        finally:
            release.set()
        first_result = first.result(timeout=5)
    second = datasets.import_recording(
        manifest, data["records"][1]["id"], second_source, session_id="second", speaker="fixture"
    )
    imported = json.loads(manifest.read_text())
    assert imported["records"][0] == first_result["record"]
    assert imported["records"][1] == second["record"]
    assert {s["id"] for s in imported["sessions"]} == {"first", "second"}


def test_recording_import_never_removes_an_existing_transaction_lock(private_store):
    manifest, data = minimal_dataset(private_store)
    source = synthetic_wav(private_store / "take.wav")
    lock = manifest.with_name(f".{manifest.name}.import.lock")
    lock.mkdir()
    owner = lock / "owner.txt"
    owner.write_text("another importer")
    before = manifest.read_bytes()
    with pytest.raises(OCFError, match="busy"):
        datasets.import_recording(
            manifest, data["records"][0]["id"], source, session_id="session", speaker="fixture"
        )
    assert owner.read_text() == "another importer" and manifest.read_bytes() == before


@pytest.mark.parametrize(
    "failure",
    ["staging-copy", "staging-checksum", "destination-copy", "destination-checksum", "manifest"],
)
def test_failed_recording_transaction_rolls_back_for_retry(private_store, monkeypatch, failure):
    manifest, data = minimal_dataset(private_store)
    source = synthetic_wav(private_store / "take.wav")
    before, original_audio = manifest.read_bytes(), source.read_bytes()
    prompt = data["records"][0]
    destination = manifest.parent / f"audio/session/{prompt['id']}.wav"
    original_copy = datasets.shutil.copyfileobj

    def failing_copy(incoming, out):
        original_copy(incoming, out)
        phase = "staging" if Path(out.name).name == "recording.wav" else "destination"
        if failure == phase + "-copy":
            raise OSError("injected copy failure")
        if failure == phase + "-checksum":
            out.write(b"corrupt copied fixture")

    def failed_manifest(*args, **kwargs):
        raise OSError("injected manifest failure")

    with monkeypatch.context() as patch:
        patch.setattr(datasets.shutil, "copyfileobj", failing_copy)
        if failure == "manifest":
            patch.setattr(datasets, "write_text_atomic", failed_manifest)
        with pytest.raises(OCFError, match="failure|checksum"):
            datasets.import_recording(
                manifest, prompt["id"], source, session_id="session", speaker="fixture"
            )
    assert manifest.read_bytes() == before and source.read_bytes() == original_audio
    assert (
        not destination.exists()
        and not manifest.with_name(f".{manifest.name}.import.lock").exists()
    )
    result = datasets.import_recording(
        manifest, prompt["id"], source, session_id="session", speaker="fixture"
    )
    assert destination.read_bytes() == original_audio
    assert len(json.loads(manifest.read_text())["records"]) == len(data["records"])
    assert result["record"]["sha256"] == sha256_of_file(source)


def test_recording_rollback_never_removes_a_destination_created_by_another_writer(
    private_store, monkeypatch
):
    manifest, data = minimal_dataset(private_store)
    source = synthetic_wav(private_store / "take.wav")
    prompt = data["records"][0]
    destination = manifest.parent / f"audio/session/{prompt['id']}.wav"
    before = manifest.read_bytes()
    original_copy = datasets.shutil.copyfileobj

    def racing_copy(incoming, out):
        original_copy(incoming, out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"another writer's prior asset")

    monkeypatch.setattr(datasets.shutil, "copyfileobj", racing_copy)
    with pytest.raises(OCFError, match="import failed"):
        datasets.import_recording(
            manifest, prompt["id"], source, session_id="session", speaker="fixture"
        )
    assert destination.read_bytes() == b"another writer's prior asset"
    assert manifest.read_bytes() == before


def test_recording_import_detects_manifest_conflict_and_preserves_operator_edit(
    private_store, monkeypatch
):
    manifest, data = minimal_dataset(private_store)
    source = synthetic_wav(private_store / "take.wav")
    prompt = data["records"][0]
    original_copy = datasets.shutil.copyfileobj
    data["license"] = "operator edit during import"

    def edit_during_copy(incoming, out):
        original_copy(incoming, out)
        manifest.write_text(json.dumps(data))

    with monkeypatch.context() as patch:
        patch.setattr(datasets.shutil, "copyfileobj", edit_during_copy)
        with pytest.raises(OCFError, match="manifest changed"):
            datasets.import_recording(
                manifest, prompt["id"], source, session_id="session", speaker="fixture"
            )
    assert json.loads(manifest.read_text()) == data
    assert not (manifest.parent / f"audio/session/{prompt['id']}.wav").exists()
    datasets.import_recording(
        manifest, prompt["id"], source, session_id="session", speaker="fixture"
    )
    assert json.loads(manifest.read_text())["license"] == "operator edit during import"


def test_recording_postcommit_exception_never_removes_committed_audio(private_store, monkeypatch):
    manifest, data = minimal_dataset(private_store)
    source = synthetic_wav(private_store / "take.wav")
    original_write = datasets.write_text_atomic

    def write_then_fail(*args, **kwargs):
        original_write(*args, **kwargs)
        raise OSError("injected postcommit failure")

    monkeypatch.setattr(datasets, "write_text_atomic", write_then_fail)
    with pytest.raises(OCFError, match="postcommit failure"):
        datasets.import_recording(
            manifest, data["records"][0]["id"], source, session_id="session", speaker="fixture"
        )
    record = json.loads(manifest.read_text())["records"][0]
    assert sha256_of_file(manifest.parent / record["audio"]) == record["sha256"]
    assert not manifest.with_name(f".{manifest.name}.import.lock").exists()


def test_importing_a_populated_scaffold_slot_completes_one_row_and_preserves_original(
    private_store,
):
    manifest, data = minimal_dataset(private_store)
    prompt = data["records"][0]
    original = synthetic_wav(manifest.parent / prompt["audio"])
    original_bytes = original.read_bytes()
    result = datasets.import_recording(
        manifest, prompt["id"], original, session_id="session", speaker="fixture"
    )
    imported = json.loads(manifest.read_text())
    assert len(imported["records"]) == len(data["records"])
    assert imported["records"][0] == result["record"]
    assert imported["records"][0]["id"] == prompt["id"]
    assert original.read_bytes() == original_bytes
    assert (manifest.parent / result["record"]["audio"]).read_bytes() == original_bytes
    assert not any(
        d["code"] == "duplicate-audio" for d in datasets.validate_dataset(manifest)["diagnostics"]
    )


@pytest.mark.parametrize("kind", ["cloned", "trained-adapted", "reference-audio"])
def test_asset_validation_requires_real_consent_file_but_declarations_allow_missing(
    private_store, kind
):
    if kind == "reference-audio":
        profile = reference_profile(private_store)
        consent = voices.asset_root() / profile["reference_audio"]["consent_record"]
    else:
        profile = synthetic_model(private_store)
        profile.update(consent_status="self-recorded", consent_record="consent.txt")
        if kind == "cloned":
            profile["voice_kind"] = "cloned"
        else:
            profile["customization_method"] = "trained-adapted"
            profile["training_provenance"] = {
                "dataset_id": "synthetic",
                "dataset_sha256": "a" * 64,
                "backend_version": "test-only",
                "training_config_sha256": "b" * 64,
            }
        consent = voices.asset_root() / "consent.txt"
        consent.write_text("Synthetic declaration only.")
    assert voices.validate_profile(profile)["valid"]
    consent.unlink()
    assert voices.validate_profile(profile, assets=False)["valid"]
    with pytest.raises(OCFError, match="consent record must exist as a file"):
        voices.validate_profile(profile)
    consent.mkdir()
    with pytest.raises(OCFError, match="consent record must exist as a file"):
        voices.validate_profile(profile)
    consent.rmdir()
    outside = private_store / "outside-consent.txt"
    outside.write_text("Outside asset root.")
    consent.symlink_to(outside)
    with pytest.raises(OCFError, match="escapes"):
        voices.validate_profile(profile)


@pytest.mark.parametrize("source_state", ["missing", "corrupt", "escape-symlink"])
def test_metadata_only_profile_import_does_not_require_sender_assets(
    private_store, monkeypatch, source_state
):
    profile = synthetic_model(private_store)
    bundle_path = private_store / "metadata.json"
    voices.export_profile(profile, bundle_path, include_assets=True)
    bundle = json.loads(bundle_path.read_text())
    for entry in bundle["assets"]:
        source = private_store / entry["path"]
        if source_state == "corrupt":
            source.write_bytes(b"corrupt sender fixture")
        else:
            source.unlink()
            if source_state == "escape-symlink":
                source.symlink_to(private_store.parent / "not-a-shared-asset")
    monkeypatch.setenv("OCF_VOICE_ASSETS", str(private_store / "receiving-models"))
    result = voices.import_profile(bundle_path, voice_id="OCF-VOICE-9802")
    assert result["assets_copied"] == 0 and not result["availability"]["available"]
    with pytest.raises(OCFError, match="checksum|missing|escapes"):
        voices.import_profile(bundle_path, include_assets=True, voice_id="OCF-VOICE-9803")
    bundle["assets"][0]["sha256"] = "f" * 64
    bundle_path.write_text(json.dumps(bundle))
    with pytest.raises(OCFError, match="identity/checksum"):
        voices.import_profile(bundle_path, voice_id="OCF-VOICE-9804")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize(
    "control", ["gain_db", "piper_length_scale", "processing_defaults", "rate_defaults"]
)
def test_nonfinite_profile_controls_fail_before_export_publication(private_store, value, control):
    profile = synthetic_model(private_store)
    if control == "processing_defaults":
        profile[control] = {"gain_db": value}
    elif control == "rate_defaults":
        profile[control] = {"speed": value}
    else:
        profile[control] = value
    with pytest.raises(OCFError, match="non-finite"):
        voices.validate_profile(profile, assets=False)
    output = private_store / "nonfinite.json"
    with pytest.raises(OCFError, match="non-finite"):
        voices.export_profile(profile, output, include_assets=True)
    assert not output.exists() and not (private_store / "nonfinite-assets").exists()


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e309", "-1e309"])
def test_import_rejects_nonfinite_json_including_exponent_overflow(private_store, token):
    profile = synthetic_model(private_store)
    profile["gain_db"] = 1.0
    path = private_store / "nonfinite.json"
    voices.export_profile(profile, path)
    path.write_text(path.read_text().replace('"gain_db": 1.0', f'"gain_db": {token}'))
    with pytest.raises(OCFError, match="non-finite"):
        voices.import_profile(path, voice_id="OCF-VOICE-9802")
    assert not any(p["id"] == "OCF-VOICE-9802" for p in load_voice_profiles())


def test_nonfinite_nested_metadata_is_rejected_even_if_field_would_be_redacted(private_store):
    profile = synthetic_model(private_store)
    # Invalid metadata must not be hidden by redaction.
    profile["notes"] = {"private": [{"numeric": float("nan")}]}
    with pytest.raises(OCFError, match=r"notes.private\[0\].numeric.*non-finite"):
        voices.export_profile(profile, private_store / "hidden-nonfinite.json")
