from __future__ import annotations

import json
import shutil
import struct
import zlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ocf_tools import audio_build
from ocf_tools import release as rel
from ocf_tools.utils import OCFError, sha256_of_file, yaml_safe_dump


def _png(path: Path, width: int = 2, height: int = 2) -> Path:
    def chunk(name: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + name
            + body
            + struct.pack(">I", zlib.crc32(name + body) & 0xFFFFFFFF)
        )

    rows = b"".join(b"\x00" + bytes([30, 90, 160, 255]) * width for _ in range(height))
    body = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(body)
    return path


def _wav(path: Path) -> Path:
    import wave
    from array import array

    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16000)
        writer.writeframes(array("h", [1000, -1000] * 8000).tobytes())
    return path


def test_image_validation_and_localized_title_fallback(tmp_path):
    image = _png(tmp_path / "cover.png")
    assert rel._image_info(image) == ("image/png", 2, 2)
    title, provenance = rel._function_title("OCF-BOD-010", "es", rel.LocaleCatalog())
    assert title == "Nutricia"
    assert provenance == {
        "requested_locale": "es",
        "resolved_locale": "en-US",
        "fallback": True,
        "resource_key": "functions.ocf-bod-010.title",
    }


def test_image_validation_rejects_unknown_or_oversized_image(tmp_path):
    fake = tmp_path / "fake.png"
    fake.write_bytes(b"not an image")
    with pytest.raises(OCFError, match="PNG or JPEG"):
        rel._image_info(fake)
    with pytest.raises(OCFError, match="dimensions"):
        rel._image_info(_png(tmp_path / "large.png", 12001, 1))


def test_transcript_uses_synthesis_text_in_timeline_order_and_is_utf8_ready():
    render = {
        "narration_timing": {
            "cues": [
                {"id": "late", "at": 2, "spoken_text": "Café is ready."},
                {
                    "id": "early",
                    "at": 1,
                    "display_text": "Display",
                    "spoken_text": "Final spoken form.",
                },
            ]
        }
    }
    expected = "Final spoken form.\n\nCafé is ready.\n"
    assert rel.transcript_from_render(render) == expected
    assert rel.transcript_from_render(render).encode("utf-8").decode("utf-8") == expected
    assert rel.transcript_from_render({"narration_timing": {"cues": []}}) == "\n"
    with pytest.raises(OCFError, match="spoken_text"):
        rel.transcript_from_render({"narration_timing": {"cues": [{"id": "keyed-cue"}]}})


def test_manifest_checks_relative_files_and_hashes(tmp_path):
    item = tmp_path / "file.txt"
    item.write_text("release\n", encoding="utf-8")
    artifact = {
        "path": "file.txt",
        "format": "text/plain; charset=utf-8",
        "size_bytes": item.stat().st_size,
        "sha256": sha256_of_file(item),
    }
    rel._verify_manifest(
        tmp_path,
        {
            "schema_version": "1.0",
            "function_id": "OCF-BOD-010",
            "audio_id": "OCF-AUDIO-0010",
            "title": "Nutricia",
            "requested_locale": "en-US",
            "title_resolution": {
                "requested_locale": "en-US",
                "resolved_locale": "en-US",
                "fallback": False,
                "resource_key": "functions.ocf-bod-010.title",
            },
            "release_version": "1.0",
            "voice_profile_id": None,
            "narrator": None,
            "source_narration": "audio/scripts/source.yaml",
            "narration_resolution": None,
            "rendering": {
                "backend": "fixture",
                "locale": "en-US",
                "sample_rate": 16000,
                "channels": 1,
                "timing_mode": "fixture",
            },
            "created_at": "2026-10-13T00:00:00Z",
            "artifacts": [artifact, artifact, artifact],
        },
    )
    for unsafe_path in ("../outside", "..\\outside", "C:\\outside"):
        artifact["path"] = unsafe_path
        with pytest.raises(OCFError, match="unsafe relative"):
            rel._verify_manifest(tmp_path, _valid_manifest(artifact))


def test_dry_run_reports_paths_without_rendering_or_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        rel,
        "_select_audio_manifest",
        lambda _query: {"id": "OCF-AUDIO-9910", "function_id": "OCF-BOD-010"},
    )
    image = _png(tmp_path / "cover.png")
    result = rel.package_release(
        "OCF-BOD-010", artwork=image, output=tmp_path / "release-out", dry_run=True
    )
    assert result["dry_run"] is True
    assert result["artifacts"][-1] == "manifest.json"
    assert not (tmp_path / "release-out").exists()
    versioned = rel.package_release(
        "OCF-BOD-010",
        artwork=image,
        output=tmp_path / "release-out",
        version="2.0.0",
        dry_run=True,
    )
    assert versioned["release_directory"].endswith("OCF-BOD-010-Nutricia-v2.0.0")
    with pytest.raises(OCFError, match="240-character"):
        rel.package_release(
            "OCF-BOD-010",
            artwork=image,
            output=tmp_path / ("x" * 180),
            dry_run=True,
        )


def test_release_rejects_unsupported_or_path_bearing_metadata(tmp_path):
    image = _png(tmp_path / "cover.png")
    with pytest.raises(OCFError, match="unsupported.*override"):
        rel.package_release("OCF-BOD-010", artwork=image, metadata_overrides={"api_key": "secret"})


def test_release_cli_routes_options_to_release_builder(monkeypatch, capsys):
    from ocf_tools import cli

    calls = []
    monkeypatch.setattr(
        "ocf_tools.release.package_release",
        lambda query, **kwargs: calls.append((query, kwargs)) or {"dry_run": True},
    )
    assert (
        cli.main(
            [
                "audio",
                "release",
                "OCF-BOD-010",
                "--artwork",
                "cover.png",
                "--locale",
                "es",
                "--format",
                "flac",
                "--tag",
                "artist=Configured Voice",
                "--dry-run",
            ]
        )
        == 0
    )
    assert calls == [
        (
            "OCF-BOD-010",
            {
                "locale": "es",
                "formats": ["flac"],
                "voice": None,
                "artwork": "cover.png",
                "output": None,
                "version": None,
                "metadata_overrides": {"artist": "Configured Voice"},
                "dry_run": True,
                "overwrite": False,
            },
        )
    ]
    assert '"dry_run": true' in capsys.readouterr().out


def _valid_manifest(artifact):
    return {
        "schema_version": "1.0",
        "function_id": "OCF-BOD-010",
        "audio_id": "OCF-AUDIO-0010",
        "title": "Nutricia",
        "requested_locale": "en-US",
        "title_resolution": {
            "requested_locale": "en-US",
            "resolved_locale": "en-US",
            "fallback": False,
            "resource_key": "functions.ocf-bod-010.title",
        },
        "release_version": "1.0",
        "voice_profile_id": None,
        "narrator": None,
        "source_narration": "audio/scripts/source.yaml",
        "narration_resolution": None,
        "rendering": {
            "backend": "fixture",
            "locale": "en-US",
            "sample_rate": 16000,
            "channels": 1,
            "timing_mode": "fixture",
        },
        "created_at": "2026-10-13T00:00:00Z",
        "artifacts": [artifact, artifact, artifact],
    }


@pytest.mark.integration
@pytest.mark.audio_integration
@pytest.mark.external_tool
@pytest.mark.parametrize("fmt", ["mp3", "flac"])
def test_real_codec_metadata_and_artwork_round_trip(tmp_path, fmt):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("real codec round-trip requires optional ffmpeg and ffprobe")
    cover = _png(tmp_path / "cover.png")
    source = _wav(tmp_path / "source.wav")
    output = tmp_path / f"roundtrip.{fmt}"
    audio_build._encode(
        source,
        fmt,
        output,
        {
            "title": "Nutrícia",
            "album": "Nutrícia",
            "artist": "Configured Narrator",
            "album_artist": "Open Consciousness Functions",
            "language": "en-US",
            "OCF_FUNCTION_ID": "OCF-BOD-010",
        },
        artwork=cover,
    )
    verified = rel._verify_audio(
        output,
        function_id="OCF-BOD-010",
        title="Nutrícia",
        artwork=cover,
        expected_tags={
            "artist": "Configured Narrator",
            "album_artist": "Open Consciousness Functions",
            "language": "en-US",
        },
    )
    assert verified["codec"] == ("mp3" if fmt == "mp3" else "flac")
    assert verified["tags"]["artist"] == "Configured Narrator"
    assert verified["channels"] == 1


@pytest.mark.integration
@pytest.mark.audio_integration
@pytest.mark.external_tool
def test_package_publishes_complete_verified_release_and_blocks_collision(tmp_path, monkeypatch):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("real package verification requires optional ffmpeg and ffprobe")
    audio_manifest = {
        "id": "OCF-AUDIO-9910",
        "function_id": "OCF-BOD-010",
        "transcript_path": "audio/scripts/fixture.yaml",
        "version": "0.1.0",
        "narrator": "Fixture Narrator",
        "language": "en-US",
        "voice_profile": "fixture-voice",
    }
    monkeypatch.setattr(rel, "_select_audio_manifest", lambda _query: audio_manifest)
    cover = _png(tmp_path / "cover.png")

    def fake_build(query, *, out_root, formats, tag_overrides, artwork, **kwargs):
        assert query == "OCF-AUDIO-9910"
        out_root = Path(out_root)
        out_root.mkdir(parents=True)
        source = _wav(tmp_path / "render.wav")
        for fmt in formats:
            audio_build._encode(
                source, fmt, out_root / f"{query}-master.{fmt}", tag_overrides, artwork
            )
        render = {
            "voice": {
                "backend": "fixture",
                "profile_id": "fixture-voice",
                "locale": "en-US",
            },
            "master": {"sample_rate": 16000, "channels": 1, "duration": 1.0},
            "timing_mode": "fixture",
            "narration_timing": {
                "cues": [
                    {"id": "second", "at": 2, "spoken_text": "Second sentence."},
                    {"id": "first", "at": 1, "spoken_text": "First transformed text."},
                ]
            },
        }
        render_path = out_root / "OCF-RENDER-9910.yaml"
        render_path.write_text(yaml_safe_dump(render), encoding="utf-8")
        return render

    monkeypatch.setattr(audio_build, "build", fake_build)
    timestamp = datetime(2026, 10, 13, tzinfo=UTC)
    result = rel.package_release(
        "OCF-BOD-010",
        formats=["flac", "mp3"],
        artwork=cover,
        output=tmp_path / "out",
        created_at=timestamp,
    )
    release_dir = Path(result["release_directory"])
    assert result["manifest"]["title"] == "Nutricia"
    assert result["manifest"]["title_resolution"]["fallback"] is False
    audio_names = [name for name in result["artifacts"] if name.endswith((".flac", ".mp3"))]
    assert audio_names == [
        "OCF-BOD-010 - Nutricia - en-US.flac",
        "OCF-BOD-010 - Nutricia - en-US.mp3",
    ]
    transcript = next(release_dir.glob("*.txt"))
    assert transcript.read_text(encoding="utf-8") == "First transformed text.\n\nSecond sentence.\n"
    assert (release_dir / "manifest.json").is_file()
    manifest = json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))
    rel._verify_manifest(release_dir, manifest)
    with pytest.raises(OCFError, match="already exists"):
        rel.package_release("OCF-BOD-010", formats=["flac"], artwork=cover, output=tmp_path / "out")
    replaced = rel.package_release(
        "OCF-BOD-010",
        formats=["flac"],
        artwork=cover,
        output=tmp_path / "out",
        overwrite=True,
    )
    previous = list(release_dir.parent.glob(f".{release_dir.name}.previous-*"))
    assert Path(replaced["release_directory"]) == release_dir
    assert len(previous) == 1 and (previous[0] / "manifest.json").is_file()


@pytest.mark.integration
@pytest.mark.audio_integration
@pytest.mark.external_tool
def test_failed_manifest_validation_never_publishes_partial_release(tmp_path, monkeypatch):
    audio_manifest = {
        "id": "OCF-AUDIO-9910",
        "function_id": "OCF-BOD-010",
        "transcript_path": "audio/scripts/fixture.yaml",
    }
    monkeypatch.setattr(rel, "_select_audio_manifest", lambda _query: audio_manifest)
    cover = _png(tmp_path / "cover.png")

    def fake_build(query, *, out_root, formats, tag_overrides, artwork, **kwargs):
        out_root = Path(out_root)
        out_root.mkdir(parents=True)
        for fmt in formats:
            (out_root / f"{query}-master.{fmt}").write_bytes(b"fixture")
        render = {
            "voice": {},
            "master": {"sample_rate": 16000, "channels": 1},
            "narration_timing": {"cues": []},
        }
        (out_root / "OCF-RENDER-9910.yaml").write_text(yaml_safe_dump(render), encoding="utf-8")
        return render

    monkeypatch.setattr(audio_build, "build", fake_build)
    monkeypatch.setattr(
        rel,
        "_verify_audio",
        lambda path, **kwargs: {
            "codec": path.suffix.lstrip("."),
            "sample_rate": 16000,
            "channels": 1,
            "duration_seconds": 1.0,
            "bit_rate": None,
            "tags": {},
        },
    )
    monkeypatch.setattr(
        rel, "_verify_manifest", lambda *_args: (_ for _ in ()).throw(OCFError("injected"))
    )
    output = tmp_path / "releases"
    with pytest.raises(OCFError, match="injected"):
        rel.package_release("OCF-BOD-010", formats=["flac"], artwork=cover, output=output)
    assert not (output / "en-US" / "OCF-BOD-010-Nutricia").exists()
    assert not list((output / "en-US").glob(".ocf-release-stage-*"))
