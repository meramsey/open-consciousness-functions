"""Catalog-wide editorial status and immutable spoken-content boundaries."""

import hashlib
import json
from copy import deepcopy

import pytest
from ocf_tools.locale import LocaleCatalog
from ocf_tools.paths import REPO_ROOT

pytestmark = pytest.mark.integration


def test_all_function_metadata_is_useful_draft_without_changing_approved_content():
    catalog = LocaleCatalog()
    assert not catalog.problems
    pack = catalog.require("en-US")
    baseline = json.loads(
        (REPO_ROOT / "function-content/editorial/catalog-metadata-baseline-006.json").read_text()
    )
    assert len(pack.localized_functions) == len(baseline["functions"]) == 58
    for identity, data in pack.localized_functions.items():
        assert 3 <= len(data["tags"]) <= 6
        assert 2 <= len(data["common_uses"]) <= 5
        assert all(
            value["status"] == "draft" and value["text"].strip()
            for field in ("tags", "common_uses")
            for value in data[field]
        )
        protected = {
            key: deepcopy(data[key])
            for key in ("title", "description", "activation", "secondary_commands", "entries")
        }
        for entry in protected["entries"].values():
            entry.pop("notes", None)
        for command in [protected["activation"], *protected["secondary_commands"]]:
            command.pop("control", None)
            command.pop("procedure_steps", None)
        protected["activation"].pop("role", None)
        digest = hashlib.sha256(
            json.dumps(protected, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        assert digest == baseline["functions"][identity]["protected_sha256"]
        approved = {k: v for k, v in data["relationships"].items() if k != "proposals"}
        digest = hashlib.sha256(
            json.dumps(approved, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        assert digest == baseline["functions"][identity]["reviewed_relationships_sha256"]


def test_proposals_are_evidenced_drafts_and_six_approved_edges_remain_exact():
    from ocf_tools.guide_review import record, relationships, verify
    from ocf_tools.indexes import load_function_by_id

    pack = LocaleCatalog().require("en-US")
    ledger = record()
    assert verify() == []
    actual = []
    kinds = []
    for identity, data in pack.localized_functions.items():
        for edge in data["relationships"]["related_functions"]:
            actual.append((identity, edge["function_id"], edge["description"]["text"]))
        for proposal in data["relationships"].get("proposals", []):
            assert proposal["status"] == proposal["description"]["status"] == "draft"
            assert proposal["dependency"] == "optional"
            assert proposal["reciprocal_proposed"] is False
            assert {v["function_id"] for v in proposal["evidence"]} == {
                identity,
                proposal["function_id"],
            }
            for evidence in proposal["evidence"]:
                text = pack.localized_functions[evidence["function_id"]]["description"]["text"]
                assert hashlib.sha256(text.encode()).hexdigest() == evidence["sha256"]
            kinds.append(proposal["relationship_type"])
    expected = []
    for decision in ledger["decisions"]:
        owner = load_function_by_id(decision["source_id"])
        edge = next(
            row
            for row in relationships(owner)
            if row["relationship_id"] == decision["relationship_id"]
        )
        expected.append(
            (decision["source_id"], decision["related_id"], edge["approved_explanation"])
        )
    assert sorted(actual) == sorted(expected)
    assert len(actual) == 6
    assert kinds.count("related") == 14
    assert kinds.count("complementary") == 13


def test_current_locale_has_single_canonical_function_files_and_valid_locks():
    from ocf_tools.audio_defaults import check_lock
    from ocf_tools.function_catalog import resources

    pack = LocaleCatalog().require("en-US")
    declared = [r["file"] for r in pack.manifest["resources"]]
    assert len(declared) == len(set(declared))
    assert len(resources(REPO_ROOT)) == 58
    assert (
        len(pack.localized_function_files) == len(set(pack.localized_function_files.values())) == 58
    )
    assert not list(pack.path.glob("hplus-OCF-*.yaml"))
    assert not list(pack.path.glob("original-OCF-*.yaml"))
    assert not (REPO_ROOT / "functions").exists()
    for directory in (
        "function-content/editorial/historical-functions",
        "function-content/editorial/historical-locales",
        "function-content/bindings",
        "function-content/specifications",
        "function-content/decisions",
        "function-content/evidence",
    ):
        assert not (REPO_ROOT / directory).exists()
    for name in (
        "hplus-focus10.yaml",
        "hplus-focus11-open.yaml",
        "hplus-relaxation.yaml",
        "hplus-transmutation-box.yaml",
        "hplus-waking-return.yaml",
    ):
        assert name in declared and (pack.path / name).is_file()
    assert check_lock()["id"] == "OCF-AUDIO-DEFAULTS-HPLUS-016"
