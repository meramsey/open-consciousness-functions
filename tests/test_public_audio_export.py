"""Existing-master public exports never render speech or retain private metadata."""

import json
import shutil
import subprocess

import numpy as np
import pytest
from ocf_tools import audio_build
from ocf_tools import public_audio_export as exports
from ocf_tools.audition_exports import audio_hash
from ocf_tools.utils import OCFError, sha256_of_file

pytestmark = pytest.mark.integration


def delivery(
    tmp_path,
    monkeypatch,
    *,
    preparation=False,
    subtype="PCM_16",
    cover_format="png",
    progressive=False,
):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("public export requires optional FFmpeg/ffprobe")
    sf = pytest.importorskip("soundfile")
    image = pytest.importorskip("PIL.Image")
    mutagen = pytest.importorskip("mutagen.flac")
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    source = tmp_path / "source"
    source.mkdir()
    t = np.arange(44100) / 44100
    samples = np.column_stack((0.1 * np.sin(t * 1300), 0.08 * np.sin(t * 1700)))
    master = source / "retained.flac"
    sf.write(master, samples, 44100, subtype=subtype)
    metadata = mutagen.FLAC(master)
    metadata["PRIVATE_REFERENCE"] = "/private/reference.wav"
    metadata["comment"] = "DO_NOT_PUBLISH"
    metadata.save()
    cover = source / ("cover." + cover_format)
    image.new("RGB", (8, 8), "#19415c").save(cover, progressive=progressive)
    audio_build._encode(
        master, "mp3", source / "retained.mp3", {"comment": "DO_NOT_PUBLISH"}, artwork=cover
    )
    (source / "transcript.txt").write_text("Synthetic export fixture.\n", encoding="utf-8")
    files = [master, source / "retained.mp3", cover, source / "transcript.txt"]
    document = {
        "schema_version": "1.0",
        "status": "verified-candidate",
        "session_kind": "preparation-learning" if preparation else "function",
        "function_id": None if preparation else "OCF-EXP-001",
        "title": "Preparation Learning" if preparation else "Manifest",
        "export_identity": {
            "locale": "en-US",
            "version": "1.0.0",
            "voice_display_label": "Private fixture voice",
        },
        "measurements": {
            "clipped_sample_count": 0,
            "channels": 2,
            "sample_rate": 44100,
            "frames": 44100,
        },
        "artifacts": [
            {"file": p.name, "bytes": p.stat().st_size, "sha256": sha256_of_file(p)} for p in files
        ],
    }
    path = source / "delivery.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(
        audio_build, "build", lambda *a, **k: pytest.fail("export attempted rendering")
    )
    return path, files


def arguments(path, output):
    return {
        "expected_source_sha256": sha256_of_file(path),
        "public_voice_id": "example-public",
        "public_voice_name": "Example Voice",
        "output": output,
        "source_commit": "a" * 40,
        "source_version": "1.0.0",
    }


@pytest.mark.parametrize(
    "preparation,subtype,cover_format,progressive",
    [
        (False, "PCM_16", "png", False),
        (True, "PCM_24", "png", False),
        (False, "PCM_16", "jpg", False),
        (False, "PCM_16", "jpg", True),
    ],
)
def test_public_export_preserves_lossless_audio_and_encodes_mp3_once(
    tmp_path, monkeypatch, preparation, subtype, cover_format, progressive
):
    path, originals = delivery(
        tmp_path,
        monkeypatch,
        preparation=preparation,
        subtype=subtype,
        cover_format=cover_format,
        progressive=progressive,
    )
    before = {p.name: sha256_of_file(p) for p in originals}
    output = tmp_path / "public-candidate"
    assert exports.export_delivery(path, **arguments(path, output), dry_run=True)["dry_run"]
    assert not output.exists()
    report = exports.export_delivery(path, **arguments(path, output))["candidate"]
    assert report["publication_approved"] is False
    assert report["session"]["function_id"] == (None if preparation else "OCF-EXP-001")
    flac = next(output.glob("*.flac"))
    mp3 = next(output.glob("*.mp3"))
    assert audio_hash(flac) == audio_hash(originals[0])
    assert audio_hash(flac, packets=True) == audio_hash(originals[0], packets=True)
    assert report["audio"]["flac"]["bit_depth"] == (24 if subtype == "PCM_24" else 16)
    assert report["audio"]["mp3"]["operation"] == "encode-from-lossless"
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=bit_rate",
            "-of",
            "json",
            str(mp3),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert int(json.loads(result.stdout)["streams"][0]["bit_rate"]) == 320000
    for audio in (flac, mp3):
        tags = exports._probe(audio)["tags"]
        assert "private_reference" not in tags and "comment" not in tags
        assert "DO_NOT_PUBLISH" not in json.dumps(tags)
        assert tags["artist"] == "Example Voice"
    assert {p.name: sha256_of_file(p) for p in originals} == before
    assert not (output / ".source").exists()
    assert flac.name.startswith(
        "00 - Preparation-Learning" if preparation else "OCF-EXP-001 - Manifest"
    )


def test_explicit_reuse_preserves_mp3_packets_and_pcm(tmp_path, monkeypatch):
    path, originals = delivery(tmp_path, monkeypatch)
    output = tmp_path / "reused"
    report = exports.export_delivery(path, **arguments(path, output), reuse_existing_mp3=True)[
        "candidate"
    ]
    exported = next(output.glob("*.mp3"))
    assert audio_hash(exported) == audio_hash(originals[1])
    assert audio_hash(exported, packets=True) == audio_hash(originals[1], packets=True)
    assert report["audio"]["mp3"]["operation"] == "stream-copy"


def test_tamper_no_overwrite_and_false_function_preflight(tmp_path, monkeypatch):
    path, originals = delivery(tmp_path, monkeypatch, preparation=True)
    output = tmp_path / "output"
    params = arguments(path, output)
    assert exports.export_delivery(path, **params, dry_run=True)["publication_approved"] is False
    assert not output.exists()
    originals[-1].write_text("changed", encoding="utf-8")
    with pytest.raises(OCFError, match="size|checksum"):
        exports.export_delivery(path, **params)
    assert not output.exists()
    output.mkdir()
    with pytest.raises(OCFError, match="overwrite"):
        exports.export_delivery(path, **params)
    output.rmdir()
    doc = json.loads(path.read_text())
    doc["function_id"] = "OCF-EXP-001"
    path.write_text(json.dumps(doc))
    with pytest.raises(OCFError, match="function ID"):
        exports.export_delivery(path, **arguments(path, output), dry_run=True)


def test_public_export_is_repeatable_and_cli_dry_run_is_nonmutating(tmp_path, monkeypatch, capsys):
    from ocf_tools.cli import main

    path, _ = delivery(tmp_path, monkeypatch, preparation=True)
    assert (
        main(
            [
                "audio",
                "export-public",
                str(path),
                "--expected-source-sha256",
                sha256_of_file(path),
                "--public-voice-id",
                "example-public",
                "--public-voice-name",
                "Example Voice",
                "--source-commit",
                "a" * 40,
                "--source-version",
                "1.0.0",
                "--output",
                str(tmp_path / "dry-run"),
                "--dry-run",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["dry_run"] is True
    assert not (tmp_path / "dry-run").exists()
    first = exports.export_delivery(path, **arguments(path, tmp_path / "first"))["candidate"]
    second = exports.export_delivery(path, **arguments(path, tmp_path / "second"))["candidate"]
    assert first == second


@pytest.mark.parametrize("bits", [16, 24])
@pytest.mark.parametrize("positive", [False, True])
def test_master_full_scale_rails_are_rejected(tmp_path, monkeypatch, bits, positive):
    import soundfile as sf

    path, originals = delivery(tmp_path, monkeypatch)
    rail = 1 - 2 ** (1 - bits) if positive else -1.0
    sf.write(originals[0], np.full((44100, 2), rail), 44100, subtype=f"PCM_{bits}")
    document = json.loads(path.read_text())
    document["artifacts"][0].update(
        bytes=originals[0].stat().st_size, sha256=sha256_of_file(originals[0])
    )
    path.write_text(json.dumps(document))
    with pytest.raises(OCFError, match="full-scale"):
        exports.export_delivery(path, **arguments(path, tmp_path / "out"))


@pytest.mark.parametrize("late", [False, True])
def test_hidden_artwork_metadata_rejected_before_export(tmp_path, monkeypatch, late):
    from PIL import Image, PngImagePlugin

    path, originals = delivery(tmp_path, monkeypatch)
    text = PngImagePlugin.PngInfo()
    text.add(b"tEXt", b"reference\x00/private/DO_NOT_PUBLISH.wav", after_idat=late)
    with Image.open(originals[2]) as image:
        image.save(originals[2], pnginfo=text)
    document = json.loads(path.read_text())
    document["artifacts"][2].update(
        bytes=originals[2].stat().st_size, sha256=sha256_of_file(originals[2])
    )
    path.write_text(json.dumps(document))
    with pytest.raises(OCFError, match="image metadata"):
        exports.export_delivery(path, **arguments(path, tmp_path / "out"), dry_run=True)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "kind", ["png-unknown", "png-trailing", "jpeg-unknown", "jpeg-after-scan", "jpeg-trailing"]
)
def test_opaque_cover_payloads_are_rejected_without_changing_artwork(tmp_path, monkeypatch, kind):
    from PIL import Image, PngImagePlugin

    jpeg = kind.startswith("jpeg")
    path, originals = delivery(tmp_path, monkeypatch, cover_format="jpg" if jpeg else "png")
    cover = originals[2]
    if kind == "png-unknown":
        metadata = PngImagePlugin.PngInfo()
        metadata.add(b"vpAg", b"PRIVATE_METADATA_FIXTURE", after_idat=True)
        with Image.open(cover) as image:
            image.save(cover, pnginfo=metadata)
    elif kind in {"jpeg-unknown", "jpeg-after-scan"}:
        data = cover.read_bytes()
        payload = b"PRIVATE_METADATA_FIXTURE"
        segment = b"\xff\xef" + (len(payload) + 2).to_bytes(2, "big") + payload
        cover.write_bytes(
            data[:2] + segment + data[2:]
            if kind == "jpeg-unknown"
            else data[:-2] + segment + data[-2:]
        )
    else:
        cover.write_bytes(cover.read_bytes() + b"PRIVATE_METADATA_FIXTURE")
    document = json.loads(path.read_text())
    checksum = sha256_of_file(cover)
    document["artifacts"][2].update(bytes=cover.stat().st_size, sha256=checksum)
    path.write_text(json.dumps(document))
    with pytest.raises(OCFError, match="image metadata|trailing data"):
        exports.export_delivery(path, **arguments(path, tmp_path / "out"), dry_run=True)
    assert sha256_of_file(cover) == checksum
    assert not (tmp_path / "out").exists()


def test_progressive_jpeg_cover_container_remains_supported(tmp_path):
    from PIL import Image

    path = tmp_path / "progressive.jpg"
    Image.new("RGB", (16, 16), "#19415c").save(path, progressive=True)
    checksum = sha256_of_file(path)
    exports._check_cover_container(path)
    assert sha256_of_file(path) == checksum


@pytest.mark.parametrize(
    "kind",
    [
        "gamma-extra",
        "idat-unused",
        "idat-second-stream",
        "idat-decoded-extra",
        "idat-truncated",
        "bad-crc",
    ],
)
def test_png_payload_leaks_fail_full_preflight_without_modifying_cover(tmp_path, monkeypatch, kind):
    import zlib

    path, originals = delivery(tmp_path, monkeypatch)
    cover = originals[2]
    data = cover.read_bytes()

    def chunk(marker, payload):
        return (
            len(payload).to_bytes(4, "big")
            + marker
            + payload
            + zlib.crc32(marker + payload).to_bytes(4, "big")
        )

    if kind == "gamma-extra":
        data = (
            data[:33]
            + chunk(b"gAMA", (45455).to_bytes(4, "big") + b"PRIVATE_METADATA_FIXTURE")
            + data[33:]
        )
    elif kind == "bad-crc":
        data = data[:33] + chunk(b"gAMA", (45455).to_bytes(4, "big"))[:-1] + b"\x00" + data[33:]
    else:
        position = data.index(b"IDAT") - 4
        size = int.from_bytes(data[position : position + 4], "big")
        payload = data[position + 8 : position + 8 + size]
        if kind == "idat-unused":
            payload += b"PRIVATE_METADATA_FIXTURE"
        elif kind == "idat-second-stream":
            payload += zlib.compress(b"PRIVATE_METADATA_FIXTURE")
        elif kind == "idat-decoded-extra":
            payload = zlib.compress(zlib.decompress(payload) + b"PRIVATE_METADATA_FIXTURE")
        else:
            payload = payload[:-2]
        data = data[:position] + chunk(b"IDAT", payload) + data[position + 12 + size :]
    cover.write_bytes(data)
    checksum = sha256_of_file(cover)
    document = json.loads(path.read_text())
    document["artifacts"][2].update(bytes=cover.stat().st_size, sha256=checksum)
    path.write_text(json.dumps(document))
    with pytest.raises(OCFError, match="image metadata|PNG data"):
        exports.export_delivery(path, **arguments(path, tmp_path / "out"), dry_run=True)
    assert sha256_of_file(cover) == checksum
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("mode", ["1", "L", "LA", "P", "RGB", "RGBA", "I;16"])
def test_valid_png_color_modes_and_structured_metadata_are_supported(tmp_path, mode):
    from PIL import Image, PngImagePlugin

    path = tmp_path / "cover.png"
    metadata = PngImagePlugin.PngInfo()
    metadata.add(b"gAMA", (45455).to_bytes(4, "big"))
    metadata.add(b"sRGB", b"\x00")
    Image.new(mode, (9, 7)).save(path, pnginfo=metadata, dpi=(72, 72))
    checksum = sha256_of_file(path)
    exports._check_cover_container(path)
    assert sha256_of_file(path) == checksum


def test_interlaced_png_complete_idat_stream_is_supported(tmp_path):
    import struct
    import zlib

    from PIL import Image

    def chunk(marker, payload):
        return (
            len(payload).to_bytes(4, "big")
            + marker
            + payload
            + zlib.crc32(marker + payload).to_bytes(4, "big")
        )

    header = struct.pack(">IIBBBBB", 9, 7, 8, 2, 0, 0, 1)
    rows = b""
    for x, y, dx, dy in [
        (0, 0, 8, 8),
        (4, 0, 8, 8),
        (0, 4, 4, 8),
        (2, 0, 4, 4),
        (0, 2, 2, 4),
        (1, 0, 2, 2),
        (0, 1, 1, 2),
    ]:
        width, height = max(0, (9 - x + dx - 1) // dx), max(0, (7 - y + dy - 1) // dy)
        if width and height:
            rows += b"\x00" * (height * (1 + width * 3))
    compressed = zlib.compress(rows)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
    data += chunk(b"IDAT", compressed[:5]) + chunk(b"IDAT", compressed[5:]) + chunk(b"IEND", b"")
    path = tmp_path / "cover.png"
    path.write_bytes(data)
    with Image.open(path) as image:
        image.load()
        assert image.size == (9, 7)
    exports._check_cover_container(path)
    assert path.read_bytes() == data
