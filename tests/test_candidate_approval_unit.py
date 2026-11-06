"""Canonical approval metadata is hash-only and scope-limited."""

import pytest
from ocf_tools import candidate_approval
from ocf_tools.editorial_candidates import CANDIDATES
from ocf_tools.indexes import load_function_by_id
from ocf_tools.validators import _load_schema, validate_against_schema

pytestmark = pytest.mark.unit


def test_approval_projection_contains_only_canonical_decisions_and_digests():
    record = candidate_approval.record()
    assert record["id"] == "OCF-APPROVED-CANDIDATES-001"
    assert set(record["approvals"]) == set(CANDIDATES)
    assert not record["release_ready"] and not record["listening_approval"]
    assert "files" not in record and "speech" not in record
    for row in record["approvals"].values():
        assert row["user_response"] == "1"
        assert len(row["snapshot_sha256"]) == 64
        assert all(len(digest) == 64 for digest in row["resolved_sha256"].values())
        assert not any(isinstance(value, str) and len(value) > 80 for value in row.values())


@pytest.mark.parametrize("identity", CANDIDATES.values())
def test_approval_is_embedded_in_the_matching_canonical_locale_resource(identity):
    record = load_function_by_id(identity)
    assert record is not None
    approval = record.path.read_text(encoding="utf-8")
    import yaml

    resource = yaml.safe_load(approval)
    metadata = resource["record_metadata"]["editorial_approval"]
    assert metadata["approval_id"] == "OCF-APPROVED-CANDIDATES-001"
    assert metadata["decision"] == "approve_full_draft"
    assert metadata["release_ready"] is False
    assert metadata["listening_approval"] is False


def test_malformed_approval_hash_fails_canonical_schema_validation():
    record = load_function_by_id("OCF-EXP-006")
    import yaml

    resource = yaml.safe_load(record.path.read_text(encoding="utf-8"))
    resource["record_metadata"]["editorial_approval"]["presented_snapshot_sha256"] = "not-a-hash"
    errors = validate_against_schema(resource, _load_schema("localized-function.schema.json"))
    assert any("presented_snapshot_sha256" in error for error in errors)


def test_approval_compatibility_view_does_not_restore_predecessor_text():
    record = candidate_approval.record()
    assert all("before" not in row and "text" not in row for row in record["approvals"].values())

    assert candidate_approval.predecessor(None, "retired-resource", "canonical text") == (
        "canonical text"
    )
    assert candidate_approval.before_texts(None, {"entry": "canonical text"}) == {
        "entry": "canonical text"
    }


def test_approval_projection_fails_closed_when_an_owner_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(candidate_approval, "load_functions", lambda root: [])

    assert candidate_approval.record(tmp_path) is None


def test_approval_projection_fails_closed_when_embedded_metadata_is_missing(monkeypatch, tmp_path):
    from types import SimpleNamespace

    import yaml

    identity = next(iter(CANDIDATES.values()))
    path = tmp_path / "locales/en-US/function.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump({"function_id": identity}), encoding="utf-8")
    monkeypatch.setattr(
        candidate_approval,
        "load_functions",
        lambda root: [SimpleNamespace(id=identity, path=path)],
    )

    assert candidate_approval.record(tmp_path) is None


def test_approval_verification_rejects_an_alternate_catalog_root(tmp_path):
    assert candidate_approval.verify(tmp_path) == [
        "approval verification requires the canonical repository locale catalog"
    ]
