"""Audio build toolchain: mixing, mastering, render manifests, inspection.

Combines the narration stem produced by `.voice` with an optional Farfield
background and writes a master file plus a machine-readable render manifest.

Mixing is performed in pure stdlib PCM math (deterministic, no binary
dependency); FLAC/MP3 encoding delegates to ffmpeg (or the flac CLI) when
requested, and falls back to WAV with a warning when an encoder is missing, so
the toolchain degrades gracefully.
"""

from __future__ import annotations

import io
import json
import math
import shutil
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import __version__ as OCF_VERSION
from . import farfield as farfield_mod
from . import sbagenx as sbagenx_mod
from .indexes import find_audio_manifest, load_background_manifests, load_function_by_id
from .paths import (
    AUDIO_RENDERED_DIR,
    REPO_ROOT,
    cleanup_workspace_temp,
    ensure_dir,
    unique_run_id,
    workspace_run,
    workspace_temp_directory,
)
from .transcript import load_timed_doc
from .utils import (
    OCFError,
    current_date,
    generated_content,
    sha256_of_file,
    write_text_atomic,
    yaml_safe_dump,
)
from .voice import DEFAULT_SAMPLE_RATE, render_narration


def _clip(value: int) -> int:
    return max(-32768, min(32767, value))


def _read_mono_pcm(path: Path, target_rate: int | None = None) -> tuple[int, list[int]]:
    """Read a 16-bit WAV into (rate, mono int16 samples), downmixing stereo."""
    from .voice import _resample

    with wave.open(str(path), "rb") as reader:
        rate = reader.getframerate()
        channels = reader.getnchannels()
        width = reader.getsampwidth()
        frames = reader.readframes(reader.getnframes())
    if width != 2:
        raise OCFError(f"{path.name}: expected 16-bit PCM (got {width * 8}-bit)")
    sample_count = len(frames) // 2
    samples = [
        int.from_bytes(frames[i * 2 : i * 2 + 2], "little", signed=True)
        for i in range(sample_count)
    ]
    if channels == 2:
        samples = [(samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples) - 1, 2)]
    elif channels != 1:
        raise OCFError(f"{path.name}: unsupported channel count {channels}")
    if target_rate is not None:
        samples = _resample(samples, rate, target_rate)
        rate = target_rate
    return rate, samples


def _write_wav(
    path: Path, samples: list[int], sample_rate: int, *, overwrite: bool, channels: int = 1
) -> None:
    if path.exists() and not overwrite:
        raise OCFError(f"Refusing to overwrite existing file: {path} (use --force)")
    ensure_dir(path.parent)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        frames = bytearray()
        for sample in samples:
            frames.extend(int(_clip(sample)).to_bytes(2, "little", signed=True))
        writer.writeframes(bytes(frames))
    path.write_bytes(buffer.getvalue())


def _db_gain_factor(db: float) -> float:
    return 10.0 ** (db / 20.0)


def _narration_gain_windows(
    doc: dict[str, Any], duration: float, event_timing: list[dict] | None = None
) -> list[tuple[float, float, float]]:
    """Return (start, end, gain_db) windows from sections declaring ``gain_db``.

    A section's window runs from its first event to the next section's first
    event (or the track end), so the whole quiet region — including the
    trailing speech of the last attenuated line — is scaled together. Used for
    barely-audible reinforcement (e.g. the twentieth-state sleep wording).
    """
    from .transcript import parse_timestamp

    bounds: list[tuple[float, str]] = []
    actual = {event["id"]: event["at"] for event in event_timing or []}
    for section in doc.get("sections") or []:
        first_at: float | None = None
        for event in section.get("timeline") or []:
            at = actual.get(event.get("id"), event.get("at"))
            if isinstance(at, str):
                at = parse_timestamp(at)
            if at is not None:
                first_at = float(at)
                break
        if first_at is not None:
            bounds.append((first_at, str(section["id"])))
    bounds.sort(key=lambda item: item[0])
    by_id = {str(section["id"]): section for section in doc.get("sections") or []}
    windows: list[tuple[float, float, float]] = []
    for index, (start, section_id) in enumerate(bounds):
        gain_db = by_id.get(section_id, {}).get("gain_db")
        if gain_db is None:
            continue
        end = bounds[index + 1][0] if index + 1 < len(bounds) else float(duration)
        windows.append((start, end, float(gain_db)))
    return windows


def mix(
    speech_path: str | Path,
    background_path: str | Path | None,
    out_path: str | Path,
    *,
    background_gain: float = 0.25,
    speech_gain: float = 1.0,
    speech_gain_windows: list[tuple[float, float, float]] | None = None,
    overwrite: bool = True,
) -> dict[str, Any]:
    """Mix a narration WAV with an optional background WAV (pure stdlib PCM).

    ``speech_gain_windows`` is a list of ``(start_s, end_s, gain_db)`` regions
    in which the narration is scaled independently (barely-audible
    reinforcement). Overlapping windows are not supported.
    """
    target = Path(out_path)
    speech_path = Path(speech_path)
    with wave.open(str(speech_path), "rb") as reader:
        speech_rate, channels = reader.getframerate(), reader.getnchannels()
    if background_path is not None:
        with wave.open(str(background_path), "rb") as reader:
            channels = max(channels, reader.getnchannels())
    if channels not in (1, 2):
        raise OCFError("mixer requires mono/stereo audio")
    from .voice import _source_pcm

    speech_samples = _source_pcm(speech_path.read_bytes(), speech_rate, channels)

    windows: list[tuple[int, int, float]] = []
    for start, end, db in speech_gain_windows or []:
        if end <= start:
            continue
        factor = _db_gain_factor(db)
        windows.append(
            (int(start * speech_rate) * channels, int(end * speech_rate) * channels, factor)
        )
    windows.sort(key=lambda item: item[0])

    length = len(speech_samples)
    bg_mono: list[int] = []
    if background_path is not None:
        bg_path = Path(background_path)
        bg_mono = _source_pcm(bg_path.read_bytes(), speech_rate, channels)
        length = max(length, len(bg_mono))

    combined: list[int] = []
    window_index = 0
    for index in range(length):
        factor = speech_gain
        while window_index < len(windows) and windows[window_index][1] <= index:
            window_index += 1
        if (
            window_index < len(windows)
            and windows[window_index][0] <= index < windows[window_index][1]
        ):
            factor *= windows[window_index][2]
        speech = speech_samples[index] if index < len(speech_samples) else 0
        bg = bg_mono[index] if index < len(bg_mono) else 0
        combined.append(_clip(int(speech * factor + bg * background_gain)))
    _write_wav(target, combined, speech_rate, overwrite=overwrite, channels=channels)
    return {
        "channels": channels,
        "sample_rate": speech_rate,
        "duration": round(length / (speech_rate * channels), 3),
    }


def _encode(
    intermediate: Path,
    fmt: str,
    out_path: Path,
    tags: dict[str, str] | None = None,
    artwork: str | Path | None = None,
    *,
    copy_audio: bool = False,
    mp3_bitrate: str | None = None,
) -> str:
    """Encode a WAV to another format; returns encoder name.

    ``tags`` (key -> value) are embedded as FLAC Vorbis comments or ID3v2
    tags on MP3. WAV is plain PCM and is never tagged.
    """
    tags = tags or {}
    if fmt == "wav":
        out_path.write_bytes(intermediate.read_bytes())
        return "none"

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        codec = {"flac": "flac", "mp3": "libmp3lame"}.get(fmt)
        cmd = [ffmpeg, "-y", "-i", str(intermediate)]
        if artwork is not None:
            cmd += ["-i", str(artwork)]
        cmd += ["-map", "0:a:0"]
        if artwork is not None:
            cmd += ["-map", "1:v:0", "-c:v", "copy", "-disposition:v:0", "attached_pic"]
            cmd += [
                "-metadata:s:v:0",
                "title=Album cover",
                "-metadata:s:v:0",
                "comment=Cover (front)",
            ]
        cmd += ["-map_metadata", "0", "-codec:a", "copy" if copy_audio else codec]
        if fmt == "mp3" and mp3_bitrate and not copy_audio:
            cmd += ["-b:a", mp3_bitrate]
        for key, value in tags.items():
            cmd += ["-metadata", f"{key}={value}"]
        if fmt == "mp3":
            cmd += ["-id3v2_version", "3", "-write_id3v1", "1"]
        cmd.append(str(out_path))
        result = workspace_run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return "ffmpeg"
        raise OCFError(f"ffmpeg encode to {fmt} failed: {result.stderr[-200:]}")

    if copy_audio:
        raise OCFError("stream-copy listening exports require ffmpeg; install ffmpeg")
    if fmt == "flac":
        if artwork is not None:
            raise OCFError("embedding release artwork requires ffmpeg; install ffmpeg")
        flac = shutil.which("flac")
        if flac:
            cmd = [flac, "-f", "-o", str(out_path), str(intermediate)]
            for key, value in tags.items():
                cmd += ["-T", f"{key}={value}"]
            result = workspace_run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return "flac"
    raise OCFError(
        f"no encoder available for {fmt!r}. Install ffmpeg (or flac for FLAC); "
        "the master was kept as WAV."
    )


def _doc_is_original(doc: dict[str, Any]) -> bool:
    """Whether the timed document's narration is original OCF wording.

    Conservative by default: without explicit provenance a document is treated
    as source-derived. It is classified original when composed from an
    ``original-ocf`` session template, or when it declares hand-authored
    (``format: manual``) narration and carries no third-party import snapshot.
    This is provenance classification, not release approval or rights clearance.
    """
    if not isinstance(doc, dict):
        return False
    source = doc.get("source") or {}
    if isinstance(source, dict) and source.get("snapshot") is not None and "snapshot" in source:
        return False
    template = doc.get("template")
    if isinstance(template, dict) and template.get("origin") == "original-ocf":
        return True
    if isinstance(source, dict) and source.get("format") == "manual":
        return True
    return False


def _resolve_tags(
    manifest: dict[str, Any],
    doc: dict[str, Any],
    narration_meta: dict[str, Any],
    tag_overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Derive the FLAC/MP3 tag set from manifests and narration metadata.

    Overrides (``key=value`` from ``--tag``) win over derived values. Extra
    OCF namespaced tags record function, version, command, and template
    provenance so rendered files are self-describing.
    """
    title = str(manifest.get("title") or "")
    audio_id = str(manifest.get("id", ""))
    function_id = manifest.get("function_id")
    function_name = ""
    command = ""
    album = title
    if function_id:
        record = load_function_by_id(function_id)
        if record:
            function_name = record.canonical_name or title
            command = record.canonical_command or ""
            album = function_name or title
    track = audio_id.split("-")[-1] if "-" in audio_id else "1"
    comment = f"Generated by OCF audio build (ocf v{OCF_VERSION}); narration: " + (
        "original OCF wording; release approval and rights clearance are separate"
        if _doc_is_original(doc)
        else "source-derived wording; citation-only unless separately release-cleared; see provenance and release/rights records"
    )
    extra: dict[str, str] = {
        "OCF_AUDIO_ID": audio_id,
        "OCF_FUNCTION": function_name,
        "OCF_COMMAND": command,
        "OCF_AUDIO_VERSION": str(manifest.get("version") or ""),
        "OCF_RELEASE_VERSION": str(
            manifest.get("release_version") or manifest.get("version") or ""
        ),
        "OCF_NARRATOR": str(manifest.get("narrator") or ""),
        "OCF_GENERATOR": f"OCF audio build v{OCF_VERSION}",
        "OCF_TIMING_MODE": str(narration_meta.get("timing_mode") or ""),
    }
    doc_template = doc.get("template") if isinstance(doc, dict) else None
    if isinstance(doc_template, dict) and doc_template.get("id"):
        extra["OCF_SESSION_TEMPLATE"] = str(doc_template["id"])
    pacing_profile = doc.get("pacing_profile") if isinstance(doc, dict) else None
    if isinstance(pacing_profile, dict) and pacing_profile.get("id"):
        extra["OCF_PACING_PROFILE"] = str(pacing_profile["id"])
    artist = str(manifest.get("narrator") or "Open Consciousness Functions")
    tags = {
        "title": title,
        "artist": artist,
        "album_artist": "Open Consciousness Functions",
        "album": album,
        "track": track,
        "comment": comment,
        "language": str(manifest.get("language") or ""),
        "OCF_FUNCTION_ID": str(function_id or ""),
        "date": str(manifest.get("release_date") or ""),
    }
    tags.update(extra)
    for key, value in (tag_overrides or {}).items():
        tags[key] = value
    return {k: v for k, v in tags.items() if v}


def _mix_master_ffmpeg(
    speech_path: Path,
    background_path: Path | None,
    out_path: Path,
    *,
    background_gain: float = 0.25,
    speech_gain: float = 1.0,
    speech_gain_windows: list[tuple[float, float, float]] | None = None,
    mix_profile: dict[str, Any] | str | Path | None = None,
) -> dict[str, Any] | None:
    """Mix narration + reference-master bed to a stereo master via ffmpeg.

    Mirrors the established stereo master pipeline (narration upmixed to
    stereo, background scaled, amixed to the shorter input with no
    normalization, then peak-limited). Pure-stdlib ``mix()`` loads entire
    tracks into Python integer lists, which is impractical for ~30-minute
    reference beds, so the reference-master path delegates the heavy lift to
    ffmpeg. ``speech_gain_windows`` applies ``volume`` filters gated with
    ``enable='between(t,...)'`` so barely-audible sections stay quiet.
    """
    from .mix_profiles import MIX_TIMEOUT_SECONDS, mix_master

    if mix_profile is not None:
        return mix_master(
            speech_path,
            background_path,
            out_path,
            mix_profile=mix_profile,
            sample_rate=DEFAULT_SAMPLE_RATE,
            background_gain=background_gain,
            speech_gain=speech_gain,
            speech_gain_windows=speech_gain_windows,
        )
    ffmpeg = _require_ffmpeg()
    narration_filters = [f"aformat=channel_layouts=stereo,volume={speech_gain:.6f}"]
    for start, end, db in speech_gain_windows or []:
        narration_filters.append(
            f"volume={_db_gain_factor(db):.6f}:enable='between(t,{start:.3f},{end:.3f})'"
        )
    narration_chain = ",".join(narration_filters) + "[n];"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(speech_path),
        "-i",
        str(background_path),
        "-filter_complex",
        f"[0:a]{narration_chain}"
        f"[1:a]volume={background_gain:.6f}[b];"
        "[n][b]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.97:level=false[out]",
        "-map",
        "[out]",
        "-ar",
        str(DEFAULT_SAMPLE_RATE),
        "-ac",
        "2",
        str(out_path),
    ]
    ensure_dir(out_path.parent)
    result = workspace_run(cmd, capture_output=True, timeout=MIX_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise OCFError(f"ffmpeg master mix failed: {result.stderr.decode(errors='replace')[-200:]}")


def _render_background(
    preset: str | None,
    strategy: str,
    engine: str = "farfield",
    *,
    max_seconds: float | None = None,
    scratch_dir: Path | None = None,
) -> tuple[Path | None, str]:
    """Render the configured background preset; degrade gracefully when absent.

    When a matching background manifest declares an ``engine``, that engine
    wins unless the caller explicitly requested a different one (the default
    ``farfield`` acts as "auto"). ``reference-master`` composites an
    operator-supplied reference bed (see ``_render_reference_master``).
    """
    if not preset:
        return None, "none"
    manifest = _resolve_background_manifest(preset)
    effective = engine
    if manifest and manifest.get("engine") and engine == "farfield":
        effective = str(manifest.get("engine"))
    if effective == "sbagenx":
        return _render_sbagenx(preset, strategy, scratch_dir=scratch_dir)
    if effective == "reference-master":
        return _render_reference_master(
            preset, strategy, max_seconds=max_seconds, scratch_dir=scratch_dir
        )
    return _render_farfield(preset, strategy, scratch_dir=scratch_dir)


def _render_farfield(
    preset: str, strategy: str, *, scratch_dir: Path | None = None
) -> tuple[Path | None, str]:
    status = farfield_mod.check_farfield()
    if not status.available:
        if strategy == "required":
            raise OCFError(
                "background strategy is 'required' but Farfield is not installed.\n"
                + farfield_mod.installation_guidance()
            )
        return None, "farfield-unavailable (narration only)"
    source = _farfield_preset_file(preset, strategy)
    tmp = scratch_dir or workspace_temp_directory(prefix="ocf-farfield-")
    out = tmp / f"farfield-{_preset_stem(source)}-{unique_run_id('stem')}.wav"
    result = farfield_mod.render_preset(source, output=out)
    if not out.is_file():
        raise OCFError(f"farfield render produced no file for preset {preset!r}\n{result}")
    return out, "farfield"


def _preset_stem(preset: str) -> str:
    """A filesystem-safe stem for `preset`, which may be an id or a path."""
    stem = Path(preset).stem or preset
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in stem) or "preset"


def _farfield_preset_file(preset: str, strategy: str = "optional") -> str:
    """Resolve a background preset id/name to its Farfield session file.

    Mirrors :func:`_sbagenx_sequence_file`: an audio manifest may name the
    background by id (``OCF-BG-0007``) while Farfield only accepts a session
    YAML path.

    Resolution order, most preferred first:

    1. a literal path, used as given;
     2. the preset *name* across the Farfield search path - explicit overrides,
        committed OCF copies, then optional source-checkout extensions;
    3. the background manifest's declared ``preset.file``.

    Farfield's wheel ships no presets, so tier 2 finds them in the source
    checkout recorded by PEP 610 and falls back to
    ``audio/background/presets/farfield/`` for names only OCF carries.
    """
    explicit = Path(preset).expanduser()
    if explicit.is_file():
        return str(explicit)
    declared = _declared_background_file(preset)
    for name in (Path(preset).stem, Path(declared).stem if declared else None):
        if not name:
            continue
        resolved = farfield_mod.resolve_preset(name)
        if resolved is not None:
            return str(resolved)
    if declared:
        return declared
    if strategy == "required":
        raise OCFError(farfield_mod.preset_search_report(preset))
    return preset


def _declared_background_file(preset: str) -> str | None:
    """The `preset.file` a Farfield background manifest declares, if usable."""
    for manifest in load_background_manifests():
        if not (manifest.get("id") == preset or manifest.get("name") == preset):
            continue
        if manifest.get("engine") != "farfield":
            break
        file_rel = (manifest.get("preset") or {}).get("file")
        if file_rel:
            candidate = REPO_ROOT / str(file_rel)
            if candidate.is_file():
                return str(candidate)
        break
    return None


def _render_sbagenx(
    preset: str, strategy: str, *, scratch_dir: Path | None = None
) -> tuple[Path | None, str]:
    status = sbagenx_mod.check_sbagenx()
    if not status.available:
        if strategy == "required":
            raise OCFError(
                "background strategy is 'required' but SBaGenX is not installed.\n"
                + sbagenx_mod.installation_guidance()
            )
        return None, "sbagenx-unavailable (narration only)"
    sb_seq = _sbagenx_sequence_file(preset)
    tmp = scratch_dir or workspace_temp_directory(prefix="ocf-sbagenx-")
    out = tmp / f"sbagenx-{_preset_stem(preset)}-{unique_run_id('stem')}.wav"
    result = sbagenx_mod.render_preset(sb_seq, output=out, sample_rate=DEFAULT_SAMPLE_RATE)
    if not out.is_file():
        raise OCFError(f"sbagenx render produced no file for preset {preset!r}\n{result}")
    return out, "sbagenx"


def _sbagenx_sequence_file(preset: str) -> str:
    """Resolve a background preset id/name to its SBaGenX `.sbg` file."""
    for manifest in load_background_manifests():
        if not (manifest.get("id") == preset or manifest.get("name") == preset):
            continue
        if manifest.get("engine") != "sbagenx":
            break
        file_rel = (manifest.get("preset") or {}).get("file")
        if file_rel:
            candidate = REPO_ROOT / str(file_rel)
            if candidate.is_file():
                return str(candidate)
        break
    return preset


def _resolve_background_manifest(preset: str | None) -> dict[str, Any] | None:
    """Load the background manifest whose id or name matches ``preset``."""
    if not preset:
        return None
    for manifest in load_background_manifests():
        if manifest.get("id") == preset or manifest.get("name") == preset:
            return manifest
    return None


def _require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise OCFError(
            "ffmpeg is required to decode reference-master audio. Install ffmpeg "
            "(or use a farfield/sbagenx preset)."
        )
    return ffmpeg


def _decode_to_s16le(
    path: Path,
    *,
    start: float | None = None,
    seconds: float | None = None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> bytes:
    """Decode any audio to raw interleaved 16-bit s16le via ffmpeg."""
    cmd = [_require_ffmpeg(), "-v", "error", "-i", str(path)]
    if start is not None:
        cmd += ["-ss", str(start)]
    if seconds is not None:
        cmd += ["-t", str(seconds)]
    cmd += ["-ar", str(sample_rate), "-ac", "2", "-f", "s16le", "-"]
    result = workspace_run(cmd, capture_output=True)
    if result.returncode != 0:
        raise OCFError(
            f"ffmpeg decode failed for {path.name}: {result.stderr.decode(errors='replace')[-200:]}"
        )
    return result.stdout


def _render_reference_master(
    preset: str,
    strategy: str,
    *,
    max_seconds: float | None = None,
    scratch_dir: Path | None = None,
) -> tuple[Path | None, str]:
    """Composite a background bed from an operator-supplied reference master.

    The manifest's ``reference.source`` is the continuous reference bed
    (citation-only, provided by the operator). Each ``splices`` entry decodes
    a slice of another audio file and crossfades it into its access-channel
    window, gain-matched to the surrounding reference, so no synthesis engine
    (Farfield/SBaGenX) is required. Files are never vendored into the repo.
    """
    manifest = _resolve_background_manifest(preset)
    ref = (manifest or {}).get("reference")

    def _degrade(message: str) -> tuple[Path | None, str]:
        if strategy == "required":
            raise OCFError(f"background strategy is 'required': {message}")
        print(f"Note: {message}")
        return None, "reference-master-unavailable (narration only)"

    if not ref or not ref.get("source"):
        return _degrade(f"{preset}: reference-master manifest has no reference.source")
    source = REPO_ROOT / str(ref["source"])
    if not source.is_file():
        return _degrade(f"reference master not found (citation-only, keep it local): {source}")
    if shutil.which("ffmpeg") is None:
        return _degrade("ffmpeg is required to decode reference-master audio")

    from array import array

    base = array("h")
    if max_seconds is not None and max_seconds > 0:
        base.frombytes(_decode_to_s16le(source, seconds=max_seconds))
    else:
        base.frombytes(_decode_to_s16le(source))
    channels = 2
    if len(base) == 0:
        return _degrade(f"reference master decoded to silence: {source}")
    frame_count = len(base) // channels
    base = base[: frame_count * channels]

    for spl in ref.get("splices") or []:
        seg_source = REPO_ROOT / str(spl["source"])
        if not seg_source.is_file():
            return _degrade(f"reference-master splice source not found: {seg_source}")
        seg = array("h")
        seg.frombytes(
            _decode_to_s16le(
                seg_source,
                start=float(spl["slice_start"]),
                seconds=float(spl["slice_length"]),
            )
        )
        seg = seg[: (len(seg) // channels) * channels]
        if len(seg) == 0:
            continue
        target_start = int(float(spl["target_start"]) * DEFAULT_SAMPLE_RATE)
        crossfade = int(float(spl.get("crossfade", 0.0)) * DEFAULT_SAMPLE_RATE)
        seg_frames = min(len(seg) // channels, frame_count - target_start)
        if seg_frames <= 0:
            print(
                f"Note: {preset} splice target {float(spl['target_start']):.1f}s "
                "falls outside the rendered bed; skipped"
            )
            continue

        # Gain-match: scale the splice so its RMS matches the reference window
        # it replaces (both channels coupled). Guard against silent edges.
        def _rms(channel: array) -> float:
            total = 0
            for value in channel:
                total += value * value
            return (total / len(channel)) ** 0.5 if len(channel) else 0.0

        base_l = base[target_start * channels :: channels][:seg_frames]
        seg_l = seg[::channels][:seg_frames]
        base_rms = _rms(base_l)
        seg_rms = _rms(seg_l)
        scale = (base_rms / seg_rms) if seg_rms else 0.0
        if scale <= 0.0 or scale > 16.0:
            scale = 1.0
        if scale != 1.0:
            seg = array("h", (_clip(round(v * scale)) for v in seg))

        # Crossfade each splice end against the reference over `overlap` frames.
        overlap = min(crossfade, seg_frames // 2)
        pos = target_start * channels
        for i in range(overlap):
            p = i / overlap
            for c in range(channels):
                base[pos + c] = _clip(round(base[pos + c] * (1 - p) + seg[i * channels + c] * p))
            pos += channels
        for i in range(overlap):
            p = (overlap - i) / overlap
            frame = target_start + seg_frames - overlap + i
            for c in range(channels):
                offset = frame * channels
                base[offset + c] = _clip(
                    round(
                        base[offset + c] * (1 - p)
                        + seg[(seg_frames - overlap + i) * channels + c] * p
                    )
                )
        mid_start = (target_start + overlap) * channels
        mid_end = (target_start + seg_frames - overlap) * channels
        if mid_end > mid_start:
            base[mid_start:mid_end] = seg[overlap * channels : (seg_frames - overlap) * channels]

    if max_seconds is not None and max_seconds > 0:
        base = base[: int(max_seconds * DEFAULT_SAMPLE_RATE) * channels]

    tmp = scratch_dir or workspace_temp_directory(prefix="ocf-reference-")
    out = tmp / f"reference-{_preset_stem(preset)}-{unique_run_id('stem')}.wav"
    ensure_dir(out.parent)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(DEFAULT_SAMPLE_RATE)
        writer.writeframes(base.tobytes())
    out.write_bytes(buffer.getvalue())
    return out, "reference-master"


def build(
    query: str,
    *,
    manifest_override: dict[str, Any] | None = None,
    document_override: dict[str, Any] | None = None,
    render_label: str | None = None,
    out_root: str | Path | None = None,
    fmt: str = "wav",
    formats: list[str] | tuple[str, ...] | None = None,
    tag_overrides: dict[str, str] | None = None,
    voice: str | dict[str, Any] | None = None,
    background_gain: float = 0.25,
    voice_gain: float = 1.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    render_cue: Callable[[str], bytes] | None = None,
    render_cue_with_profile: Callable[[str, dict[str, Any]], bytes] | None = None,
    overwrite: bool = True,
    fit: bool = False,
    flow: bool = False,
    even_counts: bool = False,
    locale: str | None = None,
    strict: bool = True,
    dsp_profile: str | Path | dict[str, Any] | None = None,
    recordings: str | Path | None = None,
    narration_sources: str | Path | None = None,
    narration_source: str | None = None,
    source_rate_scale: float = 1.0,
    source_fallback_voice: str | None = None,
    artwork: str | Path | None = None,
    retain_background_stem: bool = False,
    mix_profile: dict[str, Any] | str | Path | None = None,
) -> dict[str, Any]:
    """`ocf audio build <AUDIO_ID|MANIFEST>` — render narration, mix, master.

    ``formats`` selects which derivatives to emit besides the WAV master
    (defaults to a single format derived from ``fmt`` for library callers;
    the CLI passes ``wav,flac,mp3`` by default). FLAC/MP3 files are tagged
    with metadata derived from the manifests (see ``_resolve_tags``), plus any
    ``tag_overrides``.
    """
    if mix_profile is not None:
        from .mix_profiles import load_mix_profile

        mix_profile = load_mix_profile(mix_profile)
    if manifest_override is not None and document_override is None:
        raise OCFError("manifest_override requires document_override")
    manifest = manifest_override if manifest_override is not None else find_audio_manifest(query)
    if manifest is None:
        raise OCFError(f"audio implementation manifest not found: {query}")
    registered_audio_id = manifest.get("id")
    audio_id = str(registered_audio_id or render_label or "")
    if not audio_id:
        raise OCFError("an unregistered document render requires a nonempty render_label")
    transcript_rel = manifest.get("transcript_path")
    if document_override is None and not transcript_rel:
        raise OCFError(
            f"audio manifest {audio_id} has no transcript_path; add a timed-transcript "
            "script (audio/scripts/*.yaml) and record it first"
        )
    transcript_path = (REPO_ROOT / str(transcript_rel)).resolve() if transcript_rel else None
    if transcript_path is not None and not transcript_path.is_file():
        raise OCFError(f"transcript referenced by {audio_id} not found: {transcript_path}")

    doc = document_override if document_override is not None else load_timed_doc(transcript_path)
    if doc.get("function_id") and doc["function_id"] != manifest.get("function_id"):
        raise OCFError("audio manifest and transcript disagree about command-owning function_id")
    if manifest.get("function_id"):
        doc["function_id"] = manifest["function_id"]
    selected_voice = voice or manifest.get("voice_profile") or doc.get("voice_profile")
    if (
        not isinstance(voice_gain, (int, float))
        or isinstance(voice_gain, bool)
        or not math.isfinite(float(voice_gain))
        or voice_gain < 0
    ):
        raise OCFError("voice_gain must be a finite nonnegative linear gain")
    formats = list(dict.fromkeys((fmt,) if formats is None else formats))
    if any(value not in ("wav", "flac", "mp3") for value in formats):
        raise OCFError("output formats must be wav, flac or mp3")
    out_root = Path(AUDIO_RENDERED_DIR if out_root is None else out_root)
    master_path = out_root / f"{audio_id}-master.wav"
    render_name = f"OCF-RENDER-{audio_id.split('-')[-1]}"
    render_manifest = out_root / f"{render_name}.yaml"
    background_stem_path = out_root / f"{audio_id}-background.wav"
    default_cover = (
        artwork is None
        and registered_audio_id
        and manifest.get("function_id")
        and load_function_by_id(manifest["function_id"]) is not None
    )
    cover_output = out_root / f"{audio_id}-cover.png"
    planned_outputs = (
        [master_path, render_manifest]
        + ([cover_output] if default_cover else [])
        + ([background_stem_path] if retain_background_stem else [])
        + [out_root / f"{audio_id}-master.{value}" for value in formats if value != "wav"]
    )
    if not overwrite:
        occupied = next((path for path in planned_outputs if path.exists()), None)
        if occupied is not None:
            raise OCFError(f"refusing to overwrite existing output: {occupied}; use --force")
    stage_dir = workspace_temp_directory(prefix=f"ocf-build-{audio_id}-")
    (stage_dir / "build-context.json").write_text(
        json.dumps({"audio_id": audio_id, "query": query, "status": "rendering"}, indent=2) + "\n",
        encoding="utf-8",
    )
    narration_wav = stage_dir / "narration.wav"
    from .progress import report as report_progress

    report_progress("narration")
    narration_meta = render_narration(
        doc,
        narration_wav,
        backend=(voice or manifest.get("voice_profile"))
        if narration_sources is not None
        else selected_voice,
        sample_rate=sample_rate,
        render_cue=render_cue,
        render_cue_with_profile=render_cue_with_profile,
        overwrite=True,
        fit=fit,
        flow=flow,
        even_counts=even_counts,
        locale=locale,
        strict=strict,
        recordings=recordings,
        **(
            {
                "narration_sources": narration_sources,
                "narration_source": narration_source,
                "source_rate_scale": source_rate_scale,
                "source_fallback_voice": source_fallback_voice,
            }
            if narration_sources is not None or narration_source is not None
            else {}
        ),
    )

    background_conf = manifest.get("background_audio", {})
    report_progress("background-dsp", detail="measured narration complete")
    bg_preset = background_conf.get("preset")
    selected_profile = (
        dsp_profile or background_conf.get("semantic_profile") or doc.get("semantic_dsp_profile")
    )
    state_program = None
    if selected_profile:
        from .semantic_dsp import load_profile, render_program

        if bg_preset and dsp_profile is None:
            raise OCFError("manifest must choose static preset or semantic DSP profile, not both")
        profile = (
            selected_profile
            if isinstance(selected_profile, dict)
            else load_profile(selected_profile)
        )
        if retain_background_stem:
            ensure_dir(out_root)
            bg_path = background_stem_path
        else:
            bg_path = stage_dir / "semantic-state-bed.wav"
        state_program = render_program(
            doc,
            narration_meta["event_timing"],
            narration_meta["duration"],
            profile,
            bg_path,
            scratch_dir=stage_dir,
        )
        bg_note = "semantic-state-program"
    else:
        bg_path, bg_note = _render_background(
            bg_preset,
            background_conf.get("strategy", "optional"),
            background_conf.get("engine", "farfield"),
            max_seconds=narration_meta["duration"],
            scratch_dir=stage_dir,
        )
    if bg_note.startswith(
        ("farfield-unavailable", "sbagenx-unavailable", "reference-master-unavailable")
    ):
        print(f"Note: {bg_note}")

    gain_windows = _narration_gain_windows(
        doc, narration_meta["duration"], narration_meta.get("event_timing")
    )

    ensure_dir(out_root)
    mix_processing = None
    report_progress("stereo-mixing")
    if bg_path is not None or mix_profile is not None:
        # Any engine-rendered bed (Farfield, SBaGenX, reference-master) goes
        # through ffmpeg: those stems are long, stereo, and often 24-bit, which
        # the pure-stdlib PCM path cannot decode or hold in memory.
        mix_processing = _mix_master_ffmpeg(
            narration_wav,
            bg_path,
            master_path,
            background_gain=background_gain,
            speech_gain=float(voice_gain),
            speech_gain_windows=gain_windows,
            **({"mix_profile": mix_profile} if mix_profile is not None else {}),
        )
    else:
        mix(
            narration_wav,
            None,
            master_path,
            speech_gain=float(voice_gain),
            speech_gain_windows=gain_windows,
            overwrite=overwrite,
        )

    tags = _resolve_tags(manifest, doc, narration_meta, tag_overrides)
    cover_provenance = None
    if default_cover:
        from .audition_exports import copy_cover, select_cover

        edition_version = str(manifest.get("version") or "0.1.0")
        selected, cover_provenance, _ = select_cover(
            manifest["function_id"],
            locale or manifest.get("language") or "en-US",
            edition_version,
            artwork_theme=manifest.get("artwork_theme"),
        )
        # Build's ordinary overwrite policy is unchanged; cover files obey it too.
        if cover_output.exists():
            if not overwrite:
                raise OCFError("refusing to overwrite existing build cover")
            cover_output.unlink()
        copy_cover(selected, cover_output)
        artwork = cover_output
        tags.setdefault("OCF_AUDIO_VERSION", edition_version)
        tags.setdefault("OCF_VERSION_LABEL", "v" + edition_version)

    outputs: list[dict[str, Any]] = []
    for out_fmt in formats:
        if out_fmt == "wav":
            outputs.append(
                {
                    "file": master_path.name,
                    "format": "wav",
                    "encoder": "none",
                    "checksum_sha256": sha256_of_file(master_path),
                }
            )
            continue
        encoded = out_root / f"{audio_id}-master.{out_fmt}"
        try:
            if artwork is None:
                encoder = _encode(master_path, out_fmt, encoded, tags=tags)
            else:
                encoder = _encode(master_path, out_fmt, encoded, tags=tags, artwork=artwork)
        except OCFError as exc:
            print(f"Warning: {exc}")
            continue
        outputs.append(
            {
                "file": encoded.name,
                "format": out_fmt,
                "encoder": encoder,
                "checksum_sha256": sha256_of_file(encoded),
            }
        )

    master_entry = {
        "file": master_path.name,
        "format": "wav",
        "encoder": "none",
        "checksum_sha256": sha256_of_file(master_path),
    }
    narration_check = sha256_of_file(narration_wav)
    master_rate = DEFAULT_SAMPLE_RATE if bg_path is not None else narration_meta["sample_rate"]
    master_channels = 2 if bg_path is not None else 1
    try:
        with wave.open(str(master_path), "rb") as reader:
            master_rate = reader.getframerate()
            master_channels = reader.getnchannels()
            duration = round(reader.getnframes() / master_rate, 3)
    except wave.Error:
        duration = narration_meta["duration"]

    render_doc = {
        # Progress is an observer only and is deliberately absent from artifact identity.
        "schema_version": "1.0",
        "generated": current_date(),
        "audio_manifest": {
            "id": registered_audio_id,
            "function_id": manifest.get("function_id"),
            "title": manifest.get("title"),
            "narrator": manifest.get("narrator"),
            "language": manifest.get("language"),
            "voice_profile": manifest.get("voice_profile") or doc.get("voice_profile"),
        },
        "transcript_path": str(transcript_rel) if transcript_rel else None,
        "pacing_profile": doc.get("pacing_profile"),
        "slot_provenance": doc.get("slot_provenance", {}),
        "voice": {
            "backend": narration_meta["backend"],
            "profile_id": narration_meta.get("profile_id"),
            "options": narration_meta.get("voice_options", {}),
            "sample_rate": narration_meta["sample_rate"],
            "channels": narration_meta["channels"],
            "locale": narration_meta.get("locale"),
            "locale_notes": narration_meta.get("locale_notes", []),
            "pronunciation_hints": narration_meta.get("pronunciation_hints", 0),
        },
        "narration_timing": {
            "mode": narration_meta.get("timing_mode", "explicit-at-timestamps"),
            "measured": True,
            "duration_seconds": narration_meta["duration"],
            "note": (
                "Per-cue speech durations measured from the rendered stem. Subtitle "
                "export can use these instead of the semantic timeline."
            ),
            "cues": [
                {
                    "id": cue["id"],
                    "source_ids": cue.get("source_ids", [cue["id"]]),
                    "display_text": cue.get("display_text", cue.get("text", "")),
                    "spoken_text": cue.get("text", cue.get("display_text", "")),
                    "at": round(float(cue["at"]), 3),
                    # `duration` is seconds when the renderer recorded it, and
                    # otherwise derived from the sample count.
                    "duration": round(
                        float(cue["duration"])
                        if cue.get("duration") is not None
                        else float(cue["samples"]) / narration_meta["sample_rate"],
                        3,
                    ),
                    "speech_duration": round(
                        float(cue.get("speech_duration", cue.get("duration", 0))), 3
                    ),
                    "pacing": cue.get("pacing"),
                    "spoken_units": cue.get("spoken_units", []),
                    **(
                        {"narration_source": cue["narration_source"]}
                        if "narration_source" in cue
                        else {}
                    ),
                }
                for cue in narration_meta.get("cue_stats", [])
            ],
        },
        "event_timing": narration_meta.get("event_timing", []),
        "semantic_dsp": state_program,
        "auditory_cues": narration_meta.get("auditory_cues", []),
        "narration_resolution": narration_meta.get("narration_resolution"),
        "narration_pacing": narration_meta.get("narration_pacing", {}),
        "narration_source": narration_meta.get("narration_source"),
        "cues": narration_meta["cues"],
        "overlap_mode": narration_meta["overlap_mode"],
        "timing_mode": narration_meta.get("timing_mode", "explicit-at-timestamps"),
        "background": {"preset": background_conf.get("preset"), "engine": bg_note},
        "mixing": {
            "voice_gain": float(voice_gain),
            "background_gain": float(background_gain) if bg_path is not None else 0.0,
            "method": "ffmpeg-stereo"
            if bg_path is not None or mix_profile is not None
            else "pcm-mono",
            **({"processing": mix_processing} if mix_profile is not None else {}),
        },
        "narration_gain_windows": [
            {"start": start, "end": end, "gain_db": db} for start, end, db in gain_windows
        ],
        "source_text_policy": (
            "OCF-authored narration (original wording); recorded in the "
            "repository under audio/scripts/"
            if _doc_is_original(doc)
            else "source-derived expression; citation-only unless separately release-cleared; working text is local and release/rights approval is separate"
        ),
        "narration": {
            "file": str(narration_wav.name),
            "checksum_sha256": narration_check,
        },
        "formats": [entry["format"] for entry in outputs],
        "outputs": outputs,
        "tags": tags,
        "master": {
            "file": master_entry["file"],
            "format": master_entry["format"],
            "encoder": master_entry["encoder"],
            "sample_rate": master_rate,
            "channels": master_channels,
            "duration": duration,
            "checksum_sha256": master_entry["checksum_sha256"],
        },
    }
    if retain_background_stem and bg_path is not None:
        if bg_path != background_stem_path:
            shutil.copy2(bg_path, background_stem_path)
        render_doc["background_stem"] = {
            "file": background_stem_path.name,
            "format": "wav",
            "sample_rate": DEFAULT_SAMPLE_RATE,
            "channels": 2,
            "checksum_sha256": sha256_of_file(background_stem_path),
        }
    if cover_provenance:
        render_doc["artwork"] = {
            "file": cover_output.name,
            "sha256": sha256_of_file(cover_output),
            "provenance": cover_provenance,
        }
    write_text_atomic(render_manifest, generated_content(yaml_safe_dump(render_doc)))

    print(
        f"Built {', '.join(o['file'] for o in outputs)} from {audio_id}: "
        f"{narration_meta['cues']} cue(s), {duration}s, background={bg_note.split(' ')[0]}"
    )
    (stage_dir / "build-context.json").write_text(
        json.dumps({"audio_id": audio_id, "query": query, "status": "completed"}, indent=2) + "\n",
        encoding="utf-8",
    )
    cleanup_workspace_temp(stage_dir)
    return render_doc


def default_narration_output(script: str | Path) -> str:
    """DEFAULT output narration path for a timed script."""
    return str(AUDIO_RENDERED_DIR / f"{Path(script).stem}-narration.wav")


def inspect(path: str | Path) -> dict[str, Any]:
    """Return metadata for an audio file (WAV parsed; others sha256 only)."""
    target = Path(path)
    if not target.is_file():
        raise OCFError(f"file not found: {target}")
    info: dict[str, Any] = {
        "file": str(target),
        "size_bytes": target.stat().st_size,
        "checksum_sha256": sha256_of_file(target),
    }
    if target.suffix.lower() == ".wav":
        try:
            with wave.open(str(target), "rb") as reader:
                frames = reader.getnframes()
                rate = reader.getframerate()
                info.update(
                    {
                        "format": "WAV (PCM)",
                        "channels": reader.getnchannels(),
                        "sample_rate": rate,
                        "sample_width": reader.getsampwidth(),
                        "frames": frames,
                        "duration": round(frames / rate, 3),
                    }
                )
        except wave.Error as exc:
            raise OCFError(f"{target}: not a readable WAV: {exc}") from exc
    else:
        info["format"] = target.suffix.upper()
    return info
