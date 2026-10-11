"""Prepare initial English function review resources from explicit source extents.

This is an offline editorial importer, not a runtime source loader. It creates
only missing resource files and never overwrites subsequent human edits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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


def prepare(workspace: Path, source_root: Path, output: Path, plan_path: Path, *, write=False, report_path=None):
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    schema = json.loads((REPO_ROOT / "schemas/hplus-review-selection.schema.json").read_text())
    jsonschema.validate(plan, schema)
    owners = {function.id: function.canonical_name for function in load_all_functions()}
    selections = plan["selections"]
    if set(selections) - set(owners):
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
        source_bytes = None
        if record["source"]:
            source = (source_root / record["source"]["file"]).resolve()
            if not source.is_relative_to(source_root.resolve()):
                raise ValueError(f"{owner}: source path leaves the supplied source root")
            source_bytes = source.read_bytes()
        data, missing, notes = resource_for(record, selections.get(owner), source_bytes)
        jsonschema.validate(data, resource_schema)
        target = output / f"hplus-{owner}.yaml"
        existing = target.exists()
        if existing:
            current = yaml.safe_load(target.read_text(encoding="utf-8"))
            jsonschema.validate(current, resource_schema)
            if current["locale"] != "en-US" or current["domain"] != data["domain"]:
                raise ValueError(f"{owner}: existing review resource has an incompatible locale/domain")
            data = current
        if target.name in registered and registered[target.name]["domain"] != data["domain"]:
            raise ValueError(f"{owner}: manifest domain mismatch")
        # Preflight all inputs before writing any resource or manifest.
        products.append((owner, name, record, data, missing, notes, target, existing))
    for owner, name, record, data, missing, notes, target, existing in products:
        print(f"{owner}: {'preserve existing' if existing else 'create'}; "
              f"missing {', '.join(missing) or 'none'}; {target.relative_to(output)}")
        if write and not existing:
            with target.open("x", encoding="utf-8") as handle:
                handle.write(header(owner, name, record, missing, notes) + dump(data))
        if target.name not in registered:
            manifest["resources"].append({"file": target.name, "domain": data["domain"],
                                          "description": f"{name}: function-specific English review {'status' if data['domain'] == 'ui' else 'candidate'}"})
    if write:
        if any(target.name not in registered for *_, target, existing in products):
            manifest["semantic_version"] = "1.4.0"
        manifest_path.write_text(dump(manifest), encoding="utf-8")
        report = ["# English HPlus function review", "", "Initial source selections prepared for human review; no narration has been approved or rendered by this importer.",
                  "", "Edit the linked YAML file: its entries are the wording source of truth. Shared narration stays in the separate `hplus-*.yaml` resources.",
                  "Missing spoken keys are omitted, not filled with placeholders. Source-unavailable files contain UI review status only and cannot compose as spoken sessions.",
                  "", "| Function | Name | Source status | Opener | Body | Closer | Editable English file |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for owner, name, record, data, missing, notes, target, existing in products:
            cells = ["missing" if slot in missing else "candidate" for slot in SLOTS]
            report.append(f"| {owner} | {name} | {record['source_status']} | {' | '.join(cells)} | [{target.name}](../locales/en-US/{target.name}) |")
        report += ["", "## Boundary and uncertainty notes", ""]
        for owner, name, record, data, missing, notes, target, existing in products:
            if missing or notes:
                report.append(f"### {owner} — {name}")
                report += [f"- Missing {slot}: {reason}" for slot, reason in missing.items()]
                report += [f"- {note}" for note in notes]
                report.append("")
        report += ["## Import behavior", "", "`scripts/tools/prepare_hplus_function_review.py` reads the explicit extent recipe in `function-content/hplus-review-selections.yaml` and the local SOURCE records only during editorial preparation. It verifies each source hash and never overwrites an existing locale file. Runtime composition reads committed locale resources only.", "",
                   "These are separate source-derived candidates. Existing Relax, Hearing and Sleep Easy pilot editorial resources and RC1/V2/V2.1 material remain frozen.", ""]
        (report_path or REPO_ROOT / "docs/HPLUS_FUNCTION_REVIEW.md").write_text("\n".join(report), encoding="utf-8")
    return products


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=REPO_ROOT / ".ocf-authoring")
    parser.add_argument("--source-root", type=Path, default=REPO_ROOT / "references/HumanPlusTranscripts")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "locales/en-US")
    parser.add_argument("--plan", type=Path, default=REPO_ROOT / "function-content/hplus-review-selections.yaml")
    parser.add_argument("--report", type=Path, default=REPO_ROOT / "docs/HPLUS_FUNCTION_REVIEW.md")
    parser.add_argument("--write", action="store_true", help="create missing review resources and update the review list/locale manifest")
    args = parser.parse_args()
    prepare(args.workspace, args.source_root, args.output, args.plan, write=args.write, report_path=args.report)


if __name__ == "__main__":
    main()
