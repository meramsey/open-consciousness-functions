"""Verify the reviewed en-US HPlus narration against frozen text fingerprints.

This check covers every entry in the 55 function resources and four shared
resources. The fixture fingerprints effective narration text. Declared symbolic
resources resolve through LocaleCatalog first; their raw templates and exact
structural delta are independently protected by the symbolic successor ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocf_tools.utils import OCFError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCALE_ROOT = Path("locales/en-US")
SHARED_RESOURCES = (
    "hplus-focus20.yaml",
    "hplus-relaxation.yaml",
    "hplus-transmutation-box.yaml",
    "hplus-waking-return.yaml",
)
PREVIOUS_BASELINE_PATH = REPO_ROOT / "tests/fixtures/hplus-narration-text-baseline.json"
BASELINE_PATH = REPO_ROOT / "tests/fixtures/hplus-narration-text-baseline-002.json"
KEY_RE = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z0-9-]+)+$")


def narration_texts(root: Path = REPO_ROOT) -> dict[str, str]:
    """Return the exact parsed text for every targeted resource key."""
    locale_root = root / LOCALE_ROOT
    function_files = sorted(locale_root.glob("hplus-OCF-*.yaml"))
    if len(function_files) != 55:
        raise ValueError(f"expected 55 function resources, found {len(function_files)}")

    paths = function_files + [locale_root / name for name in SHARED_RESOURCES]
    manifest = yaml.safe_load((locale_root / "manifest.yaml").read_text(encoding="utf-8"))
    declared_resources = {
        str(resource.get("file")): str(resource.get("domain"))
        for resource in manifest.get("resources", [])
        if isinstance(resource, dict)
    }
    texts: dict[str, str] = {}
    owners: dict[str, str] = {}
    symbolic_catalog = None
    for path in paths:
        if not path.is_file():
            raise ValueError(f"required narration resource is missing: {path}")
        if declared_resources.get(path.name) != "narration":
            raise ValueError(
                f"resource is not declared as narration in the locale manifest: {path}"
            )
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("locale") != "en-US":
            raise ValueError(f"resource must declare locale en-US: {path}")
        if data.get("domain") != "narration" or not isinstance(data.get("entries"), dict):
            raise ValueError(f"resource must declare narration entries: {path}")

        for key, value in data["entries"].items():
            key = str(key)
            if not KEY_RE.fullmatch(key):
                raise ValueError(f"invalid localization key {key!r} in {path}")
            if key in owners:
                raise ValueError(f"duplicate narration key {key!r} in {owners[key]} and {path}")
            text = (
                value
                if isinstance(value, str)
                else value.get("text")
                if isinstance(value, dict)
                else None
            )
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"narration entry has no non-empty parsed text: {path}::{key}")
            if isinstance(value, dict) and value.get("cue_template"):
                from ocf_tools.locale import LocaleCatalog

                if symbolic_catalog is None:
                    symbolic_catalog = LocaleCatalog(root / LOCALE_ROOT.parent)
                text = symbolic_catalog.resource(key, "en-US", domain="narration", fallback=False)[
                    0
                ].text
            owners[key] = path.relative_to(root).as_posix()
            texts[f"{owners[key]}::{key}"] = text
    return texts


def text_fingerprints(texts: dict[str, str]) -> dict[str, str]:
    """Hash each key's exact parsed text independently for actionable drift."""
    return {
        identity: hashlib.sha256(text.encode("utf-8")).hexdigest()
        for identity, text in sorted(texts.items())
    }


def differences(expected: dict[str, str], actual: dict[str, str]) -> list[str]:
    """Describe missing, additional, and changed key fingerprints."""
    rows = [f"missing key: {key}" for key in sorted(expected.keys() - actual.keys())]
    rows.extend(f"unexpected key: {key}" for key in sorted(actual.keys() - expected.keys()))
    rows.extend(
        f"text changed: {key}"
        for key in sorted(expected.keys() & actual.keys())
        if expected[key] != actual[key]
    )
    return rows


def check(root: Path = REPO_ROOT, baseline: Path = BASELINE_PATH) -> list[str]:
    """Return integrity failures; an empty list means all narration is unchanged."""
    expected: Any = json.loads(baseline.read_text(encoding="utf-8"))
    if not isinstance(expected, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in expected.items()
    ):
        raise ValueError(f"invalid narration integrity baseline: {baseline}")
    current = text_fingerprints(narration_texts(root))
    problems = differences(expected, current)
    if baseline == BASELINE_PATH and root == REPO_ROOT:
        from ocf_tools.cue_migration import verify_migration

        problems.extend(verify_migration())
        if (root / "function-content/editorial/symbolic-cues-001.json").is_file():
            from ocf_tools.symbolic_integrity import verify

            problems.extend(verify(root))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline", type=Path, default=BASELINE_PATH, help="expected key/text hash JSON"
    )
    args = parser.parse_args(argv)
    try:
        problems = check(baseline=args.baseline)
    except (OCFError, OSError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        print(f"narration integrity error: {exc}", file=sys.stderr)
        return 2
    if problems:
        print("Narration text integrity failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    total = len(json.loads(args.baseline.read_text(encoding="utf-8")))
    print(
        f"Narration text integrity passed: {total} keys across 55 function and 4 shared resources."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
