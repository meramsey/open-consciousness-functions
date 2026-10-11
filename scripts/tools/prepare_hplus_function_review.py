"""Prepare initial English function review resources from explicit source extents.

This is an offline editorial importer, not a runtime source loader. It creates
missing resources; explicit proposal import may populate untouched status-only
placeholders. Existing narration and subsequent human edits are preserved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import jsonschema
import yaml

from ocf_tools.indexes import load_all_functions
from ocf_tools.paths import REPO_ROOT

SLOTS = ("opener", "function-body", "closer")
RIGHTS = "Rights: user_cleared, per user's lawyer-clearance attestation. Wording review and finished-session release pending."


class LiteralDumper(yaml.SafeDumper):
    """Keep selected narration readable as literal multiline YAML."""


def _string(dumper, value):
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|" if "\n" in value else None)


LiteralDumper.add_representer(str, _string)


def dump(data):
    return yaml.dump(data, Dumper=LiteralDumper, allow_unicode=True, sort_keys=False, width=1000)


def select_text(lines: list[str], ranges: list[dict]) -> tuple[str, str]:
    """Select exact words, permitting explicit within-line boundaries only."""
    chunks = []
    locators = []
    previous_end = 0
    for extent in ranges:
        start, end = extent["start_line"], extent["end_line"]
        if not 1 <= start <= end <= len(lines) or start <= previous_end:
            raise ValueError(f"invalid, overlapping or unordered source range: {start}–{end}")
        part = list(lines[start - 1:end])
        locator = f"{start}–{end}"
        if extent.get("start_at"):
            literal = extent["start_at"]
            if part[0].count(literal) != 1:
                raise ValueError(f"start boundary must occur once on source line {start}: {literal!r}")
            part[0] = part[0][part[0].index(literal):]
            locator += f" (starts at {literal!r})"
        if extent.get("end_before"):
            literal = extent["end_before"]
            if part[-1].count(literal) != 1:
                raise ValueError(f"end boundary must occur once on source line {end}: {literal!r}")
            part[-1] = part[-1][:part[-1].index(literal)].rstrip()
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
            raise ValueError(f"{owner}: source-unavailable record cannot acquire inferred source wording")
        data["domain"] = "ui"
        data["entries"][f"hplus.review.{owner.lower()}.availability"] = {
            "text": "Historical source unavailable. Opener, function body and closer are not authored; reimplementation remains planned.",
            "status": "draft", "version": "1.0.0",
            "notes": "Review status only, not spoken narration. No reconstruction or previous candidate has been substituted for SOURCE.",
        }
        return data, {slot: "Historical source unavailable; reimplementation planned." for slot in SLOTS}, []
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
        raise ValueError(f"{owner}: every ordinary slot needs either a selection or an explicit missing reason")
    for slot, ranges in selected.items():
        text, locators = select_text(lines, ranges)
        data["entries"][f"hplus.function.{owner.lower()}.{slot}"] = {
            "status": "draft", "version": "1.0.0",
            "notes": (
                f"Reference-derived review candidate; {record['source_status']}. "
                f"SOURCE {record['source']['file']}; SHA-256 {actual}; lines {locators}. "
                "Selected words and punctuation retained; shared preparation/state/return wording excluded. "
                "Source repetitions, transcription uncertainties and claims remain for human review. "
                + RIGHTS + " " + " ".join(selection["notes"])
            ),
            "text": text,
        }
    if not data["entries"]:
        raise ValueError(f"{owner}: available source has no selected content")
    return data, missing, selection["notes"]


def header(owner, name, record, missing, notes):
    lines = [f"# {owner} — {name}", "# English function-specific review candidate; edit this file as the wording source of truth.",
             f"# Source status: {record['source_status']}; authentication remains unverified."]
    for slot, reason in missing.items():
        lines.append(f"# Missing {slot}: {reason}")
    for note in notes:
        lines.append(f"# Review note: {note}")
    return "\n".join(lines) + "\n"


def resource_for_proposal(record, proposal, raw, legacy):
    """Select user-proposed reconstruction text without changing SOURCE identity."""
    owner = record["function_id"]
    if record["source_availability"] != "unavailable" or record.get("source") is not None:
        raise ValueError(f"{owner}: proposal import is only for historical source-unavailable records")
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
    if not legacy["commands"] or any(command not in lines[:clean] for command in legacy["commands"]):
        raise ValueError(f"{owner}: proposal's listed legacy commands do not match function metadata")
    end = lines.index("END OF RECONSTRUCTED SCRIPT") if "END OF RECONSTRUCTED SCRIPT" in lines else len(lines)
    selection = proposal["selection"]
    if set(selection["slots"]) != set(SLOTS) or selection["missing"]:
        raise ValueError(f"{owner}: proposed draft needs an explicit opener, body and closer selection")
    notes = [
        "User-proposed reconstruction, not a recovered historical transcript. Historical source availability remains unavailable; reimplementation remains planned.",
        f"Proposed input: {input_record['file']}; SHA-256 {digest}; header {input_record['header']!r}.",
        "Identity checked against the document title and listed legacy commands, not inferred from the filename. Header claims of confirmation/authenticity are not independently verified.",
        "Only selected narration is reused; shared sections, production directions and non-narration prefatory notes remain separate. Suggested input timings are not measured evidence.",
        *selection["notes"],
    ]
    data = {"schema_version": "1.0", "locale": "en-US", "domain": "narration", "entries": {}}
    for slot, extents in selection["slots"].items():
        if any(not clean + 1 < extent["start_line"] <= extent["end_line"] <= end for extent in extents):
            raise ValueError(f"{owner}: proposed narration extent leaves the clean-script boundaries")
        text, locators = select_text(lines, extents)
        if any(line.strip().startswith(("[", "=")) for line in text.splitlines()):
            raise ValueError(f"{owner}: proposed narration contains production directions or delimiters")
        data["entries"][f"hplus.function.{owner.lower()}.{slot}"] = {
            "status": "draft", "version": "1.0.0", "text": text,
            "notes": f"User-proposed reconstruction draft; input lines {locators}. " + " ".join(notes) + " " + RIGHTS,
        }
    return data, {}, notes


def prepare(workspace: Path, source_root: Path, output: Path, plan_path: Path, *, write=False, report_path=None, proposal_plan=None, apply_proposals=False):
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    schema = json.loads((REPO_ROOT / "schemas/hplus-review-selection.schema.json").read_text())
    jsonschema.validate(plan, schema)
    functions = {function.id: function for function in load_all_functions()}
    owners = {owner: function.canonical_name for owner, function in functions.items()}
    proposals = {}
    if proposal_plan is not None:
        proposed_plan = yaml.safe_load(proposal_plan.read_text(encoding="utf-8"))
        jsonschema.validate(proposed_plan, schema)
        proposals = proposed_plan.get("proposals", {})
    selections = plan["selections"]
    if (set(selections) | set(proposals)) - set(owners):
        raise ValueError("selection references an unknown canonical function")
    products = []
    resource_schema = json.loads((REPO_ROOT / "schemas/locale-resource.schema.json").read_text())
    manifest_path = output / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    registered = {entry["file"]: entry for entry in manifest["resources"]}
    for owner, name in sorted(owners.items()):
        record = yaml.safe_load((workspace / "functions" / f"{owner}.yaml").read_text(encoding="utf-8"))
        if record["function_id"] != owner:
            raise ValueError(f"workspace record disagrees with owner {owner}")
        target = output / f"hplus-{owner}.yaml"
        existing = target.exists()
        current = yaml.safe_load(target.read_text(encoding="utf-8")) if existing else None
        if current is not None:
            jsonschema.validate(current, resource_schema)
        proposal = proposals.get(owner)
        use_proposal = proposal is not None and (apply_proposals or current is not None and current["domain"] == "narration")
        source_bytes = None
        if record["source"]:
            source = (source_root / record["source"]["file"]).resolve()
            if not source.is_relative_to(source_root.resolve()):
                raise ValueError(f"{owner}: source path leaves the supplied source root")
            source_bytes = source.read_bytes()
        if use_proposal:
            proposed_path = (source_root / proposal["input"]["file"]).resolve()
            if not proposed_path.is_relative_to(source_root.resolve()):
                raise ValueError(f"{owner}: proposal path leaves the supplied source root")
            data, missing, notes = resource_for_proposal(record, proposal, proposed_path.read_bytes(), functions[owner].data["legacy"])
        else:
            data, missing, notes = resource_for(record, selections.get(owner), source_bytes)
        jsonschema.validate(data, resource_schema)
        upgrade = False
        if existing:
            if use_proposal and current["domain"] == "ui" and apply_proposals:
                placeholder = resource_for(record, None, None)[0]
                if current != placeholder:
                    raise ValueError(f"{owner}: existing status-only file has human edits; refusing to replace it")
                upgrade = True
            elif current["locale"] != "en-US" or current["domain"] != data["domain"]:
                raise ValueError(f"{owner}: existing review resource has an incompatible locale/domain")
            else:
                data = current
        if target.name in registered and registered[target.name]["domain"] != data["domain"] and not upgrade:
            raise ValueError(f"{owner}: manifest domain mismatch")
        # Preflight all inputs before writing any resource or manifest.
        products.append((owner, name, record, data, missing, notes, target, existing, upgrade))
    for owner, name, record, data, missing, notes, target, existing, upgrade in products:
        print(f"{owner}: {'populate proposed draft' if upgrade else 'preserve existing' if existing else 'create'}; "
              f"missing {', '.join(missing) or 'none'}; {target.relative_to(output)}")
        if write and (not existing or upgrade):
            with target.open("w" if upgrade else "x", encoding="utf-8") as handle:
                handle.write(header(owner, name, record, missing, notes) + dump(data))
        if target.name not in registered:
            manifest["resources"].append({"file": target.name, "domain": data["domain"],
                                          "description": f"{name}: function-specific English review {'status' if data['domain'] == 'ui' else 'candidate'}"})
        elif upgrade:
            registered[target.name]["domain"] = "narration"
            registered[target.name]["description"] = f"{name}: user-proposed reconstruction draft; historical source unavailable"
    if write:
        if any(product[-1] for product in products):
            manifest["semantic_version"] = "1.5.0"
        elif any(product[-3].name not in registered for product in products):
            manifest["semantic_version"] = "1.4.0"
        manifest_path.write_text(dump(manifest), encoding="utf-8")
        report = ["# English HPlus function review", "", "Historical source selections and separately labeled user-proposed reconstructions prepared for human review; no narration has been approved or rendered by this importer.",
                  "", "Edit the linked YAML file: its entries are the wording source of truth. Shared narration stays in the separate `hplus-*.yaml` resources.",
                  "Missing spoken keys are omitted. User-proposed reconstructions are labeled separately from historical SOURCE; historical source-unavailable records remain unavailable and planned.",
                  "", "| Function | Name | Historical source status | Wording basis | Opener | Body | Closer | Editable English file |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for owner, name, record, data, missing, notes, target, existing, upgrade in products:
            cells = [
                "suggestion pending approval"
                if slot in missing and f"hplus.function.{owner.lower()}.{slot}" in data["entries"]
                else "missing"
                if slot in missing
                else "candidate"
                for slot in SLOTS
            ]
            basis = "user-proposed reconstruction" if owner in proposals and data["domain"] == "narration" else "historical source selection" if record["source"] else "status only"
            report.append(f"| {owner} | {name} | {record['source_status']} | {basis} | {' | '.join(cells)} | [{target.name}](../locales/en-US/{target.name}) |")
        report += ["", "## Boundary and uncertainty notes", ""]
        for owner, name, record, data, missing, notes, target, existing, upgrade in products:
            if missing or notes:
                report.append(f"### {owner} — {name}")
                report += [
                    f"- Historical source is missing {slot}; an OCF-authored suggestion is pending human approval: {data['entries'][f'hplus.function.{owner.lower()}.{slot}']['text']}"
                    if f"hplus.function.{owner.lower()}.{slot}" in data["entries"]
                    else f"- Missing {slot}: {reason}"
                    for slot, reason in missing.items()
                ]
                report += [f"- {note}" for note in notes]
                report.append("")
        report += ["## Import behavior", "", "`scripts/tools/prepare_hplus_function_review.py` reads the historical selection recipe and the separately labeled proposal recipe in `function-content/hplus-proposed-review-selections.yaml` only during offline editorial preparation. It verifies input hashes and identities. `--apply-proposals` replaces only untouched status-only placeholders; existing narration/human edits are preserved. Runtime composition reads committed locale resources only.", "",
                   "These are separate draft candidates with their wording basis recorded. Existing Relax, Hearing and Sleep Easy pilot editorial resources and RC1/V2/V2.1 material remain frozen.", ""]
        (report_path or REPO_ROOT / "docs/HPLUS_FUNCTION_REVIEW.md").write_text("\n".join(report), encoding="utf-8")
    return products


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=REPO_ROOT / ".ocf-authoring")
    parser.add_argument("--source-root", type=Path, default=REPO_ROOT / "references/HumanPlusTranscripts")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "locales/en-US")
    parser.add_argument("--plan", type=Path, default=REPO_ROOT / "function-content/hplus-review-selections.yaml")
    parser.add_argument("--report", type=Path, default=REPO_ROOT / "docs/HPLUS_FUNCTION_REVIEW.md")
    parser.add_argument("--proposal-plan", type=Path, default=REPO_ROOT / "function-content/hplus-proposed-review-selections.yaml")
    parser.add_argument("--apply-proposals", action="store_true", help="populate untouched status-only files from explicitly selected user proposals")
    parser.add_argument("--write", action="store_true", help="create missing review resources and update the review list/locale manifest")
    args = parser.parse_args()
    prepare(args.workspace, args.source_root, args.output, args.plan, write=args.write, report_path=args.report,
            proposal_plan=args.proposal_plan, apply_proposals=args.apply_proposals)


if __name__ == "__main__":
    main()
