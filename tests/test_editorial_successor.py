"""Finite source-only editorial approval fails closed outside exact scope."""

from copy import deepcopy

import pytest
from ocf_tools import editorial_successor
from ocf_tools.function_catalog import resources
from ocf_tools.paths import REPO_ROOT
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.integration


def test_exact_approved_resources_and_immutable_receipts():
    receipt = editorial_successor.verify_resources()
    assert len(receipt["resources"]) == 10
    assert receipt["publication_authorized"] is False
    keys = receipt["hashes"]["resolved_entries"]
    assert len([key for key in keys if key.startswith("hplus.")]) == 28
    assert not any(
        "ocf-bod-008.opener" in key or "ocf-bod-008.function-body" in key for key in keys
    )


@pytest.mark.parametrize("field", ["cue", "lifecycle", "immune-body", "narration", "relationship"])
def test_unapproved_mutations_fail_closed(field):
    snapshot = {data["function_id"]: deepcopy(data) for _, data in resources(REPO_ROOT)}
    data = snapshot["OCF-BOD-001"]
    if field == "cue":
        data["activation"]["spoken_cue"]["text"] += " other"
    elif field == "lifecycle":
        data["lifecycle"]["persistence"] = "unapproved"
    elif field == "immune-body":
        snapshot["OCF-BOD-008"]["entries"]["hplus.function.ocf-bod-008.function-body"]["text"] += (
            " other"
        )
    elif field == "narration":
        data["entries"]["hplus.function.ocf-bod-001.closer"]["text"] += " other"
    else:
        data["relationships"]["related_functions"] = []
    with pytest.raises(OCFError, match="canonical resource differs"):
        editorial_successor.verify_resources(snapshot=snapshot)


def test_only_bound_previous_hash_can_advance():
    receipt = editorial_successor.receipt()
    row = receipt["hashes"]["narration_sha256"]["OCF-BOD-001"]
    assert (
        editorial_successor.expected_hash("narration_sha256", "OCF-BOD-001", row["before"])
        == row["after"]
    )
    with pytest.raises(OCFError, match="previous hash differs"):
        editorial_successor.expected_hash("narration_sha256", "OCF-BOD-001", "0" * 64)
    assert (
        editorial_successor.expected_hash("lifecycle_sha256", "OCF-BOD-001", "unchanged")
        == "unchanged"
    )
    assert (
        editorial_successor.expected_hash("narration_sha256", "OCF-UNKNOWN-001", "unchanged")
        == "unchanged"
    )


def test_modified_receipt_fails_closed(tmp_path):
    path = tmp_path / editorial_successor.RECEIPT
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    with pytest.raises(OCFError, match="receipt differs"):
        editorial_successor.receipt(tmp_path)


def test_modified_predecessor_fails_closed(tmp_path):
    path = tmp_path / editorial_successor.RECEIPT
    path.parent.mkdir(parents=True)
    path.write_bytes((REPO_ROOT / editorial_successor.RECEIPT).read_bytes())
    receipt = editorial_successor.receipt()
    for name in receipt["predecessors"]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / name).read_bytes())
    target.write_text("{}")
    with pytest.raises(OCFError, match="predecessor differs"):
        editorial_successor.receipt(tmp_path)
