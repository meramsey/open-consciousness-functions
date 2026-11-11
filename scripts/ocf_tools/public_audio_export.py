"""Prepare public-safe audio candidates from verified retained deliveries, never TTS.

This is local export only. It does not grant rights or publication approval.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .artifact_names import listener_export_names
from .audio_build import _encode
from .audition_exports import _probe, audio_hash
from .indexes import load_function_by_id
from .paths import (
    SCHEMAS_DIR,
    publish_workspace_temp_directory,
    record_workspace_failure,
    workspace_temp_directory,
)
from .release import _image_info, _verify_embedded_cover
from .utils import OCFError, sha256_of_file


def _require(value: Any, message: str) -> None:
    if not value:
        raise OCFError(message)


def _plain(value: Any, label: str) -> str:
    _require(isinstance(value, str) and value.strip() == value and bool(value), f"invalid {label}")
    _require(not any(ord(c) < 32 or ord(c) == 127 for c in value), f"control character in {label}")
    return value


def _source(root: Path, item: dict[str, Any]) -> Path:
    name = item.get("file")
    _plain(name, "source filename")
    _require(
        Path(name).name == name and not any(c in name for c in "/\\:") and not name.startswith("."),
        "unsafe source filename",
    )
    path = root / name
    _require(not path.is_symlink() and path.is_file(), "missing or symlink source")
    _require(
        type(item.get("bytes")) is int and path.stat().st_size == item["bytes"],
        "source size mismatch",
    )
    _require(sha256_of_file(path) == item.get("sha256"), "source checksum mismatch")
    return path


def _record(path: Path) -> dict[str, Any]:
    return {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_of_file(path)}


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _check_png_container(data: bytes) -> None:
    """Validate the complete PNG structure and one exact, bounded zlib stream."""
    import struct
    import zlib

    message = "cover contains invalid image metadata or trailing PNG data"
    position = 8
    seen: set[bytes] = set()
    compressed = bytearray()
    width = height = depth = color = interlace = palette_entries = 0
    idat_closed = False
    allowed = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM", b"sRGB", b"pHYs"}
    while position + 12 <= len(data):
        length = int.from_bytes(data[position : position + 4], "big")
        kind = data[position + 4 : position + 8]
        end = position + length + 12
        _require(kind in allowed and end <= len(data), message)
        payload = data[position + 8 : end - 4]
        _require(zlib.crc32(kind + payload) == int.from_bytes(data[end - 4 : end], "big"), message)
        _require((not seen and kind == b"IHDR") or b"IHDR" in seen, message)
        _require(kind == b"IDAT" or kind not in seen, message)
        if b"IDAT" in seen and kind != b"IDAT":
            idat_closed = True
        if kind == b"IHDR":
            _require(length == 13, message)
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            legal_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            _require(0 < width <= 12000 and 0 < height <= 12000, message)
            _require(depth in legal_depths.get(color, set()), message)
            _require(compression == filtering == 0 and interlace in {0, 1}, message)
        elif kind in {b"gAMA", b"cHRM", b"sRGB"}:
            _require(b"PLTE" not in seen and b"IDAT" not in seen, message)
            if kind == b"gAMA":
                _require(length == 4 and int.from_bytes(payload, "big") > 0, message)
            elif kind == b"cHRM":
                _require(length == 32, message)
                coordinates = struct.unpack(">8I", payload)
                _require(
                    all(x + y <= 100000 for x, y in zip(coordinates[::2], coordinates[1::2])),
                    message,
                )
            else:
                _require(length == 1 and payload[0] <= 3, message)
        elif kind == b"pHYs":
            _require(b"IDAT" not in seen and length == 9 and payload[-1] <= 1, message)
        elif kind == b"PLTE":
            _require(b"IDAT" not in seen and b"tRNS" not in seen and color in {2, 3, 6}, message)
            _require(0 < length <= 768 and length % 3 == 0, message)
            palette_entries = length // 3
            _require(color != 3 or palette_entries <= 2**depth, message)
        elif kind == b"tRNS":
            _require(b"IDAT" not in seen, message)
            if color in {0, 2}:
                _require(length == (2 if color == 0 else 6), message)
                values = struct.unpack(">" + "H" * (length // 2), payload)
                _require(all(value < 2**depth for value in values), message)
            else:
                _require(color == 3 and b"PLTE" in seen and 0 < length <= palette_entries, message)
        elif kind == b"IDAT":
            _require(not idat_closed and (color != 3 or b"PLTE" in seen), message)
            compressed.extend(payload)
        elif kind == b"IEND":
            _require(length == 0 and end == len(data) and b"IDAT" in seen, message)
            channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
            passes = (
                [(0, 0, 1, 1)]
                if not interlace
                else [
                    (0, 0, 8, 8),
                    (4, 0, 8, 8),
                    (0, 4, 4, 8),
                    (2, 0, 4, 4),
                    (0, 2, 2, 4),
                    (1, 0, 2, 2),
                    (0, 1, 1, 2),
                ]
            )
            expected = 0
            for x, y, dx, dy in passes:
                pass_width = max(0, (width - x + dx - 1) // dx)
                pass_height = max(0, (height - y + dy - 1) // dy)
                if pass_width and pass_height:
                    expected += pass_height * (1 + (pass_width * channels * depth + 7) // 8)
            decoder = zlib.decompressobj()
            pending = bytes(compressed)
            decoded = 0
            try:
                while pending:
                    block = decoder.decompress(pending, 262144)
                    decoded += len(block)
                    _require(decoded <= expected and not decoder.unused_data, message)
                    pending = decoder.unconsumed_tail
                _require(decoder.eof and decoded == expected, message)
            except zlib.error as exc:
                raise OCFError(message) from exc
            return
        seen.add(kind)
        position = end
    raise OCFError(message)


def _check_cover_container(path: Path) -> None:
    """Reject opaque container payloads that image-library metadata can omit."""
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        _check_png_container(data)
        return
    from .jpeg_guard import check_jpeg

    check_jpeg(data)


def _repair_new_mp3_padding(path, expected_frames):
    """Repair only FFmpeg's recognized MPEG-1 stereo multi-packet padding loss.

    The caller must supply a newly encoded, owned temporary output and the exact
    validated lossless master frame count. Compressed audio bytes are unchanged.
    Unknown layouts and other length disagreements fail without writing.
    """

    def require(value):
        if not value:
            raise OCFError("unrecognized MP3 gapless padding mismatch")

    def crc16(data):
        value = 0
        for byte in data:
            value ^= byte
            for _ in range(8):
                value = (value >> 1) ^ (0xA001 if value & 1 else 0)
        return value

    path = Path(path)
    with path.open("r+b") as stream:
        tag = stream.read(10)
        require(len(tag) == 10 and tag[:3] == b"ID3" and tag[3] == 3 and tag[5] == 0)
        require(all(byte < 128 for byte in tag[6:10]))
        position = 10 + sum(byte << shift for byte, shift in zip(tag[6:10], (21, 14, 7, 0)))
        stream.seek(position)
        header = bytearray(stream.read(192))
        require(len(header) == 192)
        require(header[0] == 255 and header[1] == 251)  # MPEG-1 Layer III, no CRC.
        require(header[2] >> 4 == 14)  # This export path encodes 320 kbps.
        require((header[3] >> 6) != 3 and (header[2] & 12) != 12)
        require(header[36:40] in (b"Info", b"Xing") and header[40:44] == b"\0\0\0\x0f")
        require(header[156:160] in (b"Lavf", b"Lavc"))
        require(crc16(header[:190]) == int.from_bytes(header[190:192], "big"))
        count = int.from_bytes(header[44:48], "big")
        combined = int.from_bytes(header[177:180], "big")
        delay, padding = combined >> 12, combined & 4095
        decoded = count * 1152 - delay - padding
        excess = decoded - expected_frames
        require(delay == 576 and padding == 1681 and 0 < excess <= 47)
        corrected = padding + excess
        require(corrected <= 4095)
        header[177:180] = ((delay << 12) | corrected).to_bytes(3, "big")
        header[190:192] = crc16(header[:190]).to_bytes(2, "big")
        stream.seek(position)
        stream.write(header)
    return {
        "discard_padding_samples_before": padding,
        "discard_padding_samples_after": corrected,
        "corrected_samples": excess,
        "frames": expected_frames,
    }


def export_delivery(
    source_manifest: str | Path,
    *,
    expected_source_sha256: str,
    public_voice_id: str,
    public_voice_name: str,
    output: str | Path,
    source_commit: str,
    source_version: str,
    dry_run: bool = False,
    reuse_existing_mp3: bool = False,
    render_source: dict[str, Any] | None = None,
    export_commit: str | None = None,
) -> dict[str, Any]:
    """Export a verified retained delivery with explicit public voice metadata.

    The source receipt is private and hash-bound. Its existing FLAC is the retained
    lossless master; we do not claim to reconstruct a deleted original WAV.
    MP3 is encoded once from lossless FLAC at 320 kbps by default. Explicit reuse
    preserves existing MP3 packets instead. Public tags are allowlisted.
    """
    source_manifest = Path(source_manifest).expanduser().absolute()
    root = source_manifest.parent
    final = Path(output).expanduser().absolute()
    _require(
        not any(p.is_symlink() for p in (source_manifest, *source_manifest.parents)),
        "symlink in source path",
    )
    _require(not any(p.is_symlink() for p in (final, *final.parents)), "symlink in export path")
    _require(not final.exists(), "refusing to overwrite an existing export")
    _require(
        bool(re.fullmatch(r"[a-f0-9]{64}", expected_source_sha256)),
        "invalid source receipt SHA-256",
    )
    _require(
        sha256_of_file(source_manifest) == expected_source_sha256,
        "source receipt checksum mismatch",
    )
    _require(
        bool(re.fullmatch(r"[a-f0-9]{40}", source_commit)), "source commit must be a full Git SHA"
    )
    for label, value in (("voice ID", public_voice_id), ("source version", source_version)):
        _require(
            bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}", _plain(value, label))),
            f"invalid {label}",
        )
    _plain(public_voice_name, "public voice name")
    document = json.loads(source_manifest.read_text(encoding="utf-8"))
    _require(
        document.get("schema_version") == "1.0" and document.get("status") == "verified-candidate",
        "unsupported or incomplete retained delivery",
    )
    kind, function_id = document.get("session_kind"), document.get("function_id")
    _require(kind in {"function", "preparation-learning"}, "unsupported session kind")
    if kind == "preparation-learning":
        _require(function_id is None, "Preparation Learning must not have a function ID")
    else:
        _require(
            isinstance(function_id, str)
            and bool(re.fullmatch(r"OCF-[A-Z]{3}-[A-Z0-9]{3,4}", function_id)),
            "invalid function identity",
        )
        _require(load_function_by_id(function_id) is not None, "unknown canonical function")
    identity = document.get("export_identity", {})
    title, locale, edition = (
        _plain(document.get("title"), "title"),
        _plain(identity.get("locale"), "locale"),
        _plain(identity.get("version"), "edition"),
    )
    measurements = document.get("measurements", {})
    _require(measurements.get("clipped_sample_count") == 0, "delivery is not verified as unclipped")
    artifacts = document.get("artifacts")
    _require(isinstance(artifacts, list) and artifacts, "delivery has no artifacts")
    selected: dict[str, Path] = {}
    originals: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        suffix = Path(str(item.get("file", ""))).suffix.lower().lstrip(".")
        if suffix not in {"flac", "mp3", "png", "jpg", "txt", "srt", "vtt", "lrc"}:
            continue
        _require(suffix not in selected, "duplicate delivery artifact format")
        selected[suffix] = _source(root, item)
        originals[suffix] = item
    _require({"flac", "mp3"} <= selected.keys(), "retained delivery requires verified FLAC and MP3")
    covers = [x for x in ("png", "jpg") if x in selected]
    _require(len(covers) == 1, "delivery requires exactly one verified cover")
    cover_format = covers[0]
    _image_info(selected[cover_format])
    _check_cover_container(selected[cover_format])
    from PIL import Image

    with Image.open(selected[cover_format]) as image:
        # Preserve the approved cover bytes. Reject hidden metadata rather than
        # silently altering or disclosing an owner's artwork/reference details.
        # PNG text may follow IDAT and only become visible after decoding.
        image.load()
        _require(
            not image.getexif()
            and set(image.info)
            <= {
                "dpi",
                "gamma",
                "srgb",
                "chromaticity",
                "transparency",
                "jfif",
                "jfif_version",
                "jfif_unit",
                "jfif_density",
                "adobe",
                "adobe_transform",
                "progressive",
                "progression",
            },
            "cover contains unreviewed image metadata; supply a metadata-free cover",
        )
    names = listener_export_names(
        function_id,
        title,
        locale,
        list(selected),
        voice_label=public_voice_name,
        version=edition,
        session_kind=kind,
    )["files"]
    _require(
        all(len(n.encode("utf-8")) <= 200 for n in names.values()),
        "public export filenames exceed publication limit",
    )
    public_session = {
        "kind": kind,
        "function_id": function_id,
        "title": title,
        "locale": locale,
        "voice_id": public_voice_id,
        "voice_name": public_voice_name,
        "edition": edition,
    }
    if dry_run:
        return {
            "dry_run": True,
            "session": public_session,
            "files": names,
            "publication_approved": False,
        }
    # This only creates owned assembly scratch; original deliveries are untouched.
    stage = workspace_temp_directory(prefix="ocf-public-export-")
    try:
        snapshots = stage / ".source"
        snapshots.mkdir()
        for fmt, path in selected.items():
            target = snapshots / path.name
            shutil.copyfile(path, target)
            _source(snapshots, originals[fmt])
        master = snapshots / selected["flac"].name
        import numpy as np
        import soundfile as sf

        info = sf.info(master)
        bit_depth = {"PCM_16": 16, "PCM_24": 24, "PCM_32": 32}.get(info.subtype)
        _require(
            bit_depth is not None and info.format == "FLAC" and info.frames > 0,
            "retained master must be integer PCM FLAC",
        )
        _require(
            info.channels == measurements.get("channels") == 2
            and info.samplerate == measurements.get("sample_rate")
            and info.frames == measurements.get("frames"),
            "retained master measurements disagree with receipt",
        )
        peak, clipped = 0.0, 0
        for block in sf.blocks(master, blocksize=262144, dtype="float64", always_2d=True):
            _require(bool(np.isfinite(block).all()), "non-finite master audio")
            peak = max(peak, float(np.abs(block).max(initial=0)))
            clipped += int(np.count_nonzero((block <= -1) | (block >= 1 - 2 ** (1 - bit_depth))))
        _require(clipped == 0, "retained master contains full-scale samples")
        tags = {
            "title": title,
            "album": title,
            "artist": public_voice_name,
            "album_artist": "Open Consciousness Functions",
            "language": locale,
            "OCF_SESSION_KIND": kind,
            "OCF_RELEASE_VERSION": edition,
            "OCF_PUBLIC_VOICE_ID": public_voice_id,
        }
        if function_id:
            tags["OCF_FUNCTION_ID"] = function_id
        cover = snapshots / selected[cover_format].name
        receipts = {}
        for fmt in ("flac", "mp3"):
            copy_audio = fmt == "flac" or reuse_existing_mp3
            source = snapshots / selected[fmt].name if copy_audio else master
            source_probe = _probe(source)
            _require(
                source_probe["codec"] == (fmt if copy_audio else "flac")
                and source_probe["channels"] == info.channels
                and source_probe["sample_rate"] == info.samplerate,
                "retained audio format mismatch",
            )
            before_pcm = audio_hash(source) if copy_audio else None
            before_packets = audio_hash(source, packets=True) if copy_audio else None
            destination = stage / names[fmt]
            _encode(
                source,
                fmt,
                destination,
                tags,
                artwork=cover,
                copy_audio=copy_audio,
                mp3_bitrate="320k" if not copy_audio else None,
                copy_metadata=False,
            )
            if fmt == "mp3" and not copy_audio and sf.info(destination).frames != info.frames:
                _repair_new_mp3_padding(destination, info.frames)
            after_pcm, after_packets = (
                audio_hash(destination),
                audio_hash(destination, packets=True),
            )
            if copy_audio:
                _require(
                    after_pcm == before_pcm and after_packets == before_packets,
                    "export changed retained audio",
                )
            if fmt == "mp3":
                decoded = sf.info(destination)
                _require(
                    decoded.frames == info.frames
                    and decoded.samplerate == info.samplerate
                    and decoded.channels == info.channels,
                    "MP3 decoded frame alignment differs from master",
                )
                decoded_frames = 0
                for block in sf.blocks(
                    destination, blocksize=262144, dtype="float64", always_2d=True
                ):
                    decoded_frames += len(block)
                    _require(
                        bool(np.isfinite(block).all()) and not np.any(np.abs(block) >= 1),
                        "MP3 decode contains non-finite or full-scale samples",
                    )
                _require(
                    decoded_frames == info.frames, "MP3 decoded frame count differs from master"
                )
            _verify_embedded_cover(destination, cover)
            probe = _probe(destination)
            allowed = {key.lower() for key in tags} | {"encoder"}
            _require(
                set(probe["tags"]) <= allowed
                and all(probe["tags"].get(k.lower()) == v for k, v in tags.items()),
                "public metadata read-back mismatch or unapproved tag",
            )
            receipts[fmt] = {
                "decoded_pcm_sha256": after_pcm,
                "packet_sha256": after_packets,
                "operation": "stream-copy" if copy_audio else "encode-from-lossless",
                "sample_rate_hz": info.samplerate,
                "channels": info.channels,
                "duration_seconds": probe["duration_seconds"],
                "encoding": "MP3 320 kbps" if not copy_audio else probe["codec"],
                **({"bit_depth": bit_depth} if fmt == "flac" else {}),
            }
        for fmt in selected.keys() - {"flac", "mp3"}:
            shutil.copyfile(snapshots / selected[fmt].name, stage / names[fmt])
        for fmt in selected:
            _source(root, originals[fmt])
        _require(
            sha256_of_file(source_manifest) == expected_source_sha256,
            "source receipt changed during export",
        )
        technical = {
            "schema_version": 1,
            "source_kind": "verified-retained-flac",
            "source_commit": source_commit,
            "source_version": source_version,
            "frames": info.frames,
            "peak": peak,
            "clipped_sample_count": clipped,
            "audio": receipts,
        }
        technical_path = stage / Path(names["flac"]).with_suffix(".json").name
        technical_path.write_bytes(_json_bytes(technical))
        report = {
            "schema_version": 1,
            "session": public_session,
            "source_commit": source_commit,
            "source_version": source_version,
            "source_manifest_sha256": expected_source_sha256,
            "master_sha256": originals["flac"]["sha256"],
            "technical_receipt_sha256": sha256_of_file(technical_path),
            "audio": receipts,
            "artifacts": [_record(stage / names[fmt]) for fmt in sorted(selected)]
            + [_record(technical_path)],
            "publication_approved": False,
        }
        if render_source is not None:
            _require(
                render_source.get("base_commit") == source_commit,
                "render source base commit mismatch",
            )
            report["render_source"] = render_source
        if export_commit is not None:
            report["export_commit"] = export_commit
        from jsonschema import Draft202012Validator

        schema = json.loads(
            (SCHEMAS_DIR / "public-export-candidate.schema.json").read_text(encoding="utf-8")
        )
        errors = list(Draft202012Validator(schema).iter_errors(report))
        _require(not errors, "public export candidate failed schema validation")
        (stage / "export-candidate.json").write_bytes(_json_bytes(report))
        shutil.rmtree(snapshots)
        publish_workspace_temp_directory(stage, final)
        return {"dry_run": False, "output": str(final), "candidate": report}
    except BaseException as exc:
        record_workspace_failure(
            stage.name, f"public export failed: {type(exc).__name__}; retained scratch: {stage}"
        )
        raise
