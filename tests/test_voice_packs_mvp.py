"""Portable private voice-pack and preparation contract tests; no speech inference."""

import math
import os
import stat
import wave
from array import array
from pathlib import Path

import pytest
from ocf_tools import voice_packs
from ocf_tools.custom_voices import asset_root, validate_profile
from ocf_tools.utils import OCFError, sha256_of_file


def tone(path: Path, seconds=6, rate=24000, silence_prefix=0, frequency=220):
    pcm = array("h")
    pcm.extend([0] * int(silence_prefix * rate))
    pcm.extend(
        round(6000 * math.sin(2 * math.pi * frequency * i / rate)) for i in range(seconds * rate)
    )
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm.tobytes())
    return path


@pytest.fixture
def private_store(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("OCF_VOICE_ASSETS", str(tmp_path / "assets"))
    return tmp_path


def test_prepare_reference_selects_active_audio_and_preserves_source(private_store):
    source = tone(private_store / "input.wav", silence_prefix=1)
    original = source.read_bytes()
    prepared = voice_packs.prepare_reference(source)
    output = Path(prepared["path"])
    assert source.read_bytes() == original
    assert prepared["metadata"]["source_sha256"] == sha256_of_file(source)
    assert prepared["metadata"]["clip"]["start_s"] >= 0.9
    if os.name == "posix":
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
    pack = voice_packs.create_pack(
        output,
        voice_id="OCF-VOICE-9893",
        name="Prepared synthetic fixture",
        locale="en-US",
        transcript="Synthetic fixture, not speech.",
        consent_declaration="Generated fixture for tests.",
    )
    assert pack["profile"]["creation_provenance"]["source_sha256"] == sha256_of_file(source)
    with wave.open(str(output), "rb") as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (24000, 1, 2)


def test_prepare_reference_rejects_corrupt_and_invalid_clip(private_store):
    corrupt = private_store / "corrupt.wav"
    corrupt.write_bytes(b"not wave")
    with pytest.raises(OCFError):
        voice_packs.prepare_reference(corrupt)
    source = tone(private_store / "input.wav")
    with pytest.raises(OCFError, match="extends beyond"):
        voice_packs.prepare_reference(source, start_s=5, duration_s=3)


def test_private_pack_registry_integrity_and_duplicate_id(private_store):
    source = tone(private_store / "reference.wav")
    result = voice_packs.create_pack(
        source,
        voice_id="OCF-VOICE-9891",
        name="Synthetic test fixture",
        locale="en-US",
        transcript="This is a synthetic fixture, not a speaker sample.",
        consent_declaration="Fixture generated for automated tests only.",
    )
    profile = result["profile"]
    assert profile["privacy"] == "private"
    assert profile["creation_provenance"]["source_sha256"] == sha256_of_file(source)
    assert validate_profile(profile)["valid"]
    assert voice_packs.inspect_pack("OCF-VOICE-9891")["pack_type"] == "reference-based-zero-shot"
    with pytest.raises(OCFError, match="already exists"):
        voice_packs.create_pack(
            source,
            voice_id="OCF-VOICE-9891",
            name="Duplicate",
            locale="en-US",
            transcript="Text",
            consent_declaration="Declared",
        )
    asset = asset_root() / profile["reference_audio"]["asset"]
    if os.name == "posix":
        assert stat.S_IMODE(asset.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(asset.stat().st_mode) == 0o600
    asset.write_bytes(b"tampered")
    with pytest.raises(OCFError, match="checksum"):
        validate_profile(profile)


def test_chatterbox_pack_allows_untranscribed_reference_without_claiming_transcript(
    private_store,
):
    reference = tone(private_store / "reference.wav")
    created = voice_packs.create_pack(
        reference,
        voice_id="OCF-VOICE-9890",
        name="Untranscribed local reference",
        locale="en-US",
        consent_declaration="Owner authorizes private local reference-conditioned inference.",
    )
    pack = created["profile"]["reference_audio"]
    assert pack["transcript_status"] == "not-provided"
    assert "reference_text" not in pack
    assert validate_profile(created["profile"])["valid"]


def test_pack_allows_missing_transcript_but_requires_consent(private_store):
    source = tone(private_store / "reference.wav")
    with pytest.raises(OCFError, match="transcript"):
        voice_packs.create_pack(
            source,
            voice_id="OCF-VOICE-9892",
            name="Fixture",
            locale="en-US",
            transcript=" ",
            consent_declaration="Declared",
        )
    with pytest.raises(OCFError, match="English locales only"):
        voice_packs.create_pack(
            tone(private_store / "reference.wav"),
            voice_id="OCF-VOICE-9892",
            name="Unsupported locale",
            locale="es-ES",
            transcript="Texto exacto.",
            consent_declaration="Authorized test only.",
        )


def test_optional_backend_missing_is_reported_without_tts_fallback(private_store, monkeypatch):
    source = tone(private_store / "reference.wav")
    voice_packs.create_pack(
        source,
        voice_id="OCF-VOICE-9894",
        name="Synthetic fixture",
        locale="en-US",
        transcript="Fixture text.",
        consent_declaration="Test fixture only.",
    )
    monkeypatch.delenv("OCF_CHATTERBOX_PYTHON", raising=False)
    with pytest.raises(OCFError, match="optional environment is missing"):
        voice_packs.synthesize("OCF-VOICE-9894", "A new sentence.")
    assert not voice_packs.inspect_pack("OCF-VOICE-9894")["inference_verified"]


def test_registered_pack_resolves_explicitly_without_becoming_default(private_store):
    from ocf_tools.voice import first_available_backend, resolve_backend

    voice_packs.create_pack(
        tone(private_store / "reference.wav"),
        voice_id="OCF-VOICE-9895",
        name="Synthetic fixture",
        locale="en-US",
        transcript="Fixture text.",
        consent_declaration="Test fixture only.",
    )
    selected = resolve_backend("OCF-VOICE-9895", locale="en-US")
    assert selected["name"] == "chatterbox-nano"
    assert selected["profile_id"] == "OCF-VOICE-9895"
    assert first_available_backend() != "chatterbox-nano"
    with pytest.raises(OCFError, match="requires selecting"):
        resolve_backend("chatterbox-nano")


def test_session_voice_adapter_routes_explicit_pack_and_returns_actual_wav(
    private_store, monkeypatch
):
    from ocf_tools import voice

    voice_packs.create_pack(
        tone(private_store / "reference.wav"),
        voice_id="OCF-VOICE-9898",
        name="Synthetic fixture",
        locale="en-US",
        transcript="Fixture words.",
        consent_declaration="Test fixture only.",
    )
    output = tone(private_store / "expected.wav")
    monkeypatch.setattr(
        voice_packs,
        "synthesize",
        lambda query, text, **kwargs: {"output": str(output)},
    )
    spec = voice.resolve_backend("OCF-VOICE-9898", locale="en-US")
    assert voice._render_cue_wav(spec, "A new sentence.") == output.read_bytes()


def test_narration_profile_resolution_accepts_python_backend(private_store, monkeypatch):
    from ocf_tools import voice_capabilities
    from ocf_tools.locale import LocaleCatalog
    from ocf_tools.narration_first import _voice_profile

    voice_packs.create_pack(
        tone(private_store / "reference.wav"),
        voice_id="OCF-VOICE-9899",
        name="Synthetic fixture",
        locale="en-US",
        transcript="Fixture words.",
        consent_declaration="Test fixture only.",
    )
    original = voice_capabilities.backend_capability

    def available(backend):
        result = original(backend)
        if backend == "chatterbox-nano":
            result["available"] = True
            result["installation"]["executable_found"] = True
            result["installation"]["package_found"] = True
        return result

    monkeypatch.setattr(voice_capabilities, "backend_capability", available)
    profile, spec = _voice_profile("OCF-VOICE-9899", "en-US", LocaleCatalog())
    assert profile["id"] == "OCF-VOICE-9899"
    assert spec["name"] == "chatterbox-nano"


def test_synthesis_cache_fingerprints_reference_without_executable(private_store):
    from ocf_tools.speech_cache import voice_identity
    from ocf_tools.voice import resolve_backend

    pack = voice_packs.create_pack(
        tone(private_store / "reference.wav"),
        voice_id="OCF-VOICE-9892",
        name="Synthetic fixture",
        locale="en-US",
        transcript="Fixture words.",
        consent_declaration="Test fixture only.",
    )
    identity = voice_identity(resolve_backend(pack["profile"], locale="en-US"))
    assert identity["assets"]["reference_audio"] == pack["profile"]["reference_audio"]["sha256"]
    assert "binary" not in identity["assets"]


def test_synthesis_receipt_promotes_only_after_success(private_store, monkeypatch):
    from types import SimpleNamespace

    profile = voice_packs.create_pack(
        tone(private_store / "reference.wav"),
        voice_id="OCF-VOICE-9891",
        name="Synthetic fixture",
        locale="en-US",
        transcript="Fixture words.",
        consent_declaration="Test fixture only.",
    )["profile"]
    executable = private_store / "optional" / "python"
    executable.parent.mkdir()
    executable.write_text("test interpreter")
    monkeypatch.setenv("OCF_CHATTERBOX_PYTHON", str(executable))
    output = private_store / "generated.wav"
    tone(output)
    request = {}

    def run(command, **kwargs):
        request.update(__import__("json").loads(kwargs["input"]))
        Path(request["output"]).parent.mkdir(parents=True, exist_ok=True)
        Path(request["output"]).write_bytes(output.read_bytes())
        return SimpleNamespace(
            returncode=0,
            stdout=__import__("json").dumps(
                {
                    "backend": "chatterbox-nano",
                    "model_identifier": "ResembleAI/chatterbox-nano",
                    "model_revision": "a" * 40,
                    "model_tree_sha256": "b" * 64,
                    "adapter_revision": profile["reference_audio"]["adapter_revision"],
                    "output": request["output"],
                    "output_sha256": sha256_of_file(output),
                    "reference_sha256": profile["reference_audio"]["sha256"],
                    "reference_text_sha256": request["reference_text_sha256"],
                    "text_sha256": __import__("hashlib").sha256(b"New text.").hexdigest(),
                    "sample_rate": 24000,
                    "duration_s": 6.0,
                    "sample_peak": 0.8,
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(
        voice_packs,
        "workspace_run",
        run,
    )
    report = voice_packs.synthesize("OCF-VOICE-9891", "New text.")
    assert report["output_sha256"] == sha256_of_file(output)
    inspected = voice_packs.inspect_pack("OCF-VOICE-9891")
    assert inspected["inference_receipts"][0]["status"] == "success"
    assert inspected["inference_verified"] is True
    assert inspected["validation"]["inference_verified"] is True


def test_pack_export_import_is_portable_and_requires_local_consent(private_store, monkeypatch):
    source = tone(private_store / "reference.wav")
    pack = voice_packs.create_pack(
        source,
        voice_id="OCF-VOICE-9896",
        name="Portable synthetic fixture",
        locale="en-US",
        transcript="Fixture words.",
        consent_declaration="Local test fixture only.",
    )
    bundle_path = private_store / "portable.json"
    exported = voice_packs.custom_voices.export_profile(
        pack["profile"], bundle_path, include_assets=True
    )
    assert exported["assets_included"] == 1
    bundle = __import__("json").loads(bundle_path.read_text())
    assert bundle["kind"] == "ocf-voice-pack"
    assert all(not Path(entry["path"]).is_absolute() for entry in bundle["assets"])
    assert "consent.txt" not in bundle_path.read_text()
    relocated_assets = private_store / "relocated-assets"
    monkeypatch.setenv("OCF_VOICE_ASSETS", str(relocated_assets))
    local_consent = asset_root() / "local/consent.txt"
    local_consent.parent.mkdir(parents=True, exist_ok=True)
    local_consent.write_text("Reauthorized locally for this test.")
    imported = voice_packs.custom_voices.import_profile(
        bundle_path,
        include_assets=True,
        voice_id="OCF-VOICE-9897",
        consent_record="local/consent.txt",
    )
    assert imported["profile"]["privacy"] == "private"
    assert imported["assets_copied"] == 1
    assert imported["profile"]["reference_audio"]["source_sha256"] == sha256_of_file(source)


def test_chatterbox_runner_enforces_upstream_reference_minimum(private_store):
    from ocf_tools.chatterbox_backend import synthesize

    reference = tone(private_store / "short.wav", seconds=2)
    with pytest.raises(ValueError, match="longer than five seconds"):
        synthesize(
            reference,
            "A new utterance.",
            private_store / "out.wav",
            reference_text_sha256="0" * 64,
        )


def test_chatterbox_output_uses_only_downward_peak_gain():
    from ocf_tools.chatterbox_backend import _pcm16

    pcm, gain, peak = _pcm16([1.0622, -0.5, 0.0])
    assert peak == 1.0622 and 0 < gain < 1
    assert max(map(abs, pcm)) / 32768 <= 0.98
    _, unity_gain, _ = _pcm16([0.8, -0.4])
    assert unity_gain == 1


def test_persistent_engine_reuses_model_and_never_reuses_other_reference_conditioning(
    private_store,
):
    from ocf_tools.chatterbox_backend import PersistentEngine

    loaded = []

    class Model:
        def __init__(self):
            self.references = []

        def prepare_conditionals(self, reference, **kwargs):
            self.references.append(reference)

    class ModelClass:
        @classmethod
        def from_pretrained(cls, **kwargs):
            loaded.append(kwargs)
            return Model()

    first_ref = tone(private_store / "speaker-a.wav")
    second_ref = tone(private_store / "speaker-b.wav", frequency=330)
    engine = PersistentEngine()
    torch = object()
    first = engine.prepare(torch, ModelClass, "cpu", first_ref)
    repeated = engine.prepare(torch, ModelClass, "cpu", first_ref)
    other = engine.prepare(torch, ModelClass, "cpu", second_ref)
    assert len(loaded) == 1
    assert first[1:3] == (False, False)
    assert repeated[1:3] == (True, True)
    assert other[1:3] == (True, False)
    assert len(engine.model.references) == 2


@pytest.mark.skipif(
    not os.environ.get("OCF_CHATTERBOX_INTEGRATION_VOICE_ID"),
    reason="requires an explicitly supplied local voice pack and downloaded Chatterbox Nano model",
)
def test_opt_in_real_chatterbox_inference_reuses_pack_for_new_text(monkeypatch):
    from ocf_tools.paths import REPO_ROOT

    monkeypatch.setenv("OCF_WORK_DIR", str(REPO_ROOT / ".ocf-work"))
    voice_id = os.environ["OCF_CHATTERBOX_INTEGRATION_VOICE_ID"]
    with voice_packs.persistent_worker():
        first = voice_packs.synthesize(voice_id, "A first original test sentence.", device="auto")
        second = voice_packs.synthesize(
            voice_id, "A different sentence, followed by three, two, one.", device="auto"
        )
    assert first["reference_sha256"] == second["reference_sha256"]
    assert first["text_sha256"] != second["text_sha256"]
    assert first["output_sha256"] != second["output_sha256"]
    assert not first["model_reused"] and second["model_reused"]
    assert second["speaker_conditioning_reused"]
    for result in (first, second):
        with wave.open(result["output"], "rb") as wav:
            assert wav.getnframes() / wav.getframerate() > 0
        assert result["sample_peak"] <= 0.98
    assert voice_packs.inspect_pack(voice_id)["inference_verified"] is True
