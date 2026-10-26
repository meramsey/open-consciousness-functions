import hashlib
import json

import pytest
from tools.render_private_reference_v4 import _verified_export


@pytest.mark.unit
def test_batch_export_resume_requires_matching_session_report_and_all_hashes(tmp_path):
    source = tmp_path / "session-report.json"
    source.write_text('{"session":1}\n', encoding="utf-8")
    artifact = tmp_path / "verified.mp3"
    artifact.write_bytes(b"private-audio")

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = {
        "kind": "private-audition-export",
        "source_report": {"sha256": digest(source)},
        "artifacts": {
            "mp3": {
                "path": artifact.name,
                "size_bytes": artifact.stat().st_size,
                "sha256": digest(artifact),
            }
        },
    }
    output = tmp_path / "export"
    output.mkdir()
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (output / artifact.name).write_bytes(artifact.read_bytes())
    assert _verified_export(output, source)
    artifact_copy = output / artifact.name
    artifact_copy.write_bytes(b"altered")
    assert not _verified_export(output, source)
    artifact_copy.write_bytes(b"private-audio")
    source.write_text('{"session":2}\n', encoding="utf-8")
    assert not _verified_export(output, source)
