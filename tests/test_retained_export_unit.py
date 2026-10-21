"""Isolated retained-export identity and integrity boundaries, with synthetic bytes."""

import json

import pytest
from ocf_tools import audition_exports as exports
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


@pytest.fixture
def retained(tmp_path, monkeypatch):
    monkeypatch.setattr(exports, "_load_schema", lambda _: {})
    monkeypatch.setattr(exports, "validate_against_schema", lambda *args: [])
    source = tmp_path / "retained"
    source.mkdir()
    edition = {
        "schema_version": "1.0",
        "kind": "private-audition",
        "function_id": "OCF-TST-999",
        "locale": "en-US",
        "version": "0.1.0",
        "voice_profile_id": "unit-voice",
        "master_sha256": "a" * 64,
        "session_report_sha256": "b" * 64,
        "publication_approval": False,
        "human_listening_approval": None,
    }
    items = {}
    for fmt in ("flac", "mp3"):
        path = source / ("synthetic." + fmt)
        path.write_bytes(b"synthetic metadata-boundary bytes; not actual audio")
        items[fmt] = {
            **exports._artifact(path),
            "packet_sha256": "c" * 64,
            "pcm_sha256": "d" * 64,
            "tags": {
                "ocf_function_id": edition["function_id"],
                "ocf_locale": edition["locale"],
                "ocf_voice_profile": edition["voice_profile_id"],
                "ocf_audio_version": edition["version"],
                "ocf_narrator": "Unit narrator",
            },
        }
    manifest = {
        "kind": "private-audition-export",
        "edition": edition.copy(),
        "function_id": edition["function_id"],
        "locale": edition["locale"],
        "version": edition["version"],
        "source_master": {"sha256": edition["master_sha256"]},
        "source_report": {"sha256": edition["session_report_sha256"]},
        "artifacts": items,
    }

    def save():
        (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (source / "audition-edition.json").write_text(json.dumps(edition), encoding="utf-8")

    save()
    return source, manifest, edition, save


def test_retained_sources_preserve_historical_identity_without_fabricating_master(retained):
    source, manifest, edition, _ = retained
    result = exports._retained_export(source, None, None)
    assert result["edition"] == edition
    assert result["document"] == manifest
    assert result["narrator"] == "Unit narrator"
    assert result["inputs"] == {fmt: source / ("synthetic." + fmt) for fmt in ("flac", "mp3")}
    assert not (source / "session-report.json").exists()
    assert not list(source.glob("*.wav"))


def test_legacy_encoded_receipt_uses_verified_file_and_pcm_evidence(retained):
    source, manifest, _, save = retained
    for item in manifest["artifacts"].values():
        item["packet_sha256"] = None
        item["operation"] = "encode-from-master"
    save()
    assert exports._retained_export(source, None, None)["inputs"]["flac"].is_file()


def test_retained_input_cannot_be_replaced_before_any_codec_process(retained, tmp_path):
    source, _, _, _ = retained
    with pytest.raises(OCFError, match="must use its verified artifacts"):
        exports.export_audition(
            source, mp3_source=tmp_path / "unverified.mp3", output=tmp_path / "new"
        )


@pytest.mark.parametrize(
    "failure",
    [
        "kind",
        "schema",
        "edition",
        "function",
        "locale",
        "version",
        "master-reference",
        "report-reference",
        "version-override",
        "missing-format",
        "missing-packet-evidence",
        "missing-pcm-evidence",
        "voice-tag",
        "locale-tag",
        "function-tag",
        "version-tag",
        "narrator-missing",
        "narrator-conflict",
        "file-size",
    ],
)
def test_retained_export_rejects_incomplete_or_conflicting_evidence(retained, monkeypatch, failure):
    source, manifest, edition, save = retained
    version = None
    if failure == "kind":
        manifest["kind"] = "release"
    elif failure == "schema":
        monkeypatch.setattr(exports, "validate_against_schema", lambda *a: ["unit invalid schema"])
    elif failure == "edition":
        edition["voice_profile_id"] = "different"
    elif failure in {"function", "locale", "version"}:
        manifest[{"function": "function_id", "locale": "locale", "version": "version"}[failure]] = (
            "different"
        )
    elif failure == "master-reference":
        manifest["source_master"]["sha256"] = "e" * 64
    elif failure == "report-reference":
        manifest["source_report"]["sha256"] = "e" * 64
    elif failure == "version-override":
        version = "0.2.0"
    elif failure == "missing-format":
        manifest["artifacts"].pop("mp3")
    elif failure == "missing-packet-evidence":
        manifest["artifacts"]["mp3"].pop("packet_sha256")
    elif failure == "missing-pcm-evidence":
        manifest["artifacts"]["flac"].pop("pcm_sha256")
    elif failure.endswith("-tag"):
        key = {
            "voice-tag": "ocf_voice_profile",
            "locale-tag": "ocf_locale",
            "function-tag": "ocf_function_id",
            "version-tag": "ocf_audio_version",
        }[failure]
        manifest["artifacts"]["mp3"]["tags"][key] = "different"
    elif failure == "narrator-missing":
        manifest["artifacts"]["flac"]["tags"].pop("ocf_narrator")
    elif failure == "narrator-conflict":
        manifest["artifacts"]["mp3"]["tags"]["ocf_narrator"] = "different"
    elif failure == "file-size":
        manifest["artifacts"]["mp3"]["size_bytes"] = 0
    save()
    with pytest.raises(OCFError):
        exports._retained_export(source, version, None)
    assert not (source / "session-report.json").exists()
    assert not list(source.glob("*.wav"))
