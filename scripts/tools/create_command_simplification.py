"""One-shot migration of the twelve explicitly confirmed editorial decisions."""

from __future__ import annotations

import json
import re
import subprocess
import sys

import yaml
from ocf_tools.command_simplification import (
    ARTWORK,
    BASELINE,
    ID,
    LEDGER,
    PAIRS,
    PREVIOUS_BASELINE,
    PREVIOUS_LOCK,
    SOURCE,
    approved_function,
    sha,
)
from ocf_tools.paths import REPO_ROOT
from ocf_tools.utils import OCFError


def bump(version):
    major, minor, _ = map(int, version.split("."))
    return f"{major}.{minor + 1}.0"


def replace_entry(text, key, update):
    """Retain all bytes outside the one explicitly selected locale entry."""
    pattern = re.compile(r"^  " + re.escape(key) + r":[^\n]*\n.*?(?=^  [a-z]|\Z)", re.M | re.S)
    match = pattern.search(text)
    if match:
        entry = yaml.safe_load(match.group())[key]
        if isinstance(entry, str):
            entry = {"text": entry, "version": "1.0.0"}
        update(entry)
    else:
        entry = {"text": "", "status": "reviewed", "version": "0.0.0"}
        update(entry)
    block = yaml.safe_dump({key: entry}, allow_unicode=True, sort_keys=False, width=100)
    block = "".join("  " + line + "\n" for line in block.splitlines())
    if match:
        return text[: match.start()] + block + text[match.end() :]
    return text.replace("entries:\n", "entries:\n" + block, 1)


def main():
    from ocf_tools.audio_defaults import LOCK_PATH, create_lock
    from ocf_tools.cue_headers import plans as preview_plans
    from ocf_tools.session_plans import generate_plans
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    root = REPO_ROOT
    recover = sys.argv[1:] == ["--recover-incomplete"]
    if sys.argv[1:] and not recover:
        raise OCFError("only --recover-incomplete is supported")
    if any((root / name).exists() for name in (LEDGER, BASELINE)) or (
        LOCK_PATH.exists() and not recover
    ):
        raise OCFError("command simplification already exists; never overwrite evidence")

    def dump(data):
        return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def write(name, text):
        (root / name).write_text(text, encoding="utf-8", newline="\n")

    def prior(name):
        return subprocess.check_output(["git", "show", SOURCE + ":" + name], cwd=root).decode(
            "utf-8"
        )

    function_files = {}
    for path in sorted((root / "functions").rglob("*.yaml")):
        owner = yaml.safe_load(path.read_text())["id"]
        if owner in PAIRS:
            function_files[owner] = path.relative_to(root).as_posix()
    if set(function_files) != set(PAIRS):
        raise OCFError("approved function scope is incomplete")
    names = list(function_files.values()) + [f"locales/en-US/hplus-{owner}.yaml" for owner in PAIRS]
    names += [
        "locales/en-US/commands.yaml",
        "locales/en-US/activation-cues.yaml",
        "locales/en-US/ui.yaml",
    ]
    names += [
        path.relative_to(root).as_posix()
        for path in sorted((root / "audio/session-plans/en-US").glob("*.json"))
    ]
    before = {name: prior(name) for name in names}
    if not recover and any(
        (root / name).read_text(encoding="utf-8") != raw for name, raw in before.items()
    ):
        raise OCFError("migration input differs from approved checkpoint")
    if recover:
        # Only for this driver interrupted before writing its immutable ledger.
        # Its deterministic output is checked against the pinned checkpoint below.
        old_texts = None
    else:
        old_texts = narration_texts(root)
    for name in ("locales/en-US/commands.yaml", "locales/en-US/activation-cues.yaml"):
        write(name, before[name])
    for owner, name in function_files.items():
        updated = approved_function(yaml.safe_load(before[name]))
        write(name, yaml.safe_dump(updated, allow_unicode=True, sort_keys=False, width=100))
        primary = next(row for row in updated["commands"] if row.get("designation") == "primary")
        title, display, old_spoken, spoken = PAIRS[owner]
        for locale_file, kind, value in (
            ("locales/en-US/commands.yaml", "display", display),
            ("locales/en-US/activation-cues.yaml", "spoken", spoken),
        ):

            def edit(entry, value=value):
                entry.update(
                    text=value, status="reviewed", version=bump(entry.get("version", "0.0.0"))
                )
                entry["notes"] = (
                    "Explicit user approval " + ID + "; not listening or release approval."
                )

            write(
                locale_file,
                replace_entry(
                    (root / locale_file).read_text(),
                    primary["localization"][kind + "_cue_key"],
                    edit,
                ),
            )
        if owner == "OCF-FND-002":

            def edit_title(entry):
                entry.update(
                    text=title, status="reviewed", version=bump(entry.get("version", "0.0.0"))
                )

            locale_file = "locales/en-US/commands.yaml"
            write(
                locale_file,
                replace_entry(
                    (root / locale_file).read_text(), "functions.ocf-fnd-002.title", edit_title
                ),
            )
        name = f"locales/en-US/hplus-{owner}.yaml"
        text = before[name]
        roles = ("closer",) if old_spoken == spoken else ("function-body", "closer")
        for role in roles:
            key = f"hplus.function.{owner.lower()}.{role}"
            # Preserve authored literal-block bytes and every provenance field.
            marker = "  " + key + ":\n"
            start = text.index(marker)
            stop = text.find("\n  hplus.function.", start + len(marker))
            stop = len(text) if stop == -1 else stop
            section = text[start:stop]
            section = re.sub(
                r'(version: ["\']?)(\d+\.\d+\.\d+)',
                lambda match: match[1] + bump(match[2]),
                section,
                count=1,
            )
            if owner == "OCF-FND-002":
                section = section.replace(
                    "This concludes your OCF Attention exercise.",
                    "This concludes your OCF Focus exercise.",
                )
            text = text[:start] + section + text[stop:]
        write(name, text)
    ui_name = "locales/en-US/ui.yaml"
    ui = before[ui_name]
    for owner, value in ARTWORK.items():

        def edit_artwork(entry, value=value):
            entry.update(text=value, status="reviewed", version=bump(entry["version"]))
            entry["notes"] = (
                "Artwork wording explicitly approved in "
                + ID
                + ". Not narration, listening approval or release approval."
            )

        ui = replace_entry(ui, f"functions.{owner.lower()}.artwork-description", edit_artwork)
    write(ui_name, ui)
    for name, text in preview_plans(root).items():
        if name in before:
            write(name, text)
    if not LOCK_PATH.exists():
        create_lock(dependency_names=list(json.loads((root / PREVIOUS_LOCK).read_text())["files"]))
    else:
        from ocf_tools.audio_defaults import check_lock

        check_lock()
    generate_plans(locale="en-US")
    texts = narration_texts(root)
    if old_texts is None:
        old_texts = dict(texts)
        for owner, (_, _, old, new) in PAIRS.items():
            for role in ("closer",) if old == new else ("function-body", "closer"):
                identity = (
                    f"locales/en-US/hplus-{owner}.yaml::hplus.function.{owner.lower()}.{role}"
                )
                # Reconstruct only explicitly approved substitutions, then prove
                # every predecessor hash against the frozen baseline.
                left, right = (
                    (new, old)
                    if old != new
                    else (
                        "This concludes your OCF Focus exercise.",
                        "This concludes your OCF Attention exercise.",
                    )
                )
                old_texts[identity] = texts[identity].replace(left, right)
        if text_fingerprints(old_texts) != json.loads((root / PREVIOUS_BASELINE).read_text()):
            raise OCFError("recovery cannot prove the exact predecessor narration")
    speech = {
        identity: {
            "before": old,
            "after": texts[identity],
            "before_sha256": sha(old),
            "after_sha256": sha(texts[identity]),
        }
        for identity, old in old_texts.items()
        if texts[identity] != old
    }
    immutable = [PREVIOUS_BASELINE, PREVIOUS_LOCK, "locales/en-US/manifest.yaml"]
    immutable += [
        path.relative_to(root).as_posix()
        for path in sorted((root / "function-content/editorial").glob("*.json"))
    ]
    immutable += [
        path.relative_to(root).as_posix()
        for path in sorted((root / "functions").rglob("*.yaml"))
        if path.relative_to(root).as_posix() not in function_files.values()
    ]
    data = {
        "schema_version": "1.0",
        "id": ID,
        "source_commit": SOURCE,
        "confirmation": "Confirm implementation",
        "decisions": {
            owner: {"title": row[0], "display": row[1], "before_spoken": row[2], "spoken": row[3]}
            for owner, row in PAIRS.items()
        },
        "artwork": ARTWORK,
        "speech": speech,
        "function_files": sorted(function_files.values()),
        "previous_baseline": PREVIOUS_BASELINE,
        "baseline": BASELINE,
        "previous_lock": PREVIOUS_LOCK,
        "lock": LOCK_PATH.relative_to(root).as_posix(),
        "files": {
            name: {
                "before": raw,
                "before_sha256": sha(raw),
                "after_sha256": sha((root / name).read_text()),
            }
            for name, raw in before.items()
            if raw != (root / name).read_text()
        },
        "immutable_files": {name: sha((root / name).read_text()) for name in immutable},
        "recording_cache_impact": "Only approved resolved cue/sign-off changes invalidate speech hashes. Preserve originals and require matching speech before rebinding recordings.",
    }
    write(BASELINE, dump(text_fingerprints(texts)))
    write(LEDGER, dump(data))
    print("Pin LEDGER_SHA256 to " + sha(dump(data)))
    print(f"Approved speech changes: {len(speech)}; predecessor files: {len(data['files'])}")


if __name__ == "__main__":
    main()
