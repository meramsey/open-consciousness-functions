"""Preserve local generated auditions without rebuilding speech or changing bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def preserve(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if output == source or output.is_relative_to(source):
        raise ValueError("preservation output must be outside the source directory")
    paths = sorted(source.rglob("*") if source.is_dir() else [source])
    files = [path for path in paths if path.is_file()]
    if not files:
        raise ValueError(f"no audition artifacts available: {source}")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": "1.0", "operation": "byte-preservation; no generation or approval", "files": []}
    for path in files:
        relative = path.relative_to(source) if source.is_dir() else Path(path.name)
        target = output / relative
        before = fingerprint(path)
        if target.exists() and fingerprint(target) != before:
            raise ValueError(f"refusing to overwrite different existing artifact: {target}")
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        after = fingerprint(target)
        if before != after or fingerprint(path) != before:
            raise ValueError(f"source/copy identity changed: {path}")
        manifest["files"].append({"file": relative.as_posix(), "sha256": after, "bytes": target.stat().st_size})
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = preserve(args.source, args.output)
    name = args.source.name if args.source.is_file() else "directory"
    (args.output / f"preservation-{name}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(data['files'])} preserved artifact(s)")


if __name__ == "__main__":
    main()
