"""Read-only view of explicit functional metadata decisions embedded canonically."""

from __future__ import annotations

from .function_catalog import resources
from .paths import REPO_ROOT

ID = "OCF-FUNCTIONAL-METADATA-001"


def record(root=REPO_ROOT):
    decisions = []
    source_commit = None
    for _path, data in resources(root):
        for item in data.get("record_metadata", {}).get("editorial_decisions", []):
            if item.get("kind") != "approved-functional-metadata":
                continue
            source_commit = source_commit or item["source_commit"]
            issue = item["scope"]
            title, _, response = item["review_note"].partition(": ")
            decisions.append(
                {
                    "issue_id": issue,
                    "function_id": data["function_id"],
                    "title": title,
                    "decision": {
                        "choice": item["approval_response"],
                        "user_text": response,
                        "approved_values_sha256": item["current_values_sha256"],
                    },
                }
            )
    return {
        "id": ID,
        "source_commit": source_commit,
        "confirmation": "Canonical editorial decision metadata; no sidecar source is loaded.",
        "decisions": sorted(decisions, key=lambda row: row["issue_id"]),
        "runtime_policy": "editorial metadata does not alter function runtime semantics",
        "locales_requiring_review": ["es"],
    }


def verify(data=None, root=REPO_ROOT):
    data = data or record(root)
    expected = record(root)
    return [] if data == expected else ["canonical functional metadata decision view drift"]
