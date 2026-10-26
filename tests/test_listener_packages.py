"""Copy-only package contracts; media bytes are synthetic, no engines run."""

import json
import shutil

import pytest
from ocf_tools import listener_packages as packages
from ocf_tools.audition_exports import _artifact
from ocf_tools.utils import OCFError


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(packages, "work_root", lambda: tmp_path)
    monkeypatch.setattr(
        packages, "workspace_temp_directory", lambda **kw: _directory(tmp_path / "stage")
    )
    monkeypatch.setattr(packages, "record_workspace_failure", lambda *args: None)
    monkeypatch.setattr(packages, "publish_workspace_temp_directory", lambda a, b: a.rename(b))

    def fake_guides(stage, function_ids, **kwargs):
        result = []
        for stem in ["listening-guide", "index", *(f"functions/{fid}" for fid in function_ids)]:
            for suffix in ("md", "pdf", "html"):
                path = stage / "guides" / f"{stem}.{suffix}"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic guide")
                result.append({**_artifact(path), "path": path.relative_to(stage).as_posix()})
        return result

    monkeypatch.setattr(packages, "attach_guides", fake_guides)
    folder = _directory(tmp_path / "source")
    manifest = {
        "kind": "private-audition-export",
        "function_id": "OCF-EXP-003",
        "locale": "en-US",
        "version": "0.2.0",
        "publication_approval": False,
        "edition": {
            "schema_version": "1.0",
            "kind": "private-audition",
            "function_id": "OCF-EXP-003",
            "version": "0.2.0",
            "locale": "en-US",
            "voice_profile_id": "synthetic-voice",
            "master_sha256": "0" * 64,
            "session_report_sha256": "1" * 64,
            "publication_approval": False,
            "human_listening_approval": None,
        },
        "source_master": {"sha256": "0" * 64},
        "source_report": {"sha256": "1" * 64},
        "artifacts": {},
        "listener_text": {"artifacts": {}},
    }
    for suffix in ("flac", "mp3", "txt", "lrc", "srt", "vtt", "png", "json"):
        path = folder / ("Café - 私 - v0.2.0." + suffix)
        path.write_bytes(("synthetic:" + suffix).encode())
        item = _artifact(path)
        if suffix in ("flac", "mp3"):
            item.update(
                pcm_sha256="2" * 64,
                packet_sha256="3" * 64,
                tags={
                    "ocf_function_id": "OCF-EXP-003",
                    "ocf_locale": "en-US",
                    "ocf_voice_profile": "synthetic-voice",
                    "ocf_audio_version": "0.2.0",
                    "ocf_narrator": "Synthetic Narrator",
                },
            )
            manifest["artifacts"][suffix] = item
        elif suffix == "png":
            manifest["cover"] = item
        elif suffix == "json":
            manifest["listener_text"]["timing_receipt"] = item
        else:
            manifest["listener_text"]["artifacts"][suffix] = item
    _save(folder, manifest)
    return folder, manifest


def _directory(path):
    path.mkdir()
    return path


def _save(folder, manifest):
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.unit
def test_single_relocation_resume_byte_identity(source, tmp_path):
    folder, manifest = source
    output = tmp_path / "portable"
    result = packages.package_auditions([folder], output)
    assert result["sessions"][0]["version"] == "0.2.0"
    assert result["publication_approval"] is False
    for item in manifest["artifacts"].values():
        assert (output / "OCF-EXP-003" / item["path"]).read_bytes() == (
            folder / item["path"]
        ).read_bytes()
    assert packages.package_auditions([folder], output, resume=True) == result
    relocated = tmp_path / "elsewhere"
    shutil.copytree(output, relocated)
    assert packages.verify_package(relocated) == result
    with pytest.raises(OCFError, match="overwrite"):
        packages.package_auditions([folder], output)


@pytest.mark.unit
@pytest.mark.parametrize(
    "change,match",
    [
        ("txt", "transcripts"),
        ("cover", "cover"),
        ("edition", "identity"),
        ("rights", "private"),
        ("duplicate", "duplicate"),
        ("absolute", "absolute"),
        ("traversal", "unsafe"),
        ("windows", "unsafe"),
        ("corrupt", "checksum"),
        ("missing", "missing"),
    ],
)
def test_invalid_sources_fail_closed(source, tmp_path, change, match):
    folder, manifest = source
    if change == "txt":
        del manifest["listener_text"]["artifacts"]["txt"]
    elif change == "cover":
        del manifest["cover"]
    elif change == "edition":
        manifest["edition"]["version"] = "9.0.0"
    elif change == "rights":
        manifest["publication_approval"] = True
    elif change == "duplicate":
        manifest["artifacts"]["mp3"] = manifest["artifacts"]["flac"]
    elif change == "absolute":
        manifest["provenance"] = {"source": "C:\\private\\reference.flac"}
    elif change in ("traversal", "windows"):
        manifest["artifacts"]["mp3"]["path"] = (
            "../escape.mp3" if change == "traversal" else "..\\escape.mp3"
        )
    elif change == "corrupt":
        manifest["artifacts"]["mp3"]["sha256"] = "0" * 64
    else:
        (folder / manifest["artifacts"]["mp3"]["path"]).unlink()
    _save(folder, manifest)
    with pytest.raises(OCFError, match=match):
        packages.package_auditions([folder], tmp_path / "output")
    assert not (tmp_path / "output").exists()


@pytest.mark.unit
def test_collection_and_duplicate_identity(source, tmp_path):
    folder, manifest = source
    with pytest.raises(OCFError, match="duplicate function"):
        packages.package_auditions([folder, folder], tmp_path / "bad")
    second = tmp_path / "second"
    shutil.copytree(folder, second)
    manifest["function_id"] = manifest["edition"]["function_id"] = "OCF-EXP-001"
    for item in manifest["artifacts"].values():
        item["tags"]["ocf_function_id"] = "OCF-EXP-001"
    _save(second, manifest)
    result = packages.package_auditions([folder, second], tmp_path / "collection")
    assert len(result["sessions"]) == 2
    assert len(list((tmp_path / "collection").glob("*/manifest.json"))) == 2


@pytest.mark.unit
def test_resume_corruption_and_interruption(source, tmp_path):
    folder, manifest = source
    output = tmp_path / "output"
    packages.package_auditions([folder], output)
    (output / "extra").write_bytes(b"interruption")
    with pytest.raises(OCFError, match="undeclared"):
        packages.package_auditions([folder], output, resume=True)
    (output / "extra").unlink()
    manifest["note"] = "different source receipt"
    _save(folder, manifest)
    with pytest.raises(OCFError, match="different sources"):
        packages.package_auditions([folder], output, resume=True)


@pytest.mark.integration
def test_current_cached_guides_subset_and_corruption(tmp_path):
    pytest.importorskip("reportlab")
    cache = tmp_path / "cache"
    cache.mkdir()
    artifacts = packages.attach_guides(cache, ["OCF-EXP-003"])
    assert len(artifacts) == 12
    assert (cache / "guides/functions/OCF-EXP-006.pdf").is_file()
    for item in artifacts:
        assert (cache / item["path"]).is_file()
    output = tmp_path / "output"
    output.mkdir()
    assert len(packages.attach_guides(output, ["OCF-EXP-003"], source=cache / "guides")) == 12
    (cache / "guides/functions/OCF-EXP-003.pdf").write_bytes(b"%PDF-corrupt")
    with pytest.raises(OCFError, match="corrupt or stale guide"):
        packages.attach_guides(tmp_path / "bad", ["OCF-EXP-003"], source=cache / "guides")
    with pytest.raises(OCFError, match="en-US"):
        packages.attach_guides(tmp_path / "locale", ["OCF-EXP-003"], locale="fr-FR")


@pytest.mark.unit
def test_audition_cli_routes_lyrics_and_guides(monkeypatch):
    from pathlib import Path

    from ocf_tools import cli

    calls = []
    monkeypatch.setattr(
        "ocf_tools.audition_exports.export_audition",
        lambda *args, **kw: calls.append(kw) or {"dry_run": True},
    )
    assert (
        cli.main(
            ["audio", "export-audition", "source", "--lyrics", "--guides", "guides", "--dry-run"]
        )
        == 0
    )
    assert calls[0]["lyrics"] is True
    assert calls[0]["guides"] == Path("guides")


@pytest.mark.unit
@pytest.mark.parametrize("field", ["master_sha256", "session_report_sha256", "voice_profile_id"])
def test_conflicting_provenance_rejected(source, tmp_path, field):
    folder, manifest = source
    manifest["edition"][field] = "9" * 64
    _save(folder, manifest)
    with pytest.raises(OCFError, match="identity|tags"):
        packages.package_auditions([folder], tmp_path / "bad")


@pytest.mark.unit
@pytest.mark.parametrize("omission", ["session", "audio", "guides", "manifest-receipt"])
def test_resume_requires_complete_sessions_and_guides(source, tmp_path, omission):
    folder, _ = source
    output = tmp_path / "output"
    document = packages.package_auditions([folder], output)
    if omission == "manifest-receipt":
        document["sessions"][0]["source_manifest_sha256"] = "9" * 64
    else:
        removed = []
        for item in document["artifacts"]:
            name = item["path"]
            if (
                (omission == "session" and name.startswith("OCF-"))
                or (omission == "audio" and name.endswith(".mp3"))
                or (omission == "guides" and name.startswith("guides/"))
            ):
                removed.append(item)
                (output / name).unlink()
        document["artifacts"] = [x for x in document["artifacts"] if x not in removed]
    (output / "package.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(OCFError, match="missing or conflicting session|missing package guides"):
        packages.package_auditions([folder], output, resume=True)


@pytest.mark.unit
def test_interrupted_copy_retains_stage_and_retry_publishes(source, tmp_path, monkeypatch):
    folder, _ = source
    original_copy = shutil.copyfile

    def interrupted_copy(source, target):
        if str(source).endswith(".mp3"):
            raise OSError("simulated interruption")
        return original_copy(source, target)

    monkeypatch.setattr(shutil, "copyfile", interrupted_copy)
    output = tmp_path / "output"
    with pytest.raises(OSError, match="interruption"):
        packages.package_auditions([folder], output)
    assert not output.exists()
    assert (tmp_path / "stage").is_dir()
    monkeypatch.setattr(shutil, "copyfile", original_copy)
    monkeypatch.setattr(
        packages, "workspace_temp_directory", lambda **kw: _directory(tmp_path / "retry")
    )
    packages.package_auditions([folder], output)
    packages.verify_package(output)


@pytest.mark.unit
def test_private_output_must_stay_in_workspace(source, tmp_path):
    folder, _ = source
    with pytest.raises(OCFError, match="workspace"):
        packages.package_auditions([folder], tmp_path.parent / "public-output")


@pytest.mark.integration
def test_private_export_cannot_be_selected_as_registered_release(source):
    from ocf_tools.release import package_release

    folder, _ = source
    with pytest.raises(OCFError, match="no audio implementation is registered"):
        package_release(str(folder), dry_run=True)


@pytest.mark.unit
def test_portable_filename_comparison_handles_unicode_normalization():
    assert packages._filename_key("Café.MP3") == packages._filename_key("Cafe\u0301.mp3")


@pytest.mark.unit
@pytest.mark.parametrize("link", ["missing.pdf", "../../outside.txt", "file:///outside.txt"])
def test_package_verification_rejects_broken_or_escaping_guide_links(source, tmp_path, link):
    folder, _ = source
    output = tmp_path / "output"
    document = packages.package_auditions([folder], output)
    target = output / "guides/index.md"
    target.write_text(f"[Bad]({link})", encoding="utf-8")
    for item in document["artifacts"]:
        if item["path"] == "guides/index.md":
            item.update({k: v for k, v in _artifact(target).items() if k != "path"})
    (output / "package.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(OCFError, match="package guide link"):
        packages.verify_package(output)


@pytest.mark.integration
def test_related_guide_closure_and_encoded_edition_navigation(tmp_path):
    pytest.importorskip("reportlab")
    artifacts = packages.attach_guides(
        tmp_path,
        ["OCF-EXP-001"],
        edition_files={"OCF-EXP-001": [{"path": "OCF-EXP-001/Café test.mp3", "label": ".mp3"}]},
    )
    assert len(artifacts) == 15
    assert (tmp_path / "guides/functions/OCF-EXP-006.pdf").is_file()
    index = (tmp_path / "guides/index.md").read_text(encoding="utf-8")
    assert "Caf%C3%A9%20test.mp3" in index and "FLAC audio" not in index
    assert "MP3 audio" in index and "do not imply" in index
