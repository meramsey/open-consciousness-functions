"""Read-only compatibility view over approval metadata in canonical resources."""

from __future__ import annotations

from .editorial_candidates import CANDIDATES, verify_approvals
from .function_catalog import load_functions


def record(root=None):
    from .paths import REPO_ROOT

    root = root or REPO_ROOT
    records = {row.id: row for row in load_functions(root)}
    approvals = {}
    scope = confirmation = None
    source_commit = None
    for name, identity in CANDIDATES.items():
        owner = records.get(identity)
        if owner is None:
            return None
        metadata = owner.path.read_text(encoding="utf-8")
        import yaml

        localized = yaml.safe_load(metadata)
        approval = localized.get("record_metadata", {}).get("editorial_approval")
        if not approval:
            return None
        scope = approval["scope"]
        confirmation = approval["implementation_confirmation"]
        source_commit = approval.get("source_commit")
        approvals[name] = {
            "function_id": identity,
            "decision": approval["decision"],
            "user_response": approval["user_response"],
            "snapshot_sha256": approval["presented_snapshot_sha256"],
            "resolved_sha256": approval["resolved_text_sha256"],
            "source_commit": source_commit,
        }
    return {
        "id": "OCF-APPROVED-CANDIDATES-001",
        "source_commit": source_commit,
        "approval_scope": scope,
        "confirmation": confirmation,
        "approvals": approvals,
        "listening_approval": False,
        "release_ready": False,
    }


def verify(root=None):
    from .paths import REPO_ROOT

    root = root or REPO_ROOT
    if root.resolve() != REPO_ROOT.resolve():
        return ["approval verification requires the canonical repository locale catalog"]
    return verify_approvals(root)


def predecessor(root, name, text):
    """No predecessor projection remains; this adapter is identity-only."""
    return text


def before_texts(root, texts):
    """No predecessor wording is stored or supplied from a secondary source."""
    return dict(texts)
