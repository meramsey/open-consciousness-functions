"""Resumable, one-function-at-a-time editorial decisions; no automatic renames."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .paths import REPO_ROOT, work_path
from .utils import OCFError, write_text_atomic

CHOICES = {"approve", "keep", "custom", "skip", "context"}


def fingerprint(function_id):
    from .indexes import load_function_by_id
    from .locale import LocaleCatalog

    owner = load_function_by_id(function_id)
    if owner is None:
        raise OCFError("review function no longer exists: " + function_id)
    catalog = LocaleCatalog()
    evidence = []
    for row in (owner.data.get("narration") or {}).get("sequence", []):
        entry, resolution = catalog.raw_resource(
            row["key"], "en-US", domain="narration", fallback=False
        )
        evidence.append(
            {
                "key": row["key"],
                "text": entry.text,
                "version": entry.version,
                "status": entry.status,
                "cue_template": entry.cue_template,
                "locale": resolution.origin_locale,
            }
        )
    return hashlib.sha256(
        owner.path.read_bytes()
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def check_current(row, source_fingerprint=None):
    source_fingerprint = source_fingerprint or fingerprint
    if (
        not row.get("source_sha256")
        or source_fingerprint(row["function_id"]) != row["source_sha256"]
    ):
        raise OCFError(
            "review source changed; preserve prior decisions, refresh the single-function presentation and obtain explicit reconfirmation"
        )


def create():
    from .editorial_successors import current_decision_record
    from .indexes import load_all_functions

    current = json.loads(
        (REPO_ROOT / "docs/releases/OCF_TITLE_CUE_CURRENT.json").read_text(encoding="utf-8")
    )
    source = json.loads(
        (REPO_ROOT / "docs/releases/OCF_TITLE_CUE_REVIEW.json").read_text(encoding="utf-8")
    )
    recommendations = {row["function_id"]: row for row in source["functions"]}
    decisions = current_decision_record()
    approved = {
        row["function_id"] for row in decisions["decisions"] if not row.get("pending_title")
    }
    kept = {row["function_id"] for row in decisions["kept_decisions"]}
    records = {record.id: record for record in load_all_functions()}
    rows = []
    for row in current["functions"]:
        owner = row["function_id"]
        if owner in approved or owner in kept:
            continue
        prior = recommendations[owner]
        if row["decision_status"] == "EXISTING PAIR RETAINED" and owner != "OCF-BOD-006":
            continue
        record = records[owner]
        mismatch = not row["metadata_teaching_consistent"]
        rank = (
            0
            if mismatch
            else 1
            if owner in {"OCF-BOD-010", "OCF-BOD-005", "OCF-EMG-001", "OCF-EMG-002"}
            else 2
            if owner == "OCF-BOD-006"
            else 3
        )
        rows.append(
            {
                "function_id": owner,
                "priority": rank,
                "current_title": record.canonical_name,
                "display_cue": record.canonical_command,
                "spoken": next(
                    (
                        command.data.get("spoken")
                        for command in record.command_records
                        if command.designation == "primary"
                    ),
                    None,
                ),
                "taught": row["spoken_teaching"],
                "purpose": record.purpose_summary,
                "lifecycle": record.data["lifecycle"],
                "controls": [
                    {"id": command.id, "role": command.role}
                    for command in record.command_records
                    if command.designation != "primary"
                ],
                "recommended_title": "Heart Flow"
                if owner == "OCF-BOD-006"
                else prior["recommended_title"],
                "recommended_cue": record.canonical_command
                if owner == "OCF-BOD-006"
                else prior["recommended_primary_cue"],
                "reason": prior["contextual_review"],
                "alternatives": prior["alternatives"][:2],
                "status": "pending",
                "source_sha256": fingerprint(record.id),
                "decisions": [],
            }
        )
    rows.sort(key=lambda row: (row["priority"], row["function_id"]))
    return {"schema_version": "1.0", "position": 0, "items": rows}


def next_item(queue):
    awaiting = next(
        (
            row
            for row in queue["items"]
            if row["status"] == "approved-awaiting-scoped-implementation"
        ),
        None,
    )
    if awaiting:
        return awaiting
    return next((row for row in queue["items"] if row["status"] == "pending"), None)


def decide(
    queue,
    function_id,
    choice,
    text,
    *,
    title=None,
    display_cue=None,
    spoken_cue=None,
    source_fingerprint=None,
):
    """Record explicit human text; approval is never implementation or release."""
    if choice not in CHOICES or not isinstance(text, str) or not text.strip():
        raise OCFError(
            "record one explicit approve/keep/custom/skip/context response with the user's exact words"
        )
    row = next_item(queue)
    if row is None or row["function_id"] != function_id or row["status"] != "pending":
        raise OCFError("decision must address the current single function")
    check_current(row, source_fingerprint)
    if choice in {"approve", "custom"} and not all(
        isinstance(value, str) and value.strip() for value in (title, display_cue, spoken_cue)
    ):
        raise OCFError(
            "approved decision requires the presented or custom title, display cue and spoken realization; do not infer punctuation"
        )
    record = {
        "choice": choice,
        "user_text": text,
        "title": title,
        "display_cue": display_cue,
        "spoken_cue": spoken_cue,
    }
    row["decisions"].append(record)
    if choice in {"approve", "custom"}:
        row["status"] = "approved-awaiting-scoped-implementation"
    elif choice == "keep":
        row["status"] = "keep-current-pair-recorded"
    elif choice == "skip":
        row["status"] = "deferred"
    queue["position"] = sum(item["status"] != "pending" for item in queue["items"])
    return row


def save(queue, path=None):
    target = Path(path) if path else work_path("logs", "editorial-review", "queue.json")
    from .paths import work_root

    if not target.resolve().is_relative_to(work_root()):
        raise OCFError("review queue must remain in the local workspace")
    write_text_atomic(target, json.dumps(queue, ensure_ascii=False, indent=2) + "\n")
    return target


def load_or_create(path=None, *, source_fingerprint=None):
    target = Path(path) if path else work_path("logs", "editorial-review", "queue.json")
    if target.exists():
        queue = json.loads(target.read_text(encoding="utf-8"))
        current = next_item(queue)
        if current is not None:
            check_current(current, source_fingerprint)
        return queue
    queue = create()
    save(queue, target)
    return queue
