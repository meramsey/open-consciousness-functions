"""Small shared utilities: I/O, hashing, and atomic writes."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import tempfile
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .paths import (
    GENERATED_HEADER,
    cleanup_workspace_temp,
    record_workspace_failure,
    workspace_temp_file,
)

UTF8 = "utf-8"


class OCFError(Exception):
    """Base error for OCF CLI and validation failures."""


class OCFFileExistsError(OCFError):
    """Raised when an atomic write would overwrite an existing file."""


def read_json_object(path: Path) -> dict:
    """Read operator JSON with the same actionable error boundary as YAML."""

    def reject_constant(token):
        raise ValueError(f"non-finite JSON number is not permitted: {token}")

    try:
        value = json.loads(read_text(path), parse_constant=reject_constant)
    except ValueError as exc:
        raise OCFError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise OCFError(f"{path} must contain a JSON object")
    return value


def yaml_safe_load(data: str) -> Any:
    """Parse fresh file content safely; never share mutable parsed objects."""
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    if isinstance(data, str) and len(data) <= 262144:
        return deepcopy(_parsed_yaml(data, loader))
    return yaml.load(data, Loader=loader)


@lru_cache(maxsize=128)
def _parsed_yaml(data: str, loader) -> Any:
    return yaml.load(data, Loader=loader)


def yaml_safe_dump(data: Any) -> str:
    """Serialize YAML deterministically (sort keys, block style)."""
    return yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=True,
        default_flow_style=False,
        width=100,
    )


def read_text(path: Path) -> str:
    """Read a UTF-8 text file, raising a clear error if missing."""
    if not path.exists():
        raise OCFError(f"File not found: {path}")
    try:
        return path.read_text(encoding=UTF8)
    except (OSError, UnicodeError) as exc:
        raise OCFError(f"Cannot read UTF-8 text from {path}: {exc}") from exc


def write_text_atomic(path: Path, content: str, *, overwrite: bool = True) -> None:
    """Write UTF-8 text atomically (temp file + os.replace).

    Raises OCFFileExistsError if the target exists and overwrite is False.
    """
    if path.exists() and not overwrite:
        raise OCFFileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = workspace_temp_file(prefix="ocf-atomic-write-", suffix=".tmp")
    fallback: str | None = None
    try:
        with os.fdopen(fd, "w", encoding=UTF8, newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.replace(tmp, path)
        except OSError as exc:
            if exc.errno != errno.EXDEV:
                raise
            # Atomic rename is only possible within the explicitly selected
            # output filesystem; this fallback is confined to that target.
            descriptor, fallback = tempfile.mkstemp(
                dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
            )
            with os.fdopen(descriptor, "w", encoding=UTF8, newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(fallback, path)
            fallback = None
            tmp.unlink(missing_ok=True)
        cleanup_workspace_temp(tmp.parent)
    except BaseException as exc:
        if fallback is not None:
            Path(fallback).unlink(missing_ok=True)
        record_workspace_failure(tmp.stem, f"atomic write failed for {path}: {exc}")
        raise


def sha256_of_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(text: str) -> str:
    """Convert arbitrary text into a kebab-case slug."""
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_", "/", "\\", ":", "."):
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def generated_content(body: str) -> str:
    """Prepend the mandatory generated-file banner to derived content."""
    return f"{GENERATED_HEADER}\n\n{body}"


def current_date() -> str:
    """Return today's local calendar date in ISO format."""
    import datetime

    return datetime.date.today().isoformat()
