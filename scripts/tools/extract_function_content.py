"""Initialize separated, explicitly partial research specifications without narration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from ocf_tools.content import BLOCKS, validate_layers  # noqa: E402
from ocf_tools.indexes import load_all_functions, load_yaml_file  # noqa: E402
from ocf_tools.utils import OCFError, write_text_atomic, yaml_safe_dump  # noqa: E402

MATCH_BLOCK = {
    "opener": "opener",
    "main": "main",
    "command_association": "association",
    "future_use": "future_use",
    "closer": "closer",
    "return": "handoff",
}


def initialize(inventory: dict, record, templates: list[dict]) -> dict:
    rows = [row for row in inventory["files"] if row["function_id"] == record.id]
    sources = {}
    observations = []
    for row in rows:
        sources.setdefault(
            row["sha256"],
            {
                "sha256": row["sha256"],
                "path": row["path"],
                "evidence_class": row["evidence_class"],
                "authentication": "operator-designated"
                if row["evidence_class"] in ("source_transcript", "partial_source_transcript")
                else "unverified",
                "completeness": row["completeness"],
            },
        )
        for category, candidates in row["candidate_locators"].items():
            if candidates and row["source_type"] == "txt":
                observations.append(
                    {
                        "id": f"{row['sha256']}:{category}",
                        "kind": "structural-inference",
                        "scope": "document",
                        "source_sha256": row["sha256"],
                        "category": category,
                        "line_candidates": candidates,
                        "confidence": "low",
                    }
                )
    observations = list({item["id"]: item for item in observations}.values())
    blocks = {name: {"status": "unknown", "operations": [], "evidence_refs": []} for name in BLOCKS}
    blocks["purpose"]["status"] = "specified"
    blocks["purpose"]["operations"] = ["consult-canonical-purpose-metadata"]
    for observation in observations:
        target = MATCH_BLOCK.get(observation["category"])
        if target:
            blocks[target]["status"] = "inferred"
            blocks[target]["evidence_refs"].append(observation["id"])
    selected = [template for template in templates if template.get("function_id") == record.id]
    resources = sorted(
        {
            override["narration_key"]
            for template in selected
            for section in template["sections"]
            for override in section.get("narration", {}).values()
            if override.get("narration_key")
        }
    )
    base = {"schema_version": "1.0", "function_id": record.id}
    evidence = {
        **base,
        "sources": list(sources.values()),
        "observations": observations,
        "questions": [
            "Source derivatives are not independently authenticated recordings",
            "Keyword candidate locators require full semantic review; absence of a match does not establish absence of an operation",
        ],
    }
    spec = {
        **base,
        "metadata_ref": "canonical-function-record",
        "command_ref": "canonical.command",
        "extraction_status": "partial",
        "maturity": "pilot" if any("PILOT" in template["id"] for template in selected) else "draft",
        "human_review": "required",
        "states": {"status": "unknown", "required": [], "preferred": []},
        "preparation": [],
        "blocks": blocks,
        "questions": [
            "Function-specific operations, state requirements and claim transformations require source review; no inferred runtime state binding"
        ],
    }
    binding = {
        **base,
        "session_templates": [template["id"] for template in selected],
        "narration_resources": [{"locale": "en-US", "key": key} for key in resources],
        "voice_sources": ["tts", "prerecorded-user", "externally-generated"] if resources else None,
        "duration": None,
    }
    decisions = {**base, "decisions": []}
    return {
        "evidence": evidence,
        "specifications": spec,
        "decisions": decisions,
        "bindings": binding,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory", type=Path, default=ROOT / "docs/research/humanplus-corpus-inventory.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    templates = [
        load_yaml_file(path) for path in (ROOT / "audio/templates/sessions").glob("*.yaml")
    ]
    pending = []
    for record in load_all_functions():
        layers = initialize(inventory, record, templates)
        errors = validate_layers(layers, record.id)
        if errors:
            raise OCFError(" | ".join(errors))
        for layer, data in layers.items():
            path = args.output / layer / f"{record.id}.yaml"
            if path.exists() and load_yaml_file(path) != data:
                raise OCFError(
                    f"refusing to overwrite reviewed/customized content: {path}; choose a separate output for comparison"
                )
            pending.append((path, data))
    for path, data in pending:
        write_text_atomic(path, yaml_safe_dump(data))
    print(
        f"Initialized {len(pending) // 4} partial research records; no localized wording authored"
    )


if __name__ == "__main__":
    main()
