"""The bounded, user-authorized English editorial migration (no other renames).

Plan before applying. Source data must match the recorded predecessor. This is a
one-version authoring operation, not a generic replacement or rebaseline tool.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocf_tools.indexes import load_all_functions  # noqa: E402
from ocf_tools.paths import REPO_ROOT, workspace_run  # noqa: E402
from ocf_tools.utils import OCFError, write_text_atomic, yaml_safe_dump  # noqa: E402
from tools.check_hplus_narration_integrity import narration_texts, text_fingerprints  # noqa: E402

SOURCE = "21e63ac6f8bf5a7bce9506f033330df967aa4f97"
DECISION = "OCF-EDITORIAL-TITLE-CUES-001"
MANIFEST = "function-content/editorial/approved-title-cues-001.json"
BASELINE = "tests/fixtures/hplus-narration-text-baseline.json"
SUCCESSOR = "tests/fixtures/hplus-narration-text-baseline-002.json"
# Exact user display spelling is intentional. None means retain committed title.
APPROVED = {
    "OCF-EXP-001": (
        "Manifest",
        "PLUS-MANIFEST",
        "Plus Manifest",
        "Plus Change Change",
        "Sets a consciously selected future condition and completion time through intention and total-self alignment.",
    ),
    "OCF-SLP-005": (
        "Sleep Easy",
        "PLUS-SLEEP EASY",
        "Plus Sleep Easy",
        "Plus Quiet Sleep",
        "Supports entering, remaining in, and returning to natural sleep amid unfamiliar or distracting surroundings.",
    ),
    "OCF-BOD-001": (
        "Brain Flow",
        "PLUS-BRAIN FLOW",
        "Plus Brain Flow",
        "Plus Flow Better",
        "Supports balanced brain and neck circulation and maintenance, with conscious reinforcement when desired.",
    ),
    "OCF-BOD-009": (
        "Breathe Better",
        "PLUS-BREATHE BETTER",
        "Plus Breathe Better",
        "Plus Breathe Better",
        "Supports efficient breathing and respiratory maintenance, with conscious reinforcement when desired.",
    ),
    "OCF-EMO-002": (
        "Offload",
        "PLUS-OFFLOAD",
        "Plus Offload",
        "Plus Fade Fade",
        "Reduces selected recurring thought and emotional-pattern interference while retaining useful memories and conscious choice.",
    ),
    "OCF-EMO-003": (
        "Empathize",
        "PLUS-EMPATHIZE",
        "Plus Empathize",
        "Plus Profile Profile",
        "Develops consciously directed understanding and communication with another being through sensory, intuitive, and total-self awareness.",
    ),
    "OCF-EXP-002": (
        "Insulate",
        "PLUS-INSULATE",
        "Plus Insulate",
        "Plus Insulate Insulate",
        "Establishes an adjustable whole-body zone of temperature comfort; Cancel ends the current adjustment and Release places the selected application on hold.",
    ),
    "OCF-SLP-004": (
        "Sleep Insight",
        "PLUS-SLEEP INSIGHT",
        "Plus Sleep Insight",
        "Plus Sleep Help",
        "Requests an answer or constructive solution through sleep, with useful insight recognized on awakening.",
    ),
    "OCF-PRF-002": (
        "Inner Power",
        "PLUS-INNER POWER",
        "Plus Inner Power",
        "Plus Eight Great",
        "Strengthens recognition and expression of total-self strength, unity, resources, and power throughout daily life.",
    ),
    "OCF-BOD-004": (
        "Detox",
        "PLUS-DETOX",
        "Plus Detox",
        "Plus Clean Clear",
        "Supports the body's self-regulating cleansing, renewal, and maintenance, with conscious reinforcement when desired.",
    ),
    "OCF-BOD-006": (
        None,
        "PLUS-HEART-BETTER",
        "Plus Heart Better",
        "Plus Heart Better Better",
        "Supports heart strength, circulation, coordinated function, and maintenance, with conscious reinforcement when desired.",
    ),
}
SELF_REFERENCES = {
    "OCF-BOD-001": [("OCF Brain Repairs and Maintenance exercise", "OCF Brain Flow exercise")],
    "OCF-BOD-009": [("OCF Lungs Repairs\nand Maintenance exercise", "OCF Breathe Better exercise")],
    "OCF-EMO-002": [("OCF Off-Loading exercise", "OCF Offload exercise")],
    "OCF-EMO-003": [("OCF Empathizing exercise", "OCF Empathize exercise")],
    "OCF-EXP-002": [
        ("ability to establish Zoning", "ability to use Insulate"),
        ("Zoning", "Insulate"),
    ],
    "OCF-SLP-004": [("OCF Wake/Know exercise", "OCF Sleep Insight exercise")],
    "OCF-PRF-002": [("OCF Eight-Great exercise", "OCF Inner Power exercise")],
    "OCF-BOD-004": [("OCF De-Tox Body exercise", "OCF Detox exercise")],
}
TRANSLATOR_NOTES = {
    "OCF-EXP-001": "Retain desired future-condition selection, completion time and total-self manifestation; not generic productivity or loop-breaking.",
    "OCF-SLP-005": "Retain unfamiliar/distracting surroundings, sleep continuity and resettling; preserve close-eyes, inhale/hold, cue and slow mouth exhale, then natural breathing.",
    "OCF-BOD-001": "Brain/neck circulation support and maintenance; not generic creativity or cognitive flow. Preserve targeting and breathing.",
    "OCF-BOD-009": "Respiratory-support intent and procedures remain; Breathe is the approved verb. Existing body speech already matches.",
    "OCF-EMO-002": "Selected recurring thought/emotional-pattern interference, useful memory and conscious choice; not indiscriminate clearing or memory erasure.",
    "OCF-EMO-003": "Retain the existing understanding/communication and total-self intention; impressions are not independently verified knowledge.",
    "OCF-EXP-002": "Temperature-comfort scope. Cancel ends the current adjustment; Release puts the selected application on hold. Preserve both operations.",
    "OCF-SLP-004": "Request an answer/insight through sleep and recognize it on waking; not choosing a wake-up time.",
    "OCF-PRF-002": "Retain total-self strength, unity, resources and expression; not only confidence or temporary physical performance.",
    "OCF-BOD-004": "Detox is the selected title and cue. Preserve current bodily cleansing scope; no Body Cleansing/Body Cleanse title or new medical mechanism.",
    "OCF-BOD-006": "Cue contains Better once. Retain the committed heart title, purpose and scope; Heart Flow is tentative and Heart Renewal is rejected.",
}


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fields(node):
    return {key.value: value for key, value in node.value}


def replace_entries(raw, replacements):
    """Patch only named scalar text spans, preserving all unrelated YAML bytes."""
    entries = fields(fields(yaml.compose(raw))["entries"])
    edits = []
    for key, (before, after) in replacements.items():
        node = entries[key]
        scalar = node if isinstance(node, yaml.ScalarNode) else fields(node)["text"]
        if scalar.value != before:
            raise OCFError(f"entry changed during migration planning: {key}")
        if before == after:
            continue
        if scalar.style == "|":
            # Preserve block indicator, indentation, blank lines and chomp policy.
            fragment = raw[scalar.start_mark.index : scalar.end_mark.index]
            for old, new in text_operations(before, after):
                physical_old = old.replace("\n", "\n      ")
                physical_new = new.replace("\n", "\n      ")
                if physical_old not in fragment:
                    raise OCFError(f"literal scalar patch cannot locate {old!r} in {key}")
                fragment = fragment.replace(physical_old, physical_new)
            edits.append((scalar.start_mark.index, scalar.end_mark.index, fragment))
            if isinstance(node, yaml.MappingNode) and "version" in fields(node):
                version = fields(node)["version"]
                parts = version.value.split(".")
                parts[-1] = str(int(parts[-1]) + 1)
                edits.append((version.start_mark.index, version.end_mark.index, ".".join(parts)))
        else:
            edits.append(
                (
                    scalar.start_mark.index,
                    scalar.end_mark.index,
                    json.dumps(after, ensure_ascii=False),
                )
            )
    for start, end, replacement in sorted(edits, reverse=True):
        raw = raw[:start] + replacement + raw[end:]
    return raw


def text_operations(before, after):
    """Whole approved substitutions, replayed in declared order; no fuzzy edits."""
    value, used = before, []
    for title, display, spoken, taught, purpose in APPROVED.values():
        if taught != spoken and taught in value:
            used.append((taught, spoken))
            value = value.replace(taught, spoken)
    for pairs in SELF_REFERENCES.values():
        for old, new in pairs:
            if old in value:
                used.append((old, new))
                value = value.replace(old, new)
    if value != after:
        raise OCFError("narration delta contains a non-allowlisted change")
    return used


def source_text(path):
    result = workspace_run(
        ["git", "show", f"{SOURCE}:{path}"], cwd=REPO_ROOT, capture_output=True, check=True
    )
    return result.stdout.decode("utf-8")


def plan():
    if (REPO_ROOT / MANIFEST).exists():
        raise OCFError("migration already recorded; use --check, never regenerate its approval")
    for name in (
        SUCCESSOR,
        "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-002.json",
        "locales/en-US/activation-cues.yaml",
    ):
        if (REPO_ROOT / name).exists():
            raise OCFError("refusing to replace existing successor artifact: " + name)
    for name in (
        BASELINE,
        "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-001.json",
        "locales/en-US/commands.yaml",
        "locales/en-US/manifest.yaml",
    ):
        if (REPO_ROOT / name).read_bytes() != source_text(name).encode("utf-8"):
            raise OCFError("approval predecessor differs from pinned source: " + name)
    functions = load_all_functions()
    by_id = {record.id: record for record in functions}
    if not APPROVED.keys() <= by_id.keys():
        raise OCFError("approved IDs must exist in the canonical catalog")
    for record in functions:
        name = record.path.relative_to(REPO_ROOT).as_posix()
        if record.path.read_bytes() != source_text(name).encode("utf-8"):
            raise OCFError("canonical input differs from approval predecessor: " + name)
    old_texts = narration_texts(REPO_ROOT)
    old_baseline = json.loads((REPO_ROOT / BASELINE).read_text(encoding="utf-8"))
    if text_fingerprints(old_texts) != old_baseline:
        raise OCFError("predecessor protected narration has drifted")
    files, decisions, changed = {}, [], []
    ui_path = "locales/en-US/commands.yaml"
    ui_raw = (REPO_ROOT / ui_path).read_text(encoding="utf-8")
    ui_data = yaml.safe_load(ui_raw)["entries"]
    ui_updates, cue_ui = {}, {}
    spoken_entries = {}
    for owner, (title, display, spoken, taught, purpose) in APPROVED.items():
        record = by_id[owner]
        name = record.path.relative_to(REPO_ROOT).as_posix()
        raw = record.path.read_text(encoding="utf-8")
        if raw != source_text(name):
            raise OCFError(f"canonical input differs from approval predecessor: {name}")
        data = yaml.safe_load(raw)
        primary = next(row for row in data["commands"] if row["designation"] == "primary")
        if primary["id"] != f"OCF-CMD-{owner[4:]}-PRIMARY":
            raise OCFError(f"unexpected primary identity for {owner}")
        previous = {
            "title": record.canonical_name,
            "display_cue": record.canonical_command,
            "spoken_cue": taught,
            "observed_phrase": primary.get("observed_phrase"),
            "aliases": data["aliases"],
        }
        # Copy mutable aliases before clearing: retain predecessor evidence.
        previous = json.loads(json.dumps(previous))
        data["canonical"]["name"] = title or record.canonical_name
        data["canonical"]["command"]["primary"] = display
        # This field is the source canonical-command review, not specification,
        # translation, mechanism, listening or release approval.
        data.setdefault("ocf", {})["command_review"] = "approved"
        primary["localization"]["display_cue_key"] = f"commands.{primary['id'].lower()}.display-cue"
        primary["localization"]["spoken_cue_key"] = f"commands.{primary['id'].lower()}.spoken-cue"
        primary["observed_phrase"] = {
            "text": spoken,
            "narration_key": f"hplus.function.{owner.lower()}.function-body",
            "relationship": "canonical-match",
        }
        history = [
            {"text": record.canonical_name, "kind": "former-title", "decision": DECISION},
            {
                "text": record.canonical_command,
                "kind": "former-primary",
                "command_id": primary["id"],
                "decision": DECISION,
            },
            {
                "text": taught,
                "kind": "former-teaching",
                "command_id": primary["id"],
                "decision": DECISION,
            },
        ]
        demoted = []
        for row in data["commands"]:
            if row["role"] == "legacy-alias":
                row["availability"] = "historical-lookup"
                row["documentation"]["visible"] = False
                demoted.append(row["id"])
        aliases = data["aliases"]
        retained = [
            (phrase, cid)
            for phrase, cid in zip(aliases["commands"], aliases["command_ids"], strict=True)
            if cid not in demoted
        ]
        aliases["commands"] = [pair[0] for pair in retained]
        aliases["command_ids"] = [pair[1] for pair in retained]
        data["historical_lookup"] = history
        data["compatibility"] = {
            "state": "historical-lookup",
            "rationale": "Former primary vocabulary is discovery-only under "
            + DECISION
            + "; secondary operational commands remain unchanged.",
        }
        if title is not None:
            data["purpose"]["summary"] = data["purpose"]["community_description"] = purpose
        files[name] = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
        for suffix, new in (
            ("title", title or record.canonical_name),
            ("purpose", purpose),
            ("short-description", purpose),
        ):
            if title is None and suffix != "title":
                continue
            key = f"functions.{owner.lower()}.{suffix}"
            entry = ui_data[key]
            before = entry if isinstance(entry, str) else entry["text"]
            ui_updates[key] = (before, new)
        cue_ui[primary["localization"]["display_cue_key"]] = display
        spoken_entries[primary["localization"]["spoken_cue_key"]] = {
            "text": spoken,
            "status": "reviewed",
            "version": "1.0.0",
            "notes": "Exact en-US spoken realization approved by the user in "
            + DECISION
            + ". Terminology approval is not listening or release approval.",
        }
        nar_name = f"locales/en-US/hplus-{owner}.yaml"
        nar_raw = (REPO_ROOT / nar_name).read_text(encoding="utf-8")
        if nar_raw != source_text(nar_name):
            raise OCFError(f"narration input differs from approval predecessor: {nar_name}")
        updates, keys = {}, []
        for key, entry in yaml.safe_load(nar_raw)["entries"].items():
            before = entry["text"]
            after = before.replace(taught, spoken) if taught != spoken else before
            for old, new in SELF_REFERENCES.get(owner, []):
                after = after.replace(old, new)
            if before != after:
                operations = text_operations(before, after)
                identity = nar_name + "::" + key
                replay, substitutions = before, []
                for old, new in operations:
                    substitutions.append({"before": old, "after": new, "count": replay.count(old)})
                    replay = replay.replace(old, new)
                changed.append(
                    {
                        "identity": identity,
                        "function_id": owner,
                        "before_sha256": digest(before),
                        "after_sha256": digest(after),
                        "before_text": before,
                        "substitutions": substitutions,
                        "diff": "".join(
                            difflib.unified_diff(
                                before.splitlines(True),
                                after.splitlines(True),
                                fromfile=identity + "@001",
                                tofile=identity + "@002",
                            )
                        ),
                    }
                )
                updates[key] = (before, after)
                keys.append(key)
        nar_new = replace_entries(nar_raw, updates).lstrip("\n")
        annotation = (
            "# Editorial successor "
            + DECISION
            + ": prior cue-preservation notes describe predecessor versions; only approved title/cue substitutions changed.\n"
        )
        files[nar_name] = annotation + nar_new
        decisions.append(
            {
                "function_id": owner,
                "primary_command_id": primary["id"],
                "previous": previous,
                "current_title": title or record.canonical_name,
                "display_cue": display,
                "spoken_cue": spoken,
                "title_status": "TENTATIVE TITLE" if title is None else "APPROVED AND IMPLEMENTED",
                "pending_title": "Heart Flow" if title is None else None,
                "cue_status": "APPROVED AND IMPLEMENTED",
                "scope": "Heart primary cue only; committed title and purposes retained. Heart Flow remains tentative."
                if title is None
                else "English primary cue, finalized title, exact teaching substitutions and narration-supported presentation summaries; procedures/mechanisms/secondary controls unchanged.",
                "narration_keys_changed": keys,
                "historical_command_ids": demoted,
                "narration_file": nar_name,
                "function_file": name,
                "translator_notes": TRANSLATOR_NOTES[owner],
            }
        )
    extra_key = "commands.ocf-cmd-exp-002-release.usage"
    old_usage = ui_data[extra_key]
    old_usage = old_usage if isinstance(old_usage, str) else old_usage["text"]
    ui_updates[extra_key] = (old_usage, old_usage.replace("Zoning", "Insulate"))
    files[ui_path] = (
        replace_entries(ui_raw, ui_updates).rstrip()
        + "\n"
        + "".join(f"  {key}: {json.dumps(value)}\n" for key, value in cue_ui.items())
    )
    files["locales/en-US/activation-cues.yaml"] = yaml_safe_dump(
        {
            "schema_version": "1.0",
            "locale": "en-US",
            "domain": "narration",
            "entries": spoken_entries,
        }
    )
    manifest_name = "locales/en-US/manifest.yaml"
    raw = (REPO_ROOT / manifest_name).read_text(encoding="utf-8")
    files[manifest_name] = raw.replace(
        "semantic_version: 1.6.0", "semantic_version: 1.7.0", 1
    ).replace(
        "resources:\n",
        "resources:\n- file: activation-cues.yaml\n  domain: narration\n  description: Explicit user-approved en-US primary spoken cues; other locales require their own reviewed terminology.\n",
        1,
    )
    successor = dict(old_baseline)
    for row in changed:
        successor[row["identity"]] = row["after_sha256"]
    files[SUCCESSOR] = json.dumps(successor, indent=2, sort_keys=True) + "\n"
    old_lock_name = "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-001.json"
    new_lock_name = "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-002.json"
    old_lock_raw = (REPO_ROOT / old_lock_name).read_text(encoding="utf-8")
    new_lock = json.loads(old_lock_raw)
    new_lock["id"], new_lock["version"] = "OCF-AUDIO-DEFAULTS-HPLUS-002", "2.0.0"
    for name in new_lock["files"]:
        if name in files:
            new_lock["files"][name] = digest(files[name])
    files[new_lock_name] = json.dumps(new_lock, indent=2, sort_keys=True) + "\n"
    data = {
        "schema_version": "1.0",
        "id": DECISION,
        "source_commit": SOURCE,
        "decision_source": "Explicit user approval in the approved English title-cue migration task",
        "approval_scope": "Eleven English primary cues; nine approved title-cue pairs, user-selected Detox correction, heart cue only. No listening/release approval.",
        "decisions": decisions,
        "allowed_text_changes": changed,
        "previous_integrity_baseline": BASELINE,
        "integrity_baseline": SUCCESSOR,
        "previous_baseline_sha256": digest((REPO_ROOT / BASELINE).read_text(encoding="utf-8")),
        "rejected_or_superseded": [
            "Heart Renewal",
            "PLUS-HEART RENEWAL",
            "Body Cleansing",
            "Body Cleanse",
            "PLUS-BODY CLEANSE",
        ],
        "pending": [
            "Heart Flow final title",
            "Nutricia paired vocabulary",
            "De-Hab alternatives",
            "Other unselected proposals",
            "HPLUS identifier migration",
            "Per-locale Plus policy and production translations",
            "Human listening and release decisions",
        ],
        "locales_requiring_review": ["es"],
        "unaffected_function_sha256": {
            record.path.relative_to(REPO_ROOT).as_posix(): digest(
                record.path.read_text(encoding="utf-8")
            )
            for record in functions
            if record.id not in APPROVED
        },
        "previous_defaults_lock": old_lock_name,
        "defaults_lock": new_lock_name,
        "previous_defaults_sha256": digest(old_lock_raw),
        "source_files": {
            name: {
                "before_sha256": digest((REPO_ROOT / name).read_text(encoding="utf-8"))
                if (REPO_ROOT / name).exists()
                else None,
                "after_sha256": digest(text),
            }
            for name, text in files.items()
        },
    }
    files[MANIFEST] = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return data, files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.check:
            from ocf_tools.cue_migration import verify_migration

            problems = verify_migration()
            if problems:
                raise OCFError(" | ".join(problems))
            print("Approved title-cue migration verified.")
            return 0
        data, files = plan()
        preflight = {
            "source_commit": SOURCE,
            "authorization": data["approval_scope"],
            "functions": len(data["decisions"]),
            "protected_entries_changed": len(data["allowed_text_changes"]),
            "files": list(files),
            "pending": data["pending"],
        }
        if args.report:
            write_text_atomic(args.report, json.dumps(preflight, indent=2) + "\n", overwrite=False)
        print(json.dumps(preflight, indent=2))
        if args.apply:
            # Immutable successors are claimed first, without replacing races.
            order = sorted(
                files,
                key=lambda name: (
                    0
                    if name == "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-002.json"
                    else 3
                    if name == MANIFEST
                    else 1
                    if data["source_files"][name]["before_sha256"] is None
                    else 2,
                    name,
                ),
            )
            for name in order:
                immutable = name == MANIFEST or data["source_files"][name]["before_sha256"] is None
                write_text_atomic(REPO_ROOT / name, files[name], overwrite=not immutable)
        return 0
    except (OCFError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
