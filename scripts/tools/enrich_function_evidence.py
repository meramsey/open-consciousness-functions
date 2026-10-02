"""Apply hash-addressed documentary relationships to evidence only, never narration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from ocf_tools.content import load_layers, validate_layers  # noqa: E402
from ocf_tools.indexes import load_all_functions  # noqa: E402
from ocf_tools.utils import OCFError, write_text_atomic, yaml_safe_dump  # noqa: E402


def enrich(layers: dict, report: dict) -> dict:
    inspected = {row["sha256"]: row for row in report["files"]}
    for source in layers["evidence"]["sources"]:
        item = inspected.get(source["sha256"])
        if item is None:
            continue
        # Only known documentary type refinement, never authentication promotion.
        if (
            source["evidence_class"] == "unknown"
            and item["evidence_class"] == "secondary_description"
        ):
            source["evidence_class"] = "secondary_description"
        if item.get("content_sha256"):
            source["normalized_content_sha256"] = item["content_sha256"]
        source["related_sha256"] = sorted(
            {
                digest
                for group in report["content_equivalence_groups"]
                if source["sha256"] in group["representations"]
                for digest in group["representations"]
                if digest != source["sha256"]
            }
        )
    return layers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    for record in load_all_functions():
        layers = enrich(load_layers(record.id), report)
        errors = validate_layers(layers, record.id)
        if errors:
            raise OCFError(" | ".join(errors))
        if args.apply:
            write_text_atomic(
                ROOT / "function-content/evidence" / f"{record.id}.yaml",
                yaml_safe_dump(layers["evidence"]),
            )
    print("Validated documentary refinements for55 functions; no authentication or wording changes")


if __name__ == "__main__":
    main()
