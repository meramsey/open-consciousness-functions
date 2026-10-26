"""One-shot approved Options migration from the pinned implementation checkpoint.

Never refreshes an existing ledger. Run from the supported repository environment.
"""

import json
import subprocess

import yaml
from ocf_tools.options_successor import (
    BASELINE,
    FUNCTION,
    LEDGER,
    NARRATION,
    NEW,
    OLD,
    OWNER,
    approved_function,
    sha,
)
from ocf_tools.paths import REPO_ROOT
from ocf_tools.utils import OCFError

SOURCE = "e4226aac3feac72d62049314f807175175717a48"


def main():
    from ocf_tools.audio_defaults import LOCK_PATH, create_lock
    from ocf_tools.cue_headers import header, split_header
    from ocf_tools.indexes import load_all_functions
    from ocf_tools.locale import LocaleCatalog
    from ocf_tools.session_plans import generate_plans
    from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints

    root = REPO_ROOT
    if (root / LEDGER).exists() or (root / BASELINE).exists() or LOCK_PATH.exists():
        raise OCFError("Options successor already exists; never overwrite evidence")

    def prior(name):
        return subprocess.check_output(["git", "show", SOURCE + ":" + name], cwd=root).decode(
            "utf-8"
        )

    def write(name, text):
        (root / name).write_text(text, encoding="utf-8", newline="\n")

    def dump(data):
        return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    names = [
        FUNCTION,
        NARRATION,
        "locales/en-US/commands.yaml",
        "locales/en-US/activation-cues.yaml",
    ]
    names += [
        p.relative_to(root).as_posix()
        for p in sorted((root / "audio/session-plans/en-US").glob("*.json"))
    ]
    before = {name: prior(name) for name in names}
    if any((root / name).read_text(encoding="utf-8") != text for name, text in before.items()):
        raise OCFError("migration inputs differ from pinned checkpoint")
    old_texts = narration_texts(root)
    write(
        FUNCTION,
        yaml.safe_dump(
            approved_function(yaml.safe_load(before[FUNCTION])),
            allow_unicode=True,
            sort_keys=False,
            width=100,
        ),
    )
    for name, kind, text, domain in (
        (names[2], "display", "PLUS-OPTIONS", "ui"),
        (names[3], "spoken", NEW, "narration"),
    ):
        addition = {
            "commands.ocf-cmd-cog-005-primary." + kind + "-cue": {
                "text": text,
                "status": "reviewed",
                "version": "1.0.0",
                "notes": "Explicit user approval OCF-OPTIONS-001; not listening or release approval.",
            }
        }
        # Insert only the new entry, retaining every predecessor byte.
        block = yaml.safe_dump(addition, allow_unicode=True, sort_keys=False)
        indented = "".join("  " + line + "\n" for line in block.splitlines())
        write(name, before[name].replace("entries:\n", "entries:\n" + indented, 1))
    text = before[NARRATION]
    for role, old_version, version in (
        ("function-body", "1.1.0", "1.2.0"),
        ("closer", "1.2.0", "1.3.0"),
    ):
        marker = "  hplus.function.ocf-cog-005." + role + ":\n"
        start = text.index(marker)
        stop = text.find("\n  hplus.function.", start + len(marker))
        stop = len(text) if stop == -1 else stop
        section = text[start:stop].replace("version: " + old_version, "version: " + version, 1)
        pos = section.index("    text: |-")
        contract = (
            "    cue_template:\n      function_id: OCF-COG-005\n      allowed: [cue.primary]\n"
        )
        section = section[:pos] + contract + section[pos:].replace(OLD, "{{ cue.primary }}")
        text = text[:start] + section + text[stop:]
    owner = next(row for row in load_all_functions() if row.id == OWNER)
    text = header(owner, "en-US", LocaleCatalog(), root) + split_header(text)[1]
    write(NARRATION, text)
    previous_lock = "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-008.json"
    create_lock(dependency_names=list(json.loads((root / previous_lock).read_text())["files"]))
    generate_plans(locale="en-US")
    texts = narration_texts(root)
    speech = {}
    parsed = yaml.safe_load(text)
    for identity, old in old_texts.items():
        if old == texts[identity]:
            continue
        key = identity.split("::")[1]
        speech[identity] = {
            "before": old,
            "after": texts[identity],
            "before_sha256": sha(old),
            "after_sha256": sha(texts[identity]),
            "raw_before": yaml.safe_load(before[NARRATION])["entries"][key]["text"],
            "raw_template_sha256": sha(parsed["entries"][key]["text"]),
        }
    previous_baseline = "tests/fixtures/hplus-narration-text-baseline-005.json"
    data = {
        "schema_version": "1.0",
        "id": "OCF-OPTIONS-001",
        "source_commit": SOURCE,
        "decision_source": "Explicit user approval: OCF COMPLETE OPTIONS MIGRATION AND EDITORIAL CANDIDATE INTEGRATION",
        "approval": {"function_id": OWNER, "display": "PLUS-OPTIONS", "before": OLD, "after": NEW},
        "previous_baseline": previous_baseline,
        "previous_baseline_sha256": sha((root / previous_baseline).read_text()),
        "baseline": BASELINE,
        "previous_lock": previous_lock,
        "lock": LOCK_PATH.relative_to(root).as_posix(),
        "speech": speech,
        "unchanged_protected": {
            key: sha(value) for key, value in texts.items() if key not in speech
        },
        "recording_cache_impact": "Changed resolved speech invalidates normal text fingerprints and synthesis keys; originals are retained. Old Options recordings must be re-recorded or explicitly rebound only after matching speech verification.",
        "files": {
            name: {
                "before": old,
                "before_sha256": sha(old),
                "after_sha256": sha((root / name).read_text()),
            }
            for name, old in before.items()
            if old != (root / name).read_text()
        },
    }
    write(BASELINE, dump(text_fingerprints(texts)))
    write(LEDGER, dump(data))


if __name__ == "__main__":
    main()
