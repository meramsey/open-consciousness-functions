"""Versioned private listening copies from completed sessions; never renders audio."""

from __future__ import annotations

import json
import shutil
from pathlib import Path, PureWindowsPath

from . import artwork, audio_build
from .artifact_names import ArtifactNamer
from .indexes import find_audio_manifest, load_function_by_id
from .locale import LocaleCatalog
from .paths import (
    publish_workspace_temp_directory,
    record_workspace_failure,
    unique_run_id,
    work_path,
    work_root,
    workspace_run,
    workspace_temp_directory,
)
from .release import _ffmpeg, _function_title, _image_info, _verify_audio
from .utils import OCFError, read_json_object, sha256_of_file, write_text_atomic
from .validators import _load_schema, validate_against_schema


def _artifact(path: Path) -> dict:
    return {"path": path.name, "size_bytes": path.stat().st_size, "sha256": sha256_of_file(path)}


def _source_artifact(root: Path, item: dict) -> Path:
    relative = item["path"]
    path = root / relative
    windows = PureWindowsPath(relative)
    if (
        Path(relative).is_absolute()
        or windows.root
        or windows.drive
        or ".." in windows.parts
        or not path.resolve().is_relative_to(root.resolve())
    ):
        raise OCFError("unsafe audition artifact path")
    if not path.is_file() or path.stat().st_size != item["size_bytes"]:
        raise OCFError(f"missing/truncated audition artifact: {relative}")
    if sha256_of_file(path) != item["sha256"]:
        raise OCFError(f"audition artifact checksum mismatch: {relative}")
    return path


def _probe(path: Path) -> dict:
    binary = shutil.which("ffprobe")
    if not binary:
        raise OCFError("ffprobe is required for private listening exports")
    result = workspace_run(
        [binary, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise OCFError(f"could not inspect audio: {result.stderr[-400:]}")
    info = json.loads(result.stdout)
    streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if len(streams) != 1:
        raise OCFError("listening export requires exactly one audio stream")
    stream = streams[0]
    return {
        "codec": stream["codec_name"],
        "channels": int(stream["channels"]),
        "sample_rate": int(stream["sample_rate"]),
        "duration_seconds": float(info["format"]["duration"]),
        "tags": {str(k).lower(): str(v) for k, v in info["format"].get("tags", {}).items()},
    }


def audio_hash(path: Path, *, packets: bool = False) -> str:
    """Hash demuxed compressed packets or decoded PCM, without writing audio."""
    result = workspace_run(
        [
            _ffmpeg(),
            "-v",
            "error",
            "-xerror",
            "-nostdin",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-c:a",
            "copy" if packets else "pcm_s32le",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode or not result.stdout.strip().startswith("SHA256="):
        raise OCFError(f"audio integrity check failed: {path.name}: {result.stderr[-400:]}")
    return result.stdout.strip().split("=", 1)[1]


def front_cover_type(path: Path) -> int:
    """Read native FLAC PICTURE / ID3v2.3 APIC type, rather than trusting tags."""
    with path.open("rb") as stream:
        header = stream.read(10)
        if header[:4] == b"fLaC":
            stream.seek(4)
            while True:
                block = stream.read(4)
                if len(block) != 4:
                    break
                size = int.from_bytes(block[1:], "big")
                if block[0] & 127 == 6:
                    return int.from_bytes(stream.read(4), "big")
                stream.seek(size, 1)
                if block[0] & 128:
                    break
        elif header[:4] == b"ID3\x03":
            size = sum(value << shift for value, shift in zip(header[6:10], (21, 14, 7, 0)))
            end = 10 + size
            while stream.tell() + 10 <= end:
                frame = stream.read(10)
                length = int.from_bytes(frame[4:8], "big")
                if not length or stream.tell() + length > end:
                    break
                if frame[:4] == b"APIC":
                    payload = stream.read(length)
                    mime_end = payload.find(b"\0", 1)
                    if mime_end >= 1 and mime_end + 1 < len(payload):
                        return payload[mime_end + 1]
                    break
                stream.seek(length, 1)
    raise OCFError(f"{path.name}: native front-cover picture was not found")


def _edition(report: dict, report_path: Path, version: str | None, edition: Path | None):
    origin = "explicit-audition-edition"
    existing = read_json_object(edition) if edition else None
    if existing is not None:
        errors = validate_against_schema(existing, _load_schema("audition-edition.schema.json"))
        if errors:
            raise OCFError("invalid audition edition record: " + " | ".join(errors))
    authoritative = existing["version"] if existing else report.get("audition_version")
    if existing:
        origin = "audition-edition-record"
    elif authoritative:
        origin = "render-audition-version"
    elif report.get("audio_implementation_id"):
        registered = find_audio_manifest(report["audio_implementation_id"])
        if registered and registered.get("function_id") == report["function_id"]:
            authoritative = registered.get("version")
            origin = "registered-audio-implementation"
    if authoritative and version and authoritative != version:
        raise OCFError(
            "requested edition version conflicts with authoritative audio/session version"
        )
    selected = authoritative or version
    if not selected:
        raise OCFError(
            "missing audio/session edition version; supply --edition-version X.Y.Z for a new "
            "private audition edition or --edition FILE; narration/template/brand versions are not editions"
        )
    record = {
        "schema_version": "1.0",
        "kind": "private-audition",
        "function_id": report["function_id"],
        "locale": report["requested_locale"],
        "version": selected,
        "voice_profile_id": report["voice_profile"]["id"],
        "master_sha256": report["artifacts"]["wav"]["sha256"],
        "session_report_sha256": sha256_of_file(report_path),
        "publication_approval": False,
        "human_listening_approval": None,
    }
    if report.get("background_variant"):
        record["background_variant"] = report["background_variant"]
    errors = validate_against_schema(record, _load_schema("audition-edition.schema.json"))
    if errors:
        raise OCFError("invalid audition edition: " + " | ".join(errors))
    if existing != record and existing is not None:
        raise OCFError(
            "audition edition belongs to different audio, voice, locale or session report"
        )
    return record, origin


def select_cover(
    function_id,
    locale,
    version,
    *,
    artwork_file=None,
    artwork_theme=None,
    no_artwork=False,
    artwork_resolution=1400,
    dry_run=False,
    show_cue=True,
    show_description=True,
):
    """Common render/export cover policy; approval never suppresses artwork."""
    if no_artwork:
        if artwork_file or artwork_theme:
            raise OCFError("--no-artwork cannot be combined with artwork/theme overrides")
        return None, {"source": "disabled-explicitly", "publication_approval": False}, None
    if artwork_file:
        path = Path(artwork_file).expanduser().resolve()
        mime, width, height = _image_info(path)
        if width != height or width < 320:
            raise OCFError("private cover must be square and at least 320 pixels")
        return (
            path,
            {
                "source": "explicit-user-cover",
                "mime": mime,
                "version_visibility": "operator-supplied",
                "publication_approval": False,
            },
            None,
        )
    record = load_function_by_id(function_id)
    theme, theme_source = artwork.select_theme(record, artwork_theme)
    generated = artwork.generate_cover(
        function_id,
        locale=locale,
        theme=theme,
        resolution=artwork_resolution,
        version=version,
        status_label="BETA / PRIVATE",
        dry_run=dry_run,
        show_cue=show_cue,
        show_description=show_description,
    )
    return (
        Path(generated["path"]),
        {
            "source": "generated-ocf",
            "theme_selection": theme_source,
            "theme_id": generated["settings"]["theme"]["id"],
            "brand_version": generated["settings"]["brand"]["version"],
            "fingerprint": generated["fingerprint"],
            "review_status": "candidate",
            "version_label": "v" + version,
            "status_label": "BETA / PRIVATE",
            "publication_approval": False,
        },
        generated,
    )


def copy_cover(source: Path, destination: Path) -> None:
    if destination.exists():
        raise OCFError("refusing to overwrite existing cover")
    mime, width, height = _image_info(source)
    if mime == "image/png":
        shutil.copyfile(source, destination)
    else:
        from PIL import Image

        with Image.open(source, formats=("JPEG",)) as image:
            if image.size != (width, height):
                raise OCFError(
                    "cover dimensions changed between header inspection and JPEG decoding"
                )
            image.convert("RGB").save(destination, format="PNG")


def attach_render_artwork(
    report: dict, stage: Path, *, version="0.1.0", artwork_file=None, artwork_theme=None
) -> None:
    """New private session renders always retain a companion cover, including WAV-only."""
    # This initializes an explicitly private edition, not a production release version.
    from jsonschema import Draft7Validator

    errors = list(
        Draft7Validator(
            _load_schema("audition-edition.schema.json")["properties"]["version"]
        ).iter_errors(version)
    )
    if errors:
        raise OCFError("invalid private audition edition version")
    path, provenance, generated = select_cover(
        report["function_id"],
        report.get("requested_locale") or report["locale"],
        version,
        artwork_file=artwork_file,
        artwork_theme=artwork_theme,
    )
    target = stage / "cover.png"
    copy_cover(path, target)
    report["audition_version"] = version
    report["artwork_provenance"] = provenance
    report["artifacts"]["cover"] = {**_artifact(target), "format": "image/png"}
    if generated:
        write_text_atomic(
            stage / "artwork-report.json",
            json.dumps(generated, ensure_ascii=False, indent=2) + "\n",
        )
        report["artifacts"]["artwork_report"] = {
            **_artifact(stage / "artwork-report.json"),
            "format": "application/json",
        }


def _verify_export_identity(previous: dict, record: dict) -> str:
    """Validate portable edition/provenance identity without reading or decoding audio."""
    errors = validate_against_schema(record, _load_schema("audition-edition.schema.json"))
    if errors:
        raise OCFError("invalid retained audition edition: " + " | ".join(errors))
    if (
        record != previous.get("edition")
        or record["function_id"] != previous.get("function_id")
        or record["locale"] != previous.get("locale")
        or record["version"] != previous.get("version")
        or record["master_sha256"] != previous.get("source_master", {}).get("sha256")
        or record["session_report_sha256"] != previous.get("source_report", {}).get("sha256")
    ):
        raise OCFError("retained export edition/source identity does not match")
    items = previous.get("artifacts", {})
    if not all(fmt in items for fmt in ("flac", "mp3")):
        raise OCFError("retained export requires verified FLAC and MP3 sources")
    for fmt in ("flac", "mp3"):
        item = items[fmt]
        pcm_valid = isinstance(item.get("pcm_sha256"), str) and len(item["pcm_sha256"]) == 64
        packet = item.get("packet_sha256")
        packet_valid = isinstance(packet, str) and len(packet) == 64
        # Older encode-from-master receipts recorded decoded PCM and the exact
        # encoded file checksum, but not a separate packet digest. That verified
        # file checksum still binds every packet; compute the digest on read.
        legacy_encoded = packet is None and item.get("operation") == "encode-from-master"
        if not pcm_valid or not (packet_valid or legacy_encoded):
            raise OCFError("retained export requires packet and PCM checksum evidence")
        tags = item.get("tags", {})
        if (
            tags.get("ocf_function_id") != record["function_id"]
            or tags.get("ocf_locale") != record["locale"]
            or tags.get("ocf_voice_profile") != record["voice_profile_id"]
            or tags.get("ocf_audio_version") != record["version"]
        ):
            raise OCFError("retained export tags do not match its edition")
    narrator = items["flac"]["tags"].get("ocf_narrator")
    if not narrator or narrator != items["mp3"]["tags"].get("ocf_narrator"):
        raise OCFError("retained export narrator identity is missing/inconsistent")
    return narrator


def _retained_export(source: Path, version: str | None, edition: str | Path | None) -> dict:
    """Open verified listening copies without inventing a missing session report/WAV."""
    previous = read_json_object(source / "manifest.json")
    if previous.get("kind") != "private-audition-export":
        raise OCFError("source must be a completed session or a verified private audition export")
    record = read_json_object(Path(edition) if edition else source / "audition-edition.json")
    narrator = _verify_export_identity(previous, record)
    if version and version != record["version"]:
        raise OCFError("requested edition version conflicts with retained export")
    inputs = {fmt: _source_artifact(source, previous["artifacts"][fmt]) for fmt in ("flac", "mp3")}
    return {"document": previous, "edition": record, "inputs": inputs, "narrator": narrator}


def export_audition(
    source: str | Path,
    *,
    edition_version: str | None = None,
    edition: str | Path | None = None,
    flac_source: str | Path | None = None,
    mp3_source: str | Path | None = None,
    artwork_file: str | Path | None = None,
    artwork_theme: str | None = None,
    no_artwork: bool = False,
    artwork_resolution: int = 1400,
    output: str | Path | None = None,
    dry_run: bool = False,
    show_cue: bool = True,
    show_description: bool = True,
    lyrics: bool = False,
    guides: str | Path | None = None,
) -> dict:
    """Export a completed session privately, reusing existing compressed audio when supplied."""
    if no_artwork and (artwork_file or artwork_theme):
        raise OCFError("--no-artwork cannot be combined with artwork/theme overrides")
    source = Path(source).expanduser().resolve()
    report_path = source / "session-report.json"
    retained = None
    if report_path.is_file():
        report = read_json_object(report_path)
        if report.get("render_type") != "complete-session-audition":
            raise OCFError("export requires a completed complete-session audition report")
        artifacts = report.get("artifacts", {})
        if "wav" not in artifacts:
            raise OCFError("complete-session report has no master WAV")
        originals = {key: _source_artifact(source, item) for key, item in artifacts.items()}
        master = originals["wav"]
        edition_record, version_source = _edition(
            report, report_path, edition_version, Path(edition) if edition else None
        )
        narrator = report.get("voice_profile", {}).get("name")
        inputs = {
            "flac": Path(flac_source).resolve() if flac_source else master,
            "mp3": Path(mp3_source).resolve() if mp3_source else master,
        }
    else:
        retained = _retained_export(source, edition_version, edition)
        report_path = source / "manifest.json"
        report, edition_record, inputs, narrator = (
            retained[key] for key in ("document", "edition", "inputs", "narrator")
        )
        artifacts = dict(report["artifacts"])
        if report.get("cover"):
            artifacts["cover"] = report["cover"]
        for fmt, supplied in (("flac", flac_source), ("mp3", mp3_source)):
            if supplied and Path(supplied).resolve() != inputs[fmt].resolve():
                raise OCFError("retained export source overrides must use its verified artifacts")
        master = None
        version_source = "verified-private-export-edition"
    document_sha256 = sha256_of_file(report_path)
    if lyrics:
        from .listener_text import measured_document

        if retained:
            raise OCFError(
                "lyrics require the original measured session report, not a retained export"
            )
        measured_document(report, float(report.get("measurements", {}).get("duration_seconds", 0)))
    version = edition_record["version"]
    function_id, locale = edition_record["function_id"], edition_record["locale"]
    title, title_resolution = _function_title(function_id, locale, LocaleCatalog())
    if not narrator:
        raise OCFError("completed report must declare its narrator/voice display name")
    final = (
        Path(output).expanduser().resolve()
        if output
        else work_path("renders", "listening-exports", unique_run_id(function_id + "-v" + version))
    )
    if not final.is_relative_to(work_root().resolve()):
        raise OCFError("private audition exports must remain inside the OCF workspace")
    if final.exists():
        raise OCFError("refusing to overwrite an existing private audition export")
    probes = {fmt: _probe(path) for fmt, path in inputs.items()}
    master_info = _probe(master or inputs["flac"])
    if master_info["channels"] != 2:
        raise OCFError("complete-session listening master must retain stereo")
    for fmt, info in probes.items():
        expected = fmt if inputs[fmt] != master else master_info["codec"]
        if (
            info["codec"] != expected
            or any(info[key] != master_info[key] for key in ("channels", "sample_rate"))
            or abs(info["duration_seconds"] - master_info["duration_seconds"]) > 0.1
        ):
            raise OCFError(
                f"{fmt} source codec, stereo format or duration differs from session master"
            )
    if master is not None and not master_info["codec"].startswith("pcm_"):
        raise OCFError("session master must be PCM")
    tags = {
        "title": title,
        "album": title,
        "artist": narrator,
        "album_artist": "Open Consciousness Functions",
        "language": locale,
        "OCF_FUNCTION_ID": function_id,
        "OCF_LOCALE": locale,
        "OCF_NARRATOR": narrator,
        "OCF_VOICE_PROFILE": edition_record["voice_profile_id"],
        "OCF_AUDIO_VERSION": version,
        "OCF_AUDITION_VERSION": version,
        "OCF_VERSION_LABEL": "v" + version,
        "OCF_EDITION_KIND": "private-audition",
    }
    if edition_record.get("background_variant"):
        tags["OCF_BACKGROUND_VARIANT"] = edition_record["background_variant"]
    from .artwork_content import content_tags, function_artwork_content

    function_content = function_artwork_content(function_id, locale)
    tags.update(content_tags(function_content))
    cover_path, provenance, generated = select_cover(
        function_id,
        locale,
        version,
        artwork_file=artwork_file,
        artwork_theme=artwork_theme,
        no_artwork=no_artwork,
        artwork_resolution=artwork_resolution,
        dry_run=dry_run,
        show_cue=show_cue,
        show_description=show_description,
    )
    namer = ArtifactNamer()
    all_names = namer.filenames(
        function_id,
        title,
        locale,
        ["flac", "mp3", *(["txt", "lrc", "srt", "vtt", "timing.json"] if lyrics else [])],
        variant=narrator,
        version=version,
    )
    names = {fmt: all_names[fmt] for fmt in ("flac", "mp3")}
    if dry_run:
        return {
            "dry_run": True,
            "output_directory": str(final),
            "edition": edition_record,
            "artwork": provenance,
            "tags": tags,
            "files": names,
            "lyrics": lyrics,
            "include_guides": guides is not None,
            "audio_operations": {
                fmt: "stream-copy" if path != master else "encode-from-master"
                for fmt, path in inputs.items()
            },
        }
    master_hash = (
        audio_hash(master) if master is not None else report["artifacts"]["flac"]["pcm_sha256"]
    )
    input_checks = {
        fmt: {
            "file": _artifact(path),
            "pcm_sha256": audio_hash(path),
            "packet_sha256": audio_hash(path, packets=True) if path != master else None,
        }
        for fmt, path in inputs.items()
    }
    if input_checks["flac"]["pcm_sha256"] != master_hash:
        raise OCFError("FLAC input is not PCM-identical to the session master")
    if retained and any(
        report["artifacts"][fmt].get(key) is not None
        and input_checks[fmt][key] != report["artifacts"][fmt][key]
        for fmt in inputs
        for key in ("pcm_sha256", "packet_sha256")
    ):
        raise OCFError("retained export audio differs from its verified checksum evidence")
    stage = workspace_temp_directory(prefix="ocf-audition-export-")
    try:
        guide_artifacts = []
        if guides is not None:
            from .listener_packages import attach_guides

            guide_artifacts = attach_guides(
                stage,
                [function_id],
                source=Path(guides),
                locale=locale,
                edition_files={
                    function_id: [
                        {"path": name, "label": Path(name).suffix}
                        for name in [
                            *names.values(),
                            "manifest.json",
                            *(
                                [all_names[f] for f in ("txt", "lrc", "srt", "vtt", "timing.json")]
                                if lyrics
                                else []
                            ),
                            *(["cover.png"] if cover_path else []),
                        ]
                    ]
                },
            )
        if cover_path:
            # Normalize only custom JPEG imagery to the requested separate cover.png.
            # Generated PNG bytes stay exact, including their embedded copies.
            target = stage / "cover.png"
            copy_cover(cover_path, target)
            cover_path = target
        verified = {}
        listener_text = None
        if lyrics:
            from .listener_text import write_listener_text

            listener_text = write_listener_text(
                report, master_info["duration_seconds"], stage / names["mp3"]
            )
        for fmt, path in inputs.items():
            target = stage / names[fmt]
            audio_build._encode(
                path, fmt, target, tags, cover_path, copy_audio=path != master, mp3_bitrate="320k"
            )
            if lyrics:
                from .listener_text import embed_listener_text

                embed_listener_text(target, report, master_info["duration_seconds"], locale)
            info = _verify_audio(
                target, function_id=function_id, title=title, artwork=cover_path, expected_tags=tags
            )
            if (
                info["channels"] != 2
                or info["sample_rate"] != master_info["sample_rate"]
                or abs(info["duration_seconds"] - probes[fmt]["duration_seconds"]) > 0.1
            ):
                raise OCFError("export changed stereo format or duration")
            pcm = audio_hash(target)
            packets = audio_hash(target, packets=True)
            if path != master and (
                pcm != input_checks[fmt]["pcm_sha256"]
                or packets != input_checks[fmt]["packet_sha256"]
            ):
                raise OCFError(f"{fmt} stream-copy changed audio packets or decoded PCM")
            if fmt == "flac" and pcm != master_hash:
                raise OCFError("exported FLAC PCM differs from master")
            if cover_path and front_cover_type(target) != 3:
                raise OCFError("embedded picture is not a native front cover")
            preserved = {
                k: v
                for k, v in probes[fmt]["tags"].items()
                if k not in {key.lower() for key in tags} and k != "encoder"
            }
            if any(info["tags"].get(k) != v for k, v in preserved.items()):
                raise OCFError("existing valid metadata was not preserved")
            verified[fmt] = {
                **_artifact(target),
                **info,
                "pcm_sha256": pcm,
                "packet_sha256": packets,
                "operation": "stream-copy" if path != master else "encode-from-master",
                "embedded_cover_verified": cover_path is not None,
            }
        for key, item in artifacts.items():
            _source_artifact(source, item)
        if sha256_of_file(report_path) != document_sha256:
            raise OCFError("source narration/render report changed during export")
        for fmt, path in inputs.items():
            if sha256_of_file(path) != input_checks[fmt]["file"]["sha256"]:
                raise OCFError("original compressed audition changed during export")
        manifest = {
            "schema_version": "1.0",
            "kind": "private-audition-export",
            "function_id": function_id,
            "locale": locale,
            "title": title,
            "title_resolution": title_resolution,
            "version": version,
            "version_label": "v" + version,
            "version_source": version_source,
            "edition": edition_record,
            "publication_approval": False,
            "human_listening_approval": None,
            "source_report": report["source_report"] if retained else _artifact(report_path),
            "source_master": report["source_master"] if retained else _artifact(master),
            "source_mode": "verified-private-export" if retained else "completed-session",
            "predecessor_export_manifest": _artifact(report_path) if retained else None,
            "original_master_verified_this_export": master is not None,
            "master_pcm_verification": "verified predecessor FLAC evidence"
            if retained
            else "direct master PCM",
            "source_exports": input_checks,
            "artwork": provenance,
            "artifacts": verified,
            "cover": _artifact(cover_path) if cover_path else None,
            "source_artifacts_unchanged": True,
            "function_content": function_content,
            "cover_options": {"show_cue": show_cue, "show_description": show_description},
            "listener_text": listener_text,
            "guides": guide_artifacts,
        }
        write_text_atomic(
            stage / "audition-edition.json", json.dumps(edition_record, indent=2) + "\n"
        )
        if generated:
            write_text_atomic(
                stage / "artwork-report.json",
                json.dumps(generated, ensure_ascii=False, indent=2) + "\n",
            )
        write_text_atomic(
            stage / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        )
        final.parent.mkdir(parents=True, exist_ok=True)
        if final.exists():
            raise OCFError("audition export appeared during verification; refusing to overwrite")
        publish_workspace_temp_directory(stage, final)
        return {"dry_run": False, "output_directory": str(final), "manifest": manifest}
    except BaseException as exc:
        record_workspace_failure(stage.name, f"audition export failed; retained {stage}: {exc}")
        raise
