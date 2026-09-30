"""Small shared utilities: I/O, hashing, and atomic writes."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .paths import GENERATED_HEADER

UTF8 = "utf-8"


class OCFError(Exception):
    """Base error for OCF CLI and validation failures."""


class OCFFileExistsError(OCFError):
    """Raised when an atomic write would overwrite an existing file."""


def yaml_safe_load(data: str) -> Any:
    """Parse YAML with safe loader."""
    return yaml.safe_load(data)


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
    return path.read_text(encoding=UTF8)


def write_text_atomic(path: Path, content: str, *, overwrite: bool = True) -> None:
    """Write UTF-8 text atomically (temp file + os.replace).

    Raises OCFFileExistsError if the target exists and overwrite is False.
    """
    if path.exists() and not overwrite:
        raise OCFFileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=UTF8, newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
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
    """Return today's ISO date (UTC)."""
    import datetime

    return datetime.date.today().isoformat()
