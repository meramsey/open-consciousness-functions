"""Verified exact-duration Farfield stem cache; unfingerprinted engines bypass it."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from .paths import work_path
from .session_plans import digest
from .utils import OCFError, sha256_of_file, write_text_atomic

MAX_BYTES = 2 * 1024**3


def cache_key(source: Path, seed: int, duration: float) -> str | None:
    from .speech_cache import _active

    if not _active.get():
        return None
    from . import farfield

    status = farfield.check_farfield()
    if not status.available or not status.executable:
        return None
    engine_files = {}
    for presets in farfield._source_preset_dirs():
        for root in (presets.parent / "src/farfield", presets.parent / "farfield"):
            for path in sorted(root.rglob("*.py")):
                engine_files[path.relative_to(presets.parent).as_posix()] = sha256_of_file(path)
    executable = Path(status.executable).resolve()
    prefix = executable.parent.parent
    with executable.open("rb") as handle:
        first = handle.read(512).split(b"\n", 1)[0]
    if first.startswith(b"#!"):
        interpreter = Path(first[2:].decode("utf-8", "replace").strip())
        if interpreter.is_file():
            prefix = interpreter.parent.parent
    for library in (prefix / "lib", prefix / "Lib"):
        for package in ("farfield", "numpy", "scipy", "soundfile"):
            for pattern in (
                f"python*/site-packages/{package}*.dist-info/METADATA",
                f"site-packages/{package}*.dist-info/METADATA",
                f"python*/site-packages/{package}*.dist-info/RECORD",
                f"site-packages/{package}*.dist-info/RECORD",
            ):
                for path in library.glob(pattern):
                    engine_files[path.relative_to(prefix).as_posix()] = sha256_of_file(path)
    if not engine_files:
        return None
    return digest(
        {
            "version": "ocf-dsp-stem/1",
            "preset": sha256_of_file(source),
            "seed": seed,
            "duration": format(duration, ".9f"),
            "engine_version": status.version,
            "executable": sha256_of_file(executable),
            "engine_files": engine_files,
            "adapter": sha256_of_file(Path(__file__).with_name("farfield.py")),
            "renderer": sha256_of_file(Path(__file__).with_name("semantic_dsp.py")),
        }
    )


def lookup(key: str | None) -> Path | None:
    if key is None:
        return None
    root = work_path("cache", "dsp") / key
    if root.is_symlink():
        return None
    try:
        metadata = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        path = root / "stem.wav"
        if (
            metadata["key"] == key
            and not path.is_symlink()
            and path.stat().st_size == metadata["size_bytes"]
            and sha256_of_file(path) == metadata["sha256"]
        ):
            return path
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def store(key: str | None, source: Path) -> bool:
    if key is None:
        return False
    from .dev_jobs import lock

    root = work_path("cache", "dsp") / key
    try:
        with lock("dsp-cache", wait=True):
            if root.is_symlink():
                return False
            if root.exists():
                marker = root / ".ocf-cache-owned"
                if not marker.is_file() or marker.read_text(encoding="ascii") != key:
                    return False
            used = sum(
                p.lstat().st_size for p in work_path("cache", "dsp").glob("*/*") if p.is_file()
            )
            if used + source.stat().st_size + 4096 > MAX_BYTES:
                return False
            root.mkdir(parents=True, exist_ok=True)
            (root / ".ocf-cache-owned").write_text(key, encoding="ascii")
            temporary = root / ("." + uuid4().hex + ".wav")
            try:
                shutil.copyfile(source, temporary)
                checksum = sha256_of_file(temporary)
                if checksum != sha256_of_file(source):
                    return False
                os.replace(temporary, root / "stem.wav")
                write_text_atomic(
                    root / "manifest.json",
                    json.dumps(
                        {"key": key, "sha256": checksum, "size_bytes": source.stat().st_size}
                    )
                    + "\n",
                )
            finally:
                temporary.unlink(missing_ok=True)
            return True
    except (OSError, OCFError):
        return False
