"""Catalog-wide editorial status and immutable spoken-content boundaries."""

import hashlib
import json

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
            key: data[key]
            for key in ("title", "description", "activation", "secondary_commands", "entries")
        }
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
    pack = LocaleCatalog().require("en-US")
    ledger = json.loads(
        (REPO_ROOT / "function-content/editorial/guide-review-001.json").read_text()
    )
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
    assert sorted(actual) == sorted(
        (v["source_id"], v["related_id"], v["approved_explanation"]) for v in ledger["decisions"]
    )
    assert len(actual) == 6
    assert kinds.count("related") == 14
    assert kinds.count("complementary") == 13


def test_clean_active_directory_and_all_65_virtual_historical_resources():
    from ocf_tools.audio_defaults import check_lock
    from ocf_tools.locale_history import historical_resources, predecessor, read_logical

    pack = LocaleCatalog().require("en-US")
    names = historical_resources(REPO_ROOT)
    assert len(names) == 65
    declared = [r["file"] for r in pack.manifest["resources"]]
    assert len(declared) == len(set(declared))
    assert all(name not in {"locales/en-US/" + f for f in declared} for name in names)
    assert (
        len(pack.localized_function_files) == len(set(pack.localized_function_files.values())) == 58
    )
    assert not list(pack.path.glob("hplus-OCF-*.yaml"))
    assert not list(pack.path.glob("original-OCF-*.yaml"))
    for name, row in names.items():
        assert not (REPO_ROOT / name).exists()
        text = read_logical(REPO_ROOT, name)
        assert hashlib.sha256(text.encode()).hexdigest() == row["sha256"]
        assert predecessor(REPO_ROOT, name, text)
    for name in (
        "hplus-focus10.yaml",
        "hplus-focus11-open.yaml",
        "hplus-relaxation.yaml",
        "hplus-transmutation-box.yaml",
        "hplus-waking-return.yaml",
    ):
        assert name in declared and (pack.path / name).is_file()
    assert check_lock()["id"] == "OCF-AUDIO-DEFAULTS-HPLUS-015"
