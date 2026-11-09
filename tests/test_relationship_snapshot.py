"""Per-operation reuse must not become stale or share mutable projections."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from ocf_tools import guide_review
from ocf_tools.locale import LocaleCatalog
from ocf_tools.utils import OCFError


@pytest.fixture
def relationship_source(monkeypatch):
    data = {
        "function_id": "OCF-TST-001",
        "record_metadata": {
            "editorial_decisions": [
                {
                    "kind": "approved-relationship",
                    "relationship_id": "rel-1",
                    "related_function_id": "OCF-TST-002",
                    "relationship_type": "related",
                    "dependency": "optional",
                    "reciprocal_approved": False,
                    "decision_source": "human review",
                    "source_row_sha256": "a" * 64,
                    "source_commit": "b" * 40,
                }
            ]
        },
        "relationships": {
            "related_functions": [
                {
                    "function_id": "OCF-TST-002",
                    "description_key": "relationship.test",
                    "description": {"text": "Approved explanation."},
                }
            ]
        },
    }
    reads = []

    def resources(root, locale):
        reads.append((root, locale))
        return [(None, deepcopy(data))]

    monkeypatch.setattr(guide_review, "resources", resources)
    return SimpleNamespace(data=data, reads=reads, owner=SimpleNamespace(id=data["function_id"]))


@pytest.mark.unit
def test_relationships_read_once_and_refresh_between_operations(relationship_source):
    f = relationship_source
    first = guide_review.relationships(f.owner)
    assert len(f.reads) == 1
    f.data["relationships"]["related_functions"][0]["description"]["text"] = "Changed explanation."
    second = guide_review.relationships(f.owner)
    assert len(f.reads) == 2
    assert first[0]["approved_explanation"] == "Approved explanation."
    assert second[0]["approved_explanation"] == "Changed explanation."


@pytest.mark.unit
def test_snapshot_reuses_validated_inputs_without_sharing_outputs(relationship_source):
    f = relationship_source
    snapshot = guide_review.resource_snapshot()
    first = guide_review.relationships(f.owner, snapshot=snapshot)
    first[0]["approved_explanation"] = "Caller mutation."
    assert (
        guide_review.relationships(f.owner, snapshot=snapshot)[0]["approved_explanation"]
        == "Approved explanation."
    )
    assert len(f.reads) == 1


@pytest.mark.unit
def test_missing_owner_and_missing_approved_relation_still_fail(relationship_source):
    f = relationship_source
    with pytest.raises(OCFError, match="owner resource is missing"):
        guide_review.relationships(f.owner, snapshot={})
    f.data["relationships"]["related_functions"] = []
    with pytest.raises(OCFError, match="approved relationship is missing"):
        guide_review.relationships(f.owner)


@pytest.mark.integration
def test_locale_catalog_reads_one_relationship_snapshot_per_construction(monkeypatch):
    original = guide_review.resources
    reads = []

    def counted(*args, **kwargs):
        reads.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(guide_review, "resources", counted)
    for _ in range(2):
        assert not LocaleCatalog().problems
    assert len(reads) == 2
