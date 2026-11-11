"""Standalone artwork uses real shared rendering and codec embedding boundaries."""

import hashlib
import shutil
import subprocess
import wave
from pathlib import Path

import pytest
from ocf_tools import artwork, audio_build, brand_import
from ocf_tools import audition_exports as exports
from ocf_tools.utils import OCFError, sha256_of_file

pytestmark = pytest.mark.integration


def tools():
    pytest.importorskip("PIL")
    pytest.importorskip("fontTools")


@pytest.mark.parametrize("theme", ["ocf-cosmic-dark", "ocf-cosmic-light", "ocf-dark"])
def test_standalone_cover_never_uses_sample_or_function_identity(tmp_path, monkeypatch, theme):
    tools()
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(artwork, "export_brand", lambda *a, **k: pytest.fail("sample album leaked"))
    path, provenance, report = exports.select_cover(
        None,
        "en-US",
        "0.1.0",
        session_kind="preparation-learning",
        artwork_theme=theme,
        artwork_resolution=600,
    )
    settings = report["settings"]
    assert settings["function_id"] is None
    assert settings["session_kind"] == "preparation-learning"
    assert settings["title"] == "Preparation Learning"
    assert settings["function_content"] is None
    assert not settings["show_cue"] and not settings["show_description"]
    visible = " ".join(settings["visible_text"])
    assert "Preparation Learning" in visible and "v0.1.0" in visible
    assert "Sleep Easy" not in visible and "OCF-SLP" not in visible and "PLUS" not in visible
    assert path.name.startswith("00 - Preparation-Learning")
    sample = brand_import.asset("album", artwork.load_theme("ocf-cosmic-dark"), "png")
    assert sha256_of_file(path) != sha256_of_file(sample)
    assert provenance["publication_approval"] is False
    repeated = artwork.generate_cover(
        None,
        session_kind="preparation-learning",
        theme=theme,
        resolution=600,
        version="0.1.0",
        status_label="BETA / PRIVATE",
    )
    assert repeated["cache"] == "hit" and repeated["sha256"] == sha256_of_file(path)
    with pytest.raises(OCFError, match="overwrite"):
        artwork.generate_cover(None, session_kind="preparation-learning", output=path)


@pytest.mark.parametrize(
    "identity,kind", [("OCF-SLP-005", "preparation-learning"), (None, "unknown")]
)
def test_reject_conflicting_or_unknown_identity(identity, kind):
    with pytest.raises(OCFError, match="identifier|session kind"):
        exports.select_cover(identity, "en-US", "0.1.0", session_kind=kind, no_artwork=True)
    with pytest.raises(OCFError, match="identifier|session kind"):
        artwork.generate_cover(identity, session_kind=kind, dry_run=True)


def test_localized_title_must_be_explicit_and_custom_art_remains_explicit(tmp_path, monkeypatch):
    tools()
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    with pytest.raises(OCFError, match="localized title"):
        artwork.generate_cover(None, session_kind="preparation-learning", locale="es", dry_run=True)
    result = artwork.generate_cover(
        None,
        session_kind="preparation-learning",
        locale="es",
        title_override="Aprendizaje",
        resolution=600,
        output=tmp_path / "custom.png",
    )
    assert result["settings"]["title_resolution"]["resolved_locale"] == "operator-supplied"
    path, provenance, generated = exports.select_cover(
        None,
        "en-US",
        "0.1.0",
        session_kind="preparation-learning",
        artwork_file=result["path"],
    )
    assert (
        path == Path(result["path"])
        and provenance["source"] == "explicit-user-cover"
        and generated is None
    )
    assert (
        exports.select_cover(
            None, "en-US", "0.1.0", session_kind="preparation-learning", no_artwork=True
        )[0]
        is None
    )


@pytest.mark.audio_integration
@pytest.mark.external_tool
@pytest.mark.parametrize("custom", [False, True])
def test_standalone_build_embeds_exact_cover_in_flac_and_mp3(tmp_path, monkeypatch, custom):
    tools()
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("standalone artwork embedding requires FFmpeg/ffprobe")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setattr(artwork, "export_brand", lambda *a, **k: pytest.fail("sample album leaked"))

    def narration(document, path, **kwargs):
        with wave.open(str(path), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(44100)
            f.writeframes(b"\x10\x01\x20\x02" * 22050)
        return {
            "backend": "synthetic",
            "sample_rate": 44100,
            "channels": 1,
            "duration": 1.0,
            "cues": 0,
            "overlap_mode": "reject-fixed-overlap",
        }

    monkeypatch.setattr(audio_build, "render_narration", narration)
    manifest = {
        "title": "Preparation Learning",
        "session_kind": "preparation-learning",
        "language": "en-US",
        "version": "0.1.0",
        "background_audio": {"strategy": "none"},
    }
    chosen = None
    if custom:
        from PIL import Image

        chosen = tmp_path / "custom.png"
        Image.new("RGB", (600, 600), "navy").save(chosen)
    target = tmp_path / "built"
    result = audio_build.build(
        "standalone",
        document_override={"timeline": []},
        manifest_override=manifest,
        render_label="preparation-learning",
        out_root=target,
        formats=["wav", "flac", "mp3"],
        artwork=chosen,
    )
    assert {x["format"] for x in result["outputs"]} == {"wav", "flac", "mp3"}
    assert result["audio_manifest"]["function_id"] is None
    cover = chosen or target / result["artwork"]["file"]
    master = target / result["master"]["file"]
    for fmt in ("flac", "mp3"):
        encoded = target / next(x["file"] for x in result["outputs"] if x["format"] == fmt)
        image = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(encoded),
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-f",
                "image2pipe",
                "-",
            ],
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(image).hexdigest() == sha256_of_file(cover)
        assert exports.front_cover_type(encoded) == 3
        reference = tmp_path / ("no-cover." + fmt)
        audio_build._encode(master, fmt, reference, tags=result["tags"])
        assert exports.audio_hash(encoded, packets=True) == exports.audio_hash(
            reference, packets=True
        )
        assert exports.audio_hash(encoded) == exports.audio_hash(reference)
        assert exports._probe(encoded)["tags"]["title"] == "Preparation Learning"
    original = {p.name: sha256_of_file(p) for p in target.iterdir() if p.is_file()}
    with pytest.raises(OCFError, match="overwrite"):
        audio_build.build(
            "standalone",
            document_override={"timeline": []},
            manifest_override=manifest,
            render_label="preparation-learning",
            out_root=target,
            formats=["flac", "mp3"],
            overwrite=False,
        )
    assert original == {p.name: sha256_of_file(p) for p in target.iterdir() if p.is_file()}


def test_regional_english_cover_records_same_language_fallback(tmp_path, monkeypatch):
    tools()
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    _, _, result = exports.select_cover(
        None, "en-GB", "0.1.0", session_kind="preparation-learning", dry_run=True
    )
    assert result["settings"]["title"] == "Preparation Learning"
    assert result["settings"]["title_resolution"]["resolved_locale"] == "en-US"
    assert result["settings"]["title_resolution"]["fallback"] is True
