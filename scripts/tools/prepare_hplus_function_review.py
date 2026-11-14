"""Prepare local, non-authoritative review proposals from explicit source extents.

Canonical locale metadata supplies identity and provenance. This tool never
installs resources, edits a manifest, or promotes wording into runtime narration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import jsonschema
import yaml
from ocf_tools.editorial import build_skeleton, checked_path, require_local_output
from ocf_tools.indexes import load_all_functions
from ocf_tools.paths import REPO_ROOT
from ocf_tools.utils import write_text_atomic

SLOTS = ("opener", "function-body", "closer")
RIGHTS = "Rights and finished-session release require separate recorded approval; preparation grants neither."


def select_text(lines: list[str], ranges: list[dict]) -> tuple[str, str]:
    """Select exact words, permitting explicit within-line boundaries only."""
    chunks = []
    locators = []
    previous_end = 0
    for extent in ranges:
        start, end = extent["start_line"], extent["end_line"]
        if not 1 <= start <= end <= len(lines) or start <= previous_end:
            raise ValueError(f"invalid, overlapping or unordered source range: {start}–{end}")
        part = list(lines[start - 1 : end])
        locator = f"{start}–{end}"
        if extent.get("start_at"):
            literal = extent["start_at"]
            if part[0].count(literal) != 1:
                raise ValueError(
                    f"start boundary must occur once on source line {start}: {literal!r}"
                )
            part[0] = part[0][part[0].index(literal) :]
            locator += f" (starts at {literal!r})"
        if extent.get("end_before"):
            literal = extent["end_before"]
            if part[-1].count(literal) != 1:
                raise ValueError(f"end boundary must occur once on source line {end}: {literal!r}")
            part[-1] = part[-1][: part[-1].index(literal)].rstrip()
            locator += f" (ends before {literal!r})"
        text = "\n".join(part).strip()
        if not text:
            raise ValueError(f"empty selected source range: {start}–{end}")
        chunks.append(text)
        locators.append(locator)
        previous_end = end
    return "\n\n".join(chunks), "; ".join(locators)


def resource_for(record: dict, selection: dict | None, source_bytes: bytes | None):
    owner = record["function_id"]
    data = {"schema_version": "1.0", "locale": "en-US", "domain": "narration", "entries": {}}
    if record["source_availability"] == "unavailable":
        if selection or source_bytes is not None:
            raise ValueError(
                f"{owner}: source-unavailable record cannot acquire inferred source wording"
            )
        data["domain"] = "ui"
        data["entries"][f"hplus.review.{owner.lower()}.availability"] = {
            "text": "Historical source unavailable. Opener, function body and closer are not authored; reimplementation remains planned.",
            "status": "draft",
            "version": "1.0.0",
            "notes": "Review status only, not spoken narration. No reconstruction or previous candidate has been substituted for SOURCE.",
        }
        return (
            data,
            {slot: "Historical source unavailable; reimplementation planned." for slot in SLOTS},
            [],
        )
    if selection is None or source_bytes is None:
        raise ValueError(f"{owner}: explicit source selections are required")
    actual = hashlib.sha256(source_bytes).hexdigest()
    if actual != record["source"]["sha256"]:
        raise ValueError(f"{owner}: source hash changed; review the extents before importing")
    lines = source_bytes.decode("utf-8-sig").splitlines()
    if len(lines) != record["source"]["line_count"]:
        raise ValueError(f"{owner}: source line count changed")
    missing = selection["missing"]
    selected = selection["slots"]
    if set(selected) & set(missing) or set(SLOTS) - set(selected) != set(missing):
        raise ValueError(
            f"{owner}: every ordinary slot needs either a selection or an explicit missing reason"
        )
    for slot, ranges in selected.items():
        text, locators = select_text(lines, ranges)
        data["entries"][f"hplus.function.{owner.lower()}.{slot}"] = {
            "status": "draft",
            "version": "1.0.0",
            "notes": (
                f"Reference-derived review candidate; {record['source_status']}. "
                f"SOURCE {record['source']['file']}; SHA-256 {actual}; lines {locators}. "
                "Selected words and punctuation retained; shared preparation/state/return wording excluded. "
                "Source repetitions, transcription uncertainties and claims remain for human review. "
                + RIGHTS
                + " "
                + " ".join(selection["notes"])
            ),
            "text": text,
        }
    if not data["entries"]:
        raise ValueError(f"{owner}: available source has no selected content")
    return data, missing, selection["notes"]


def resource_for_proposal(record, proposal, raw, legacy):
    """Select user-proposed reconstruction text without changing SOURCE identity."""
    owner = record["function_id"]
    if record["source_availability"] != "unavailable" or record.get("source") is not None:
        raise ValueError(
            f"{owner}: proposal import is only for historical source-unavailable records"
        )
    input_record = proposal["input"]
    digest = hashlib.sha256(raw).hexdigest()
    if digest != input_record["sha256"]:
        raise ValueError(f"{owner}: proposal hash changed; review the extents before importing")
    lines = raw.decode("utf-8-sig").splitlines()
    if not lines or lines[0] != input_record["header"]:
        raise ValueError(f"{owner}: proposal document header does not match its recorded identity")
    label = re.sub(r"\s+\([^()]+\)$", "", lines[0].split(" — ", 1)[0])
    if label != legacy["name"]:
        raise ValueError(f"{owner}: proposal title does not match the function's legacy name")
    if lines.count("CLEAN RECORDING SCRIPT") != 1:
        raise ValueError(f"{owner}: proposal needs one explicit clean-script boundary")
    clean = lines.index("CLEAN RECORDING SCRIPT")
    if not legacy["commands"] or any(
        command not in lines[:clean] for command in legacy["commands"]
    ):
        raise ValueError(
            f"{owner}: proposal's listed legacy commands do not match function metadata"
        )
    end = (
        lines.index("END OF RECONSTRUCTED SCRIPT")
        if "END OF RECONSTRUCTED SCRIPT" in lines
        else len(lines)
    )
    selection = proposal["selection"]
    if set(selection["slots"]) != set(SLOTS) or selection["missing"]:
        raise ValueError(
            f"{owner}: proposed draft needs an explicit opener, body and closer selection"
        )
    notes = [
        "User-proposed reconstruction, not a recovered historical transcript. Historical source availability remains unavailable; reimplementation remains planned.",
        f"Proposed input: {input_record['file']}; SHA-256 {digest}; header {input_record['header']!r}.",
        "Identity checked against the document title and listed legacy commands, not inferred from the filename. Header claims of confirmation/authenticity are not independently verified.",
        "Only selected narration is reused; shared sections, production directions and non-narration prefatory notes remain separate. Suggested input timings are not measured evidence.",
        *selection["notes"],
    ]
    data = {"schema_version": "1.0", "locale": "en-US", "domain": "narration", "entries": {}}
    for slot, extents in selection["slots"].items():
        if any(
            not clean + 1 < extent["start_line"] <= extent["end_line"] <= end for extent in extents
        ):
            raise ValueError(
                f"{owner}: proposed narration extent leaves the clean-script boundaries"
            )
        text, locators = select_text(lines, extents)
        if any(line.strip().startswith(("[", "=")) for line in text.splitlines()):
            raise ValueError(
                f"{owner}: proposed narration contains production directions or delimiters"
            )
        data["entries"][f"hplus.function.{owner.lower()}.{slot}"] = {
            "status": "draft",
            "version": "1.0.0",
            "text": text,
            "notes": f"User-proposed reconstruction draft; input lines {locators}. "
            + " ".join(notes)
            + " "
            + RIGHTS,
        }
    return data, {}, notes


def prepare(source_root: Path, output: Path, plan_path: Path, *, write=False, proposal_plan=None):
    """Preflight every input and destination; write only create-once local proposals.

    No workspace records or external function layers participate in discovery.
    A proposal is deliberately not a locale resource: no domain, locale, entries
    or function_id at its root. Promotion requires a separate reviewed Git edit.
    """
    require_local_output(output)
    if output.resolve().is_relative_to(
        source_root.resolve()
    ) or source_root.resolve().is_relative_to(output.resolve()):
        raise ValueError("proposal output must be outside immutable source root")
    schema = json.loads((REPO_ROOT / "schemas/hplus-review-selection.schema.json").read_text())
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    jsonschema.validate(plan, schema)
    proposals = {}
    if proposal_plan is not None:
        proposed_plan = yaml.safe_load(proposal_plan.read_text(encoding="utf-8"))
        jsonschema.validate(proposed_plan, schema)
        proposals = proposed_plan.get("proposals", {})
    functions = {function.id: function for function in load_all_functions()}
    selections = plan["selections"]
    if (set(selections) | set(proposals)) - set(functions):
        raise ValueError("selection references an unknown canonical function")
    products = []
    for owner, function in sorted(functions.items()):
        content = function.data["content"]
        review = content.get("specifications", {}).get("analysis_review", {})
        evidence = content.get("evidence", {})
        raw = None
        if function.source_availability == "available":
            raw = checked_path(source_root, review["source_extent"]["file"]).read_bytes()
        record, _ = build_skeleton(owner, function.source_availability, review, evidence, raw)
        if owner in proposals:
            proposal = proposals[owner]
            data, missing, notes = resource_for_proposal(
                record,
                proposal,
                checked_path(source_root, proposal["input"]["file"]).read_bytes(),
                function.data["legacy"],
            )
        else:
            data, missing, notes = resource_for(record, selections.get(owner), raw)
        proposal = {
            "format": "ocf-editorial-review-proposal-v1",
            "authority": "none",
            "target_function": owner,
            "source_status": record["source_status"],
            "release_status": "pending-human-review",
            "candidate_entries": data["entries"],
            "missing": missing,
            "notes": notes,
        }
        target = output / f"{owner}.review-proposal.json"
        require_local_output(target)
        if target.is_symlink():
            raise ValueError("proposal destination must not be a symlink")
        if target.exists() and json.loads(target.read_text(encoding="utf-8")) != proposal:
            raise ValueError(
                f"{owner}: existing proposal has human edits or changed inputs; use a new output directory"
            )
        products.append((target, proposal))
    for target, proposal in products:
        print(f"{proposal['target_function']}: local review proposal only; {target.name}")
        if write and not target.exists():
            write_text_atomic(
                target, json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", overwrite=False
            )
    return products


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root", type=Path, default=REPO_ROOT / "references/HumanPlusTranscripts"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="isolated local proposal directory, outside runtime/source roots",
    )
    parser.add_argument(
        "--plan", type=Path, default=REPO_ROOT / "function-content/hplus-review-selections.yaml"
    )
    parser.add_argument(
        "--proposal-plan",
        type=Path,
        default=REPO_ROOT / "function-content/hplus-proposed-review-selections.yaml",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="create non-authoritative local proposals; never install or approve wording",
    )
    args = parser.parse_args()
    prepare(
        args.source_root,
        args.output,
        args.plan,
        write=args.write,
        proposal_plan=args.proposal_plan,
    )


if __name__ == "__main__":
    main()
