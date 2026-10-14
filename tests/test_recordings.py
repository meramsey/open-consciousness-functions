"""Prerecorded speech follows event identity and measured duration, never text matching."""

import hashlib
import io
import wave
from types import SimpleNamespace

import pytest
from ocf_tools.recordings import (
    import_directory,
    prepare_recordings,
    session_fingerprint,
    unique_mapping,
)
from ocf_tools.utils import OCFError, yaml_safe_dump
from ocf_tools.voice import render_narration


def package(tmp_path):
    doc = {
        "schema_version": "1.0",
        "id": "recording-test",
        "title": "Recordings",
        "locale": "en-US",
        "source": {"format": "manual"},
        "timeline": [
            {
                "id": "first",
                "at": 0,
                "text": "Same words.",
                "semantic": "function.practice",
                "timing": {"pause_after": 1},
            },
            {
                "id": "second",
                "after": "first",
                "offset": 0,
                "text": "Same words.",
                "semantic": "function.command.rehearse",
                "timing": {"anchor": "speech-end"},
            },
        ],
    }
    recordings = {}
    for identifier, frames in [("first", 8000), ("second", 16000)]:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as writer:
            writer.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            writer.writeframes(b"\x01\x00" * frames)
        path = tmp_path / f"{identifier}.wav"
        path.write_bytes(buffer.getvalue())
        recordings[identifier] = {
            "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    manifest = {
        "schema_version": "1.0",
        "id": "user-recordings",
        "source_type": "prerecorded-user",
        "locale": "en-US",
        "author": "user",
        "license": "private use only",
        "redistribution_permission": False,
        "recordings": recordings,
    }
    path = tmp_path / "package.yaml"
    path.write_text(yaml_safe_dump(manifest))
    return doc, manifest, path


def test_no_tts_measured_timing_repeated_text_and_original_preservation(tmp_path, monkeypatch):
    from ocf_tools import voice

    doc, _, path = package(tmp_path)
    originals = {source.name: source.read_bytes() for source in tmp_path.glob("*.wav")}
    monkeypatch.setattr(
        voice, "resolve_backend", lambda *args, **kwargs: pytest.fail("TTS must not be selected")
    )
    metadata = render_narration(doc, tmp_path / "result.wav", recordings=path, sample_rate=16000)
    assert metadata["backend"] == "prerecorded"
    assert [cue["duration"] for cue in metadata["cue_stats"]] == [1, 2]
    assert metadata["cue_stats"][1]["at"] == 2
    assert metadata["duration"] == 5  # two recordings + semantic pause + final tail
    assert not metadata["narration_source"]["redistribution_permission"]
    assert all((tmp_path / name).read_bytes() == data for name, data in originals.items())


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("missing", "missing"),
        ("extra", "extra"),
        ("locale", "locale"),
        ("hash", "checksum"),
        ("escape", "relative"),
    ],
)
def test_package_preflight_errors_before_output(tmp_path, mutation, match):
    doc, manifest, path = package(tmp_path)
    if mutation == "missing":
        del manifest["recordings"]["second"]
    elif mutation == "extra":
        manifest["recordings"]["extra"] = manifest["recordings"]["first"]
    elif mutation == "locale":
        manifest["locale"] = "es"
    elif mutation == "hash":
        manifest["recordings"]["first"]["sha256"] = "0" * 64
    else:
        manifest["recordings"]["first"]["file"] = "../outside.wav"
    path.write_text(yaml_safe_dump(manifest))
    output = tmp_path / "result.wav"
    with pytest.raises(OCFError, match=match):
        render_narration(doc, output, recordings=path)
    assert not output.exists()


def test_missing_file_and_incompatible_flags(tmp_path):
    doc, _, path = package(tmp_path)
    (tmp_path / "first.wav").unlink()
    with pytest.raises(OCFError, match="unavailable"):
        prepare_recordings(path, doc, "en-US")
    with pytest.raises(OCFError, match="independent voice source"):
        render_narration(doc, tmp_path / "result.wav", recordings=path, fit=True)


def test_recording_package_hash_and_canonical_text_binding(tmp_path):
    doc, manifest, path = package(tmp_path)
    manifest["session_fingerprint"] = session_fingerprint(doc)
    manifest["recordings"]["first"]["text_sha256"] = hashlib.sha256(
        doc["timeline"][0]["text"].encode()
    ).hexdigest()
    path.write_text(yaml_safe_dump(manifest))
    prepared, provenance = prepare_recordings(path, doc, "en-US")
    assert set(prepared) == {"first", "second"}
    assert provenance["recordings"]["first"]["original_preserved"]
    changed = {**doc, "title": "Different session"}
    with pytest.raises(OCFError, match="different session/version"):
        prepare_recordings(path, changed, "en-US")

    manifest["session_fingerprint"] = session_fingerprint(doc)
    manifest["recordings"]["first"]["text_sha256"] = "0" * 64
    path.write_text(yaml_safe_dump(manifest))
    with pytest.raises(OCFError, match="canonical narration text changed"):
        prepare_recordings(path, doc, "en-US")


def test_session_fingerprint_ignores_rendered_text_for_stable_narration_keys():
    doc = {
        "timeline": [
            {"id": "event", "narration_key": "stable.key", "text": "Resolved English", "at": 0}
        ]
    }
    changed = {"timeline": [{**doc["timeline"][0], "text": "Resolved Spanish"}]}
    assert session_fingerprint(doc) == session_fingerprint(changed)


@pytest.mark.parametrize("failure", ["invalid-package", "decode-error", "empty-decoded"])
def test_recording_preflight_rejects_malformed_packages_and_audio(tmp_path, monkeypatch, failure):
    from ocf_tools import recordings

    doc, manifest, path = package(tmp_path)
    if failure == "invalid-package":
        manifest["schema_version"] = "invalid"
        path.write_text(yaml_safe_dump(manifest))
        with pytest.raises(OCFError, match="narration package"):
            prepare_recordings(path, doc, "en-US")
        return

    data = b"compressed input"
    source = tmp_path / "first.wav"
    source.write_bytes(data)
    manifest["recordings"]["first"]["sha256"] = hashlib.sha256(data).hexdigest()
    path.write_text(yaml_safe_dump(manifest))
    monkeypatch.setattr(recordings.shutil, "which", lambda _name: "/usr/bin/ffmpeg")
    if failure == "decode-error":
        monkeypatch.setattr(
            recordings,
            "workspace_run",
            lambda *_args, **_kwargs: SimpleNamespace(
                returncode=1, stderr=b"decoder error", stdout=b""
            ),
        )
        with pytest.raises(OCFError, match="decode failed: decoder error"):
            prepare_recordings(path, doc, "en-US")
    else:
        empty = io.BytesIO()
        with wave.open(empty, "wb") as writer:
            writer.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        monkeypatch.setattr(
            recordings,
            "workspace_run",
            lambda *_args, **_kwargs: SimpleNamespace(
                returncode=0, stderr=b"", stdout=empty.getvalue()
            ),
        )
        with pytest.raises(OCFError, match="empty or invalid decoded audio"):
            prepare_recordings(path, doc, "en-US")


def test_recording_package_import_maps_explicit_occurrences_and_preserves_inputs(tmp_path):
    doc, _, _ = package(tmp_path)
    originals = {name: (tmp_path / name).read_bytes() for name in ("first.wav", "second.wav")}
    output = tmp_path / "imported.yaml"
    result = import_directory(
        doc,
        tmp_path,
        {"first": "first.wav", "second": "second.wav"},
        output,
        locale="en-US",
        author="User",
        license="private",
    )
    assert result["recordings"]["first"]["measured_duration_s"] == 1
    assert result["recordings"]["second"]["measured_duration_s"] == 2
    assert {name: (tmp_path / name).read_bytes() for name in originals} == originals
    assert yaml_safe_dump(result) == output.read_text()
    with pytest.raises(OCFError, match="refusing to overwrite"):
        import_directory(
            doc,
            tmp_path,
            {"first": "first.wav", "second": "second.wav"},
            output,
            locale="en-US",
            author="User",
            license="private",
        )


def test_recording_import_rejects_duplicate_mappings_and_unmapped_assets(tmp_path):
    with pytest.raises(OCFError, match="duplicate recording event mapping"):
        unique_mapping([("event", "one.wav"), ("event", "two.wav")])
    assert unique_mapping([("first", "first.wav"), ("second", "second.wav")]) == {
        "first": "first.wav",
        "second": "second.wav",
    }

    doc, _, _ = package(tmp_path)
    (tmp_path / "unknown.wav").write_bytes(b"not selected")
    with pytest.raises(OCFError, match="unmapped audio recordings"):
        import_directory(
            doc,
            tmp_path,
            {"first": "first.wav", "second": "second.wav"},
            tmp_path / "new-package.yaml",
            locale="en-US",
            author="User",
            license="private",
        )


@pytest.mark.parametrize("mapping", [[], {"first": "first.wav"}])
def test_recording_import_validates_mapping_shape_and_occurrences(tmp_path, mapping):
    doc, _, _ = package(tmp_path)
    with pytest.raises(OCFError, match="recording mapping"):
        import_directory(
            doc,
            tmp_path,
            mapping,
            tmp_path / "mapped-package.yaml",
            locale="en-US",
            author="User",
            license="private",
        )


@pytest.mark.parametrize("unsafe_name", ["../outside.wav", "absolute"])
def test_recording_import_refuses_escaping_audio_sources(tmp_path, unsafe_name):
    doc, _, _ = package(tmp_path)
    name = str((tmp_path / "first.wav").resolve()) if unsafe_name == "absolute" else unsafe_name
    with pytest.raises(OCFError, match="missing or escaping file"):
        import_directory(
            doc,
            tmp_path,
            {"first": name, "second": "second.wav"},
            tmp_path / "mapped-package.yaml",
            locale="en-US",
            author="User",
            license="private",
        )


def test_recording_import_requires_package_output_within_recording_directory(tmp_path):
    doc, _, _ = package(tmp_path)
    outside = tmp_path / "nested" / "escaped-package.yaml"
    with pytest.raises(OCFError, match="package output must be"):
        import_directory(
            doc,
            tmp_path,
            {"first": "first.wav", "second": "second.wav"},
            outside,
            locale="en-US",
            author="User",
            license="private",
        )


def test_cli_recording_render_and_build_locale_forwarding(tmp_path, monkeypatch):
    from ocf_tools import audio_build
    from ocf_tools.cli import main

    doc, _, path = package(tmp_path)
    script = tmp_path / "session.yaml"
    script.write_text(yaml_safe_dump(doc))
    assert (
        main(
            [
                "voice",
                "render",
                str(script),
                "--recordings",
                str(path),
                "--locale",
                "en-US",
                "--output",
                str(tmp_path / "voice.wav"),
            ]
        )
        == 0
    )
    from ocf_tools.indexes import load_yaml_file

    measured = load_yaml_file(tmp_path / "voice.render.yaml")
    assert measured["narration_timing"]["measured"]
    assert measured["narration_source"]["package_id"] == "user-recordings"
    assert measured["total_duration_s"] == 5
    assert (
        main(
            [
                "transcript",
                "export",
                str(script),
                "--format",
                "srt",
                "--render-manifest",
                str(tmp_path / "voice.render.yaml"),
                "--output",
                str(tmp_path / "voice.srt"),
            ]
        )
        == 0
    )
    assert "00:00:02,000 --> 00:00:04,000" in (tmp_path / "voice.srt").read_text()
    captured = {}
    monkeypatch.setattr(audio_build, "build", lambda query, **kwargs: captured.update(kwargs))
    assert (
        main(
            [
                "audio",
                "build",
                "OCF-AUDIO-0001",
                "--recordings",
                str(path),
                "--locale",
                "es",
                "--allow-fallback",
            ]
        )
        == 0
    )
    assert (
        captured["recordings"] == str(path)
        and captured["locale"] == "es"
        and captured["strict"] is False
    )


def test_compressed_decode_dependency_error_is_not_tts_fallback(tmp_path, monkeypatch):
    from ocf_tools import recordings

    doc, manifest, path = package(tmp_path)
    data = b"unsupported audio format"
    (tmp_path / "first.wav").write_bytes(data)
    manifest["recordings"]["first"]["sha256"] = hashlib.sha256(data).hexdigest()
    path.write_text(yaml_safe_dump(manifest))
    monkeypatch.setattr(recordings.shutil, "which", lambda name: None)
    with pytest.raises(OCFError, match="install ffmpeg.*no TTS fallback"):
        prepare_recordings(path, doc, "en-US")


def test_actual_pcm24_conversion_preserves_duration_and_original(tmp_path):
    import shutil

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg format conversion integration dependency unavailable")
    doc, manifest, path = package(tmp_path)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setparams((2, 3, 8000, 0, "NONE", "not compressed"))
        writer.writeframes(b"\x00\x10\x00" * 2 * 8000)
    original = buffer.getvalue()
    source = tmp_path / "first.wav"
    source.write_bytes(original)
    manifest["recordings"]["first"]["sha256"] = hashlib.sha256(original).hexdigest()
    path.write_text(yaml_safe_dump(manifest))
    _, provenance = prepare_recordings(path, doc, "en-US")
    first = provenance["recordings"]["first"]
    assert first["decoded_to_pcm16"] and first["decoded_channels"] == 1
    assert first["measured_duration_s"] == 1 and source.read_bytes() == original
