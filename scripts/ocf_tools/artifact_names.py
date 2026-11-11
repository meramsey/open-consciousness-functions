"""Deterministic, filesystem-safe names for localized release artifacts."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .locale import normalize_tag
from .utils import OCFError

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_WHITESPACE = re.compile(r"\s+")
_DASHES = re.compile(r"-+")
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_EXTENSIONS = {
    "mp3",
    "flac",
    "wav",
    "txt",
    "json",
    "png",
    "jpg",
    "jpeg",
    "lrc",
    "srt",
    "vtt",
    "timing.json",
}


def safe_component(value: str, *, max_length: int = 72) -> str:
    """Normalize one filename component without permitting path syntax."""
    text = unicodedata.normalize("NFC", str(value)).strip()
    text = _INVALID.sub("-", text)
    text = _WHITESPACE.sub("-", text)
    text = _DASHES.sub("-", text).strip(" .-")
    if not text or text in {".", ".."}:
        raise OCFError("artifact filename component is empty or unsafe")
    if text.split(".", 1)[0].upper() in _RESERVED:
        text = f"_{text}"
    text = text[:max_length].rstrip(" .-")
    if not text:
        raise OCFError("artifact filename component is empty after normalization")
    return text


@dataclass
class ArtifactNamer:
    """Build readable artifact filenames and disambiguate case-insensitively."""

    max_filename_length: int = 180
    _used: set[str] = field(default_factory=set, init=False, repr=False)

    def filenames(
        self,
        function_id: str | None,
        title: str,
        locale: str,
        artifact_types: list[str],
        *,
        variant: str | None = None,
        version: str | None = None,
        session_kind: str = "function",
    ) -> dict[str, str]:
        """Reserve one shared stem, including at length/collision limits."""
        extensions = [value.lower().lstrip(".") for value in artifact_types]
        if not extensions or any(value not in _EXTENSIONS for value in extensions):
            raise OCFError("unsupported or empty artifact group")
        longest = max(extensions, key=len)
        while True:
            anchor = self.filename(
                function_id,
                title,
                locale,
                longest,
                variant=variant,
                version=version,
                session_kind=session_kind,
            )
            stem = anchor[: -len(longest) - 1]
            names = {extension: stem + "." + extension for extension in extensions}
            if all(
                name.casefold() not in self._used
                for extension, name in names.items()
                if extension != longest
            ):
                self._used.update(name.casefold() for name in names.values())
                return names

    def filename(
        self,
        function_id: str | None,
        title: str,
        locale: str,
        artifact_type: str,
        *,
        variant: str | None = None,
        version: str | None = None,
        session_kind: str = "function",
    ) -> str:
        """Return a stable filename such as ``OCF-BOD-010 - Nutricia - en-US.flac``."""
        if session_kind == "preparation-learning":
            if function_id is not None:
                raise OCFError("standalone preparation must not have a function identifier")
            identity = "00"
        elif (
            session_kind == "function"
            and isinstance(function_id, str)
            and re.fullmatch(r"OCF-[A-Z]{3}-[A-Z0-9]{3,4}", function_id)
        ):
            identity = function_id
        else:
            raise OCFError(f"invalid OCF export identity: {function_id!r} / {session_kind!r}")
        normalized_locale = normalize_tag(locale)
        if not normalized_locale:
            raise OCFError(f"invalid locale: {locale!r}")
        extension = artifact_type.lower().lstrip(".")
        if extension not in _EXTENSIONS:
            raise OCFError(f"unsupported artifact type: {artifact_type!r}")
        pieces = [identity, safe_component(title, max_length=96), normalized_locale]
        if variant:
            pieces.append(safe_component(variant, max_length=32))
        if version:
            pieces.append(f"v{safe_component(version, max_length=24)}")
        stem = " - ".join(pieces)
        suffix = f".{extension}"
        if len(stem) + len(suffix) > self.max_filename_length:
            stem = stem[: self.max_filename_length - len(suffix)].rstrip(" .-")
        candidate = stem + suffix
        key = candidate.casefold()
        collision = 2
        while key in self._used:
            marker = f" ({collision})"
            candidate = (
                stem[: self.max_filename_length - len(suffix) - len(marker)] + marker + suffix
            )
            key = candidate.casefold()
            collision += 1
        self._used.add(key)
        return candidate


def listener_export_names(
    function_id, title, locale, artifact_types, *, voice_label, version, session_kind="function"
):
    """Standard delivery names, distinct from low-level scratch/engine filenames.

    Explicit destinations remain caller-owned. The returned folder is an edition
    stem; standalone preparation sorts first without inventing a function ID.
    """
    if not isinstance(voice_label, str) or not voice_label.strip():
        raise OCFError("listener export requires a voice display label")
    if not isinstance(version, str) or not version.strip():
        raise OCFError("listener export requires an edition version")
    voice = safe_component(voice_label, max_length=32)
    edition = safe_component(version, max_length=24)
    normalized = normalize_tag(locale)
    if not normalized:
        raise OCFError("listener export requires a valid locale")
    identity = "00" if session_kind == "preparation-learning" else str(function_id)
    # Shorten the title first: never silently drop the voice or version suffix.
    extension_length = max((len(x.lstrip(".")) for x in artifact_types), default=0)
    title_budget = min(
        96,
        180 - len(identity) - len(normalized) - len(voice) - len(edition) - 14 - extension_length,
    )
    if title_budget < 1:
        raise OCFError("listener export identity exceeds the filename limit")
    shortened_title = safe_component(title, max_length=title_budget)
    while True:
        names = ArtifactNamer().filenames(
            function_id,
            shortened_title,
            locale,
            artifact_types,
            variant=voice,
            version=edition,
            session_kind=session_kind,
        )
        if all(len(name.encode("utf-8")) <= 240 for name in names.values()):
            break
        shortened_title = shortened_title[:-1].rstrip(" .-")
        if not shortened_title:
            raise OCFError("listener export identity exceeds the filename byte limit")
    extension = next(iter(names))
    directory = names[extension][: -len(extension) - 1]
    return {
        "directory": directory,
        "files": names,
        "session_kind": session_kind,
        "sort_order": 0 if session_kind == "preparation-learning" else 1,
    }
