"""Read-only view and verifier for the canonical Options editorial decision."""

from __future__ import annotations

import hashlib

from .function_catalog import resources
from .paths import REPO_ROOT
from .utils import OCFError

OWNER = "OCF-COG-005"
OLD = "Plus Options Choices"
NEW = "Plus Options"
DECISION_ID = "OCF-OPTIONS-001"


def record(root=REPO_ROOT):
    row = next((data for _, data in resources(root) if data["function_id"] == OWNER), None)
    if row is None:
        return None
    decisions = row.get("record_metadata", {}).get("editorial_decisions", [])
    decision = next((item for item in decisions if item.get("id") == DECISION_ID), None)
    if decision is None:
        raise OCFError("canonical Options decision metadata is missing")
    expected_keys = {
        "hplus.function.ocf-cog-005.closer",
        "hplus.function.ocf-cog-005.function-body",
    }
    if (
        decision.get("kind") != "approved-command-presentation-change"
        or decision.get("command_id") != "OCF-CMD-COG-005-PRIMARY"
        or set(decision.get("previous_resolved_text_sha256", {})) != expected_keys
        or set(decision.get("current_resolved_text_sha256", {})) != expected_keys
    ):
        raise OCFError("canonical Options decision scope is invalid")
    for group in ("previous_resolved_text_sha256", "current_resolved_text_sha256"):
        if any(
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
            for value in decision[group].values()
        ):
            raise OCFError("canonical Options decision hash is invalid")
    return {
        "id": decision["id"],
        "function_id": OWNER,
        "decision_source": decision["decision_source"],
        "source_commit": decision["source_commit"],
        "command_id": decision["command_id"],
        "scope": decision["scope"],
        "speech": {
            key: {
                "before_sha256": digest,
                "after_sha256": decision["current_resolved_text_sha256"][key],
            }
            for key, digest in decision["previous_resolved_text_sha256"].items()
        },
        "unchanged_protected_count": decision["unchanged_protected_count"],
        "listening_approval": decision["listening_approval"],
        "release_ready": decision["release_ready"],
    }


def predecessor(root, name, text):
    """Predecessor words are never reconstructed into current resources."""
    return text


def before_texts(root, texts):
    """Return current resolved speech unchanged; historical words are not stored."""
    return dict(texts)


def verify(root=REPO_ROOT):
    from .indexes import load_function_by_id
    from .locale import LocaleCatalog

    data = record(root)
    if data is None:
        return ["canonical Options function is missing"]
    owner = load_function_by_id(OWNER, root=root)
    if owner is None or owner.canonical_command != "PLUS-OPTIONS":
        return ["canonical Options display command drift"]
    historical = owner.data.get("historical_lookup", [])
    if not any(
        item.get("text") == OLD and item.get("decision") == DECISION_ID for item in historical
    ):
        return ["canonical Options historical lookup decision drift"]
    catalog = LocaleCatalog(root / "locales", function_records=lambda: [owner])
    problems = []
    for key, hashes in data["speech"].items():
        try:
            entry, _resolution = catalog.resource(key, "en-US", domain="narration", fallback=False)
        except Exception:
            problems.append("canonical Options narration resource missing: " + key)
            continue
        actual = hashlib.sha256(entry.text.encode("utf-8")).hexdigest()
        if actual != hashes["after_sha256"]:
            problems.append("canonical Options narration hash drift: " + key)
    if data["listening_approval"] or data["release_ready"]:
        problems.append("Options editorial approval exceeds its approved scope")
    return problems
