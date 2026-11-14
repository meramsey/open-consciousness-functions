"""Read-only approved relationship projection from canonical locale resources."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy

from .function_catalog import resources
from .indexes import load_all_functions
from .paths import REPO_ROOT
from .utils import OCFError

ID = "OCF-GUIDE-REVIEW-001"


def resource_snapshot(root=REPO_ROOT):
    """One validated read for a single operation; never a cross-call cache."""
    return {data["function_id"]: data for _path, data in resources(root, "en-US")}


def _decisions(localized):
    identity = localized["function_id"]
    return [
        {
            "relationship_id": decision["relationship_id"],
            "source_id": identity,
            "related_id": decision["related_function_id"],
            "relationship_type": decision["relationship_type"],
            "dependency": decision["dependency"],
            "reciprocal_approved": decision["reciprocal_approved"],
            "decision_source": decision["decision_source"],
            "source_row_sha256": decision["source_row_sha256"],
        }
        for decision in localized.get("record_metadata", {}).get("editorial_decisions", [])
        if decision.get("kind") == "approved-relationship"
    ]


def record(root=REPO_ROOT):
    rows = []
    source_revision = None
    for _path, localized in resources(root, "en-US"):
        for decision in localized.get("record_metadata", {}).get("editorial_decisions", []):
            if decision.get("kind") != "approved-relationship":
                continue
            source_revision = source_revision or decision["source_commit"]
        rows.extend(_decisions(localized))
    return {
        "id": ID,
        "source_commit": source_revision,
        "decisions": sorted(rows, key=lambda x: x["relationship_id"]),
    }


def relationships(owner, *, root=REPO_ROOT, snapshot=None):
    """Expose only reviewed relationships whose explanation is in the owner resource."""
    snapshot = resource_snapshot(root) if snapshot is None else snapshot
    resource = snapshot.get(owner.id)
    if resource is None:
        raise OCFError("canonical relationship owner resource is missing: " + owner.id)
    decisions = sorted(_decisions(resource), key=lambda row: row["relationship_id"])
    values = {
        (row["function_id"], relation_type): row
        for relation_type in ("related_functions", "complementary_functions")
        for row in resource.get("relationships", {}).get(relation_type, [])
    }
    result = []
    for decision in decisions:
        candidates = [
            row for (function_id, _), row in values.items() if function_id == decision["related_id"]
        ]
        if not candidates:
            raise OCFError(
                "approved relationship is missing from canonical locale resource: "
                + decision["relationship_id"]
            )
        relation = candidates[0]
        result.append(
            {
                **decision,
                "description_key": relation["description_key"],
                "approved_explanation": relation["description"]["text"],
                "source_hash": decision["source_row_sha256"],
            }
        )
    return result


def verify(root=REPO_ROOT):
    records = {row.id: row for row in load_all_functions(root=root)}
    decision_data = record(root)
    snapshot = resource_snapshot(root)
    errors = []
    for identity in sorted({row["source_id"] for row in decision_data["decisions"]}):
        owner = records.get(identity)
        if owner is None:
            errors.append("approved relationship owner is missing: " + identity)
            continue
        projected = relationships(owner, root=root, snapshot=snapshot)
        approved_related = {
            row["related_id"] for row in projected if row["relationship_type"] == "related"
        }
        if approved_related != set(owner.data.get("companions", [])):
            errors.append("canonical companion list differs from embedded approval: " + identity)
    return errors


SUCCESSOR = REPO_ROOT / "function-content/editorial/guide-relationships-002.json"
PREDECESSORS = {
    "semantic": "tests/fixtures/function-semantic-contract-baseline.json",
    "catalog": "function-content/editorial/catalog-metadata-baseline-006.json",
    "shared": "function-content/editorial/shared-session-v3-001.json",
    "relaxation": "function-content/editorial/relaxation-long-002.json",
}


def _metadata_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def approved_successor(root=REPO_ROOT, *, snapshot=None, records=None):
    """Verify the fixed, hash-only approval; never refresh it from current data."""
    from .canonical_integrity import digest
    from .function_catalog import structural_contract

    receipt = json.loads(SUCCESSOR.read_text(encoding="utf-8"))
    snapshot = resource_snapshot(root) if snapshot is None else snapshot
    if receipt.get("schema_version") != "1.0" or receipt.get("id") != "OCF-GUIDE-RELATIONSHIPS-002":
        raise OCFError("unsupported guide relationship successor")
    predecessors = {}
    for name, relative in PREDECESSORS.items():
        path = REPO_ROOT / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != receipt["predecessor_sha256"].get(name):
            raise OCFError("guide successor predecessor binding differs: " + name)
        predecessors[name] = json.loads(path.read_text(encoding="utf-8"))
    decisions = {
        identity: [
            row
            for row in data.get("record_metadata", {}).get("editorial_decisions", [])
            if row.get("kind") == "approved-relationship"
            and row.get("source_commit") == receipt["source_revision"]
        ]
        for identity, data in snapshot.items()
    }
    decisions = {identity: rows for identity, rows in decisions.items() if rows}
    if set(decisions) != set(receipt["functions"]) or len(decisions) != 27:
        raise OCFError("guide successor approved identity set differs")
    records = {row.id: row for row in load_all_functions(root=root)} if records is None else records
    fields = {
        "previous_contract_sha256",
        "contract_sha256",
        "approved_decisions_sha256",
        "previous_reviewed_relationships_sha256",
        "reviewed_relationships_sha256",
        "previous_record_without_bindings_sha256",
        "record_without_bindings_sha256",
    }
    added = {}
    for identity, expected in receipt["functions"].items():
        if set(expected) != fields or not all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            for value in expected.values()
        ):
            raise OCFError("guide successor has unsupported hash fields: " + identity)
        old = {
            "previous_contract_sha256": predecessors["semantic"]["functions"][identity][
                "contract_sha256"
            ],
            "previous_reviewed_relationships_sha256": predecessors["catalog"]["functions"][
                identity
            ]["reviewed_relationships_sha256"],
            "previous_record_without_bindings_sha256": predecessors["shared"][
                "unchanged_function_records_without_bindings_sha256"
            ][identity],
        }
        if any(expected[key] != value for key, value in old.items()):
            raise OCFError("guide successor previous hashes differ: " + identity)
        data = snapshot[identity]
        if _metadata_hash(decisions[identity]) != expected["approved_decisions_sha256"]:
            raise OCFError("guide successor embedded approval differs: " + identity)
        if digest(structural_contract(data)) != expected["contract_sha256"]:
            raise OCFError("guide successor structural contract differs: " + identity)
        projected = deepcopy(records[identity].data)
        projected["content"].pop("bindings")
        if _metadata_hash(projected) != expected["record_without_bindings_sha256"]:
            raise OCFError("guide successor projected record differs: " + identity)
        reviewed = {
            key: value for key, value in data["relationships"].items() if key != "proposals"
        }
        if _metadata_hash(reviewed) != expected["reviewed_relationships_sha256"]:
            raise OCFError("guide successor relationship wording differs: " + identity)
        for decision in decisions[identity]:
            kind = (
                "related_functions"
                if decision["relationship_type"] == "related"
                else "complementary_functions"
            )
            relation = next(
                row
                for row in reviewed[kind]
                if row["function_id"] == decision["related_function_id"]
            )
            checksum = hashlib.sha256(relation["description"]["text"].encode()).hexdigest()
            added[relation["description_key"]] = {
                "raw_sha256": checksum,
                "resolved_sha256": checksum,
            }
    if len(added) != 27 or added != receipt["added_canonical_entries"]:
        raise OCFError("guide successor added locale entries differ")
    return receipt
