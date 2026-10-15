import json
import math
import wave
from array import array

import pytest
from ocf_tools import voice_datasets as datasets
from ocf_tools.custom_voices import validate_profile
from ocf_tools.utils import OCFError


def test_original_dataset_scaffold_is_non_destructive_and_reports_missing_audio(tmp_path):
    result = datasets.initialize(tmp_path / "dataset")
    assert result["prompts"] > 20 and not result["audio_recorded"]
    report = datasets.validate_dataset(tmp_path / "dataset/dataset.json")
    assert report["errors"] >= result["prompts"]
    assert report["consent_status"] == "unknown"
    with pytest.raises(OCFError, match="overwrite"):
        datasets.initialize(tmp_path / "dataset")
    assert datasets.training_plan()["training_supported"] is False


def test_dataset_audio_measurements_duplicates_clipping_and_paths(tmp_path):
    records = []
    for index, split in enumerate(("train", "validation", "test")):
        path = tmp_path / f"sample-{index}.wav"
        pcm = array("h", [round(10000 * math.sin(i * (0.1 + index * 0.01))) for i in range(2205)])
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(22050)
            output.writeframes(pcm.tobytes())
        records.append(
            {
                "id": f"sample-{index}",
                "audio": path.name,
                "text": "Original synthetic fixture.",
                "split": split,
            }
        )
    data = {
        "schema_version": "1.0",
        "id": "fixture",
        "locale": "en-US",
        "sample_rate": 22050,
        "license": "test only",
        "consent_status": "unknown",
        "records": records,
    }
    manifest = tmp_path / "dataset.json"
    manifest.write_text(json.dumps(data))
    assert datasets.validate_dataset(manifest)["status"] == "passed"
    records[1]["audio"] = records[0]["audio"]
    manifest.write_text(json.dumps(data))
    assert any(
        d["code"] == "duplicate-audio" for d in datasets.validate_dataset(manifest)["diagnostics"]
    )


def test_cloned_profile_requires_declared_authorization():
    profile = {
        "schema_version": "1.0",
        "id": "OCF-VOICE-9001",
        "slug": "clone",
        "name": "Fixture",
        "backend": "piper",
        "voice_kind": "cloned",
        "consent_status": "unknown",
    }
    with pytest.raises(OCFError, match="authorization"):
        validate_profile(profile, assets=False)


def test_private_model_import_is_portable_and_detects_changed_model(monkeypatch, tmp_path):
    from ocf_tools.custom_voices import import_model, model_path

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    model = tmp_path / "fixture.onnx"
    model.write_bytes(b"synthetic metadata test; not an inference model")
    model.with_suffix(".onnx.json").write_text(
        json.dumps({"language": {"code": "en_US"}, "audio": {"sample_rate": 22050}})
    )
    imported = import_model(model, voice_id="OCF-VOICE-9005", name="Fixture")
    assert imported["inference_verified"] is False
    profile = imported["profile"]
    assert profile["model"]["asset"].endswith(".onnx") and str(tmp_path) not in json.dumps(profile)
    from pathlib import Path

    installed = Path(model_path(profile))
    installed.write_bytes(b"changed")
    with pytest.raises(OCFError, match="checksum mismatch"):
        validate_profile(profile)
