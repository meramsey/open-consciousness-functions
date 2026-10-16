"""Build and atomically publish self-contained localized audio releases."""

from __future__ import annotations

import json
import os
import re
import shutil
import struct
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any

from .artifact_names import ArtifactNamer, safe_component
from .indexes import find_audio_manifest, load_audio_manifests, load_function_by_id
from .locale import LocaleCatalog, normalize_tag
from .paths import (
    REPO_ROOT,
    SCHEMAS_DIR,
    publish_workspace_temp_directory,
    record_workspace_failure,
    workspace_run,
    workspace_temp_directory,
)
from .utils import OCFError, sha256_of_file

MAX_ARTWORK_BYTES = 20 * 1024 * 1024
MAX_ARTWORK_DIMENSION = 12000


def _image_info(path: Path) -> tuple[str, int, int]:
    """Validate and return MIME type and dimensions for PNG/JPEG artwork."""
    if not path.is_file():
        raise OCFError(f"artwork file does not exist: {path}")
    size = path.stat().st_size
    if size <= 0 or size > MAX_ARTWORK_BYTES:
        raise OCFError(f"artwork must be non-empty and at most {MAX_ARTWORK_BYTES} bytes")
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24 and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        mime = "image/png"
    elif data.startswith(b"\xff\xd8"):
        width, height = _jpeg_dimensions(data)
        mime = "image/jpeg"
    else:
        raise OCFError("artwork must be a valid PNG or JPEG image")
    if not width or not height or max(width, height) > MAX_ARTWORK_DIMENSION:
        raise OCFError(f"artwork dimensions must be between 1 and {MAX_ARTWORK_DIMENSION} pixels")
    return mime, width, height


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    offset = 2
    sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset < len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(data):
            break
        length = int.from_bytes(data[offset : offset + 2], "big")
        if length < 2 or offset + length > len(data):
            break
        if marker in sof_markers and length >= 7:
            return int.from_bytes(data[offset + 5 : offset + 7], "big"), int.from_bytes(
                data[offset + 3 : offset + 5], "big"
            )
        offset += length
    raise OCFError("invalid JPEG artwork: dimensions were not found")


def _function_title(
    function_id: str, locale: str, catalog: LocaleCatalog
) -> tuple[str, dict[str, Any]]:
    record = load_function_by_id(function_id)
    if record is None:
        raise OCFError(f"unknown function {function_id}")
    key = record.documentation.get("title_key")
    if key:
        try:
            entry, resolution = catalog.resource(key, locale, domain="ui", fallback=True)
            title = entry.render(
                {}, plural_rules=catalog.plural_rules_for(resolution.origin_locale)
            )
            return title, {
                "requested_locale": resolution.locale,
                "resolved_locale": resolution.origin_locale,
                "fallback": resolution.fallback,
                "resource_key": key,
            }
        except OCFError as exc:
            raise OCFError(f"cannot resolve localized title {key!r} for {locale}: {exc}") from exc
    return record.canonical_name, {
        "requested_locale": locale,
        "resolved_locale": "canonical-record",
        "fallback": True,
        "resource_key": None,
    }


def _select_audio_manifest(query: str) -> dict[str, Any]:
    direct = find_audio_manifest(query)
    if direct is not None:
        return direct
    matches = [item for item in load_audio_manifests() if item.get("function_id") == query]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise OCFError(f"no audio implementation is registered for {query!r}")
    ids = ", ".join(str(item.get("id")) for item in matches)
    raise OCFError(f"multiple audio implementations exist for {query!r}: {ids}; select an audio ID")


def _ffmpeg() -> str:
    value = shutil.which("ffmpeg")
    if not value:
        raise OCFError("ffmpeg is required to encode and verify release MP3/FLAC; install ffmpeg")
    return value


def _verify_audio(
    path: Path,
    *,
    function_id: str,
    title: str,
    artwork: Path,
    expected_tags: dict[str, str] | None = None,
) -> dict[str, Any]:
    ffmpeg = _ffmpeg()
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise OCFError("ffprobe is required to verify release metadata and embedded artwork")
    decode = workspace_run(
        [ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    if decode.returncode:
        raise OCFError(f"audio decode verification failed for {path.name}: {decode.stderr[-400:]}")
    probe = workspace_run(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    if probe.returncode:
        raise OCFError(f"metadata read-back failed for {path.name}: {probe.stderr[-400:]}")
    try:
        info = json.loads(probe.stdout)
    except json.JSONDecodeError as exc:
        raise OCFError(f"invalid ffprobe response for {path.name}") from exc
    tags = {str(k).lower(): str(v) for k, v in (info.get("format", {}).get("tags") or {}).items()}
    required = {"title": title, "album": title, "ocf_function_id": function_id}
    required.update({str(key).lower(): str(value) for key, value in (expected_tags or {}).items()})
    for key, value in required.items():
        if tags.get(key) != value:
            raise OCFError(f"{path.name}: metadata read-back mismatch for {key}")
    picture_stream = next(
        (
            stream
            for stream in info.get("streams", [])
            if stream.get("codec_type") == "video"
            and stream.get("disposition", {}).get("attached_pic") == 1
        ),
        None,
    )
    if picture_stream is None:
        raise OCFError(f"{path.name}: embedded cover artwork was not found")
    extracted = path.with_name(f".{path.stem}.cover{artwork.suffix}")
    try:
        result = workspace_run(
            [
                ffmpeg,
                "-v",
                "error",
                "-y",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-c",
                "copy",
                str(extracted),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode or not extracted.is_file():
            raise OCFError(f"{path.name}: could not extract embedded artwork")
        if sha256_of_file(extracted) != sha256_of_file(artwork):
            raise OCFError(f"{path.name}: embedded artwork does not match release cover")
    finally:
        extracted.unlink(missing_ok=True)
    audio_stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    return {
        "codec": audio_stream.get("codec_name"),
        "sample_rate": int(audio_stream.get("sample_rate") or 0),
        "channels": int(audio_stream.get("channels") or 0),
        "duration_seconds": float(info.get("format", {}).get("duration") or 0),
        "bit_rate": int(info.get("format", {}).get("bit_rate") or 0) or None,
        "tags": tags,
    }


def _manifest_schema() -> dict[str, Any]:
    with (SCHEMAS_DIR / "audio-release.schema.json").open(encoding="utf-8") as stream:
        return json.load(stream)


def _validate_manifest(manifest: dict[str, Any]) -> None:
    from jsonschema import Draft202012Validator

    errors = list(Draft202012Validator(_manifest_schema()).iter_errors(manifest))
    if errors:
        raise OCFError(
            "release manifest validation failed: " + "; ".join(e.message for e in errors)
        )


def transcript_from_render(render_doc: dict[str, Any]) -> str:
    """Export exactly the post-transform utterances submitted to synthesis."""
    cues = render_doc.get("narration_timing", {}).get("cues", [])
    ordered = sorted(
        cues,
        key=lambda cue: (float(cue.get("at", 0)), str(cue.get("id", ""))),
    )
    lines: list[str] = []
    for cue in ordered:
        if "spoken_text" not in cue:
            raise OCFError(
                f"render cue {cue.get('id', '?')!r} has no final spoken_text; rebuild with current OCF"
            )
        text = str(cue["spoken_text"]).strip()
        if text:
            lines.append(text)
    return "\n\n".join(lines).rstrip() + "\n"


def artwork_selection(query: str, explicit_theme: str | None = None):
    """Shared registered-implementation/function theme lookup; never renders."""
    from .artwork import select_theme

    manifest = _select_audio_manifest(query)
    function_id = str(manifest.get("function_id") or "")
    if not function_id:
        raise OCFError(f"audio implementation {manifest.get('id')} has no function_id")
    record = load_function_by_id(function_id)
    if record is None:
        raise OCFError(f"audio implementation references unknown function {function_id}")
    reference, source = select_theme(record, explicit_theme, manifest)
    return manifest, record, reference, source


def package_release(
    query: str,
    *,
    locale: str | None = None,
    formats: list[str] | None = None,
    voice: str | None = None,
    artwork: str | Path | None = None,
    artwork_theme: str | None = None,
    artwork_resolution: int = 1400,
    output: str | Path | None = None,
    version: str | None = None,
    metadata_overrides: dict[str, str] | None = None,
    dry_run: bool = False,
    overwrite: bool = False,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Render, verify, and publish one complete function release directory."""
    from . import audio_build
    from .indexes import load_yaml_file

    overrides = metadata_overrides or {}
    permitted_overrides = {
        "title",
        "album",
        "artist",
        "album_artist",
        "date",
        "track",
        "language",
        "comment",
        "publisher",
        "copyright",
        "label",
    }
    unknown_overrides = set(overrides) - permitted_overrides
    if unknown_overrides:
        raise OCFError(
            "unsupported release metadata override(s): " + ", ".join(sorted(unknown_overrides))
        )
    for key, value in overrides.items():
        normalized = str(value).strip()
        if any(ord(char) < 32 for char in normalized):
            raise OCFError(f"metadata override {key!r} contains control characters")
        if (
            normalized.startswith(("\\\\", "//"))
            or Path(normalized).is_absolute()
            or (len(normalized) >= 3 and normalized[1:3] in {":\\", ":/"})
        ):
            raise OCFError(f"metadata override {key!r} must not contain an absolute path")

    formats = list(dict.fromkeys(formats or ["flac", "mp3"]))
    if not formats or any(fmt not in {"flac", "mp3"} for fmt in formats):
        raise OCFError("release formats must contain one or more of: mp3, flac")
    audio_manifest, record, selected_theme, theme_source = artwork_selection(query, artwork_theme)
    function_id = record.id
    if artwork is None and selected_theme is None:
        raise OCFError(
            "release artwork is required; pass an explicitly approved --artwork image or select an artwork theme"
        )
    if artwork is None:
        from .artwork import generate_cover

        generated = generate_cover(
            function_id,
            locale=locale or "en-US",
            theme=selected_theme,
            resolution=artwork_resolution,
            version=version,
            title_override=overrides.get("title"),
            dry_run=dry_run,
        )
        artwork_path = Path(generated["path"])
        mime, width, height = (
            ("image/png", artwork_resolution, artwork_resolution)
            if dry_run
            else _image_info(artwork_path)
        )
        artwork_provenance = {
            "source": "generated-ocf",
            "brand_id": generated["settings"]["brand"]["id"],
            "brand_version": generated["settings"]["brand"]["version"],
            "theme_id": generated["settings"]["theme"]["id"],
            "theme_selection": theme_source,
            "fingerprint": generated["fingerprint"],
            "review_status": "candidate",
            "publication_approval": False,
        }
    else:
        artwork_path = Path(artwork).expanduser().resolve()
        mime, width, height = _image_info(artwork_path)
        artwork_provenance = {
            "source": "explicit-user-cover",
            "sha256": sha256_of_file(artwork_path),
            "publication_approval": False,
        }
    catalog = LocaleCatalog()
    requested_locale = normalize_tag(locale) if locale else catalog.canonical_locale
    if not requested_locale:
        raise OCFError(f"invalid locale: {locale!r}")
    title, title_provenance = _function_title(function_id, requested_locale, catalog)
    title = str(overrides.get("title", title))
    if "title" in overrides:
        title_provenance = {
            "requested_locale": requested_locale,
            "resolved_locale": "operator-supplied",
            "fallback": False,
            "resource_key": None,
            "source": "operator-title-override",
        }
    release_version = version or str(
        audio_manifest.get("version") or record.data.get("version", {}).get("current") or "1.0.0"
    )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}", release_version):
        raise OCFError(
            "release version must use only letters, digits, dot, underscore, plus, or hyphen"
        )
    namer = ArtifactNamer()
    artifact_names = {
        fmt: namer.filename(
            function_id, title, requested_locale, fmt, variant=voice, version=version
        )
        for fmt in formats
    }
    transcript_name = namer.filename(function_id, title, requested_locale, "txt", version=version)
    expected_suffix = ".png" if mime == "image/png" else ".jpg"
    if artwork_path.suffix.lower() not in ({".png"} if mime == "image/png" else {".jpg", ".jpeg"}):
        raise OCFError("artwork filename extension does not match its image format")
    cover_name = f"cover{expected_suffix}"
    output_root = Path(output or REPO_ROOT / "releases").expanduser().resolve()
    directory_name = f"{function_id}-{safe_component(title, max_length=64)}"
    if voice:
        directory_name += f"-{safe_component(voice, max_length=32)}"
    if version:
        directory_name += f"-v{safe_component(version, max_length=24)}"
    final_dir = output_root / requested_locale / directory_name
    if any(
        len(str(final_dir / name)) > 240
        for name in [*artifact_names.values(), transcript_name, cover_name, "manifest.json"]
    ):
        raise OCFError(
            "release output path would exceed the portable 240-character path limit; choose a shorter output root or title"
        )
    planned = {
        "release_directory": str(final_dir),
        "artifacts": [*artifact_names.values(), transcript_name, cover_name, "manifest.json"],
    }
    if dry_run:
        return {
            "dry_run": True,
            **planned,
            "title_resolution": title_provenance,
            "artwork_provenance": artwork_provenance,
        }
    if final_dir.exists() and not overwrite:
        raise OCFError(f"release already exists: {final_dir} (use --force to replace it)")

    try:
        final_dir.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OCFError(f"cannot create release output directory {final_dir.parent}: {exc}") from exc
    if not overwrite:
        collision = next(
            (
                child
                for child in final_dir.parent.iterdir()
                if child.name.casefold() == final_dir.name.casefold()
            ),
            None,
        )
        if collision is not None:
            raise OCFError(
                f"release path collides case-insensitively with existing directory: {collision}"
            )
    try:
        stage = workspace_temp_directory(prefix="ocf-release-stage-")
    except OSError as exc:
        raise OCFError(
            f"cannot create release staging directory in {final_dir.parent}: {exc}"
        ) from exc
    backup: Path | None = None
    try:
        render_dir = stage / "render"
        tag_values = {
            "title": title,
            "album": title,
            "artist": overrides.get("artist")
            or audio_manifest.get("narrator")
            or "Open Consciousness Functions",
            "album_artist": overrides.get("album_artist") or "Open Consciousness Functions",
            "language": requested_locale,
            "OCF_FUNCTION_ID": function_id,
            "OCF_RELEASE_VERSION": release_version,
            **overrides,
        }
        built = audio_build.build(
            str(audio_manifest["id"]),
            out_root=render_dir,
            formats=formats,
            tag_overrides=tag_values,
            voice=voice,
            locale=requested_locale,
            strict=True,
            overwrite=True,
            artwork=artwork_path,
        )
        stage_artifacts: dict[str, dict[str, Any]] = {}
        audio_info: dict[str, dict[str, Any]] = {}
        for fmt in formats:
            source = render_dir / f"{audio_manifest['id']}-master.{fmt}"
            if not source.is_file():
                raise OCFError(f"requested {fmt} output was not rendered")
            destination = stage / artifact_names[fmt]
            shutil.copy2(source, destination)
            audio_info[fmt] = _verify_audio(
                destination,
                function_id=function_id,
                title=title,
                artwork=artwork_path,
                expected_tags=tag_values,
            )
            expected_codec = "mp3" if fmt == "mp3" else "flac"
            if audio_info[fmt]["codec"] != expected_codec:
                raise OCFError(
                    f"requested {fmt} artifact has unexpected codec {audio_info[fmt]['codec']!r}"
                )
            stage_artifacts[fmt] = {
                "path": destination.name,
                "format": fmt,
                "size_bytes": destination.stat().st_size,
                "sha256": sha256_of_file(destination),
                **{key: value for key, value in audio_info[fmt].items() if key != "tags"},
            }

        render_manifest_path = (
            render_dir / f"OCF-RENDER-{str(audio_manifest['id']).split('-')[-1]}.yaml"
        )
        render_doc = load_yaml_file(render_manifest_path)
        transcript_text = transcript_from_render(render_doc)
        transcript_path = stage / transcript_name
        transcript_path.write_text(transcript_text, encoding="utf-8", newline="\n")
        cover_path = stage / cover_name
        shutil.copy2(artwork_path, cover_path)
        _image_info(cover_path)

        created = created_at or datetime.now(UTC)
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        source_reference = str(audio_manifest.get("transcript_path") or "")
        source_windows = PureWindowsPath(source_reference)
        if (
            Path(source_reference).is_absolute()
            or source_windows.is_absolute()
            or source_windows.drive
            or ".." in Path(source_reference).parts
            or ".." in source_windows.parts
        ):
            raise OCFError("audio manifest transcript_path must be a safe repository-relative path")
        manifest = {
            "schema_version": "1.0",
            "function_id": function_id,
            "audio_id": str(audio_manifest["id"]),
            "title": title,
            "requested_locale": requested_locale,
            "title_resolution": title_provenance,
            "release_version": release_version,
            "artwork_provenance": artwork_provenance,
            "voice_profile_id": built.get("voice", {}).get("profile_id")
            or voice
            or audio_manifest.get("voice_profile"),
            "narrator": overrides.get("artist") or audio_manifest.get("narrator"),
            "source_narration": str(audio_manifest.get("transcript_path") or ""),
            "narration_resolution": render_doc.get("narration_resolution"),
            "rendering": {
                "backend": built.get("voice", {}).get("backend"),
                "locale": built.get("voice", {}).get("locale"),
                "voice_options": built.get("voice", {}).get("options", {}),
                "sample_rate": built.get("master", {}).get("sample_rate"),
                "channels": built.get("master", {}).get("channels"),
                "timing_mode": built.get("timing_mode"),
                "background": built.get("background"),
                "narration_gain_windows": built.get("narration_gain_windows", []),
            },
            "created_at": created.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "artifacts": [
                *[stage_artifacts[fmt] for fmt in formats],
                {
                    "path": transcript_name,
                    "format": "text/plain; charset=utf-8",
                    "size_bytes": transcript_path.stat().st_size,
                    "sha256": sha256_of_file(transcript_path),
                },
                {
                    "path": cover_name,
                    "format": mime,
                    "width": width,
                    "height": height,
                    "size_bytes": cover_path.stat().st_size,
                    "sha256": sha256_of_file(cover_path),
                },
            ],
        }
        _validate_manifest(manifest)
        _verify_manifest(stage, manifest)
        if transcript_path.read_bytes().decode(
            "utf-8"
        ) != transcript_text or not transcript_text.endswith("\n"):
            raise OCFError("transcript encoding/content verification failed")
        manifest_path = stage / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _validate_manifest(manifest)
        _verify_manifest(stage, manifest)
        shutil.rmtree(render_dir)
        if final_dir.exists():
            if not overwrite:
                raise OCFError(
                    "release appeared during rendering; refusing to replace it without --force"
                )
            backup = final_dir.with_name(
                f".{final_dir.name}.previous-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{os.getpid()}"
            )
            os.replace(final_dir, backup)
        try:
            publish_workspace_temp_directory(stage, final_dir)
        except BaseException:
            if backup is not None and backup.exists() and not final_dir.exists():
                os.replace(backup, final_dir)
                backup = None
            raise
        return {"dry_run": False, **planned, "manifest": manifest}
    except OSError as exc:
        if stage.exists():
            record_workspace_failure(
                stage.name, f"release filesystem failure: {exc}; retained scratch: {stage}"
            )
        raise OCFError(f"release packaging failed because of a filesystem error: {exc}") from exc
    except BaseException as exc:
        if stage.exists():
            record_workspace_failure(
                stage.name,
                f"release failure: {type(exc).__name__}: {exc}; retained scratch: {stage}",
            )
        raise


def _verify_manifest(root: Path, manifest: dict[str, Any]) -> None:
    _validate_manifest(manifest)
    for artifact in manifest["artifacts"]:
        rel = Path(artifact["path"])
        windows_rel = PureWindowsPath(artifact["path"])
        if (
            rel.is_absolute()
            or windows_rel.is_absolute()
            or windows_rel.drive
            or ".." in rel.parts
            or ".." in windows_rel.parts
        ):
            raise OCFError(f"unsafe relative artifact reference: {rel}")
        path = root / rel
        if not path.resolve().is_relative_to(root.resolve()):
            raise OCFError(f"manifest artifact escapes release directory: {rel}")
        if not path.is_file():
            raise OCFError(f"manifest artifact is missing: {rel}")
        if path.stat().st_size != artifact["size_bytes"]:
            raise OCFError(f"size mismatch for {rel}")
        checksum = artifact.get("sha256")
        if checksum and sha256_of_file(path) != checksum:
            raise OCFError(f"checksum mismatch for {rel}")
