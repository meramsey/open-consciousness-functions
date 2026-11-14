"""Hash-only verification of the finite source-only November 14 editorial approval.

This module never supplies function content, restores predecessor wording, or
changes runtime resolution. Historical receipts remain immutable.
"""

from __future__ import annotations

import hashlib
import json

from .paths import REPO_ROOT
from .utils import OCFError

RECEIPT = "function-content/editorial/approved-editorial-20261114.json"
RECEIPT_SHA256 = "0610a99983a5121179c6d4f5e5450c89f01287d99619858d6f43f1b76d95010b"


def receipt(root=REPO_ROOT):
    raw = (root / RECEIPT).read_bytes()
    if hashlib.sha256(raw).hexdigest() != RECEIPT_SHA256:
        raise OCFError("editorial successor receipt differs from approved scope")
    data = json.loads(raw)
    for path, expected in data["predecessors"].items():
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != expected:
            raise OCFError("editorial successor predecessor differs: " + path)
    return data


def verify_resources(root=REPO_ROOT, snapshot=None):
    """Validate exact approved resources, including every untouched field."""
    from .function_catalog import resources

    approved = receipt(root)
    if snapshot is None:
        snapshot = {data["function_id"]: data for _, data in resources(root)}
    for identity, expected in approved["resources"].items():
        actual = hashlib.sha256(
            json.dumps(
                snapshot.get(identity), sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode()
        ).hexdigest()
        if actual != expected["after"]:
            raise OCFError("editorial successor canonical resource differs: " + identity)
    return approved


def expected_hash(kind, identity, previous, root=REPO_ROOT, *, approved=None):
    """Advance one exact historical hash; unrelated keys remain protected."""
    return _expected_hash(receipt(root) if approved is None else approved, kind, identity, previous)


def _expected_hash(approved, kind, identity, previous):
    row = approved["hashes"].get(kind, {}).get(identity)
    if row is None:
        return previous
    if previous != row["before"]:
        raise OCFError("editorial successor previous hash differs: " + kind + "/" + identity)
    return row["after"]


def expected_entries(previous, *, resolved=False, root=REPO_ROOT):
    kind = "resolved_entries" if resolved else "raw_entries"
    approved = receipt(root)
    return {key: _expected_hash(approved, kind, key, value) for key, value in previous.items()}


def expected_entry_pairs(previous, root=REPO_ROOT):
    """Advance a full raw/resolved map with one fresh receipt read."""
    approved = receipt(root)
    return {
        key: {
            "raw_sha256": _expected_hash(approved, "raw_entries", key, value["raw_sha256"]),
            "resolved_sha256": _expected_hash(
                approved, "resolved_entries", key, value["resolved_sha256"]
            ),
        }
        for key, value in previous.items()
    }
