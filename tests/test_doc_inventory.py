import json

from ocf_tools.doc_inventory import INVENTORY, build_inventory


def test_tracked_documentation_inventory_is_fresh_and_scoped():
    inventory = build_inventory()
    assert json.loads(INVENTORY.read_text(encoding="utf-8")) == inventory
    paths = {row["path"] for row in inventory["documents"]}
    assert {
        "README.md",
        "AGENTS.md",
        "docs/MCP.md",
        "schemas/function.schema.json",
        "scripts/ocf_tools/cli.py",
        "scripts/ocf_tools/prompts.py",
    } <= paths
    assert not any(
        p.startswith(("ReusablePrompts/", "references/HumanPlusTranscripts/", ".ocf-work/"))
        for p in paths
    )
    assert not any(row["broken_references"] for row in inventory["documents"])
    assert inventory["total"] == len(paths)
