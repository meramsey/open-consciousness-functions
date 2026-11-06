"""Canonical locale resources own current function identities and words."""

import pytest
from ocf_tools.function_catalog import resources
from ocf_tools.locale import LocaleCatalog
from ocf_tools.paths import REPO_ROOT

pytestmark = pytest.mark.integration


def test_exactly_one_canonical_resource_per_function_without_historical_trees():
    catalog = LocaleCatalog()
    assert not catalog.problems
    pack = catalog.require("en-US")
    rows = resources(REPO_ROOT)
    assert len(rows) == 58
    assert len({data["function_id"] for _, data in rows}) == 58
    assert len(pack.localized_functions) == 58
    assert len(set(pack.localized_function_files.values())) == 58
    assert all(
        (REPO_ROOT / "locales/en-US" / name).is_file()
        for name in pack.localized_function_files.values()
    )
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
    assert all(isinstance(data.get("record_metadata"), dict) for _, data in rows)
    assert all(data.get("record_metadata") and "content" in data for _, data in rows)
