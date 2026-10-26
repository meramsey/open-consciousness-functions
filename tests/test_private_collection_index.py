import json

import pytest
from ocf_tools import private_collection_index as index
from ocf_tools.indexes import load_function_by_id
from ocf_tools.utils import OCFError


@pytest.mark.unit
def test_private_index_uses_only_verified_tracks_and_keeps_unfinished_status(tmp_path, monkeypatch):
    root = tmp_path / "work"
    package = root / "package"
    output = root / "collection"
    function_id = "OCF-SEN-001"
    mp3 = package / function_id / "hearing.mp3"
    flac = package / function_id / "hearing.flac"
    mp3.parent.mkdir(parents=True)
    mp3.write_bytes(b"fixture MP3")
    flac.write_bytes(b"fixture FLAC")
    manifest = {
        "function_id": function_id,
        "title": "Hearing",
        "edition": {
            "version": "0.3.0",
            "voice_profile_id": "OCF-VOICE-9003",
            "background_variant": "REFERENCE-F10-F11-V4",
        },
        "human_listening_approval": None,
        "publication_approval": False,
        "artifacts": {
            "mp3": {
                "path": "hearing.mp3",
                "codec": "mp3",
                "duration_seconds": 120.5,
                "tags": {},
            },
            "flac": {"path": "hearing.flac"},
        },
    }
    (mp3.parent / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(index, "work_root", lambda: root)
    monkeypatch.setattr(
        index,
        "verify_package",
        lambda _: {"sessions": [{"function_id": function_id, "version": "0.3.0"}]},
    )
    monkeypatch.setattr(index, "load_function_by_id", load_function_by_id)
    progress = root / "progress.json"
    progress.write_text(
        json.dumps({"functions": [{"function_id": "OCF-AUT-001", "status": "FAILED"}]}),
        encoding="utf-8",
    )

    result = index.build_private_collection_index(package, output, progress=progress)
    assert result["verified_count"] == 1
    assert result["tracks"][0]["technical_verification"] == "verified-package"
    assert result["functions"][-1]["status"] == "failed"
    assert "../package/OCF-SEN-001/hearing.mp3" in (output / "playlist.m3u").read_text()
    assert "[FLAC](../package/OCF-SEN-001/hearing.flac)" in (output / "index.md").read_text()
    assert "[MP3](../package/OCF-SEN-001/hearing.mp3)" in (output / "index.md").read_text()
    assert 'href="../package/OCF-SEN-001/hearing.flac"' in (output / "index.html").read_text()
    assert 'href="../package/OCF-SEN-001/hearing.mp3"' in (output / "index.html").read_text()
    assert "NOT_AUTHORIZED" in (output / "dashboard.json").read_text()
    with pytest.raises(OCFError, match="outside the immutable package"):
        index.build_private_collection_index(package, package / "nested")
