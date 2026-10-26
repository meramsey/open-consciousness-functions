import json

import pytest
from ocf_tools.build_provenance import attach_audio_quality, attach_build_provenance
from ocf_tools.utils import OCFError


@pytest.mark.unit
def test_portable_build_provenance_is_checksummed_and_idempotent(tmp_path):
    root = tmp_path / "export"
    root.mkdir()
    manifest = {
        "kind": "private-audition-export",
        "function_id": "OCF-SEN-001",
        "artifacts": {},
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    evidence = {"edition": "0.3.0", "input_sha256": "a" * 64}

    first = attach_build_provenance(root, evidence)
    second = attach_build_provenance(root, evidence)
    stored = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert first == second
    assert stored["artifacts"]["build_provenance"] == first
    assert stored["build_provenance"]["sha256"] == first["sha256"]
    quality = {"integrated_loudness_lufs": -17.5, "mastering_target_applied": False}
    audio_receipt = attach_audio_quality(root, quality)
    stored = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert stored["artifacts"]["audio_quality"] == audio_receipt
    assert json.loads((root / "audio-quality.json").read_text()) == quality
    with pytest.raises(OCFError, match="absolute filesystem path"):
        attach_build_provenance(root, {"private_source": "/home/example/private.flac"})
