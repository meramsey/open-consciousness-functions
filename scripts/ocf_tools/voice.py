"""Narration speech rendering for OCF timed scripts.

Renders each timed cue of an OCF timed-YAML document to audio and assembles it
into a single WAV narration stem. Text-to-speech is provided by optional
external CLIs (``espeak-ng``, ``espeak``, or ``piper``); like Farfield, these
are detected on PATH and the toolchain degrades gracefully with installation
guidance when none is available.

Timing model (v0.4 - original, deterministic, and documented in the render
manifest):

- fixed cues retain their timestamps; end-relative cues follow measured speech;
- cues are rendered independently so wording and pacing are never rewritten;
- fixed speech overlaps fail before artifact writing; explicit reflow delays
  eligible narration instead of overwriting previous speech;
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
import json
import os
import re
import shutil
import subprocess
import wave
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .indexes import load_voice_profiles
from .locale import document_key_usage, iter_events, locale_language, normalize_tag
from .paths import (
    cleanup_workspace_temp,
    ensure_dir,
    record_workspace_failure,
    workspace_run,
    workspace_temp_file,
)
from .transcript import ResolvedEvent, load_timed_doc, resolve_timeline
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


def _detect_count_runs(timed: list[ResolvedEvent]) -> list[tuple[int, int]]:
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
    timed: list[ResolvedEvent],
) -> tuple[list[ResolvedEvent], dict[str, Any]]:
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
        if count >= 2 and first_at is not None and last_at is not None:
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


def _flow_groups(timed: list[ResolvedEvent]) -> list[list[ResolvedEvent]]:
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
        # espeak-ng carries a large multilingual voice set and names voices in
        # lowercase with a region suffix (en-us, es, de, zh-cmn).
        "locale_style": "language-region",
        "phonemes": "[[...]]",
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
        "locale_style": "language-only",
        "phonemes": None,
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
        # A piper voice is whatever model is installed, so the locale is carried
        # as metadata and a mismatch is reported rather than silently rendered.
        "locale_style": "model-bound",
        "phonemes": None,
        "default_sentence_silence_s": 0.4,
        "render": lambda exe, voice, wpm, model, text, out=None: (
            [exe, "--model", model, "-f", str(out), "--sentence-silence", "0.4"]
            if model and out is not None
            else [exe, text]
        ),
    },
}

LOCALE_STYLES = ("lower-hyphen", "language-only", "model")


@dataclass
class NarrationRequest:
    """Everything a TTS backend needs for one cue, in one place.

    Carries the target locale, the text already resolved from the locale pack
    (never raw English defaults), the selected backend and voice, the timing
    options the backend honours, and any pronunciation hints. Keeping this
    explicit is what stops a render from quietly picking the wrong language.
    """

    locale: str
    text: str
    backend: str
    voice: str | None = None
    sample_rate: int = DEFAULT_SAMPLE_RATE
    words_per_min: int | None = None
    preferred_duration: float | None = None
    pronunciation: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    narration_key: str | None = None
    event_id: str | None = None
    profile_id: str | None = None

    def backend_text(self, backend: str | None = None) -> str:
        """Text as the backend should receive it, with hints applied.

        Pronunciation hints are applied only when the backend understands the
        syntax. The visible text, subtitles, and transcript are never touched.
        """
        name = backend or self.backend
        return apply_pronunciation(self.text, self.pronunciation, name)

    def as_metadata(self) -> dict[str, Any]:
        """Serializable description for render manifests."""
        return {
            "locale": self.locale,
            "backend": self.backend,
            "voice": self.voice,
            "words_per_min": self.words_per_min,
            "preferred_duration": self.preferred_duration,
            "narration_key": self.narration_key,
            "profile_id": self.profile_id,
            "pronunciation_hints": sorted(self.pronunciation),
        }


def apply_pronunciation(
    text: str, hints: Mapping[str, Mapping[str, str]] | None, backend: str
) -> str:
    """Substitute pronunciation hints into ``text`` for ``backend``.

    A hint is written for one backend syntax; backends that do not support that
    syntax get the plain text back, unchanged.
    """
    if not hints:
        return text
    syntax = BACKENDS.get(backend, {}).get("phonemes")
    if not syntax:
        return text
    out = text
    applied = 0
    for token, per_backend in hints.items():
        hint = per_backend.get(backend)
        if not hint or token not in out:
            continue
        out = out.replace(token, hint)
        applied += 1
    return out


# How each backend wants to be told which language to speak. Surfaced by
# `ocf voice list-backends` so an operator knows before rendering whether a
# backend can follow a locale at all.
LOCALE_STYLE_LABELS = {
    "language-only": "language only (en, es) - any regional tag narrows to it",
    "language-region": "language-region (en-us, pt-br)",
    "model-bound": "bound to its voice model - a locale needs a matching model",
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
        "piper_length_scale": profile.get("piper_length_scale"),
        "piper_sentence_silence_s": profile.get("piper_sentence_silence_s"),
        "profile_id": profile.get("id"),
    }


def _locale_voice_name(backend: str, locale: str | None) -> str | None:
    """Map a BCP-47 locale onto a backend voice name.

    ``en-US`` -> ``en-us`` for espeak-ng, ``en`` for espeak, and nothing at all
    for piper, whose voice is whichever model the operator installed.
    """
    if not locale:
        return None
    style = BACKENDS.get(backend, {}).get("locale_style", "language-only")
    if style == "model-bound":
        return None
    language = locale_language(locale)
    if style == "language-only":
        return language
    return locale.replace("-", "-").lower()


def backend_locale_support(backend: str) -> dict[str, Any]:
    """Report what a backend can do with locales and pronunciation."""
    spec = BACKENDS.get(backend, {})
    return {
        "backend": backend,
        "locale_style": spec.get("locale_style", "language-only"),
        "pronunciation_syntax": spec.get("phonemes"),
        "default_language": spec.get("default_language"),
    }


def resolve_backend(
    spec: str | dict[str, Any] | None,
    profiles: list[dict[str, Any]] | None = None,
    *,
    locale: str | None = None,
    catalog: Any = None,
) -> dict[str, Any]:
    """Resolve a backend name or voice-profile into an executable spec.

    If ``spec`` matches a voice profile (by id, slug, or name) that profile
    wins; otherwise it is treated as a backend name. ``None`` picks the first
    detected backend. When ``locale`` is given, the voice is retargeted at it:
    a profile whose language already matches is preferred, and any mismatch is
    reported in ``notes`` rather than silently rendering the wrong language.
    """
    profiles = profiles if profiles is not None else load_voice_profiles()
    if isinstance(spec, dict):
        resolved = _load_profile(spec)
        return _retarget_locale(resolved, locale, catalog)
    if spec:
        lowered = spec.strip().lower()
        for profile in profiles:
            if any(str(profile.get(key, "")).lower() == lowered for key in ("id", "slug", "name")):
                return _retarget_locale(_load_profile(profile), locale, catalog)
        if lowered not in BACKENDS:
            raise OCFError(
                f"unknown voice/backend {spec!r} (expected a voice profile "
                f"id/slug or one of {', '.join(sorted(BACKENDS))})"
            )
        name = lowered
        spec_entry = BACKENDS[name]
        return _retarget_locale(
            {
                "name": name,
                "binary": spec_entry["binary"],
                "language": spec_entry["default_language"],
                "wpm": spec_entry["default_wpm"],
                "model": None,
                "piper_length_scale": None,
                "piper_sentence_silence_s": None,
                "profile_id": None,
            },
            locale,
            catalog,
        )
    first = first_available_backend()
    if first is None:
        raise OCFError(INSTALL_GUIDANCE)
    return resolve_backend(first, profiles, locale=locale, catalog=catalog)


def _retarget_locale(spec: dict[str, Any], locale: str | None, catalog: Any) -> dict[str, Any]:
    """Point a resolved backend spec at ``locale``, recording any caveats."""
    if not locale:
        return spec
    from .locale import LocalizationError, normalize_tag
    from .locale import locale_language as language_of

    try:
        normalized = normalize_tag(locale) or locale
    except LocalizationError:
        normalized = str(locale)
    spec["locale"] = normalized
    spec["notes"] = []
    voice_name = _locale_voice_name(spec["name"], normalized)
    configured = str(spec.get("language") or "")
    configured_language = language_of(configured) if configured else ""
    if voice_name:
        if configured and configured.lower() != voice_name:
            subject = spec.get("profile_id") or f"backend {spec['name']} default"
            spec["notes"].append(
                f"{subject} is set to {configured!r}; rendering {normalized} with voice "
                f"{voice_name!r}"
            )
        spec["language"] = voice_name
    else:
        # Model-bound backend: report the gap instead of pretending it is fine.
        model = spec.get("model")
        if model:
            config = Path(str(model) + ".json")
            if config.is_file():
                try:
                    metadata = json.loads(config.read_text(encoding="utf-8"))
                    if not isinstance(metadata, dict):
                        raise ValueError("model metadata must be an object")
                    language = metadata.get("language") or {}
                    if not isinstance(language, dict):
                        raise ValueError("model language metadata must be an object")
                    code = language.get("code")
                    if code is not None and not isinstance(code, str):
                        raise ValueError("model language code must be text")
                    configured = code or configured
                except (ValueError, OSError) as exc:
                    raise LocalizationError(
                        f"cannot read Piper model locale: {config}: {exc}"
                    ) from exc
                configured_language = language_of(configured)
                spec["language"] = configured
        if configured_language and configured_language != language_of(normalized):
            raise LocalizationError(
                f"{spec['name']} model is bound to {configured!r} and cannot render "
                f"{normalized}; select a matching model"
            )
        spec["locale"] = normalized
    if catalog is not None and normalized not in getattr(catalog, "packs", {}):
        spec["notes"].append(f"no locale pack provides {normalized}")
    return spec


def check_backend_locale(spec: dict[str, Any]) -> None:
    """Probe an installed language-switchable backend before synthesizing speech."""
    if not spec.get("locale") or spec["name"] == "piper":
        return
    executable = shutil.which(spec["binary"])
    if not executable:
        raise OCFError(INSTALL_GUIDANCE)
    result = workspace_run(
        [executable, f"--voices={spec['language']}"], capture_output=True, text=True, timeout=15
    )
    if result.returncode or len(result.stdout.strip().splitlines()) < 2:
        raise OCFError(
            f"backend {spec['name']} does not support requested TTS locale {spec['locale']}"
        )


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
        descriptor, out_path = workspace_temp_file(prefix="ocf-voice-cue-", suffix=".wav")
        os.close(descriptor)
    command = BACKENDS[spec["name"]]["render"](
        executable,
        spec["language"],
        spec["wpm"],
        spec.get("model"),
        text,
        out=out_path,
    )
    if spec["name"] == "piper":
        length_scale = spec.get("piper_length_scale")
        if length_scale is not None:
            command.extend(["--length-scale", str(length_scale)])
        sentence_silence = spec.get("piper_sentence_silence_s")
        if sentence_silence is not None:
            silence_index = command.index("--sentence-silence")
            command[silence_index + 1] = str(sentence_silence)
    try:
        result = workspace_run(
            command,
            input=text.encode("utf-8") if spec_mode == "file" else None,
            capture_output=True,
            timeout=timeout,
        )
    except OSError as exc:
        if out_path is not None:
            record_workspace_failure(out_path.stem, f"{spec['binary']} cue render failed: {exc}")
        raise OCFError(f"failed to run {spec['binary']}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        if out_path is not None:
            record_workspace_failure(out_path.stem, f"{spec['binary']} cue render timed out")
        raise OCFError(f"{spec['binary']} timed out rendering a cue") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or b"").decode("utf-8", "replace").strip()
        if out_path is not None:
            record_workspace_failure(
                out_path.stem,
                f"{spec['binary']} failed (exit {result.returncode}): {detail[:1000]}",
            )
        raise OCFError(
            f"{spec['binary']} failed (exit {result.returncode})"
            + (f": {detail[:160]}" if detail else "")
        )
    if spec_mode == "file":
        assert out_path is not None  # allocated above for every file-mode request
        if not out_path.is_file():
            record_workspace_failure(
                out_path.stem, f"{spec['binary']} produced no audio file for a cue"
            )
            raise OCFError(f"{spec['binary']} produced no audio file for a cue")
        try:
            if out_path.stat().st_size == 0:
                raise OCFError(f"{spec['binary']} produced empty audio for a cue")
            audio = out_path.read_bytes()
        except BaseException as exc:
            record_workspace_failure(out_path.stem, f"cue output verification failed: {exc}")
            raise
        else:
            out_path.unlink(missing_ok=True)
            if (out_path.parent / ".ocf-owned").is_file():
                cleanup_workspace_temp(out_path.parent)
            return audio
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
        # Positive block size and start < len(samples) guarantee a nonempty slice.
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


def _pronunciation_hints(
    doc: dict[str, Any], locale: str | None, catalog: Any = None, backend: str | None = None
) -> dict[str, dict[str, Any]]:
    """Map event id -> backend hints from the resolved document's resources.

    Hints live in the locale pack beside the message, so a translator can fix a
    pronunciation without touching the document or the render code.
    """
    if not locale:
        return {}
    from .locale import LocaleCatalog

    catalog = catalog or LocaleCatalog()
    origins = {
        item.get("id"): item.get("locale")
        for item in (doc.get("narration") or {}).get("resolved", [])
    }
    hints: dict[str, dict[str, Any]] = {}
    for event in iter_events(doc):
        key = event.get("narration_key")
        if not key:
            continue
        entry, _ = catalog.resource(
            str(key), origins.get(event.get("id")) or locale, domain="narration", fallback=False
        )
        for requirement in entry.required_pronunciation:
            token = str((event.get("variables") or {}).get(requirement, requirement))
            if (
                not backend
                or not entry.hint_for(backend, token)
                or not BACKENDS[backend].get("phonemes")
            ):
                raise OCFError(
                    f"event {event.get('id')}: required pronunciation for {token!r} is unavailable on {backend}"
                )
        if entry is not None and entry.pronunciation:
            hints[str(event.get("id", ""))] = dict(entry.pronunciation)
    return hints


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
    locale: str | None = None,
    catalog: Any = None,
    strict: bool = True,
    recordings: str | Path | None = None,
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

    ``locale`` selects and records the target language. A document that uses
    ``narration_key`` is resolved against that locale first, strictly by
    default: rendering must not start when required spoken narration is missing.
    """
    backend = backend or doc.get("voice_profile")
    if locale is not None or document_key_usage(doc)["keyed"]:
        from .locale import LocaleCatalog, document_locale, resolve_document

        catalog = catalog or LocaleCatalog()
        target = normalize_tag(locale) if locale else document_locale(doc)
        doc = resolve_document(doc, target, catalog=catalog, strict=strict)
        locale = target
    from .validators import validate_command_ownership, validate_narration_hygiene

    validation = validate_command_ownership(doc, Path(out_path))
    validation.extend(validate_narration_hygiene(doc, Path(out_path), catalog))
    if validation.errors:
        raise OCFError(
            "pre-render validation: " + " | ".join(issue.message for issue in validation.errors)
        )
    from .semantics import bind_document_cues

    auditory_cues = bind_document_cues(doc)
    recording_audio = None
    recording_provenance = None
    if recordings is not None:
        if backend is not None or render_cue is not None or fit or flow or even_counts:
            raise OCFError(
                "recordings are an independent voice source; omit TTS backend and speech-retiming flags"
            )
        from .locale import document_locale
        from .recordings import prepare_recordings

        locale = locale or document_locale(doc)
        recording_audio, recording_provenance = prepare_recordings(recordings, doc, locale)
        spec = {"name": "prerecorded", "locale": locale, "language": locale, "notes": []}
    elif backend == "disabled":
        if any(event.get("text", "").strip() for event in iter_events(doc)):
            raise OCFError(
                "disabled narration requires a speech-free semantic document; required speech cannot be silently dropped"
            )
        recording_audio = {}
        recording_provenance = {"source_type": "disabled", "explicit": True}
        spec = {"name": "disabled", "locale": locale, "language": None, "notes": []}
    else:
        spec = resolve_backend(backend, locale=locale, catalog=catalog)
    if render_cue is None and recording_audio is None:
        check_backend_locale(spec)
    for note in spec.get("notes") or []:
        print(f"Warning: {note}")

    events, problems = resolve_timeline(doc)
    untimed = [event for event in events if event.at is None]
    if untimed:
        raise OCFError(
            f"cannot render: {len(untimed)} event(s) have no timestamp "
            "(import a timed format first)"
        )
    if problems:
        raise OCFError("timeline problems; fix before rendering: " + " | ".join(problems[:3]))

    hints_by_event = (
        {}
        if recording_audio is not None
        else _pronunciation_hints(doc, locale, catalog, spec["name"])
    )
    timed = sorted(events, key=lambda event: event.at or 0.0)
    originals = {event["id"]: event for event in iter_events(doc)}
    has_semantics = any(event.get("semantic") or event.get("after") for event in originals.values())
    even_counts_info: dict[str, Any] | None = None
    if even_counts and not has_semantics:
        timed, even_counts_info = _even_counts(timed)
    elif even_counts:
        even_counts_info = {
            "runs": [],
            "note": "semantic anchors preserved; legacy number-word retiming skipped",
        }
    # Semantic boundaries must not be merged by punctuation heuristics.
    spoken = [event for event in timed if (event.text or "").strip()]
    utterances = (
        _flow_groups(spoken) if flow and not has_semantics else [[event] for event in spoken]
    )

    cue_stats: list[dict[str, Any]] = []
    hints_applied = 0
    rendered = {}
    scheduling_events = []
    event_to_group = {}
    source_to_groups = {}
    for group_index, group in enumerate(utterances):
        text = " ".join((e.text or "").strip() for e in group).strip()
        display_text = text
        hints: dict[str, Any] = {}
        for event in group:
            hints.update(hints_by_event.get(event.id, {}))
        if hints:
            before = text
            text = apply_pronunciation(text, hints, spec["name"])
            if text != before:
                hints_applied += 1
        if recording_audio is not None:
            wav_bytes = recording_audio[group[0].id]
        else:
            wav_bytes = render_cue(text) if render_cue is not None else render_cue_wav(spec, text)
        rate, cue_samples = _read_pcm_from_bytes(wav_bytes)
        cue_samples = _resample(cue_samples, rate, sample_rate)
        at = group[0].at or 0.0
        if fit and group_index + 1 < len(utterances):
            next_at = utterances[group_index + 1][0].at or 0.0
            cue_samples = _fit_line(cue_samples, next_at - at, sample_rate)
        group_id = "+".join(event.id for event in group)
        source_ids = list(
            dict.fromkeys(
                event.id if event.id in originals else event.id.rsplit("#", 1)[0] for event in group
            )
        )
        first = deepcopy(originals[source_ids[0]])
        first["id"] = group_id
        if "at" in first:
            first["at"] = at
        first["text"] = display_text
        scheduling_events.append(first)
        rendered[group_id] = cue_samples
        for event in group:
            event_to_group[event.id] = group_id
        for identifier in source_ids:
            event_to_group[identifier] = group_id
            source_to_groups.setdefault(identifier, []).append(group_id)
        cue_stats.append(
            {
                "id": group_id,
                "source_ids": source_ids,
                "at": at,
                "cues": len(group),
                "text": text,
                "display_text": display_text,
                "samples": len(cue_samples),
                "duration": round(len(cue_samples) / sample_rate, 3),
                "cut_previous": False,
            }
        )

    for event in iter_events(doc):
        if event["id"] not in event_to_group:
            scheduling_events.append(deepcopy(event))
    for event in scheduling_events:
        if event.get("after"):
            event["after"] = event_to_group.get(event["after"], event["after"])
    from .timing import schedule_timeline

    durations = {identifier: len(samples) / sample_rate for identifier, samples in rendered.items()}
    scheduled = schedule_timeline({"timeline": scheduling_events}, durations)
    actual = {event["id"]: event for event in scheduled}
    track: list[int] = _silence(
        int(max((event["end"] for event in scheduled), default=0) * sample_rate)
    )
    for cue in cue_stats:
        cue["at"] = actual[cue["id"]]["at"]
        offset = int(round(cue["at"] * sample_rate))
        samples = rendered[cue["id"]]
        if offset + len(samples) > len(track):
            track.extend(_silence(offset + len(samples) - len(track)))
        track[offset : offset + len(samples)] = samples
    for binding in auditory_cues:
        identifier = event_to_group.get(binding["event_id"], binding["event_id"])
        binding["at"] = actual[identifier]["at"]
    seen_bindings = set()
    for binding in auditory_cues:
        signature = (binding["identity"], binding["at"])
        if signature in seen_bindings and not originals[binding["event_id"]].get(
            "intentional_repeat"
        ):
            raise OCFError(f"duplicate auditory cue at resolved anchor: {binding['identity']}")
        seen_bindings.add(signature)
    event_timing = []
    for original in iter_events(doc):
        identifier = event_to_group.get(original["id"], original["id"])
        groups = source_to_groups.get(original["id"], [identifier])
        event_timing.append(
            {
                **actual[identifier],
                "id": original["id"],
                "utterance_id": identifier,
                "utterance_ids": groups,
                "at": min(actual[group]["at"] for group in groups),
                "end": max(actual[group]["end"] for group in groups),
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
        "narration_source": recording_provenance,
        "profile_id": spec.get("profile_id"),
        "locale": spec.get("locale"),
        "voice": spec.get("language"),
        "voice_options": (
            {
                "piper_length_scale": spec.get("piper_length_scale"),
                "piper_sentence_silence_s": (
                    spec.get("piper_sentence_silence_s")
                    if spec.get("piper_sentence_silence_s") is not None
                    else BACKENDS[spec["name"]].get("default_sentence_silence_s")
                ),
            }
            if spec["name"] == "piper"
            else {}
        ),
        "locale_notes": list(spec.get("notes") or []),
        "pronunciation_hints": hints_applied,
        "sample_rate": sample_rate,
        "channels": 1,
        "duration": round(len(track) / sample_rate, 3),
        "cues": len(cue_stats),
        "utterances": len(cue_stats),
        "overlap_mode": "reject-fixed-overlap",
        "timing_mode": timing_mode,
        "cue_stats": cue_stats,
        "event_timing": event_timing,
        "auditory_cues": auditory_cues,
        "narration_resolution": doc.get("narration"),
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
    locale: str | None = None,
    strict: bool = True,
    recordings: str | Path | None = None,
) -> int:
    """`ocf voice render SCRIPT [--voice] [--locale] [--output] [--fit] [--flow] [--even-counts]`."""
    doc = load_timed_doc(Path(script))
    sidecar = Path(out_path).with_suffix(".render.yaml")
    if sidecar.exists() and not force:
        raise OCFError(f"Refusing to overwrite existing timing manifest: {sidecar} (use --force)")
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
            locale=locale,
            strict=strict,
            recordings=recordings,
        )
    except OCFFileExistsError as exc:
        raise OCFError(f"{exc} (use --force to overwrite)") from exc
    from .utils import sha256_of_file, write_text_atomic, yaml_safe_dump

    cues = [
        {
            **cue,
            "duration": cue["samples"] / metadata["sample_rate"],
            "end": cue["at"] + cue["samples"] / metadata["sample_rate"],
        }
        for cue in metadata["cue_stats"]
    ]
    with wave.open(str(out_path)) as reader:
        total = reader.getnframes() / reader.getframerate()
    write_text_atomic(
        sidecar,
        yaml_safe_dump(
            {
                **metadata,
                "source_script_sha256": sha256_of_file(Path(script)),
                "voice": {
                    "backend": metadata["backend"],
                    "locale": metadata["locale"],
                    "language": metadata["voice"],
                    "profile_id": metadata["profile_id"],
                    "options": metadata.get("voice_options", {}),
                },
                "output_sha256": sha256_of_file(Path(out_path)),
                "total_duration_s": total,
                "narration_timing": {"measured": True, "cues": cues},
            }
        ),
    )
    named = metadata["profile_id"] or metadata["backend"]
    print(
        f"Rendered {metadata['cues']} cue(s) with backend {named!r} "
        f"({metadata['duration']}s, {metadata['sample_rate']} Hz mono) to {out_path}"
    )
    if metadata.get("locale"):
        print(f"  locale {metadata['locale']} (voice {metadata.get('voice')})")
    if metadata.get("pronunciation_hints"):
        print(f"  applied {metadata['pronunciation_hints']} pronunciation hint(s)")
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
        support = backend_locale_support(entry["name"])
        style = LOCALE_STYLE_LABELS.get(
            support.get("locale_style"), support.get("locale_style", "language-only")
        )
        syntax = support.get("pronunciation_syntax")
        detail = f"    locale: {style}; default language {support.get('default_language')}"
        detail += f"; pronunciation syntax {syntax!r}" if syntax else "; no pronunciation input"
        print(detail)
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
