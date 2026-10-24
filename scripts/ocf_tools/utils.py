"""Small shared utilities: I/O, hashing, and atomic writes."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager, suppress
from contextvars import ContextVar
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
_file_hashes: ContextVar[dict | None] = ContextVar("ocf_verified_file_hashes", default=None)


@contextmanager
def verified_file_hashes():
    """Reuse measured hashes only within a job while file identity is unchanged."""
    token = _file_hashes.set({})
    try:
        yield
    finally:
        _file_hashes.reset(token)


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
    """Publish complete UTF-8 text, exclusively unless overwrite is allowed.

    Raises OCFFileExistsError if the target exists and overwrite is False.
    """
    if path.exists() and not overwrite:
        raise OCFFileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = workspace_temp_file(prefix="ocf-atomic-write-", suffix=".tmp")
    fallback: str | None = None
    publish = os.replace if overwrite else os.link
    try:
        with os.fdopen(fd, "w", encoding=UTF8, newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            publish(tmp, path)
        except OSError as exc:
            if exc.errno != errno.EXDEV:
                raise
            # Stage complete bytes on the target filesystem before publication.
            descriptor, fallback = tempfile.mkstemp(
                dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
            )
            with os.fdopen(descriptor, "w", encoding=UTF8, newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            publish(fallback, path)
            Path(fallback).unlink(missing_ok=True)
            fallback = None
        tmp.unlink(missing_ok=True)
        cleanup_workspace_temp(tmp.parent)
    except BaseException as exc:
        if fallback is not None:
            with suppress(OSError):
                Path(fallback).unlink(missing_ok=True)
        with suppress(OSError):
            tmp.unlink(missing_ok=True)
            cleanup_workspace_temp(tmp.parent)
        record_workspace_failure(tmp.stem, f"atomic write failed for {path}: {exc}")
        if not overwrite and isinstance(exc, FileExistsError):
            raise OCFFileExistsError(f"Refusing to overwrite existing file: {path}") from exc
        if (
            not overwrite
            and isinstance(exc, OSError)
            and exc.errno
            in {
                errno.EPERM,
                errno.ENOSYS,
                errno.EOPNOTSUPP,
                errno.ENOTSUP,
            }
        ):
            raise OCFError(
                f"filesystem does not support atomic no-overwrite publication: {path}: {exc}"
            ) from exc
        raise


def sha256_of_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of a file."""
    cache = _file_hashes.get()
    key = None
    if cache is not None:
        path = path.resolve()
        before = path.stat()
        key = (
            path,
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        if key in cache:
            return cache[key]
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    result = digest.hexdigest()
    if cache is not None:
        after = path.stat()
        if key != (
            path,
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise OCFError(f"file changed while hashing: {path}")
        cache[key] = result
    return result


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
