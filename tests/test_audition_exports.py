"""Private audition packaging regressions; real codecs stay integration tests."""

import json
import math
import shutil
import wave
from array import array
from pathlib import Path

import pytest
from ocf_tools import artwork, audio_build
from ocf_tools import audition_exports as exports
from ocf_tools.utils import OCFError, sha256_of_file


def _session(tmp_path):
    source = tmp_path / "session"
    source.mkdir()
    master = source / "master.wav"
    with wave.open(str(master), "wb") as writer:
        writer.setnchannels(2)
        writer.setsampwidth(2)
        writer.setframerate(44100)
        pcm = array("h")
        for n in range(44100):
            pcm.extend((round(3000 * math.sin(n * 0.031)), round(2500 * math.sin(n * 0.047))))
        writer.writeframes(pcm.tobytes())
    (source / "transcript.txt").write_text("Plus Manifest.\n", encoding="utf-8")
    report = {
        "render_type": "complete-session-audition",
        "function_id": "OCF-EXP-001",
        "requested_locale": "en-US",
        "voice_profile": {"id": "OCF-VOICE-9999", "name": "Amy", "backend": "piper"},
        "artifacts": {
            "wav": exports._artifact(master),
            "transcript": exports._artifact(source / "transcript.txt"),
        },
    }
    (source / "session-report.json").write_text(json.dumps(report), encoding="utf-8")
    return source, master, report


def _tools():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("private listening exports require optional FFmpeg/ffprobe")
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")


def test_edition_requires_deliberate_version_and_binds_actual_audio(tmp_path):
    source, _, report = _session(tmp_path)
    path = source / "session-report.json"
    report["template"] = {"version": "7.8.9"}
    with pytest.raises(OCFError, match="missing audio/session edition"):
        exports._edition(report, path, None, None)
    for invalid in ("v0.1.0", "0.1", "01.2.3", "brand-0.3.0"):
        with pytest.raises(OCFError, match="invalid audition edition"):
            exports._edition(report, path, invalid, None)
    edition, origin = exports._edition(report, path, "0.1.0", None)
    assert origin == "explicit-audition-edition"
    assert edition["version"] == "0.1.0" and edition["publication_approval"] is False
    file = tmp_path / "edition.json"
    file.write_text(json.dumps(edition))
    assert exports._edition(report, path, None, file)[0] == edition
    with pytest.raises(OCFError, match="conflicts"):
        exports._edition(report, path, "0.2.0", file)
    report["voice_profile"]["id"] = "OCF-VOICE-9998"
    with pytest.raises(OCFError, match="different audio, voice"):
        exports._edition(report, path, None, file)


def test_registered_audio_version_wins_without_function_version_fallback(tmp_path, monkeypatch):
    source, _, report = _session(tmp_path)
    report["audio_implementation_id"] = "OCF-AUDIO-9999"
    monkeypatch.setattr(
        exports, "find_audio_manifest", lambda _: {"function_id": "OCF-EXP-001", "version": "2.3.4"}
    )
    record, origin = exports._edition(report, source / "session-report.json", None, None)
    assert record["version"] == "2.3.4" and origin == "registered-audio-implementation"
    with pytest.raises(OCFError, match="conflicts"):
        exports._edition(report, source / "session-report.json", "0.1.0", None)


def test_new_render_gets_companion_art_even_without_release_approval(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    source, master, report = _session(tmp_path)
    before = master.read_bytes()
    exports.attach_render_artwork(report, source)
    assert report["audition_version"] == "0.1.0"
    assert report["artwork_provenance"]["status_label"] == "BETA / PRIVATE"
    assert report["artwork_provenance"]["theme_id"] == "ocf-cosmic-dark"
    assert report["artifacts"]["cover"]["sha256"] == sha256_of_file(source / "cover.png")
    visible = json.loads((source / "artwork-report.json").read_text())["settings"]["visible_text"]
    assert "v0.1.0 - BETA / PRIVATE" in visible[-1]
    assert master.read_bytes() == before


@pytest.mark.parametrize("theme", ["ocf-cosmic-dark", "ocf-cosmic-light"])
def test_version_is_drawn_in_existing_cover_footer(tmp_path, monkeypatch, theme):
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    from PIL import Image, ImageChops

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    a = artwork.generate_cover("OCF-EXP-001", theme=theme, version="0.1.0", resolution=600)
    b = artwork.generate_cover("OCF-EXP-001", theme=theme, version="0.2.0", resolution=600)
    assert a["settings"]["version_label"] == "v0.1.0"
    assert a["settings"]["visible_text"][-1] == "OCF-EXP-001 / en-US - v0.1.0"
    assert a["settings"]["brand"]["version"] == "0.3.0"
    bounds = a["layout_bounds"]["footer"]
    assert 0 <= bounds[0] < bounds[2] <= 600 and bounds[3] <= 600
    assert bounds[3] - bounds[1] >= 8
    with Image.open(a["path"]) as first, Image.open(b["path"]) as second:
        assert first.size == (600, 600)
        assert ImageChops.difference(
            first.crop((0, 540, 600, 600)), second.crop((0, 540, 600, 600))
        ).getbbox()


@pytest.mark.integration
@pytest.mark.audio_integration
@pytest.mark.external_tool
@pytest.mark.parametrize("choice", ["default", "light", "custom-theme", "custom-cover", "none"])
def test_private_streamcopy_artwork_tags_and_pcm_roundtrip(tmp_path, monkeypatch, choice):
    _tools()
    from ocf_tools import complete_session, voice
    from PIL import Image

    source, master, _ = _session(tmp_path)
    workspace = tmp_path / "work"
    monkeypatch.setenv("OCF_WORK_DIR", str(workspace))
    snapshot = {p.name: p.read_bytes() for p in source.iterdir()}
    compressed = {}
    for fmt in ("flac", "mp3"):
        path = tmp_path / ("existing." + fmt)
        audio_build._encode(
            master,
            fmt,
            path,
            {"track": "7/12", "comment": "retain valid metadata"},
            mp3_bitrate="320k",
        )
        compressed[fmt] = path
    originals = {key: p.read_bytes() for key, p in compressed.items()}

    def forbidden(*args, **kwargs):
        pytest.fail("listening export must never synthesize or mix")

    monkeypatch.setattr(complete_session, "render_complete_session", forbidden)
    monkeypatch.setattr(audio_build, "build", forbidden)
    monkeypatch.setattr(voice, "render_narration", forbidden)
    options = {}
    if choice == "light":
        options["artwork_theme"] = "ocf-cosmic-light"
    elif choice == "custom-theme":
        theme = tmp_path / "custom.json"
        theme.write_text(json.dumps({"id": "custom-private", "extends": "ocf-cosmic-light"}))
        options["artwork_theme"] = str(theme)
    elif choice == "custom-cover":
        cover = tmp_path / "custom.png"
        Image.new("RGB", (320, 320), "navy").save(cover)
        options = {"artwork_file": cover, "artwork_theme": "missing-theme-must-not-load"}
    elif choice == "none":
        options["no_artwork"] = True
    output = workspace / "copies"
    result = exports.export_audition(
        source,
        edition_version="0.1.0",
        flac_source=compressed["flac"],
        mp3_source=compressed["mp3"],
        artwork_resolution=320,
        output=output,
        **options,
    )
    manifest = result["manifest"]
    assert manifest["version"] == "0.1.0" and manifest["publication_approval"] is False
    for fmt, item in manifest["artifacts"].items():
        path = output / item["path"]
        assert item["operation"] == "stream-copy"
        assert item["packet_sha256"] == exports.audio_hash(compressed[fmt], packets=True)
        assert item["pcm_sha256"] == exports.audio_hash(compressed[fmt])
        assert item["channels"] == 2 and item["sample_rate"] == 44100
        assert item["tags"]["track"] == "7/12"
        assert item["tags"]["comment"] == "retain valid metadata"
        assert item["tags"]["ocf_audio_version"] == "0.1.0"
        assert item["tags"]["ocf_version_label"] == "v0.1.0"
        assert item["tags"]["artist"] == "Amy"
        if choice != "none":
            assert exports.front_cover_type(path) == 3
        else:
            with pytest.raises(OCFError, match="front-cover"):
                exports.front_cover_type(path)
    assert exports.audio_hash(output / manifest["artifacts"]["flac"]["path"]) == exports.audio_hash(
        master
    )
    assert {p.name: p.read_bytes() for p in source.iterdir()} == snapshot
    assert {key: p.read_bytes() for key, p in compressed.items()} == originals
    assert (output / "cover.png").exists() == (choice != "none")
    if choice == "default":
        assert manifest["artwork"]["theme_id"] == "ocf-cosmic-dark"
        assert manifest["artwork"]["theme_selection"] == "artwork-surface-default"
    with pytest.raises(OCFError, match="overwrite"):
        exports.export_audition(source, edition=output / "audition-edition.json", output=output)


@pytest.mark.integration
@pytest.mark.external_tool
def test_export_preflight_failure_retains_sources_and_never_publishes(tmp_path, monkeypatch):
    _tools()
    source, _, report = _session(tmp_path)
    work = tmp_path / "work"
    monkeypatch.setenv("OCF_WORK_DIR", str(work))
    output = work / "failed"
    with pytest.raises(OCFError, match="cannot be combined"):
        exports.export_audition(
            source,
            edition_version="0.1.0",
            no_artwork=True,
            artwork_theme="ocf-cosmic-dark",
            output=output,
        )
    preview = exports.export_audition(source, edition_version="0.1.0", output=output, dry_run=True)
    assert preview["artwork"]["theme_id"] == "ocf-cosmic-dark" and not output.exists()
    assert not (work / "cache/artwork").exists()
    monkeypatch.setattr(
        exports,
        "_verify_audio",
        lambda *a, **k: (_ for _ in ()).throw(OCFError("injected verification failure")),
    )
    with pytest.raises(OCFError, match="injected"):
        exports.export_audition(source, edition_version="0.1.0", output=output, no_artwork=True)
    assert not output.exists() and list((work / "logs").glob("*.log"))
    assert sha256_of_file(source / "master.wav") == report["artifacts"]["wav"]["sha256"]
    (source / "transcript.txt").write_text("corrupt")
    with pytest.raises(OCFError, match="truncated|checksum"):
        exports.export_audition(source, edition_version="0.1.0", output=output)


def test_release_cover_uses_registered_version_without_cli_override(tmp_path, monkeypatch):
    from ocf_tools import release

    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(
        release,
        "_select_audio_manifest",
        lambda _: {"id": "OCF-AUDIO-9999", "function_id": "OCF-EXP-001", "version": "2.3.4"},
    )
    versions = []
    original = artwork.generate_cover

    def capture(*args, **kwargs):
        versions.append(kwargs["version"])
        return original(*args, **kwargs)

    monkeypatch.setattr(artwork, "generate_cover", capture)
    release.package_release(
        "OCF-EXP-001", artwork_theme="ocf-cosmic-dark", output=tmp_path / "out", dry_run=True
    )
    assert versions == ["2.3.4"]


def test_cli_routes_private_export_without_release_or_render(monkeypatch, capsys):
    from ocf_tools import cli

    calls = []
    monkeypatch.setattr(
        exports,
        "export_audition",
        lambda source, **kwargs: calls.append((source, kwargs)) or {"dry_run": True},
    )
    assert (
        cli.main(
            [
                "audio",
                "export-audition",
                ".ocf-work/session",
                "--edition-version",
                "0.1.0",
                "--no-artwork",
                "--dry-run",
            ]
        )
        == 0
    )
    assert calls[0][0] == Path(".ocf-work/session")
    assert calls[0][1]["no_artwork"] and calls[0][1]["edition_version"] == "0.1.0"
    assert '"dry_run": true' in capsys.readouterr().out
