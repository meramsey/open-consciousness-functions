"""Explicit zero-speech-drift structural successor to the approved cue migration."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocf_tools.paths import REPO_ROOT, workspace_run  # noqa: E402
from ocf_tools.utils import OCFError, write_text_atomic  # noqa: E402

SOURCE = "86ce803c36e89f2bafcfc5222dfbb94337427c5f"
RECORD = "function-content/editorial/symbolic-cues-001.json"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fields(node):
    return {key.value: value for key, value in node.value}


def source(name):
    return workspace_run(
        ["git", "show", SOURCE + ":" + name], cwd=REPO_ROOT, capture_output=True, check=True
    ).stdout.decode("utf-8")


def source_speech(owner, command, catalog):
    """Carry forward existing complete teaching, never propose a new cue here."""
    from ocf_tools.commands import command_view, resolve_phrase
    from tools.title_cue_review import mentions, words

    if command.role == "legacy-alias":
        return None, "unresolved"
    key = command.localization.get("spoken_cue_key")
    if key:
        entry, _ = catalog.raw_resource(key, "en-US", domain="narration", fallback=False)
        if entry.status not in {"reviewed", "canonical"}:
            raise OCFError(f"source speech binding is not reviewed: {owner.id}/{key}")
        return entry.text, "reviewed"
    phrase = resolve_phrase(owner, command)
    declared = [command_view(owner, item) for item in owner.command_records]
    phrases = {item["phrase"] for item in declared} | {
        item["observed_phrase"]["text"] for item in declared if item.get("observed_phrase")
    }
    keys = command.data.get("procedure", {}).get("evidence_keys", [])
    if command.observed_phrase:
        keys = list(keys) + [command.observed_phrase["narration_key"]]
    for key in keys:
        entry, _ = catalog.raw_resource(key, "en-US", domain="narration", fallback=False)
        if entry.status not in {"reviewed", "canonical"}:
            continue
        for hit in mentions(entry.text, phrases):
            if not hit["nested"] and words(hit["surface"]) == words(phrase):
                return hit["surface"], "reviewed"
        observed = command.observed_phrase or {}
        if observed.get("relationship") == "variant" and observed.get("text") in entry.text:
            # Preserve only the existing explicit orthographic realization.
            if words(observed["text"]) == words(phrase.replace("BLOODPRESSURE", "BLOOD PRESSURE")):
                return observed["text"], "reviewed"
    return None, "unresolved"


def prepare():
    from ocf_tools.indexes import load_all_functions
    from ocf_tools.locale import LocaleCatalog
    from tools.check_hplus_narration_integrity import narration_texts

    if (REPO_ROOT / RECORD).exists():
        raise OCFError("immutable symbolic migration already exists")
    for name in (
        "function-content/editorial/approved-title-cues-001.json",
        "locales/en-US/activation-cues.yaml",
        "locales/en-US/commands.yaml",
        "locales/en-US/manifest.yaml",
        "tests/fixtures/hplus-narration-text-baseline-002.json",
        "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-002.json",
    ):
        if (REPO_ROOT / name).read_bytes() != source(name).encode("utf-8"):
            raise OCFError("structural predecessor input drift: " + name)
    if (REPO_ROOT / "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-003.json").exists():
        raise OCFError("immutable structural successor lock already exists")
    records = load_all_functions()
    catalog = LocaleCatalog()
    approved = json.loads(
        (REPO_ROOT / "function-content/editorial/approved-title-cues-001.json").read_text(
            encoding="utf-8"
        )
    )["decisions"]
    approved = {row["function_id"]: row for row in approved}
    baseline = narration_texts()
    expected_baseline = json.loads(source("tests/fixtures/hplus-narration-text-baseline-002.json"))
    if {key: sha(text) for key, text in baseline.items()} != expected_baseline:
        raise OCFError("protected predecessor speech differs from approved baseline")
    updates, spans, bindings = {}, [], {}
    for record in records:
        name = record.path.relative_to(REPO_ROOT).as_posix()
        raw = record.path.read_text(encoding="utf-8")
        if record.path.read_bytes() != source(name).encode("utf-8"):
            raise OCFError("function changed from structural predecessor: " + name)
        node = yaml.compose(raw)
        commands = fields(node)["commands"].value
        edits = []
        for command, command_node in zip(record.command_records, commands, strict=True):
            spoken, status = source_speech(record, command, catalog)
            # Non-approved identities remain explicitly unresolved rather than
            # inventing speech from display spelling or promoting aliases.
            index = command_node.end_mark.index
            insertion = (
                f"  spoken: {json.dumps(spoken, ensure_ascii=False)}\n  spoken_review: {status}\n"
            )
            edits.append((index, insertion))
        for index, insertion in sorted(edits, reverse=True):
            raw = raw[:index] + insertion + raw[index:]
        binding = yaml.safe_load(source(f"function-content/bindings/{record.id}.yaml"))
        narration = binding.get("narration_plan", {"sequence": []})
        raw = (
            raw.rstrip()
            + "\n"
            + yaml.safe_dump({"narration": narration}, sort_keys=False, allow_unicode=True)
        )
        updates[name] = raw
        bindings[record.id] = narration
        if record.id not in approved:
            continue
        resource_path = f"locales/en-US/hplus-{record.id}.yaml"
        original = (REPO_ROOT / resource_path).read_text(encoding="utf-8")
        if (REPO_ROOT / resource_path).read_bytes() != source(resource_path).encode("utf-8"):
            raise OCFError("narration changed from structural predecessor: " + resource_path)
        cue = approved[record.id]["spoken_cue"]
        entries = fields(fields(yaml.compose(original))["entries"])
        replacements = []
        for key, entry_node in entries.items():
            mapping = fields(entry_node)
            text_node = mapping["text"]
            text = text_node.value
            occurrences = list(re.finditer(re.escape(cue), text))
            if not occurrences:
                continue
            if not key.endswith((".function-body", ".closer")):
                raise OCFError("unexpected approved cue location: " + key)
            for hit in occurrences:
                # Inspect complete phrase boundaries, not a prefix of legacy speech.
                if text[hit.end() :].startswith(" Better") or text[hit.end() :].startswith(
                    " Insulate"
                ):
                    raise OCFError("longer legacy phrase cannot satisfy approved teaching: " + key)
            segment = original[text_node.start_mark.index : text_node.end_mark.index]
            changed = segment.replace(cue, "{{ cue.primary }}")
            replacements.append((text_node.start_mark.index, text_node.end_mark.index, changed))
            line_start = original.rfind("\n", 0, text_node.start_mark.index) + 1
            contract = (
                f"    cue_template:\n      function_id: {record.id}\n      allowed: [cue.primary]\n"
            )
            replacements.append((line_start, line_start, contract))
            spans.append(
                {
                    "function_id": record.id,
                    "key": key,
                    "path": resource_path,
                    "before_text": text,
                    "resolved_sha256": sha(text),
                    "template_sha256": sha(text.replace(cue, "{{ cue.primary }}")),
                    "spans": [
                        {
                            "start": hit.start(),
                            "end": hit.end(),
                            "before": hit.group(),
                            "symbol": "cue.primary",
                        }
                        for hit in occurrences
                    ],
                }
            )
        for start, end, replacement in sorted(replacements, reverse=True):
            original = original[:start] + replacement + original[end:]
        updates[resource_path] = original
    before = {name: source(name) for name in updates}
    data = {
        "id": "OCF-SYMBOLIC-CUES-001",
        "source_commit": SOURCE,
        "authorization": "User-authorized structural replacement only; exact resolved speech unchanged",
        "predecessor_files": before,
        "files": {
            name: {"before_sha256": sha(before[name]), "after_sha256": sha(text)}
            for name, text in updates.items()
        },
        "entries": spans,
        "resolved_baseline": {key: sha(text) for key, text in baseline.items()},
        "narration_bindings": bindings,
        "scope": "All function definitions expose source authority and narration bindings; only eleven already-approved primary cues are templated. Other spoken choices remain explicitly unresolved.",
    }
    previous = json.loads(source("audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-002.json"))
    lock = json.loads(json.dumps(previous))
    lock.update(id="OCF-AUDIO-DEFAULTS-HPLUS-003", version="3.0.0")
    for name, text in updates.items():
        if name in lock["files"]:
            lock["files"][name] = sha(text)
    updates["audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-003.json"] = (
        json.dumps(lock, indent=2, sort_keys=True) + "\n"
    )
    data["predecessor_lock_sha256"] = sha(
        source("audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-002.json")
    )
    updates[RECORD] = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return data, updates


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    data, updates = prepare()
    print(
        json.dumps(
            {
                "functions": len(data["narration_bindings"]),
                "converted_entries": len(data["entries"]),
                "protected_entries": len(data["resolved_baseline"]),
            }
        )
    )
    if args.apply:
        for name, text in updates.items():
            write_text_atomic(REPO_ROOT / name, text, overwrite=name in data["files"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
