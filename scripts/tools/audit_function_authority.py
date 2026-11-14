"""Audit tracked structured resources, independent of retired directory names."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ocf_tools.function_catalog import resources
from ocf_tools.paths import REPO_ROOT
from ocf_tools.utils import yaml_safe_load

# These are schema/projection examples, not discoverable function definitions.
# Pin both location and dummy identity; never exempt a real function by directory.
EXAMPLES = {
    "templates/function.yaml": "OCF-XXX-000",
    "tests/fixtures/function-sample.yaml": "OCF-FND-099",
}


def audit(root: Path = REPO_ROOT) -> dict:
    """Require every definition and function narration entry to have one owner.

    Nested record_metadata and dependency hashes are provenance, not definitions.
    Git's inventory deliberately excludes local/private editorial workspaces.
    """
    tracked = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--", "*.yaml", "*.yml", "*.json"], cwd=root
        )
        .decode()
        .split("\0")
    )
    authorities = {}
    for manifest in sorted((root / "locales").glob("*/manifest.yaml")):
        for path, data in resources(root, manifest.parent.name):
            authorities[path.relative_to(root).as_posix()] = data["function_id"]
    problems = []
    inspected = 0
    for name in filter(None, tracked):
        path = root / name
        text = path.read_text(encoding="utf-8")
        if text.startswith("GENERATED FILE — DO NOT EDIT DIRECTLY\n\n"):
            text = text.split("\n\n", 1)[1]
        data = json.loads(text) if path.suffix == ".json" else yaml_safe_load(text)
        inspected += 1
        if not isinstance(data, dict):
            continue
        if (
            name in EXAMPLES
            and data.get("id") == EXAMPLES[name]
            and data["id"] not in authorities.values()
        ):
            continue
        definition = data.get("domain") == "function" or (
            "canonical" in data and "id" in data and "lifecycle" in data
        )
        entries = data.get("entries", {})
        narration = isinstance(entries, dict) and any(
            key.startswith("hplus.function.") for key in entries
        )
        if (definition or narration) and name not in authorities:
            problems.append(f"noncanonical function authority: {name}")
        if name in authorities and data.get("domain") != "function":
            problems.append(f"invalid canonical function domain: {name}")
    canonical = resources(root)
    if len(canonical) != 58 or len({data["function_id"] for _, data in canonical}) != 58:
        problems.append("en-US must contain exactly 58 unique function definitions")
    return {"structured_files": inspected, "canonical_en_US": len(canonical), "problems": problems}


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result["problems"]))
