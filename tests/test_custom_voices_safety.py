"""Focused portable-path, checksum and voice-pack input-boundary tests."""

import hashlib
import json
import wave
from array import array
from pathlib import Path

import pytest
from ocf_tools import custom_voices, narration_first, narration_pacing, voice, voice_packs
from ocf_tools.utils import OCFError, sha256_of_file

pytestmark = pytest.mark.unit


def reference(path: Path, *, seconds=6, rate=24000, channels=1, width=2):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(width)
        output.setframerate(rate)
        frames = seconds * rate
        if width == 1:
            output.writeframes(bytes([127]) * frames * channels)
        else:
            samples = [1000] if channels == 1 else [1000, -1000]
            output.writeframes(array("h", samples * frames).tobytes())
    return path


@pytest.fixture
def private_store(monkeypatch, tmp_path):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    assets = tmp_path / "assets"
    monkeypatch.setenv("OCF_VOICE_ASSETS", str(assets))
    return tmp_path


def make_pack(private_store, voice_id="OCF-VOICE-9898"):
    return voice_packs.create_pack(
        reference(private_store / f"{voice_id}.wav"),
        voice_id=voice_id,
        name="Synthetic fixture",
        locale="en-US",
        transcript="Fixture words.",
        consent_declaration="Test fixture only.",
    )


def piper_profile(private_store, config, *, speaker_id=None, include_config_hash=True):
    root = custom_voices.asset_root()
    root.mkdir(parents=True, exist_ok=True)
    model_bytes = b"synthetic piper model"
    model_hash = hashlib.sha256(model_bytes).hexdigest()
    model_asset = root / f"{model_hash}.onnx"
    model_asset.write_bytes(model_bytes)
    config_path = Path(str(model_asset) + ".json")
    config_path.write_text(json.dumps(config))
    model = {"asset": model_asset.name, "sha256": model_hash, "version": "fixture"}
    if include_config_hash:
        model["config_sha256"] = sha256_of_file(config_path)
    return {
        "schema_version": "1.0",
        "id": "OCF-VOICE-9875",
        "slug": "ocf-voice-9875",
        "name": "Synthetic Piper fixture",
        "backend": "piper",
        "customization_method": "installed-model",
        "voice_kind": "installed-model",
        "locale": "en-US",
        "language": "en_US",
        "sample_rate": 24000,
        "model": model,
        **({"speaker_id": speaker_id} if speaker_id is not None else {}),
    }


@pytest.mark.parametrize(
    "value",
    [
        "",
        ".",
        "/etc/passwd",
        "//server/share/file.wav",
        "C:\\Users\\person\\voice.wav",
        "\\\\server\\share\\voice.wav",
        "../outside.wav",
        "voice/../outside.wav",
        "voice\\reference.wav",
        "~/private.wav",
        "$HOME/private.wav",
        "voice\nreference.wav",
    ],
)
def test_portable_paths_reject_platform_and_traversal_escapes(value):
    with pytest.raises(OCFError, match="portable relative path"):
        custom_voices._portable_relative(value)


def test_portable_paths_allow_unicode_contained_relative_assets():
    assert custom_voices._portable_relative("OCF-VOICE-0001/voix de référence.wav").parts == (
        "OCF-VOICE-0001",
        "voix de référence.wav",
    )


@pytest.mark.parametrize(
    "value,match",
    [
        (float("nan"), "non-finite"),
        (float("inf"), "non-finite"),
        ({1: "non-string key"}, "keys must be strings"),
        ({"nested": [object()]}, "JSON-compatible"),
    ],
)
def test_nested_portable_metadata_rejects_non_json_values(value, match):
    with pytest.raises(OCFError, match=match):
        custom_voices._validate_finite_json(value)


def test_copy_verified_rejects_missing_bad_and_symlink_assets(private_store):
    root = private_store / "assets"
    source = private_store / "source.wav"
    source.write_bytes(b"reference bytes")
    digest = sha256_of_file(source)
    with pytest.raises(OCFError, match="checksum mismatch or asset missing"):
        custom_voices._copy_verified(private_store / "missing.wav", root / "missing.wav", digest)
    with pytest.raises(OCFError, match="checksum mismatch or asset missing"):
        custom_voices._copy_verified(source, root / "wrong.wav", "0" * 64)

    copied = root / "nested" / "reference.wav"
    assert custom_voices._copy_verified(source, copied, digest) is True
    assert copied.read_bytes() == source.read_bytes()
    assert custom_voices._copy_verified(source, copied, digest) is False
    copied.write_bytes(b"tampered")
    with pytest.raises(OCFError, match="existing model asset differs"):
        custom_voices._copy_verified(source, copied, digest)

    link = root / "linked.wav"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform")
    with pytest.raises(OCFError, match="symlink"):
        custom_voices._copy_verified(source, link, digest)


def test_copy_verified_detects_a_corrupted_copy(private_store, monkeypatch):
    source = private_store / "source.wav"
    destination = private_store / "assets/copy.wav"
    source.write_bytes(b"source bytes")
    digest = sha256_of_file(source)
    original_hash = custom_voices.sha256_of_file

    def corrupted_hash(path):
        if Path(path) == destination:
            return "0" * 64
        return original_hash(path)

    monkeypatch.setattr(custom_voices, "sha256_of_file", corrupted_hash)
    with pytest.raises(OCFError, match="copied asset checksum mismatch"):
        custom_voices._copy_verified(source, destination, digest)


def test_contained_rejects_symlink_escape(private_store, tmp_path):
    root = private_store / "assets"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "external"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform")
    with pytest.raises(OCFError, match="escapes its configured root"):
        custom_voices._contained(root, "external/voice.wav")


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("unsupported-locale", "English locales only"),
        ("locale-mismatch", "reference audio locale differs"),
        ("missing-profile-consent", "cloned/trained voice requires explicit authorization"),
        ("missing-reference-consent", "reference audio requires explicit authorization"),
        ("reference-traversal", "does not match"),
    ],
)
def test_profile_validation_keeps_reference_and_consent_boundaries(private_store, mutation, match):
    profile = make_pack(private_store)["profile"]
    if mutation == "unsupported-locale":
        profile["locale"] = "fr-FR"
    elif mutation == "locale-mismatch":
        profile["reference_audio"]["locale"] = "en-GB"
    elif mutation == "missing-profile-consent":
        profile.pop("consent_record")
        profile["consent_status"] = "unknown"
    elif mutation == "missing-reference-consent":
        profile["reference_audio"].pop("consent_record")
        profile["reference_audio"]["consent_status"] = "unknown"
    elif mutation == "reference-traversal":
        profile["reference_audio"]["asset"] = "../outside.wav"
    with pytest.raises(OCFError, match=match):
        custom_voices.validate_profile(profile)


def test_reference_profile_without_model_is_valid_but_reports_runtime_blocker(private_store):
    profile = make_pack(private_store)["profile"]
    assert custom_voices.model_path(profile) is None
    result = custom_voices.profile_availability(profile)
    assert result["available"] is False
    assert result["blockers"]


@pytest.mark.parametrize(
    "config,speaker_id,match",
    [
        ({"language": {"code": "en_US"}}, None, "lacks an audio object"),
        (
            {"language": {"code": "en_US"}, "audio": {"sample_rate": 16000}},
            None,
            "declared sample rate differs",
        ),
        (
            {
                "language": {"code": "en_US"},
                "audio": {"sample_rate": 24000},
                "num_speakers": 0,
            },
            None,
            "speaker count must be a positive integer",
        ),
        (
            {
                "language": {"code": "en_US"},
                "audio": {"sample_rate": 24000},
                "num_speakers": 1,
            },
            1,
            "outside the model speaker range",
        ),
    ],
)
def test_piper_configuration_and_speaker_identity_are_validated(
    private_store, config, speaker_id, match
):
    profile = piper_profile(private_store, config, speaker_id=speaker_id)
    with pytest.raises(OCFError, match=match):
        custom_voices.validate_profile(profile)


def test_piper_configuration_checksum_is_checked_and_export_can_derive_it(private_store):
    config = {"language": {"code": "en_US"}, "audio": {"sample_rate": 24000}}
    profile = piper_profile(private_store, config)
    profile["model"]["config_sha256"] = "0" * 64
    with pytest.raises(OCFError, match="configuration checksum mismatch"):
        custom_voices.validate_profile(profile)

    portable = piper_profile(private_store, config, include_config_hash=False)
    output = private_store / "piper-portable.json"
    exported = custom_voices.export_profile(portable, output, include_assets=True)
    assert exported["assets_included"] == 2
    assert exported["profile"]["model"]["config_sha256"] == sha256_of_file(
        Path(custom_voices.asset_root() / (portable["model"]["asset"] + ".json"))
    )


def test_profile_validation_rejects_model_symlink_escape(private_store):
    profile = piper_profile(
        private_store, {"language": {"code": "en_US"}, "audio": {"sample_rate": 24000}}
    )
    root = custom_voices.asset_root()
    outside = private_store / "outside-assets"
    outside.mkdir()
    try:
        (root / "external").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform")
    profile["model"]["asset"] = "external/model.onnx"
    with pytest.raises(OCFError, match="escapes its configured root"):
        custom_voices.validate_profile(profile)


def test_piper_model_export_requires_local_configuration(private_store):
    profile = piper_profile(
        private_store,
        {"language": {"code": "en_US"}, "audio": {"sample_rate": 24000}},
        include_config_hash=False,
    )
    Path(custom_voices.asset_root() / (profile["model"]["asset"] + ".json")).unlink()
    with pytest.raises(OCFError, match="configuration must be installed"):
        custom_voices.export_profile(profile, private_store / "no-piper-config.json")


def test_legacy_piper_model_export_builds_portable_checksums(private_store):
    model = private_store / "legacy.onnx"
    model.write_bytes(b"synthetic legacy piper model")
    Path(str(model) + ".json").write_text(
        json.dumps({"language": {"code": "en_US"}, "audio": {"sample_rate": 22050}})
    )
    profile = {
        "schema_version": "1.0",
        "id": "OCF-VOICE-9872",
        "slug": "ocf-voice-9872",
        "name": "Legacy synthetic Piper fixture",
        "backend": "piper",
        "customization_method": "installed-model",
        "piper_model": str(model),
        "voice_kind": "installed-model",
    }
    output = private_store / "legacy-portable.json"
    exported = custom_voices.export_profile(profile, output, include_assets=True)
    assert exported["assets_included"] == 2
    assert "piper_model" not in exported["profile"]
    assert exported["profile"]["model"]["sha256"] == sha256_of_file(model)


def test_portable_metadata_import_can_leave_assets_local(private_store, monkeypatch):
    profile = piper_profile(
        private_store, {"language": {"code": "en_US"}, "audio": {"sample_rate": 24000}}
    )
    bundle = private_store / "piper-metadata-only.json"
    custom_voices.export_profile(profile, bundle)
    monkeypatch.setenv("OCF_VOICE_ASSETS", str(private_store / "other-assets"))
    imported = custom_voices.import_profile(bundle, voice_id="OCF-VOICE-9873")
    assert imported["assets_copied"] == 0
    assert imported["profile"]["privacy"] == "private"
    assert imported["availability"]["available"] is False


def test_portable_profile_import_refuses_existing_symlink_destination(private_store):
    profile = make_pack(private_store)["profile"]
    bundle = private_store / "symlink-destination.json"
    custom_voices.export_profile(profile, bundle)
    destination = private_store / "work/cache/voices/profiles/OCF-VOICE-9873.yaml"
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = private_store / "work/other/different-profile.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(
        "schema_version: '1.0'\nid: OCF-VOICE-9875\nslug: different-profile\n"
        "name: Different profile\nbackend: espeak-ng\n"
    )
    try:
        destination.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform")
    consent = custom_voices.asset_root() / "local/consent.txt"
    consent.parent.mkdir(parents=True, exist_ok=True)
    consent.write_text("Local test reauthorization.")
    with pytest.raises(OCFError, match="already exists"):
        custom_voices.import_profile(
            bundle,
            voice_id="OCF-VOICE-9873",
            consent_record="local/consent.txt",
        )


def test_non_piper_model_metadata_skips_piper_configuration_checks(private_store):
    profile = piper_profile(
        private_store, {"language": {"code": "en_US"}, "audio": {"sample_rate": 24000}}
    )
    profile["backend"] = "espeak-ng"
    assert custom_voices.validate_profile(profile)["valid"]


@pytest.mark.parametrize("failure", ["occupied-sidecar", "missing-reference"])
def test_profile_export_refuses_existing_or_unverifiable_assets(private_store, failure):
    profile = make_pack(private_store)["profile"]
    output = private_store / "bundle.json"
    if failure == "occupied-sidecar":
        output.with_name(output.stem + "-assets").mkdir()
    else:
        (custom_voices.asset_root() / profile["reference_audio"]["asset"]).unlink()
    with pytest.raises(OCFError):
        custom_voices.export_profile(profile, output, include_assets=True)


@pytest.mark.parametrize(
    "tamper,match",
    [
        ("kind", "not an OCF portable"),
        ("profile-private-field", "private paths or nonportable fields"),
        ("assets-type", "bundle assets must be a list"),
        ("asset-shape", "invalid portable asset entry"),
        ("missing-assets", "does not contain every required asset"),
        ("duplicate-id", "already exists"),
    ],
)
def test_portable_profile_import_rejects_incomplete_or_private_bundles(
    private_store, tamper, match
):
    profile = make_pack(private_store)["profile"]
    bundle_path = private_store / "portable.json"
    custom_voices.export_profile(profile, bundle_path, include_assets=True)
    bundle = json.loads(bundle_path.read_text())
    voice_id = "OCF-VOICE-9874"
    kwargs = {"include_assets": True, "voice_id": voice_id, "consent_record": "local/consent.txt"}
    consent = custom_voices.asset_root() / "local/consent.txt"
    consent.parent.mkdir(parents=True, exist_ok=True)
    consent.write_text("Local test reauthorization.")
    if tamper == "kind":
        bundle["kind"] = "foreign-format"
    elif tamper == "profile-private-field":
        bundle["profile"]["notes"] = "/home/example/private.txt"
    elif tamper == "assets-type":
        bundle["assets"] = "not-a-list"
    elif tamper == "asset-shape":
        bundle["assets"][0].pop("sha256")
    elif tamper == "missing-assets":
        bundle["assets"] = []
    elif tamper == "duplicate-id":
        voice_packs.create_pack(
            reference(private_store / "existing.wav"),
            voice_id=voice_id,
            name="Existing fixture",
            locale="en-US",
            transcript="Fixture words.",
            consent_declaration="Test fixture only.",
        )
        kwargs["include_assets"] = False
    bundle_path.write_text(json.dumps(bundle))
    with pytest.raises(OCFError, match=match):
        custom_voices.import_profile(bundle_path, **kwargs)


def test_redaction_and_asset_identity_helpers_reject_private_conflicts():
    with pytest.raises(OCFError, match="metadata keys contain private absolute paths"):
        custom_voices._redacted({"/home/example/private": "value"})
    assert custom_voices._redacted({"path": "/home/example/private.wav"}) == {
        "path": "[redacted-path]"
    }
    with pytest.raises(OCFError, match="conflicting checksums"):
        custom_voices._profile_assets(
            {
                "backend": "chatterbox-nano",
                "model": {"asset": "duplicate.wav", "sha256": "a" * 64},
                "reference_audio": {"asset": "duplicate.wav", "sha256": "b" * 64},
            }
        )
    assert custom_voices._profile_assets(
        {
            "reference_audio": {
                "asset": "voice/reference.wav",
                "sha256": "a" * 64,
                "config_asset": "voice/reference.json",
                "config_sha256": "b" * 64,
            }
        }
    ) == [
        ("voice/reference.wav", "a" * 64),
        ("voice/reference.json", "b" * 64),
    ]


def test_piper_portable_assets_require_configuration_checksum():
    with pytest.raises(OCFError, match="configuration checksum"):
        custom_voices._profile_assets(
            {"backend": "piper", "model": {"asset": "model.onnx", "sha256": "a" * 64}}
        )


def test_legacy_piper_export_requires_local_model_and_configuration(private_store):
    profile = {
        "schema_version": "1.0",
        "id": "OCF-VOICE-9871",
        "slug": "ocf-voice-9871",
        "name": "Legacy model fixture",
        "backend": "piper",
        "customization_method": "installed-model",
        "piper_model": str(private_store / "missing.onnx"),
    }
    with pytest.raises(OCFError, match="legacy model must be installed"):
        custom_voices.export_profile(profile, private_store / "legacy.json")


def test_profile_export_wraps_json_serialization_failure(private_store, monkeypatch):
    profile = make_pack(private_store)["profile"]

    def fail_serialization(*args, **kwargs):
        raise TypeError("synthetic JSON encoder failure")

    monkeypatch.setattr(custom_voices.json, "dumps", fail_serialization)
    with pytest.raises(OCFError, match="not valid finite JSON"):
        custom_voices.export_profile(profile, private_store / "encoder-failure.json")


def test_export_and_import_reject_ambiguous_identity_and_existing_destination(private_store):
    profile = make_pack(private_store)["profile"]
    with pytest.raises(OCFError, match="unambiguous"):
        custom_voices.export_profile("no-such-profile", private_store / "missing.json")
    destination = private_store / "existing.json"
    destination.write_text("occupied")
    with pytest.raises(OCFError, match="refusing overwrite"):
        custom_voices.export_profile(profile, destination)


def test_import_model_validates_and_copies_model_and_configuration(private_store):
    model = private_store / "fixture.onnx"
    model.write_bytes(b"synthetic onnx fixture")
    Path(str(model) + ".json").write_text(
        __import__("json").dumps({"language": {"code": "en_US"}, "audio": {"sample_rate": 22050}})
    )
    imported = custom_voices.import_model(
        model,
        voice_id="OCF-VOICE-9878",
        name="Synthetic Piper fixture",
        consent_record="local/optional-consent.txt",
    )
    profile = imported["profile"]
    assert imported["inference_verified"] is False
    assert custom_voices.validate_profile(profile)["valid"]
    assert Path(custom_voices.model_path(profile)).is_file()
    assert profile["consent_record"] == "local/optional-consent.txt"
    with pytest.raises(OCFError, match="already exists"):
        custom_voices.import_model(model, voice_id="OCF-VOICE-9878", name="Duplicate")


@pytest.mark.parametrize("name,create_file", [("invalid.txt", True), ("missing.onnx", False)])
def test_import_model_requires_existing_onnx_path(private_store, name, create_file):
    model = private_store / name
    if create_file:
        model.write_bytes(b"not an onnx filename")
    with pytest.raises(OCFError, match="requires a local Piper .onnx model"):
        custom_voices.import_model(model, voice_id="OCF-VOICE-9876", name="Invalid model")


@pytest.mark.parametrize(
    "config,match",
    [
        ({"audio": {"sample_rate": 22050}}, "language/audio objects"),
        ({"language": {"code": "en_US"}}, "language/audio objects"),
        ({"language": {"code": "en_US"}, "audio": {"sample_rate": True}}, "lacks language.code"),
    ],
)
def test_import_model_rejects_incomplete_or_invalid_piper_configuration(
    private_store, config, match
):
    model = private_store / "fixture.onnx"
    model.write_bytes(b"synthetic onnx fixture")
    Path(str(model) + ".json").write_text(__import__("json").dumps(config))
    with pytest.raises(OCFError, match=match):
        custom_voices.import_model(model, voice_id="OCF-VOICE-9877", name="Invalid Piper fixture")


def test_export_rejects_private_transcript_paths_without_rewriting_words(private_store):
    pack = voice_packs.create_pack(
        reference(private_store / "reference.wav"),
        voice_id="OCF-VOICE-9876",
        name="Synthetic fixture",
        locale="en-US",
        transcript="The source was /home/example/Desktop/voice.wav.",
        consent_declaration="Test fixture only.",
    )
    with pytest.raises(OCFError, match="cannot rewrite source wording"):
        custom_voices.export_profile(pack["profile"], private_store / "private.json")


def test_private_original_passage_audition_uses_injected_tts_without_engine(
    private_store, monkeypatch
):
    source = private_store / "synthetic.wav"
    with wave.open(str(source), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24000)
        output.writeframes(array("h", [1200, -1200] * 2400).tobytes())
    audio = source.read_bytes()
    monkeypatch.setattr(
        narration_first,
        "_voice_profile",
        lambda query, locale, catalog: (
            {"id": query, "pronunciation": {}},
            {"name": "piper", "language": "en_US"},
        ),
    )
    monkeypatch.setattr(
        narration_pacing,
        "split_speech_units",
        lambda passage: [{"text": "Synthetic audition unit."}],
    )
    monkeypatch.setattr(voice, "render_cue_wav", lambda spec, text: audio)
    result = custom_voices.audition(["OCF-VOICE-9898"])
    report = result["report"]
    assert report["background"] == "none for every voice"
    assert report["listening_approval"] is None
    assert len(report["outputs"]) == 1
    assert report["outputs"][0]["segments"]
    assert Path(result["output_directory"], report["outputs"][0]["path"]).is_file()


def test_private_passage_audition_rejects_invalid_selection_before_audio():
    with pytest.raises(OCFError, match="select 1..4 voices"):
        custom_voices.audition([])
    with pytest.raises(OCFError, match="select 1..4 voices"):
        custom_voices.audition(["one", "two", "three", "four", "five"])
    with pytest.raises(OCFError, match="select 1..4 voices"):
        custom_voices.audition(["one"], locale="es-ES")


def test_private_passage_audition_rejects_silent_synthesis(private_store, monkeypatch):
    silent = private_store / "silent.wav"
    with wave.open(str(silent), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24000)
        output.writeframes(bytes(24000 * 2))
    monkeypatch.setattr(
        narration_first,
        "_voice_profile",
        lambda query, locale, catalog: (
            {"id": query, "pronunciation": {}},
            {"name": "piper", "language": "en_US"},
        ),
    )
    monkeypatch.setattr(
        narration_pacing,
        "split_speech_units",
        lambda passage: [{"text": "Synthetic audition unit."}],
    )
    monkeypatch.setattr(voice, "render_cue_wav", lambda spec, text: silent.read_bytes())
    with pytest.raises(OCFError, match="produced no audible samples"):
        custom_voices.audition(["OCF-VOICE-9898"])


@pytest.mark.parametrize("tamper", ["traversal", "wrong-checksum", "duplicate-asset"])
def test_import_rejects_tampered_portable_asset_entries(private_store, tamper):
    profile = make_pack(private_store)["profile"]
    bundle_path = private_store / "bundle.json"
    custom_voices.export_profile(profile, bundle_path, include_assets=True)
    bundle = __import__("json").loads(bundle_path.read_text())
    if tamper == "traversal":
        bundle["assets"][0]["path"] = "../reference.wav"
    elif tamper == "wrong-checksum":
        bundle["assets"][0]["sha256"] = "0" * 64
    else:
        bundle["assets"].append(dict(bundle["assets"][0]))
    bundle_path.write_text(__import__("json").dumps(bundle))
    consent = custom_voices.asset_root() / "local/consent.txt"
    consent.parent.mkdir(parents=True, exist_ok=True)
    consent.write_text("Local test reauthorization.")
    with pytest.raises(OCFError):
        custom_voices.import_profile(
            bundle_path,
            include_assets=True,
            voice_id="OCF-VOICE-9897",
            consent_record="local/consent.txt",
        )


@pytest.mark.parametrize(
    "case,match",
    [
        ("id", "voice ID must match"),
        ("source-type", "unsupported reference source type"),
        ("locale", "English locales only"),
        ("empty-transcript", "transcript must not be empty"),
        ("empty-consent", "explicit consent declaration"),
        ("missing-reference", "prepared local WAV"),
        ("wrong-extension", "prepared local WAV"),
        ("short-reference", "longer than five seconds"),
        ("stereo-reference", "mono 24 kHz PCM16"),
        ("wrong-rate", "mono 24 kHz PCM16"),
        ("wrong-width", "mono 24 kHz PCM16"),
        ("corrupt-reference", "prepared reference is not a valid WAV"),
        ("stale-metadata", "metadata checksum mismatch"),
        ("occupied-assets", "asset directory already exists"),
    ],
)
def test_create_pack_rejects_invalid_local_reference_inputs(private_store, case, match):
    voice_id = "OCF-VOICE-9899"
    source = reference(private_store / "reference.wav")
    kwargs = {
        "voice_id": voice_id,
        "name": "Synthetic fixture",
        "locale": "en-US",
        "transcript": "Fixture words.",
        "consent_declaration": "Test fixture only.",
    }
    if case == "id":
        kwargs["voice_id"] = "not-an-ocf-id"
    elif case == "source-type":
        kwargs["source_type"] = "unknown"
    elif case == "locale":
        kwargs["locale"] = "es-ES"
    elif case == "empty-transcript":
        kwargs["transcript"] = " "
    elif case == "empty-consent":
        kwargs["consent_declaration"] = " "
    elif case == "missing-reference":
        source = private_store / "missing.wav"
    elif case == "wrong-extension":
        source = private_store / "reference.flac"
        source.write_bytes(b"not a prepared WAV")
    elif case == "short-reference":
        source = reference(private_store / "short.wav", seconds=5)
    elif case == "stereo-reference":
        source = reference(private_store / "stereo.wav", channels=2)
    elif case == "wrong-rate":
        source = reference(private_store / "rate.wav", rate=16000)
    elif case == "wrong-width":
        source = private_store / "width.wav"
        with wave.open(str(source), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(1)
            output.setframerate(24000)
            output.writeframes(bytes(24000 * 6))
    elif case == "corrupt-reference":
        source = private_store / "corrupt.wav"
        source.write_bytes(b"not wave")
    elif case == "stale-metadata":
        source.with_suffix(".json").write_text('{"prepared_sha256":"' + "0" * 64 + '"}')
    elif case == "occupied-assets":
        (custom_voices.asset_root() / voice_id).mkdir(parents=True)

    with pytest.raises(OCFError, match=match):
        voice_packs.create_pack(source, **kwargs)
