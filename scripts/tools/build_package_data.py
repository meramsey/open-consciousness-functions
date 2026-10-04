"""Stage licensed runtime data from authoritative sources, never local research/audio."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from setuptools.command.build_py import build_py

DIRECTORIES = (
    "schemas",
    "functions",
    "function-content",
    "locales",
    "templates",
    "audio/templates/stages",
    "audio/templates/sessions",
    "audio/cues/profiles",
    "audio/voices/profiles",
    "audio/voices/registry",
    "audio/background/manifests",
    "audio/background/presets",
    "audio/background/state-profiles",
)


def stage_data(root: Path, target: Path) -> dict:
    # This is generated staging output, not a contributor working directory.
    # Reconcile the entire tree so previously eligible citation-only resources
    # cannot survive a later exclusion or removal from the source whitelist.
    if root.resolve().is_relative_to(target.resolve()):
        raise ValueError("package staging target must not contain the source root")
    if target.is_symlink():
        raise ValueError("package staging target must not be a symlink")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    omitted = []
    for directory in DIRECTORIES:
        for path in sorted((root / directory).rglob("*")):
            if (
                path.is_symlink()
                or not path.resolve().is_relative_to(root.resolve())
                or any(
                    parent.is_symlink() for parent in path.parents if parent.is_relative_to(root)
                )
            ):
                omitted.append(path.relative_to(root).as_posix())
                continue
            if not path.is_file() or path.suffix not in (
                ".json",
                ".yaml",
                ".yml",
                ".sbg",
                ".txt",
                ".md",
            ):
                continue
            relative = path.relative_to(root)
            # Reference-derived session wording remains citation-only, even if
            # historically tracked. Attention's citation-only binding is omitted
            # with that optional template; canonical function metadata is retained.
            if (
                directory == "audio/templates/sessions"
                and yaml.safe_load(path.read_text(encoding="utf-8")).get("origin") != "original-ocf"
            ):
                omitted.append(relative.as_posix())
                continue
            if relative.as_posix() == "function-content/bindings/OCF-FND-002.yaml":
                omitted.append(relative.as_posix())
                continue
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            copied.append(relative.as_posix())
    return {"included": copied, "omitted_citation_only_bindings": omitted}


class BuildWithData(build_py):
    def run(self):
        super().run()
        import json

        root = Path(__file__).resolve().parents[2]
        target = Path(self.build_lib) / "ocf_tools/data"
        report = stage_data(root, target)
        (target / "package-data-manifest.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
