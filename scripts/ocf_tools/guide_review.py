"""Read-only approved relationship projection from canonical locale resources."""

from __future__ import annotations

from .function_catalog import resources
from .indexes import load_all_functions
from .paths import REPO_ROOT
from .utils import OCFError

ID = "OCF-GUIDE-REVIEW-001"


def record(root=REPO_ROOT):
    rows = []
    source_revision = None
    for _path, localized in resources(root, "en-US"):
        identity = localized["function_id"]
        for decision in localized.get("record_metadata", {}).get("editorial_decisions", []):
            if decision.get("kind") != "approved-relationship":
                continue
            source_revision = source_revision or decision["source_commit"]
            rows.append(
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
            )
    return {
        "id": ID,
        "source_commit": source_revision,
        "decisions": sorted(rows, key=lambda x: x["relationship_id"]),
    }


def relationships(owner, *, root=REPO_ROOT):
    """Expose only reviewed relationships whose explanation is in the owner resource."""
    data = record(root)
    decisions = [row for row in data["decisions"] if row["source_id"] == owner.id]
    resource = next(
        (data for _path, data in resources(root, "en-US") if data["function_id"] == owner.id),
        None,
    )
    if resource is None:
        raise OCFError("canonical relationship owner resource is missing: " + owner.id)
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
    errors = []
    for identity in sorted({row["source_id"] for row in decision_data["decisions"]}):
        owner = records.get(identity)
        if owner is None:
            errors.append("approved relationship owner is missing: " + identity)
            continue
        projected = relationships(owner, root=root)
        approved_related = {
            row["related_id"] for row in projected if row["relationship_type"] == "related"
        }
        if approved_related != set(owner.data.get("companions", [])):
            errors.append("canonical companion list differs from embedded approval: " + identity)
    return errors
