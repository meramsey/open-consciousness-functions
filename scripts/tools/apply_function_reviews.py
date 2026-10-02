"""Apply manually authored full-content analysis; never extract semantics by keywords."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from ocf_tools.content import BLOCKS, load_layers, validate_layers  # noqa: E402
from ocf_tools.indexes import load_yaml_file  # noqa: E402
from ocf_tools.utils import OCFError, write_text_atomic, yaml_safe_dump  # noqa: E402

SECTIONS = (
    "identity",
    "purpose",
    "preparation",
    "state",
    "opener",
    "main",
    "association",
    "rehearsal",
    "future_use",
    "suspend_cancel_reset",
    "closer",
    "consolidation",
    "handoff",
    "safety_claims",
    "conversion",
    "provenance",
)


def apply_review(function_id: str, notes: dict, corpus: Path) -> dict:
    layers = load_layers(function_id)
    data = (corpus / notes["source"]).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    source = next(
        (
            item
            for item in layers["evidence"]["sources"]
            if item["sha256"] == sha and item["path"] == notes["source"]
        ),
        None,
    )
    if source is None:
        raise OCFError("reviewed source does not match hash-addressed evidence")
    line_count = len(data.decode("utf-8-sig").splitlines())
    if notes["inspected_lines"] != [1, line_count]:
        raise OCFError(f"full-source extent mismatch: {function_id}; actual lines={line_count}")

    def locator(bounds):
        return {
            "source_sha256": sha,
            "file": source["path"],
            "content_group_sha256": source.get("normalized_content_sha256"),
            "start_line": bounds[0],
            "end_line": bounds[1],
        }

    extent = locator(notes["inspected_lines"])
    answers = {}
    for section in SECTIONS:
        if section == "identity":
            summary = "Canonical/legacy identity, command variants and compatibility metadata retained; source cue association inspected without inventing a new command."
            bounds = notes["locators"]["association"]
        elif section == "provenance":
            summary = (
                f"Complete available {source['evidence_class']} text inspected; shared representations are not independent corroboration. Source accuracy/authentication remains unresolved. "
                + notes["uncertainties"]
            )
            bounds = notes["inspected_lines"]
        elif section == "safety_claims":
            summary = (
                "; ".join(notes["claims"])
                + ". Claims are classified as source assertions, not accepted OCF mechanisms/outcomes."
            )
            bounds = notes["locators"][section]
        else:
            value = notes[section]
            summary = "; ".join(value) if isinstance(value, list) else value
            bounds = notes["locators"].get(section, notes["locators"]["main"])
        status = (
            "unknown"
            if summary == "unknown"
            else ("inferred" if source["evidence_class"] == "reconstructed_mockup" else "supported")
        )
        status = notes.get("statuses", {}).get(section, status)
        if status == "unknown":
            summary = (
                "Investigated the full available source; this operation is not established. "
                + notes["uncertainties"]
            )
        if section == "conversion":
            status = "inferred"
        answers[section] = {"status": status, "summary": summary, "locators": [locator(bounds)]}
    review = {
        "method": "complete-available-source-content-review",
        "family": notes["family"],
        "source_extent": extent,
        "sections": answers,
        "claim_categories": notes["claims"],
        "scope": "documentary extraction; not narration approval, historical authentication or runtime state binding",
    }
    spec = layers["specifications"]
    for section in BLOCKS:
        observation_id = f"review:{function_id}:{section}"
        bounds = answers[section]["locators"][0]
        observation = {
            "id": observation_id,
            "kind": "function-specification-inference",
            "scope": "document",
            "source_sha256": sha,
            "category": section,
            "line_candidates": [bounds["start_line"], bounds["end_line"]],
            "confidence": "medium" if answers[section]["status"] != "unknown" else "unknown",
        }
        layers["evidence"]["observations"] = [
            item for item in layers["evidence"]["observations"] if item["id"] != observation_id
        ] + [observation]
        if answers[section]["status"] in ("unknown", "not-present", "not-applicable"):
            spec["blocks"][section] = {
                "status": answers[section]["status"],
                "operations": [],
                "evidence_refs": [observation_id],
            }
        else:
            operations = (
                notes["main"] if section == "main" else [f"documented-{section.replace('_', '-')}"]
            )
            spec["blocks"][section] = {
                "status": "inferred",
                "operations": operations,
                "evidence_refs": [observation_id],
            }
    spec["analysis_review"] = review
    spec["extraction_status"] = "complete"
    spec["questions"] = [notes["uncertainties"], notes["conversion"]]
    errors = validate_layers(layers, function_id)
    if errors:
        raise OCFError(" | ".join(errors))
    return layers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notes", type=Path)
    parser.add_argument("--corpus", type=Path, default=ROOT / "references/HumanPlusTranscripts")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    reviews = load_yaml_file(args.notes)
    for function_id, notes in reviews["functions"].items():
        notes = {**reviews.get("defaults", {}), **notes}
        layers = apply_review(function_id, notes, args.corpus)
        if args.apply:
            for layer in ("evidence", "specifications"):
                write_text_atomic(
                    ROOT / "function-content" / layer / f"{function_id}.yaml",
                    yaml_safe_dump(layers[layer]),
                )
    print(
        f"Validated full-content analytical reviews for {len(reviews['functions'])} functions; no wording or approval changes"
    )


if __name__ == "__main__":
    main()
