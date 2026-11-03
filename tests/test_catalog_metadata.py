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
