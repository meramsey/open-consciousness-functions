"""Narration speech rendering for OCF timed scripts.

Renders each timed cue of an OCF timed-YAML document to audio and assembles it
into a single WAV narration stem. Text-to-speech is provided by optional
external CLIs (``espeak-ng``, ``espeak``, or ``piper``); like Farfield, these
are detected on PATH and the toolchain degrades gracefully with installation
guidance when none is available.

Timing model (v0.4 - original, deterministic, and documented in the render
manifest):

- every cue is placed at its ``at`` timestamp;
- cues are rendered independently so wording and pacing are never rewritten;
- when a cue's start falls inside the previous cue's speech, the previous cue
  is cut at that point (``overlap_mode: cut-at-cue-start``);
- optionally (``flow=True``) consecutive fragments of the same sentence (the
  previous cue ends without sentence-final punctuation) are merged into a
  single utterance placed at the first fragment's timestamp, so whisper line
  splits never turn into unnatural mid-sentence pauses; bare countdown markers
  (``2``, ``3``, ``10``, ...) stay as their own deliberate, spaced cues;
- optionally (``fit=True``) each utterance's trailing silence is tuned so its
  speech fills its slot up to the next timestamp (capped, deliberate long
  pauses in the source document are preserved): removes TTS sentence-silence
  dead air, keeps LRC anchors; wording is never rewritten;
- optionally (``even_counts=True``) runs of consecutive pure-count cues
  ("2", "3", "4", ... or "Twelve. Thirteen.", "Fourteen.", ...) are re-timed
  onto one even grid per run, so transcribe-to-timed-lyrics timestamp jitter
  never distorts the guided counting cadence. The run's first and last count
  anchor the grid; count wording is never rewritten. A cue that contains
  several numbers ("Ten. Eleven.") is partitioned into one utterance per
  spoken number at render time so every count lands on an even beat. Surrounding
  phrase lines keep their authored timestamps.

No TTS model is vendored, and no proprietary speech is reproduced unless the
operator supplies their own lawfully held source material.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
import wave
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from .indexes import load_voice_profiles
from .paths import ensure_dir
from .transcript import load_timed_doc, resolve_timeline
from .utils import OCFError, OCFFileExistsError

DEFAULT_SAMPLE_RATE = 44100

# Per-cue adaptive pacing ("fit") bounds.
# ``FIT_MAX_SCALE`` is the largest stretch applied to a line; slots that would
# need more than this are deliberate source pauses (countdowns, breathing
# waits) and are preserved untouched. ``FIT_MIN_AIR`` seconds of trailing air
# are left before the next cue's ``at`` so words never butt together.
FIT_MAX_SCALE = 1.5
FIT_MIN_AIR = 0.12

# Sentence-boundary detection for ``flow`` merging. A cue is treated as a
# "fragment" (still inside the same spoken sentence) when its text does not
# end with sentence-final punctuation (or a closing quote after it).
SENTENCE_FINAL_RE = re.compile(r"""(?ix)[.!?…]["'”]?$""")
# Bare countdown markers authored as their own consecutive cues ("2", "3",
# "10", "11", "12", ...) stay separate so the guided pacing is preserved.
COUNT_MARKER_RE = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")

# Number-word vocabulary for even-count re-timing. Unknown words make a cue
# "not a pure count", so phrase lines ("Move now to state ten as I guide") and
# transcribed mis-hears that are not numbers are left at their authored
# timestamps.
NUMBER_WORDS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _is_sentence_final(text: str) -> bool:
    return bool(SENTENCE_FINAL_RE.search(text.strip()))


def _is_count_marker(text: str) -> bool:
    return bool(COUNT_MARKER_RE.match(text.strip()))


def _token_value(token: str) -> int | None:
    """Numeric value of a count token ("2", "Ten.", "10th"), else None."""
    stripped = token.strip().strip(".,;:!?…\"'")
    if not stripped:
        return None
    lowered = stripped.lower()
    if lowered in NUMBER_WORDS:
        return NUMBER_WORDS[lowered]
    match = re.match(r"^([+-]?\d+(?:[.,]\d+)?)(?:st|nd|rd|th)?$", lowered)
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    return int(value) if value.is_integer() else None


def _count_token_texts(text: str) -> list[tuple[str, int]]:
    """Per-token ``(text, value)`` pairs when every token is a count, else []."""
    pairs: list[tuple[str, int]] = []
    for token in text.split():
        value = _token_value(token)
        if value is None:
            return []
        pairs.append((token, value))
    return pairs


def _detect_count_runs(timed: list["ResolvedEvent"]) -> list[tuple[int, int]]:
    """Maximal consecutive index runs of pure-count cues in the sorted timeline."""
    runs: list[list[int]] = []
    for index, event in enumerate(timed):
        if not _count_token_texts(event.text or ""):
            continue
        if runs and index == runs[-1][1] + 1:
            runs[-1][1] = index
        else:
            runs.append([index, index])
    return [(start, end) for start, end in runs]


def _even_counts(
    timed: list["ResolvedEvent"],
) -> tuple[list["ResolvedEvent"], dict[str, Any]]:
    """Re-time runs of consecutive pure-count cues onto even grids.

    Each run keeps its first and last count as grid anchors; every spoken
    number in the run (one utterance per number) is placed ``gap`` seconds
    after the previous one. A cue containing several numbers is partitioned
    into its own per-number utterances (``id#k``) so all counts land on the
    even beat. Wording and surrounding cues are never rewritten.
    """
    info: dict[str, Any] = {"runs": []}
    runs = _detect_count_runs(timed)
    if not runs:
        return list(timed), info
    events = list(timed)
    # Process runs in reverse: splitting a multi-number cue grows the event
    # list, which would invalidate the precomputed indices of later runs.
    for start, end in reversed(runs):
        parts: list[dict[str, Any]] = []
        for index in range(start, end + 1):
            source = events[index]
            for token, value in _count_token_texts(source.text or ""):
                parts.append({"source": source, "text": token, "value": value})
        count = len(parts)
        first_at = parts[0]["source"].at
        last_at = parts[-1]["source"].at
        if count < 2 or first_at is None or last_at is None:
            continue
        gap = (last_at - first_at) / (count - 1)
        total: dict[str, int] = {}
        for part in parts:
            total[part["source"].id] = total.get(part["source"].id, 0) + 1
        replaced: list[Any] = []
        seen: dict[str, int] = {}
        for offset, part in enumerate(parts):
            source = part["source"]
            seen[source.id] = seen.get(source.id, 0) + 1
            new_id = source.id if total[source.id] == 1 else f"{source.id}#{seen[source.id]}"
            replaced.append(
                replace(
                    source,
                    id=new_id,
                    text=part["text"],
                    at=round(first_at + offset * gap, 6),
                )
            )
        events[start : end + 1] = replaced
        info["runs"].append(
            {
                "count": count,
                "values": [part["value"] for part in parts],
                "anchor_start": first_at,
                "anchor_end": last_at,
                "gap": round(gap, 6),
            }
        )
    return events, info


def _flow_groups(timed: list["ResolvedEvent"]) -> list[list["ResolvedEvent"]]:
    """Group consecutive sentence-fragment cues into single spoken utterances.

    Consecutive cues are joined while the previous cue's text does not end
    with sentence-final punctuation and is not a bare countdown marker. Each
    group is spoken as one continuous sentence, placed at its first fragment's
    ``at``, so whisper line splits never become unnatural mid-sentence pauses.
    """
    groups: list[list[Any]] = []
    current: list[Any] = []
    for event in timed:
        text = (event.text or "").strip()
        if text and not _is_count_marker(text) and current:
            prev_text = (current[-1].text or "").strip()
            if not _is_sentence_final(prev_text) and not _is_count_marker(prev_text):
                current.append(event)
                continue
        if current:
            groups.append(current)
        current = [event]
    if current:
        groups.append(current)
    return groups

# Probe + invocation metadata for supported TTS binaries. Each entry declares
# how the binary produces audio: "stdout" backends write WAV to stdout with the
# text as an argument; "file" backends require an output path and read the
# text on stdin (e.g. piper -f). Render lambdas receive (exe, voice, wpm,
# model, text, out) and return argv.
BACKENDS: dict[str, dict[str, Any]] = {
    "espeak-ng": {
        "binary": "espeak-ng",
        "default_language": "en-us",
        "default_wpm": 175,
        "mode": "file",
        "render": lambda exe, voice, wpm, model, text, out=None: [
            exe,
            "-w",
            str(out),
            "-v",
            voice,
            "-s",
            str(wpm),
            text,
        ],
    },
    "espeak": {
        "binary": "espeak",
        "default_language": "en",
        "default_wpm": 175,
        "mode": "file",
        "render": lambda exe, voice, wpm, model, text, out=None: [
            exe,
            "-w",
            str(out),
            "-v",
            voice,
            "-s",
            str(wpm),
            text,
        ],
    },
    "piper": {
        "binary": "piper",
        "default_language": "en_US",
        "default_wpm": None,
        "mode": "file",
        "render": lambda exe, voice, wpm, model, text, out=None: (
            [exe, "--model", model, "-f", str(out), "--sentence-silence", "0.4"]
            if model and out is not None
            else [exe, text]
        ),
    },
}

INSTALL_GUIDANCE = (
    "No text-to-speech backend was found on PATH. OCF calls optional external "
    "CLIs only and degrades gracefully when they are missing.\n"
    "  Install one, e.g.:  sudo apt install espeak-ng     (Linux)\n"
    "                      pip install piper-tts          (anywhere)\n"
    "  Re-run detection with:  ocf voice list-backends\n"
    "Existing scripts, validation, exports, and wizards are unaffected."
)


def detect_backends() -> list[dict[str, Any]]:
    """Probe PATH for supported TTS binaries (ordered, deterministic)."""
    found = []
    for name, spec in BACKENDS.items():
        executable = shutil.which(spec["binary"])
        found.append(
            {
                "name": name,
                "binary": spec["binary"],
                "executable": executable,
                "available": executable is not None,
            }
        )
    return found


def first_available_backend() -> str | None:
    """Return the first detected backend name, or None."""
    for entry in detect_backends():
        if entry["available"]:
            return entry["name"]
    return None


def _expand_model_path(value: Any) -> str | None:
    """Expand ``~`` and ``$VAR`` in a configured speech-model path.

    Committed voice profiles stay portable: operators point at their own copy
    (``~/.local/share/piper/en_US-lessac-medium.onnx``) instead of a
    machine-specific absolute path.
    """
    if not value or not isinstance(value, str):
        return None
    return os.path.expanduser(os.path.expandvars(value))


def _load_profile(profile: dict[str, Any]) -> dict[str, Any]:
    name = profile.get("backend") or profile.get("name")
    if name not in BACKENDS:
        raise OCFError(
            f"voice profile backend {name!r} is not supported "
            f"(expected one of {', '.join(sorted(BACKENDS))})"
        )
    return {
        "name": name,
        "binary": BACKENDS[name]["binary"],
        "language": profile.get("language") or BACKENDS[name]["default_language"],
        "wpm": profile.get("words_per_min") or BACKENDS[name]["default_wpm"],
        "model": _expand_model_path(profile.get("piper_model")),
        "profile_id": profile.get("id"),
    }


def resolve_backend(
    spec: str | dict[str, Any] | None, profiles: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Resolve a backend name or voice-profile into an executable spec.

    If ``spec`` matches a voice profile (by id, slug, or name) that profile
    wins; otherwise it is treated as a backend name. ``None`` picks the first
    detected backend.
    """
    profiles = profiles if profiles is not None else load_voice_profiles()
    if isinstance(spec, dict):
        return _load_profile(spec)
    if spec:
        lowered = spec.strip().lower()
        for profile in profiles:
            if any(str(profile.get(key, "")).lower() == lowered for key in ("id", "slug", "name")):
                return _load_profile(profile)
        if lowered not in BACKENDS:
            raise OCFError(
                f"unknown voice/backend {spec!r} (expected a voice profile "
                f"id/slug or one of {', '.join(sorted(BACKENDS))})"
            )
        name = lowered
        spec_entry = BACKENDS[name]
        return {
            "name": name,
            "binary": spec_entry["binary"],
            "language": spec_entry["default_language"],
            "wpm": spec_entry["default_wpm"],
            "model": None,
            "profile_id": None,
        }
    first = first_available_backend()
    if first is None:
        raise OCFError(INSTALL_GUIDANCE)
    return resolve_backend(first, profiles)


def render_cue_wav(spec: dict[str, Any], text: str, timeout: int = 60) -> bytes:
    """Render one cue with a detected backend; return raw WAV bytes."""
    executable = shutil.which(spec["binary"])
    if not executable:
        raise OCFError(
            f"backend {spec['name']!r} (binary {spec['binary']!r}) is not on PATH.\n"
            + INSTALL_GUIDANCE
        )
    spec_mode = BACKENDS[spec["name"]]["mode"]
    out_path: Path | None = None
    if spec_mode == "file":
        out_path = Path(tempfile.mkstemp(suffix=".wav")[1])
    command = BACKENDS[spec["name"]]["render"](
        executable,
        spec["language"],
        spec["wpm"],
        spec.get("model"),
        text,
        out=out_path,
    )
    try:
        result = subprocess.run(
            command,
            input=text.encode("utf-8") if spec_mode == "file" else None,
            capture_output=True,
            timeout=timeout,
        )
    except OSError as exc:
        if out_path is not None:
            out_path.unlink(missing_ok=True)
        raise OCFError(f"failed to run {spec['binary']}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        if out_path is not None:
            out_path.unlink(missing_ok=True)
        raise OCFError(f"{spec['binary']} timed out rendering a cue") from exc
    if result.returncode != 0:
        if out_path is not None:
            out_path.unlink(missing_ok=True)
        detail = (result.stderr or result.stdout or "").decode("utf-8", "replace").strip()
        raise OCFError(
            f"{spec['binary']} failed (exit {result.returncode})"
            + (f": {detail[:160]}" if detail else "")
        )
    if spec_mode == "file":
        if out_path is None or not out_path.is_file():
            raise OCFError(f"{spec['binary']} produced no audio file for a cue")
        try:
            return out_path.read_bytes()
        finally:
            out_path.unlink(missing_ok=True)
    if not result.stdout:
        raise OCFError(f"{spec['binary']} produced no audio for a cue")
    return result.stdout


def _read_pcm_from_bytes(data: bytes) -> tuple[int, list[int]]:
    """Decode mono/stereo 16-bit WAV bytes into (sample_rate, mono samples)."""
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            rate = reader.getframerate()
            channels = reader.getnchannels()
            width = reader.getsampwidth()
            frames = reader.readframes(reader.getnframes())
    except (wave.Error, EOFError) as exc:
        raise OCFError(f"TTS backend returned unreadable audio: {exc}") from exc
    if width != 2:
        raise OCFError(f"TTS backend produced {width * 8}-bit audio; expected 16-bit PCM")
    samples = list(struct_unpack_le16(frames))
    if channels == 2:
        samples = [(samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples) - 1, 2)]
    elif channels != 1:
        raise OCFError(f"unsupported channel count from TTS backend: {channels}")
    return rate, samples


def struct_unpack_le16(frames: bytes) -> list[int]:
    """Unpack signed little-endian 16-bit PCM frames."""
    count = len(frames) // 2
    return [int.from_bytes(frames[i * 2 : i * 2 + 2], "little", signed=True) for i in range(count)]


def _resample(samples: list[int], src_rate: int, dst_rate: int) -> list[int]:
    """Linear-interpolation resample of a mono int16 track."""
    if src_rate == dst_rate:
        return samples
    if src_rate <= 0 or dst_rate <= 0:
        return samples
    ratio = src_rate / dst_rate
    out_length = int(len(samples) / ratio)
    out: list[int] = []
    for index in range(out_length):
        pos = index * ratio
        left = int(pos)
        right = min(left + 1, len(samples) - 1)
        frac = pos - left
        value = samples[left] * (1 - frac) + samples[right] * frac
        out.append(int(value))
    return out


def _silence(length: int) -> list[int]:
    return [0] * length


def _active_bounds(samples: list[int], sample_rate: int, threshold: int = 400) -> tuple[int, int]:
    """First/last sample index of speech (excluding TTS padding silence).

    Uses 10 ms block RMS against ``threshold`` DAC counts (~ -38 dBFS);
    returns (first, last+1) of the voiced run or (0, 0) when no speech.
    """
    block = max(1, sample_rate // 100)
    first = -1
    last = -1
    for start in range(0, len(samples), block):
        chunk = samples[start : start + block]
        if not chunk:
            break
        energy = 0
        for value in chunk:
            energy += value * value
        if energy / len(chunk) > threshold * threshold:
            if first < 0:
                first = start
            last = start + len(chunk)
    if first < 0 or last < 0:
        return 0, 0
    return first, max(last, first + 1)


def _fit_line(cue_samples: list[int], slot: float, sample_rate: int) -> list[int]:
    """Fit one cue to its slot: trim TTS padding, stretch short flow slots.

    Removes the backend's fixed sentence-silence pad (the "robot" breaks) and
    stretches the trimmed speech to fill a slot whose required stretch is at
    most ``FIT_MAX_SCALE``. Large slots (deliberate source pauses, e.g.
    countdowns and guided waiting) are left untouched. Returns the original
    samples when the slot is empty or no fit is needed.
    """
    if slot <= FIT_MIN_AIR:
        return cue_samples
    first, last = _active_bounds(cue_samples, sample_rate)
    active = (last - first) / sample_rate
    if active <= 0.0:
        return cue_samples
    ratio = (slot - FIT_MIN_AIR) / active
    if ratio <= 1.0 or ratio > FIT_MAX_SCALE:
        return cue_samples
    trimmed = cue_samples[first:last]
    return _resample(trimmed, sample_rate, max(1, int(sample_rate * ratio)))


def _clip(value: int) -> int:
    return max(-32768, min(32767, value))


def render_narration(
    doc: dict[str, Any],
    out_path: str | Path,
    *,
    backend: str | dict[str, Any] | None = None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    render_cue: Callable[[str], bytes] | None = None,
    overwrite: bool = True,
    fit: bool = False,
    flow: bool = False,
    even_counts: bool = False,
) -> dict[str, Any]:
    """Render a timed document into a mono 16-bit WAV narration stem.

    Returns render metadata. ``render_cue`` overrides per-cue invocation (used
    by tests to avoid external binaries). ``fit`` enables per-cue adaptive
    pacing: each cue's trailing silence is tuned so its speech fills its slot
    up to the next ``at`` timestamp (see ``_fit_line``). ``flow`` merges
    consecutive sentence-fragment cues (see ``_flow_groups``) so whisper line
    splits never become unnatural mid-sentence pauses; countdown markers stay
    spaced as authored. ``even_counts`` re-times each run of consecutive
    pure-count cues onto an even grid (see ``_even_counts``).
    """
    events, problems = resolve_timeline(doc)
    untimed = [event for event in events if event.at is None]
    if untimed:
        raise OCFError(
            f"cannot render: {len(untimed)} event(s) have no timestamp "
            "(import a timed format first)"
        )
    if problems:
        raise OCFError("timeline problems; fix before rendering: " + " | ".join(problems[:3]))

    spec = resolve_backend(backend)
    timed = sorted(events, key=lambda event: event.at or 0.0)
    even_counts_info: dict[str, Any] | None = None
    if even_counts:
        timed, even_counts_info = _even_counts(timed)
    utterances = _flow_groups(timed) if flow else [[e] for e in timed]

    track: list[int] = []
    cue_stats: list[dict[str, Any]] = []
    for group_index, group in enumerate(utterances):
        text = " ".join((e.text or "").strip() for e in group).strip()
        wav_bytes = render_cue(text) if render_cue is not None else render_cue_wav(spec, text)
        rate, cue_samples = _read_pcm_from_bytes(wav_bytes)
        cue_samples = _resample(cue_samples, rate, sample_rate)
        at = group[0].at or 0.0
        if fit and group_index + 1 < len(utterances):
            next_at = utterances[group_index + 1][0].at or 0.0
            cue_samples = _fit_line(cue_samples, next_at - at, sample_rate)
        offset = int(at * sample_rate)
        needed = offset + len(cue_samples)
        preexisting = len(track)
        cut = offset < preexisting
        if needed > preexisting:
            track.extend(_silence(needed - preexisting))
        for index_of_sample, sample in enumerate(cue_samples):
            track[offset + index_of_sample] = sample
        cue_stats.append(
            {
                "id": "+".join(e.id for e in group),
                "at": at,
                "cues": len(group),
                "text": text,
                "samples": len(cue_samples),
                "cut_previous": bool(cut),
            }
        )

    tail = int(1.0 * sample_rate)
    track.extend(_silence(tail))

    _write_wav(out_path, track, sample_rate, overwrite=overwrite)
    timing_mode = "fit-soft" if fit else "explicit-at-timestamps"
    if flow:
        timing_mode = "timeline-shift" if fit else "natural"
    if even_counts:
        timing_mode = f"{timing_mode}+even-counts"
    return {
        "backend": spec["name"],
        "profile_id": spec.get("profile_id"),
        "sample_rate": sample_rate,
        "channels": 1,
        "duration": round(len(track) / sample_rate, 3),
        "cues": len(cue_stats),
        "utterances": len(cue_stats),
        "overlap_mode": "cut-at-cue-start",
        "timing_mode": timing_mode,
        "cue_stats": cue_stats,
        "even_counts": even_counts_info,
    }


def _write_wav(path: str | Path, samples: list[int], sample_rate: int, *, overwrite: bool) -> None:
    """Atomically write a mono 16-bit PCM WAV file."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        frames = bytearray()
        for sample in samples:
            frames.extend(int(_clip(sample)).to_bytes(2, "little", signed=True))
        writer.writeframes(bytes(frames))
    target = Path(path)
    if target.exists() and not overwrite:
        raise OCFFileExistsError(f"Refusing to overwrite existing file: {target}")
    ensure_dir(target.parent)
    target.write_bytes(buffer.getvalue())


def render_script(
    script: str | Path,
    out_path: str | Path,
    *,
    backend: str | dict[str, Any] | None = None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    render_cue: Callable[[str], bytes] | None = None,
    force: bool = False,
    fit: bool = False,
    flow: bool = False,
    even_counts: bool = False,
) -> int:
    """`ocf voice render SCRIPT [--voice] [--output] [--fit] [--flow] [--even-counts]`."""
    doc = load_timed_doc(Path(script))
    try:
        metadata = render_narration(
            doc,
            out_path,
            backend=backend,
            sample_rate=sample_rate,
            render_cue=render_cue,
            overwrite=force,
            fit=fit,
            flow=flow,
            even_counts=even_counts,
        )
    except OCFFileExistsError as exc:
        raise OCFError(f"{exc} (use --force to overwrite)") from exc
    named = metadata["profile_id"] or metadata["backend"]
    print(
        f"Rendered {metadata['cues']} cue(s) with backend {named!r} "
        f"({metadata['duration']}s, {metadata['sample_rate']} Hz mono) to {out_path}"
    )
    return 0


def voice_doctor() -> int:
    """`ocf voice doctor` — backend + profile health."""
    available = 0
    for entry in detect_backends():
        if entry["available"]:
            available += 1
            print(f"[ok]  {entry['name']}: {entry['executable']}")
        else:
            print(f"[!!] {entry['name']}: not on PATH (install {entry['binary']})")
    profiles = load_voice_profiles()
    print(f"voice profiles: {len(profiles)} in audio/voices/profiles/")
    if profile := next(iter(profiles), None):
        print(f"  default: {profile.get('slug')} (backend {profile.get('backend')})")
    if not profiles:
        print("  (none; copy templates/voice-profile.yaml, e.g. as espeak-en.yaml)")
    if available == 0:
        print("\nNo TTS backend available (optional): " + INSTALL_GUIDANCE.splitlines()[1])
    return 0 if available > 0 else 1


def list_backends_cmd() -> int:
    """`ocf voice list-backends`."""
    for entry in detect_backends():
        state = f"{entry['executable']}" if entry["available"] else "not installed"
        print(f"{entry['name']}: {state}")
    return 0


def list_profiles_cmd() -> int:
    """`ocf voice list` — installed voice profiles."""
    profiles = load_voice_profiles()
    if not profiles:
        print("No voice profiles yet (see: ocf voice doctor).")
        return 0
    for profile in sorted(profiles, key=lambda p: str(p.get("id", ""))):
        print(
            f"  {profile.get('id')}  {profile.get('slug')}  "
            f"backend={profile.get('backend')}  {profile.get('name', '')}"
        )
    return 0
