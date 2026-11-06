"""Generate the current decision/teaching view without rewriting historical audits."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ocf_tools.commands import command_view, cue_presentation  # noqa: E402
from ocf_tools.indexes import load_all_functions  # noqa: E402
from ocf_tools.locale import LocaleCatalog  # noqa: E402
from ocf_tools.paths import REPO_ROOT  # noqa: E402
from ocf_tools.utils import OCFError, write_text_atomic  # noqa: E402


def words(value: str) -> tuple[str, ...]:
    """Normalize cue words for a display/report-only comparison."""
    return tuple(re.findall(r"\w+", value.casefold()))


def build():
    """Generate current teaching metadata directly from canonical locale resources."""
    catalog = LocaleCatalog()
    from ocf_tools.editorial_candidates import CANDIDATES, verify_approvals

    problems = verify_approvals()
    if problems:
        raise OCFError("canonical editorial approval drift: " + " | ".join(problems))
    from tools.check_hplus_narration_integrity import check as check_narration

    problems = check_narration()
    if problems:
        raise OCFError("canonical narration integrity drift: " + " | ".join(problems))

    approval_ids = set(CANDIDATES.values())
    function_data = catalog.require("en-US").localized_functions
    records = sorted(load_all_functions(), key=lambda item: item.id)
    functions, commands = [], []
    for record in records:
        local = function_data[record.id]
        current_commands = [
            command_view(record, command, locale="en-US", catalog=catalog)
            for command in record.command_records
        ]
        commands.extend(current_commands)
        presentation = cue_presentation(record, "en-US", catalog=catalog)
        taught = presentation.get("spoken_cue")
        approval = local.get("record_metadata", {}).get("editorial_approval")
        decisions = local.get("record_metadata", {}).get("editorial_decisions", [])
        proposals = local.get("editorial", {}).get("proposals", [])
        command_review = record.data.get("ocf", {}).get("command_review")
        changed_keys = sorted((approval or {}).get("resolved_text_sha256", {}))
        changed_keys.extend(
            key
            for decision in decisions
            for key in decision.get("current_resolved_text_sha256", {})
        )
        functions.append(
            {
                "function_id": record.id,
                "current_title": record.canonical_name,
                "display_cue": record.canonical_command,
                "spoken_teaching": taught,
                "cue_presentation": presentation,
                "current_purpose": record.purpose_summary,
                "decision_status": "APPROVED AND IMPLEMENTED"
                if approval
                or decisions
                or command_review == "approved"
                or record.id in approval_ids
                else "REVIEW REQUIRED",
                "metadata_teaching_consistent": bool(taught)
                and words(record.canonical_command) == words(taught),
                "title_status": local.get("title", {}).get("status", "unknown"),
                "pending_title": next(
                    (
                        item["recommended_title"]
                        for item in proposals
                        if item["status"] == "pending"
                    ),
                    None,
                ),
                "previous_values": None,
                "unselected_proposal": None,
                "historical_lookup": record.data.get("historical_lookup", []),
                "context": record.data.get("compatibility", {}).get("rationale")
                or "Canonical locale function resource.",
                "teaching_source": "Canonical locale resource; missing speech is not inherited.",
                "changed_keys": sorted(set(changed_keys)),
                "editorial_proposals": proposals,
            }
        )
    groups = defaultdict(list)
    for row in commands:
        if row.get("availability", "active") == "active":
            groups[words(row["phrase"])].append(
                {"id": row["id"], "function_id": row["function_id"], "role": row["role"]}
            )
    baseline = json.loads(
        (REPO_ROOT / "tests/fixtures/hplus-narration-text-baseline-008.json").read_text(
            encoding="utf-8"
        )
    )
    return {
        "schema_version": "1.0",
        "decision_id": "canonical-locale-function-authority",
        "decision_ids": sorted(
            {"OCF-APPROVED-CANDIDATES-001"}
            | {
                decision["id"]
                for data in function_data.values()
                for decision in data.get("record_metadata", {}).get("editorial_decisions", [])
            }
            | {
                proposal["id"]
                for data in function_data.values()
                for proposal in data.get("editorial", {}).get("proposals", [])
            }
        ),
        "predecessor_commit": "b61ad1fcf3224d98c15ac6a589bdefe6151d6adb",
        "source_scope": "Current titles, commands, and narration resolve only from canonical locale resources; editorial approvals and historical lookup remain separate metadata.",
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
            "resolved_active_spoken_cues": sum(
                row.get("availability", "active") == "active"
                and row.get("cue_presentation", {}).get("binding_status") == "resolved"
                for row in commands
            ),
            "approved_candidate_narrations": len(approval_ids),
            "protected_entries": len(baseline),
            "embedded_approval_text_hashes": sum(len(row["changed_keys"]) for row in functions),
            "remaining_metadata_teaching_differences": sum(
                not row["metadata_teaching_consistent"] for row in functions
            ),
        },
        "functions": functions,
        "commands": commands,
        "rejected_or_superseded": [
            proposal["id"]
            for data in function_data.values()
            for proposal in data.get("editorial", {}).get("proposals", [])
            if proposal["status"] == "superseded"
        ],
        "pending": [
            proposal["id"]
            for data in function_data.values()
            for proposal in data.get("editorial", {}).get("proposals", [])
            if proposal["status"] == "pending"
        ],
        "locales_requiring_review": ["es: function narration and spoken cues remain partial"],
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
            for record in records
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
        "Approved decisions are embedded in canonical locale resources. This report is a derived view, not another source authority. Approval does not imply listening or release approval.",
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
        "Exact current wording and any approval hashes are stored with canonical locale resources. The path-free semantic and narration fixtures verify current approved invariants. Literal teaching is separate from source quotation and historical lookup.",
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
