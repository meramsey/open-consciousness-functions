"""Generate the current decision/teaching view without rewriting historical audits."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocf_tools.commands import command_view, cue_presentation  # noqa: E402
from ocf_tools.cue_migration import verify_migration  # noqa: E402
from ocf_tools.editorial_successors import current_decision_record  # noqa: E402
from ocf_tools.editorial_successors import verify as verify_successors
from ocf_tools.indexes import load_all_functions  # noqa: E402
from ocf_tools.locale import LocaleCatalog  # noqa: E402
from ocf_tools.paths import REPO_ROOT  # noqa: E402
from ocf_tools.utils import OCFError, write_text_atomic  # noqa: E402
from tools.title_cue_review import words  # noqa: E402


def build():
    problems = verify_migration()
    if not problems:
        problems = verify_successors()
    if problems:
        raise OCFError("approved migration drift: " + " | ".join(problems))
    decision = current_decision_record()
    changed = {row["function_id"]: row for row in decision["decisions"]}
    kept = {row["function_id"]: row for row in decision["kept_decisions"]}
    previous = json.loads(
        (REPO_ROOT / "docs/releases/OCF_TITLE_CUE_REVIEW.json").read_text(encoding="utf-8")
    )
    prior = {row["function_id"]: row for row in previous["functions"]}
    functions, commands = [], []
    catalog = LocaleCatalog()
    for record in sorted(load_all_functions(), key=lambda item: item.id):
        is_new_draft = record.id not in prior
        if is_new_draft:
            primary = next(row for row in record.command_records if row.designation == "primary")
            prior[record.id] = {
                "exact_taught_cue": primary.data.get("spoken"),
                "classification": "UNREVIEWED ORIGINAL DRAFT",
                "recommended_title": record.canonical_name,
                "recommended_primary_cue": record.canonical_command,
                "contextual_review": "New original draft; no prior historical or editorial approval.",
            }
        update = changed.get(record.id)
        current_commands = [
            command_view(record, command, locale="en-US", catalog=catalog)
            for command in record.command_records
        ]
        commands.extend(current_commands)
        presentation = cue_presentation(record, "en-US", catalog=catalog, strict=bool(update))
        taught = update["spoken_cue"] if update else prior[record.id]["exact_taught_cue"]
        matched = words(record.canonical_command) == words(taught)
        if record.id == "OCF-BOD-007":
            matched = True  # Existing explicit Bloodpressure/Blood Pressure realization.
        functions.append(
            {
                "function_id": record.id,
                "current_title": record.canonical_name,
                "display_cue": record.canonical_command,
                "spoken_teaching": taught,
                "cue_presentation": presentation,
                "current_purpose": record.purpose_summary,
                "decision_status": "UNREVIEWED ORIGINAL DRAFT"
                if is_new_draft
                else "APPROVED AND IMPLEMENTED"
                if update
                else "EXISTING PAIR RETAINED"
                if record.id in kept
                else "STILL UNDECIDED"
                if prior[record.id]["classification"]
                != "KEEP — TITLE, CUE, AND TEACHING ALREADY CONSISTENT"
                else "EXISTING PAIR RETAINED",
                "metadata_teaching_consistent": matched,
                "title_status": update["title_status"] if update else "UNCHANGED",
                "pending_title": update.get("pending_title") if update else None,
                "previous_values": update["previous"] if update else None,
                "unselected_proposal": None
                if update or record.id in kept
                else {
                    "title": prior[record.id]["recommended_title"],
                    "cue": prior[record.id]["recommended_primary_cue"],
                },
                "historical_lookup": record.data.get("historical_lookup", []),
                "context": update["translator_notes"]
                if update
                else kept[record.id]["implementation_scope"]
                if record.id in kept
                else prior[record.id]["contextual_review"],
                "teaching_source": "Supplied draft; not approved for production"
                if is_new_draft
                else "Approved exact substitutions, verified against immutable predecessor"
                if update
                else "Predecessor contextual review; unchanged protected text verified",
                "changed_keys": update["narration_keys_changed"] if update else [],
            }
        )
    groups = defaultdict(list)
    for row in commands:
        if row.get("availability", "active") == "active":
            groups[words(row["phrase"])].append(
                {"id": row["id"], "function_id": row["function_id"], "role": row["role"]}
            )
    return {
        "schema_version": "1.0",
        "decision_id": decision["id"],
        "decision_ids": decision["decision_ids"],
        "predecessor_commit": decision["source_commit"],
        "source_scope": "Current approved successor. Earlier source-pinned proposals remain immutable history; this is not a repin or blanket approval of them.",
        "counts": {
            "functions": len(functions),
            "structured_command_identities": len(commands),
            "active_records": sum(
                row.get("availability", "active") == "active" for row in commands
            ),
            "historical_only_command_records": sum(
                row.get("availability") == "historical-lookup" for row in commands
            ),
            "stable_primary_identities": sum(row["designation"] == "primary" for row in commands),
            "approved_cues_implemented": len(changed),
            "protected_entries": len(
                json.loads((REPO_ROOT / decision["integrity_baseline"]).read_text())
            ),
            "allowlisted_text_changes": len(decision["allowed_text_changes"]),
            "remaining_metadata_teaching_differences": sum(
                not row["metadata_teaching_consistent"] for row in functions
            ),
        },
        "functions": functions,
        "commands": commands,
        "rejected_or_superseded": decision["rejected_or_superseded"],
        "pending": decision["pending"],
        "locales_requiring_review": decision["locales_requiring_review"],
        "collision_groups": [
            {
                "source_english_words": list(key),
                "owners": owners,
                "review": "Role/selected-target reuse retained; no new unrelated primary collision",
            }
            for key, owners in sorted(groups.items())
            if len(owners) > 1
        ],
        "input_sha256": {
            record.path.relative_to(REPO_ROOT).as_posix(): hashlib.sha256(
                record.path.read_bytes()
            ).hexdigest()
            for record in load_all_functions()
        },
    }


def render(data):
    lines = [
        "# Current title–cue decisions and implementation",
        "",
        f"Decision: `{data['decision_id']}`. Predecessor commit: `{data['predecessor_commit']}`.",
        "",
        data["source_scope"],
        "",
        "Approved source: explicit user decisions recorded in the versioned title–cue ledgers. Approval covers primary English vocabulary and scoped teaching edits, not other proposals, mechanisms, listening or release. Heart Flow remains tentative; the committed heart title is retained.",
        "",
        "Counts: " + json.dumps(data["counts"], sort_keys=True) + ".",
        "",
        "## Approved implementation and remaining catalog decisions",
        "",
    ]
    terms = [
        "# Source-English terminology sheet",
        "",
        "This is a reviewed source-English terminology sheet, not a completed translation pack. Other locales need their own title/cue and Plus-prefix decisions. Stable command IDs, display labels and complete spoken realizations are distinct.",
        "",
    ]
    teaching = [
        "# Current exact-teaching status",
        "",
        "Only explicitly approved substitutions were applied. Every affected entry's before/after hashes, exact substitutions, occurrence counts and unified diff are in [the migration record](../../function-content/editorial/approved-title-cues-001.json). All other protected text remains identical. Literal teaching is separate from source quotation and historical lookup.",
        "",
    ]
    for row in data["functions"]:
        lines += [
            f"### {row['function_id']} — {row['current_title']}",
            "",
            f"- Current display cue: `{row['display_cue']}`; complete teaching: **{row['spoken_teaching']}**.",
            f"- Status: {row['decision_status']}; title: {row['title_status']}.",
            f"- Purpose: {row['current_purpose']}",
            f"- Pending title: {row['pending_title'] or 'None.'}",
            f"- Other unselected proposal: {json.dumps(row['unselected_proposal'], ensure_ascii=False)}",
            "",
        ]
        if row.get("previous_values"):
            old = row["previous_values"]
            lines += [
                f"Previous values: {old['title']} / `{old['display_cue']}`; complete teaching **{old['spoken_cue']}**.",
                "",
            ]
        teaching += [
            f"- {row['function_id']}: `{row['display_cue']}` / {row['spoken_teaching']}; metadata match {row['metadata_teaching_consistent']}; {row['teaching_source']}."
        ]
        if row["changed_keys"]:
            terms += [
                f"## {row['function_id']} / {row['cue_presentation']['command_id']}",
                "",
                f"Title: {row['current_title']}. Title status: {row['title_status']}.",
                f"Display: `{row['display_cue']}`. Complete speech: **{row['spoken_teaching']}**.",
                "",
                row["current_purpose"],
                "",
                "Translator context: " + row["context"],
                "",
                "Review: English primary cue approved and implemented. Preserve controls/procedures. Other language terminology and prefix treatment require review.",
                "",
            ]
    lines += ["## Rejected or superseded proposals", ""] + [
        "- " + text for text in data["rejected_or_superseded"]
    ]
    lines += ["", "## Still pending", ""] + ["- " + text for text in data["pending"]]
    history = [
        "# Historical lookup and active cue separation",
        "",
        "Use the shared catalog and locale services:",
        "",
        "```bash",
        'python scripts/ocf.py functions lookup "Mobius West" --locale en-US --json',
        'python scripts/ocf.py functions lookup "Plus Quiet Sleep" --locale en-US --json',
        "```",
        "",
        "A match returns the stable function, current localized title/purpose, active display cue, explicit spoken binding when available, origin locales and a labeled match reason. It never selects an activation target. UI fallback is disclosed; absent localized speech is marked requires-locale-review rather than silently borrowing English.",
        "",
        "Former primary aliases marked historical-lookup remain identifiable but are excluded from active command guides and rich activation listings. Secondary Cancel, Release, retrieval and access-close operations retain their roles. Original legacy names/phrase arrays and stable IDs remain intact; an old primary identity may have former wording in historical records and approved new wording now.",
        "",
        "Discovery normalization uses NFC, case folding and whitespace folding only. It is not an acoustic cue matcher. Technical old-ID compatibility and source history do not establish current spoken support.",
        "",
        "## Migrated vocabulary",
        "",
    ]
    for row in data["functions"]:
        if row["historical_lookup"]:
            history += [
                f"- {row['function_id']} → {row['current_title']} / `{row['display_cue']}`; historical matches: "
                + "; ".join(item["text"] for item in row["historical_lookup"])
                + "."
            ]
    return {
        "OCF_TITLE_CUE_CURRENT.json": json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        "OCF_TITLE_CUE_CURRENT.md": "\n".join(lines).rstrip() + "\n",
        "OCF_TEACHING_CURRENT.md": "\n".join(teaching).rstrip() + "\n",
        "OCF_EN_US_TERMINOLOGY.md": "\n".join(terms).rstrip() + "\n",
        "OCF_HISTORICAL_LOOKUP_CURRENT.md": "\n".join(history).rstrip() + "\n",
    }


def _run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    data = build()
    for name, text in render(data).items():
        path = REPO_ROOT / "docs/releases" / name
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                raise OCFError("current title-cue report stale: " + name)
        else:
            write_text_atomic(path, text)
    print(json.dumps(data["counts"]))
    return 0


def main(argv=None):
    try:
        return _run(argv)
    except (OCFError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
