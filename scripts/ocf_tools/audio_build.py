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
import shutil
import subprocess
import tempfile
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import __version__ as OCF_VERSION
from . import farfield as farfield_mod
from . import sbagenx as sbagenx_mod
from .indexes import find_audio_manifest, load_background_manifests, load_function_by_id
from .paths import AUDIO_RENDERED_DIR, REPO_ROOT, ensure_dir
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


def _write_wav(path: Path, samples: list[int], sample_rate: int, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise OCFError(f"Refusing to overwrite existing file: {path} (use --force)")
    ensure_dir(path.parent)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
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
    doc: dict[str, Any], duration: float
) -> list[tuple[float, float, float]]:
    """Return (start, end, gain_db) windows from sections declaring ``gain_db``.

    A section's window runs from its first event to the next section's first
    event (or the track end), so the whole quiet region — including the
    trailing speech of the last attenuated line — is scaled together. Used for
    barely-audible reinforcement (e.g. the twentieth-state sleep wording).
    """
    from .transcript import parse_timestamp

    bounds: list[tuple[float, str]] = []
    for section in doc.get("sections") or []:
        first_at: float | None = None
        for event in section.get("timeline") or []:
            at = event.get("at")
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
    speech_rate, speech_samples = _read_mono_pcm(speech_path)

    windows: list[tuple[int, int, float]] = []
    for start, end, db in speech_gain_windows or []:
        if end <= start:
            continue
        factor = _db_gain_factor(db)
        windows.append(
            (int(start * speech_rate), int(end * speech_rate), factor)
        )
    windows.sort(key=lambda item: item[0])

    length = len(speech_samples)
    bg_mono: list[int] = []
    if background_path is not None:
        bg_path = Path(background_path)
        _rate, bg_mono = _read_mono_pcm(bg_path, speech_rate)
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
    _write_wav(target, combined, speech_rate, overwrite=overwrite)
    return {
        "channels": 1,
        "sample_rate": speech_rate,
        "duration": round(length / speech_rate, 3),
    }


def _encode(
    intermediate: Path,
    fmt: str,
    out_path: Path,
    tags: dict[str, str] | None = None,
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
        cmd = [ffmpeg, "-y", "-i", str(intermediate), "-vn", "-codec:a", codec]
        for key, value in tags.items():
            cmd += ["-metadata", f"{key}={value}"]
        if fmt == "mp3":
            cmd += ["-id3v2_version", "3", "-write_id3v1", "1"]
        cmd.append(str(out_path))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return "ffmpeg"
        raise OCFError(f"ffmpeg encode to {fmt} failed: {result.stderr[-200:]}")

    if fmt == "flac":
        flac = shutil.which("flac")
        if flac:
            cmd = [flac, "-f", "-o", str(out_path), str(intermediate)]
            for key, value in tags.items():
                cmd += ["-T", f"{key}={value}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return "flac"
    raise OCFError(
        f"no encoder available for {fmt!r}. Install ffmpeg (or flac for FLAC); "
        "the master was kept as WAV."
    )


def _doc_is_original(doc: dict[str, Any]) -> bool:
    """Whether the timed document's narration is original OCF wording.

    Conservative by default: without explicit provenance a document is treated
    as citation-only. It is committable when it was composed from an
    ``original-ocf`` session template, or when it declares hand-authored
    (``format: manual``) narration and carries no third-party import snapshot.
    """
    if not isinstance(doc, dict):
        return False
    source = doc.get("source") or {}
    if isinstance(source, dict) and source.get("snapshot"):
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
    comment = (
        "Generated by OCF audio build "
        f"(ocf v{OCF_VERSION}); narration: "
        + (
            "original OCF wording, committable"
            if _doc_is_original(doc)
            else "synthesized from a citation-only transcript; wording belongs to its source"
        )
    )
    extra: dict[str, str] = {
        "OCF_AUDIO_ID": audio_id,
        "OCF_FUNCTION": function_name,
        "OCF_COMMAND": command,
        "OCF_AUDIO_VERSION": str(manifest.get("version") or ""),
        "OCF_NARRATOR": str(manifest.get("narrator") or ""),
        "OCF_GENERATOR": f"OCF audio build v{OCF_VERSION}",
        "OCF_TIMING_MODE": str(narration_meta.get("timing_mode") or ""),
    }
    doc_template = doc.get("template") if isinstance(doc, dict) else None
    if isinstance(doc_template, dict) and doc_template.get("id"):
        extra["OCF_SESSION_TEMPLATE"] = str(doc_template["id"])
    tags = {
        "title": title,
        "artist": "Open Consciousness Functions",
        "album": album,
        "track": track,
        "comment": comment,
    }
    tags.update(extra)
    for key, value in (tag_overrides or {}).items():
        tags[key] = value
    return {k: v for k, v in tags.items() if v}


def _mix_master_ffmpeg(
    speech_path: Path,
    background_path: Path,
    out_path: Path,
    *,
    background_gain: float = 0.25,
    speech_gain: float = 1.0,
    speech_gain_windows: list[tuple[float, float, float]] | None = None,
) -> None:
    """Mix narration + reference-master bed to a stereo master via ffmpeg.

    Mirrors the established stereo master pipeline (narration upmixed to
    stereo, background scaled, amixed to the shorter input with no
    normalization, then peak-limited). Pure-stdlib ``mix()`` loads entire
    tracks into Python integer lists, which is impractical for ~30-minute
    reference beds, so the reference-master path delegates the heavy lift to
    ffmpeg. ``speech_gain_windows`` applies ``volume`` filters gated with
    ``enable='between(t,...)'`` so barely-audible sections stay quiet.
    """
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
        "[n][b]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.97[out]",
        "-map",
        "[out]",
        "-ar",
        str(DEFAULT_SAMPLE_RATE),
        "-ac",
        "2",
        str(out_path),
    ]
    ensure_dir(out_path.parent)
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise OCFError(f"ffmpeg master mix failed: {result.stderr.decode(errors='replace')[-200:]}")


def _render_background(
    preset: str | None,
    strategy: str,
    engine: str = "farfield",
    *,
    max_seconds: float | None = None,
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
        return _render_sbagenx(preset, strategy)
    if effective == "reference-master":
        return _render_reference_master(preset, strategy, max_seconds=max_seconds)
    return _render_farfield(preset, strategy)


def _render_farfield(preset: str, strategy: str) -> tuple[Path | None, str]:
    status = farfield_mod.check_farfield()
    if not status.available:
        if strategy == "required":
            raise OCFError(
                "background strategy is 'required' but Farfield is not installed.\n"
                + farfield_mod.installation_guidance()
            )
        return None, "farfield-unavailable (narration only)"
    tmp = tempfile.mkdtemp(prefix="ocf-farfield-")
    out = Path(tmp) / f"{preset.replace(':', '-')}.wav"
    result = farfield_mod.render_preset(preset, output=out)
    if not out.exists():
        raise OCFError(f"farfield render produced no file for preset {preset!r}\n{result}")
    return out, "farfield"


def _render_sbagenx(preset: str, strategy: str) -> tuple[Path | None, str]:
    status = sbagenx_mod.check_sbagenx()
    if not status.available:
        if strategy == "required":
            raise OCFError(
                "background strategy is 'required' but SBaGenX is not installed.\n"
                + sbagenx_mod.installation_guidance()
            )
        return None, "sbagenx-unavailable (narration only)"
    sb_seq = _sbagenx_sequence_file(preset)
    tmp = tempfile.mkdtemp(prefix="ocf-sbagenx-")
    out = Path(tmp) / f"{preset.replace(':', '-')}.wav"
    result = sbagenx_mod.render_preset(sb_seq, output=out, sample_rate=DEFAULT_SAMPLE_RATE)
    if not out.exists():
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
    cmd += ["-ar", str(sample_rate), "-f", "s16le", "-"]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise OCFError(
            f"ffmpeg decode failed for {path.name}: "
            f"{result.stderr.decode(errors='replace')[-200:]}"
        )
    return result.stdout


def _render_reference_master(
    preset: str,
    strategy: str,
    *,
    max_seconds: float | None = None,
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
                    round(base[offset + c] * (1 - p) + seg[(seg_frames - overlap + i) * channels + c] * p)
                )
        mid_start = (target_start + overlap) * channels
        mid_end = (target_start + seg_frames) * channels
        if mid_end > mid_start:
            base[mid_start:mid_end] = seg[overlap * channels : seg_frames * channels]

    if max_seconds is not None and max_seconds > 0:
        base = base[: int(max_seconds * DEFAULT_SAMPLE_RATE) * channels]

    tmp = tempfile.mkdtemp(prefix="ocf-reference-")
    out = Path(tmp) / f"{preset.replace(':', '-')}.wav"
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
    out_root: str | Path | None = None,
    fmt: str = "wav",
    formats: list[str] | tuple[str, ...] | None = None,
    tag_overrides: dict[str, str] | None = None,
    voice: str | dict[str, Any] | None = None,
    background_gain: float = 0.25,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    render_cue: Callable[[str], bytes] | None = None,
    overwrite: bool = True,
    fit: bool = False,
    flow: bool = False,
    even_counts: bool = False,
) -> dict[str, Any]:
    """`ocf audio build <AUDIO_ID|MANIFEST>` — render narration, mix, master.

    ``formats`` selects which derivatives to emit besides the WAV master
    (defaults to a single format derived from ``fmt`` for library callers;
    the CLI passes ``wav,flac,mp3`` by default). FLAC/MP3 files are tagged
    with metadata derived from the manifests (see ``_resolve_tags``), plus any
    ``tag_overrides``.
    """
    manifest = find_audio_manifest(query)
    if manifest is None:
        raise OCFError(f"audio implementation manifest not found: {query}")
    audio_id = str(manifest.get("id", ""))
    transcript_rel = manifest.get("transcript_path")
    if not transcript_rel:
        raise OCFError(
            f"audio manifest {audio_id} has no transcript_path; add a timed-transcript "
            "script (audio/scripts/*.yaml) and record it first"
        )
    transcript_path = (REPO_ROOT / str(transcript_rel)).resolve()
    if not transcript_path.is_file():
        raise OCFError(f"transcript referenced by {audio_id} not found: {transcript_path}")

    doc = load_timed_doc(transcript_path)
    stage_dir = Path(tempfile.mkdtemp(prefix=f"ocf-build-{audio_id}-"))
    narration_wav = stage_dir / "narration.wav"
    narration_meta = render_narration(
        doc,
        narration_wav,
        backend=voice,
        sample_rate=sample_rate,
        render_cue=render_cue,
        overwrite=True,
        fit=fit,
        flow=flow,
        even_counts=even_counts,
    )

    background_conf = manifest.get("background_audio", {})
    bg_preset = background_conf.get("preset")
    bg_path, bg_note = _render_background(
        bg_preset,
        background_conf.get("strategy", "optional"),
        background_conf.get("engine", "farfield"),
        max_seconds=narration_meta["duration"],
    )
    if bg_note.startswith(
        ("farfield-unavailable", "sbagenx-unavailable", "reference-master-unavailable")
    ):
        print(f"Note: {bg_note}")

    gain_windows = _narration_gain_windows(doc, narration_meta["duration"])

    if out_root is None:
        out_root = AUDIO_RENDERED_DIR
    out_root = Path(out_root)
    ensure_dir(out_root)
    master_path = out_root / f"{audio_id}-master.wav"
    bg_manifest = _resolve_background_manifest(bg_preset) or {}
    if bg_manifest.get("engine") == "reference-master" and bg_path is not None:
        _mix_master_ffmpeg(
            narration_wav,
            bg_path,
            master_path,
            background_gain=background_gain,
            speech_gain_windows=gain_windows,
        )
    else:
        mix(
            narration_wav,
            bg_path,
            master_path,
            background_gain=background_gain,
            speech_gain_windows=gain_windows,
            overwrite=overwrite,
        )

    if formats is None:
        formats = (fmt,)
    formats = list(dict.fromkeys(formats))

    tags = _resolve_tags(manifest, doc, narration_meta, tag_overrides)

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
            encoder = _encode(master_path, out_fmt, encoded, tags=tags)
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

    actual_path = master_path
    narration_check = sha256_of_file(narration_wav)
    master_check = sha256_of_file(actual_path)
    try:
        if actual_path.suffix == ".wav":
            with wave.open(str(actual_path), "rb") as reader:
                duration = round(reader.getnframes() / reader.getframerate(), 3)
        else:
            duration = narration_meta["duration"]
    except wave.Error:
        duration = narration_meta["duration"]

    master_entry = outputs[0]
    render_doc = {
        "schema_version": "1.0",
        "generated": current_date(),
        "audio_manifest": {
            "id": audio_id,
            "function_id": manifest.get("function_id"),
            "title": manifest.get("title"),
            "narrator": manifest.get("narrator"),
            "language": manifest.get("language"),
        },
        "transcript_path": str(transcript_rel),
        "voice": {
            "backend": narration_meta["backend"],
            "profile_id": narration_meta.get("profile_id"),
            "sample_rate": narration_meta["sample_rate"],
            "channels": narration_meta["channels"],
        },
        "cues": narration_meta["cues"],
        "overlap_mode": narration_meta["overlap_mode"],
        "timing_mode": narration_meta.get("timing_mode", "explicit-at-timestamps"),
        "background": {"preset": background_conf.get("preset"), "engine": bg_note},
        "narration_gain_windows": [
            {"start": start, "end": end, "gain_db": db} for start, end, db in gain_windows
        ],
        "source_text_policy": (
            "OCF-authored narration (original wording); recorded in the "
            "repository under audio/scripts/"
            if _doc_is_original(doc)
            else "citation-only; transcript wording stays with the operator-supplied "
            "source, never in the repository"
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
            "sample_rate": narration_meta["sample_rate"],
            "duration": duration,
            "checksum_sha256": master_entry["checksum_sha256"],
        },
    }
    render_name = f"OCF-RENDER-{audio_id.split('-')[-1]}"
    render_manifest = out_root / f"{render_name}.yaml"
    write_text_atomic(render_manifest, generated_content(yaml_safe_dump(render_doc)))

    print(
        f"Built {', '.join(o['file'] for o in outputs)} from {audio_id}: "
        f"{narration_meta['cues']} cue(s), {duration}s, background={bg_note.split(' ')[0]}"
    )
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
