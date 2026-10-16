"""Isolated package verification failure paths; no codecs or real subprocesses."""

import json
from types import SimpleNamespace

import pytest
from ocf_tools import release
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def test_non_square_jpeg_dimensions_keep_width_and_height_in_order(tmp_path):
    # SOF0 precision=8, height=17, width=31; no claim this header is a decoded image.
    data = b"\xff\xd8\xff\xe0\x00\x02\xff\xc0\x00\x07\x08\x00\x11\x00\x1f"
    path = tmp_path / "header.jpg"
    path.write_bytes(data)
    assert release._image_info(path) == ("image/jpeg", 31, 17)


@pytest.mark.parametrize(
    "data",
    [
        b"\xff\xd8",
        b"\xff\xd8\x00\xff",
        b"\xff\xd8\xff\xd0\xff\xc0\x00",
        b"\xff\xd8\xff\xc0\x00\x01",
        b"\xff\xd8\xff\xc0\x00\x20",
    ],
)
def test_truncated_or_invalid_jpeg_markers_fail_without_guessing(data):
    with pytest.raises(OCFError, match="dimensions were not found"):
        release._jpeg_dimensions(data)


@pytest.mark.parametrize(
    "overrides",
    [
        {"ocf_function_id": "OCF-TST-999"},
        {"title": "a\nb"},
        {"title": "/private/path"},
        {"title": "C:\\private\\path"},
        {"title": "//server/private"},
    ],
)
def test_metadata_override_cannot_replace_identity_or_expose_private_paths(overrides):
    with pytest.raises(OCFError):
        release.package_release("unresolved", metadata_overrides=overrides)


@pytest.mark.parametrize(
    "registered,expected",
    [
        ([], "no audio implementation"),
        (
            [{"id": "one", "function_id": "target"}, {"id": "two", "function_id": "target"}],
            "multiple audio implementations",
        ),
    ],
)
def test_implementation_selection_is_explicit_when_missing_or_ambiguous(
    monkeypatch, registered, expected
):
    monkeypatch.setattr(release, "find_audio_manifest", lambda query: None)
    monkeypatch.setattr(release, "load_audio_manifests", lambda: registered)
    with pytest.raises(OCFError, match=expected):
        release._select_audio_manifest("target")


@pytest.mark.parametrize(
    "failure", ["decode", "probe", "json", "tags", "picture", "extract", "hash", None]
)
def test_readback_requires_decoding_tags_and_exact_cover_and_cleans_extraction(
    tmp_path, monkeypatch, failure
):
    path = tmp_path / "example.mp3"
    art = tmp_path / "cover.png"
    art.write_bytes(b"original-cover")
    extracted = tmp_path / ".example.cover.png"
    monkeypatch.setattr(release.shutil, "which", lambda name: name)
    info = {
        "format": {
            "tags": {"title": "Example", "album": "Example", "ocf_function_id": "OCF-TST-999"},
            "duration": "2",
        },
        "streams": [
            {"codec_type": "audio", "codec_name": "mp3", "sample_rate": "44100", "channels": 2},
            {"codec_type": "video", "disposition": {"attached_pic": 1}},
        ],
    }
    if failure == "tags":
        info["format"]["tags"]["title"] = "Wrong"
    if failure == "picture":
        info["streams"].pop()

    def process(argv, **kwargs):
        if "-show_format" in argv:
            return SimpleNamespace(
                returncode=int(failure == "probe"),
                stdout="{" if failure == "json" else json.dumps(info),
                stderr="probe failed",
            )
        if "-map" in argv:
            if failure != "extract":
                extracted.write_bytes(b"different" if failure == "hash" else art.read_bytes())
            return SimpleNamespace(returncode=int(failure == "extract"), stderr="extract failed")
        return SimpleNamespace(returncode=int(failure == "decode"), stderr="decode failed")

    monkeypatch.setattr(release, "workspace_run", process)
    if failure:
        with pytest.raises(OCFError):
            release._verify_audio(path, function_id="OCF-TST-999", title="Example", artwork=art)
    else:
        result = release._verify_audio(
            path, function_id="OCF-TST-999", title="Example", artwork=art
        )
        assert result["channels"] == 2 and result["duration_seconds"] == 2
    assert not extracted.exists()
    assert art.read_bytes() == b"original-cover"
