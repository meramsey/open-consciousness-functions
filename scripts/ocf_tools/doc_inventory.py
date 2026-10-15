"""Tracked documentation inventory with explicit machine-audit limitations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess

from .paths import REPO_ROOT
from .utils import write_text_atomic

INVENTORY = REPO_ROOT / "docs" / "documentation-index.json"
BASELINE = "351985e8362879d8a2ddac74c36327641d9a6402"


def build_inventory() -> dict:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True
    )
    paths = sorted(
        p
        for p in result.stdout.decode("utf-8").split("\0")
        if p
        and (
            p.endswith(".md")
            or p.startswith("schemas/")
            or p in ("scripts/ocf_tools/cli.py", "scripts/ocf_tools/prompts.py")
        )
    )
    rows = []
    for name in paths:
        if name.startswith(("references/HumanPlusTranscripts/", "ReusablePrompts/")):
            continue
        path = REPO_ROOT / name
        text = path.read_text(encoding="utf-8")
        heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        generated = "GENERATED FILE" in text[:400] or "GENERATED —" in text[:400]
        historical = (
            name.startswith(("docs/releases/", "docs/research/", "docs/drafts/"))
            or "Bootstrap_Prompt" in name
        )
        broken = []
        if name.endswith(".md"):
            from tools.check_markdown_links import check_file

            broken = [line.replace(str(REPO_ROOT), ".") for line in check_file(path)]
        commands = sorted(
            set(re.findall(r"(?:scripts/ocf\.py|\bocf)\s+([a-z][a-z-]+(?: [a-z][a-z-]+)?)", text))
        )
        schemas = sorted(set(re.findall(r"schemas/[\w.-]+\.json", text)))
        rows.append(
            {
                "path": name,
                "purpose": heading.group(1) if heading else path.stem,
                "audience": "maintainers/research reviewers"
                if historical
                else "contributors and agents",
                "canonical_source": "historical checkpoint (not current implementation)"
                if historical
                else ("schemas and scripts/ocf_tools; CLI capabilities is the live command index"),
                "related_commands": commands,
                "related_schemas": schemas,
                "implementation_baseline": BASELINE,
                "last_verified_implementation_checkpoint": None,
                "verification": "machine inventory and internal-link check; not a semantic accuracy certification",
                "maintenance": "generated" if generated else "manual",
                "historical": historical,
                "broken_references": broken,
                "duplicate_or_contradictory_information": [],
                "missing_information": ["per-document semantic review not recorded"]
                if historical
                else [],
                "proposed_correction": "retain historical claims; consult current workflow guides"
                if historical
                else "use docs/README.md for authoritative navigation",
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    duplicates = {}
    for row in rows:
        duplicates.setdefault(row["sha256"], []).append(row["path"])
    for row in rows:
        row["duplicate_or_contradictory_information"] = [
            f"identical content: {p}" for p in duplicates[row["sha256"]] if p != row["path"]
        ]
    return {
        "schema_version": "1.0",
        "generator": "ocf.doc_inventory/1",
        "total": len(rows),
        "documents": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    data = build_inventory()
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.check:
        fresh = INVENTORY.is_file() and INVENTORY.read_text(encoding="utf-8") == text
    else:
        write_text_atomic(INVENTORY, text)
        fresh = True
    print(
        json.dumps(
            {
                "documents": data["total"],
                "fresh": fresh,
                "broken_references": sum(
                    len(row["broken_references"]) for row in data["documents"]
                ),
            }
        )
    )
    return 0 if fresh else 1


if __name__ == "__main__":
    raise SystemExit(main())
