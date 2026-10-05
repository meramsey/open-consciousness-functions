"""Local exact-text authoring; research wording never enters runtime discovery.

Analytical locators seed candidate boundaries, not automatic editorial decisions.
No normalizing, paraphrasing, safety rewriting, or originality scoring occurs here.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .indexes import load_yaml_file
from .paths import REPO_ROOT
from .utils import OCFError, current_date, write_text_atomic, yaml_safe_dump
from .validators import _load_schema, validate_against_schema

REVIEWED = {"reviewed_unchanged", "reviewed_modified"}
RIGHTS = {"verified_redistributable", "user_cleared"}
RUNTIME_ROOTS = (
    "schemas",
    "functions",
    "function-content",
    "locales",
    "templates",
    "audio/templates",
    "audio/cues",
    "audio/voices",
    "audio/background",
)
# Existing semantic families, independent of source/English terms. These are
# candidate section associations, never injected DSP/state directives.
ROLES = {
    "preparation": ("preparation.orientation.begin", True),
    "opener": ("function.learning.attend", True),
    "purpose": ("function.purpose", False),
    "main": ("function.instruction", False),
    "association": ("function.command.association", False),
    "rehearsal": ("function.command.rehearsal", False),
    "future_use": ("function.future-use", False),
    "suspend_cancel_reset": ("function.release", False),
    "closer": ("focus.eleven.close", True),
    "consolidation": ("function.consolidation", True),
    "handoff": ("session.return.begin", True),
    "unassigned": ("authoring.unassigned", False),
}


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def checked_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or Path(relative).is_absolute():
        raise OCFError("editorial path escapes its root")
    return path


def require_local_output(path: Path) -> None:
    """Local working expression must not be accidentally staged as runtime data."""
    if any(path.resolve().is_relative_to((REPO_ROOT / name).resolve()) for name in RUNTIME_ROOTS):
        raise OCFError(
            "editorial workspace/output cannot be inside packaged runtime resource roots"
        )


def validate(data: dict, kind: str) -> None:
    errors = validate_against_schema(data, _load_schema(f"editorial-{kind}.schema.json"))
    if errors:
        raise OCFError("editorial schema: " + " | ".join(errors))


def save(path: Path, data: dict, *, overwrite: bool = True) -> None:
    write_text_atomic(path, yaml_safe_dump(data), overwrite=overwrite)


def build_skeleton(
    function_id: str,
    availability: str,
    review: dict,
    evidence: dict,
    raw: bytes | None,
    candidates: list[str] | None = None,
) -> tuple[dict, dict]:
    """Pure construction. Every byte of available UTF-8 text survives partitioning."""
    sections = review.get("sections", {})
    skeleton = {
        "schema_version": "1.0",
        "function_id": function_id,
        "source_availability": availability,
        "source_status": "unavailable",
        "skeletonization_status": "source_unavailable",
        "extraction_method": "exact-text-locator-guided-candidate-partition",
        "source": None,
        "blocks": [],
        "previous_candidates": candidates or [],
        "sections": {
            role: {
                "supported": "present",
                "not-present": "absent",
                "not-applicable": "not_applicable",
            }.get(sections.get(role, {}).get("status"), "unknown")
            for role in ROLES
            if role != "unassigned"
        },
    }
    if availability == "unavailable":
        if raw is not None:
            raise OCFError("source-unavailable function cannot inherit historical wording")
        validate(skeleton, "function")
        return skeleton, {}
    extent = review.get("source_extent", {})
    if raw is None or hashlib.sha256(raw).hexdigest() != extent.get("source_sha256"):
        raise OCFError(f"source checksum mismatch for {function_id}")
    source = next(
        (
            s
            for s in evidence.get("sources", [])
            if s["sha256"] == extent["source_sha256"] and s["path"] == extent["file"]
        ),
        None,
    )
    if not source or source["evidence_class"] not in (
        "source_transcript",
        "partial_source_transcript",
    ):
        raise OCFError("exact historical wording requires a transcript, not a mockup")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OCFError("source must be UTF-8; conversion must be explicitly recorded") from exc
    lines = text.splitlines(keepends=True)
    if extent.get("start_line") != 1 or extent.get("end_line") != len(lines) or not lines:
        raise OCFError("source extent does not cover the complete available transcript")
    partial = source["evidence_class"] == "partial_source_transcript"
    skeleton.update(
        source_status="partial_transcript" if partial else "transcript_unverified",
        skeletonization_status="candidate",
        source={
            "file": extent["file"],
            "sha256": extent["source_sha256"],
            "evidence_class": source["evidence_class"],
            "line_count": len(lines),
        },
    )
    ranges = []
    boundaries = {1, len(lines) + 1}
    for role in ROLES:
        answer = sections.get(role, {})
        if answer.get("status") not in ("supported", "inferred"):
            continue
        for locator in answer.get("locators", []):
            if locator.get("file") != extent["file"] or "start_line" not in locator:
                continue
            start, end = locator["start_line"], locator["end_line"]
            if not 1 <= start <= end <= len(lines):
                raise OCFError("candidate locator outside source extent")
            # Full-source investigative ranges do not establish a section boundary.
            if start == 1 and end == len(lines) and role != "main":
                continue
            ranges.append((start, end, role))
            boundaries.update((start, end + 1))
    chunks = {}
    points = sorted(boundaries)
    for index, (start, stop) in enumerate(zip(points, points[1:]), 1):
        matches = sorted(
            (end - begin, list(ROLES).index(role), role)
            for begin, end, role in ranges
            if begin <= start and stop - 1 <= end
        )
        role = matches[0][2] if matches else "unassigned"
        semantic, reusable = ROLES[role]
        exact = "".join(lines[start - 1 : stop - 1])
        # Deduplicate only exact words within the same reusable semantic family.
        key = fingerprint((semantic if reusable else function_id + ":" + semantic) + "\0" + exact)
        skeleton["blocks"].append(
            {
                "id": f"b{index:03}",
                "ref": key,
                "role": role,
                "semantic": semantic,
                "reusable": reusable,
                "start_line": start,
                "end_line": stop - 1,
            }
        )
        chunks[key] = {
            "schema_version": "1.0",
            "id": key,
            "semantic": semantic,
            "source": {"text": exact, "text_sha256": fingerprint(exact)},
            "working": {
                "text": exact,
                "review_status": "transcript_uncertain" if partial else "inherited",
                "reviewer": None,
                "review_sha256": None,
                "flags": [
                    "source-authentication-unverified",
                    "candidate-section-boundary",
                    "accessibility-review-required",
                ]
                + review.get("claim_categories", []),
                "corrections": [],
                "history": [],
            },
            "release": {
                "status": "pending",
                "rights": "unknown",
                "rights_evidence": None,
                "reviewer": None,
                "text_sha256": None,
            },
        }
        validate(chunks[key], "block")
    validate(skeleton, "function")
    return skeleton, chunks


def skeletonize(source_root: Path, workspace: Path, records: list, content_root: Path) -> list[str]:
    """Preflight the entire batch; refuse overwrites of customized working data."""
    require_local_output(workspace)
    if workspace.resolve().is_relative_to(
        source_root.resolve()
    ) or source_root.resolve().is_relative_to(workspace.resolve()):
        raise OCFError("workspace must be outside immutable source root")
    pending = []
    for record in records:
        spec = load_yaml_file(content_root / "specifications" / f"{record.id}.yaml")
        evidence = load_yaml_file(content_root / "evidence" / f"{record.id}.yaml")
        review = spec.get("analysis_review", {})
        raw = None
        if record.source_availability == "available":
            try:
                raw = checked_path(source_root, review["source_extent"]["file"]).read_bytes()
            except OSError as exc:
                raise OCFError(f"cannot read selected source for {record.id}: {exc}") from exc
        candidates = (
            ["audio/scripts/attention-ocf.yaml", "docs/drafts/attention-wording-review.md"]
            if record.id == "OCF-FND-002"
            else []
        )
        pilot = {"OCF-FND-004": "RELAX", "OCF-SEN-001": "HEARING", "OCF-SLP-005": "SLEEP-EASY"}.get(
            record.id
        )
        if pilot:
            candidates += [
                f"audio/templates/sessions/OCF-TPL-SESSION-PILOT-{pilot}-001.yaml",
                "locales/en-US/functions.yaml",
            ]
        doc, chunks = build_skeleton(
            record.id, record.source_availability, review, evidence, raw, candidates
        )
        pending.append((workspace / "functions" / f"{record.id}.yaml", doc))
        if raw is not None:
            pending.append(
                (
                    workspace / "sources" / f"{doc['source']['sha256']}.yaml",
                    {"text": raw.decode("utf-8"), "sha256": doc["source"]["sha256"]},
                )
            )
        pending.extend(
            (workspace / "blocks" / f"{key}.yaml", chunk) for key, chunk in chunks.items()
        )
    # Equal reusable words may carry different function-level claim flags.
    # Combine flags before writing; no function's review warnings are discarded.
    combined = {}
    for path, doc in pending:
        if path in combined and "working" in doc:
            if "transcript_uncertain" in (
                combined[path]["working"]["review_status"],
                doc["working"]["review_status"],
            ):
                doc["working"]["review_status"] = "transcript_uncertain"
            doc["working"]["flags"] = list(
                dict.fromkeys(combined[path]["working"]["flags"] + doc["working"]["flags"])
            )
        combined[path] = doc
    pending = list(combined.items())
    # An existing reviewed or edited chunk is never regenerated. Idempotence is
    # permitted only when the initial data is identical, including review state.
    for path, doc in pending:
        if path.exists():
            existing = load_yaml_file(path)
            if "working" in doc and "working" in existing:
                if (
                    existing["working"]["reviewer"] is None
                    and "transcript_uncertain"
                    in (existing["working"]["review_status"], doc["working"]["review_status"])
                    and existing["working"]["review_status"]
                    in ("inherited", "transcript_uncertain")
                ):
                    existing["working"]["review_status"] = "transcript_uncertain"
                    doc["working"]["review_status"] = "transcript_uncertain"
                flags = list(dict.fromkeys(existing["working"]["flags"] + doc["working"]["flags"]))
                doc["working"]["flags"] = flags
                existing["working"]["flags"] = flags
            if existing != doc:
                raise OCFError(f"refusing to overwrite customized editorial data: {path}")
    for path, doc in pending:
        if not path.exists():
            save(path, doc, overwrite=False)
        elif load_yaml_file(path) != doc:
            save(path, doc)
    return [record.id for record in records]


def load_function(workspace: Path, function_id: str) -> dict:
    if not re.fullmatch(r"OCF-[A-Z]{3}-[0-9]{3}", function_id):
        raise OCFError("invalid function ID")
    doc = load_yaml_file(checked_path(workspace, f"functions/{function_id}.yaml"))
    validate(doc, "function")
    if doc["function_id"] != function_id:
        raise OCFError("editorial function identity mismatch")
    if doc["source"]:
        snapshot = load_yaml_file(
            checked_path(workspace, f"sources/{doc['source']['sha256']}.yaml")
        )
        if fingerprint(snapshot["text"]) != doc["source"]["sha256"]:
            raise OCFError("immutable source snapshot changed")
        lines = snapshot["text"].splitlines(keepends=True)
        cursor = 1
        seen_ids = set()
        for occurrence in doc["blocks"]:
            if occurrence["id"] in seen_ids:
                raise OCFError("duplicate editorial block occurrence")
            seen_ids.add(occurrence["id"])
            if occurrence.get("inserted"):
                chunk = load_block(workspace, occurrence["ref"])
                if (
                    occurrence["start_line"] != 0
                    or occurrence["end_line"] != 0
                    or chunk["source"]["text"] != ""
                    or chunk["semantic"] != occurrence["semantic"]
                    or occurrence["reusable"]
                ):
                    raise OCFError("inserted OCF-only block cannot claim source wording")
                expected = fingerprint(
                    function_id + ":" + occurrence["id"] + "\0" + occurrence["semantic"]
                )
                if occurrence["ref"] != expected:
                    raise OCFError("inserted semantic identity changed")
            else:
                if occurrence["start_line"] != cursor or occurrence["end_line"] < cursor:
                    raise OCFError("source ranges must be contiguous and exhaustive")
                chunk = load_block(workspace, occurrence["ref"])
                exact = "".join(lines[cursor - 1 : occurrence["end_line"]])
                if chunk["source"]["text"] != exact or chunk["semantic"] != occurrence["semantic"]:
                    raise OCFError("source wording or semantic identity changed")
                semantic_key = (
                    occurrence["semantic"]
                    if occurrence["reusable"]
                    else function_id + ":" + occurrence["semantic"]
                )
                if fingerprint(semantic_key + "\0" + exact) != occurrence["ref"]:
                    raise OCFError("immutable source/semantic block identity changed")
                cursor = occurrence["end_line"] + 1
        if cursor != len(lines) + 1 or len(lines) != doc["source"]["line_count"]:
            raise OCFError("source ranges must cover the entire available transcript")
    return doc


def load_block(workspace: Path, key: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{64}", key):
        raise OCFError("invalid block reference")
    block = load_yaml_file(checked_path(workspace, f"blocks/{key}.yaml"))
    validate(block, "block")
    if block["id"] != key or fingerprint(block["source"]["text"]) != block["source"]["text_sha256"]:
        raise OCFError("immutable source block changed")
    return block


def working_text(workspace: Path, block: dict, *, release: bool = False, seen: tuple = ()) -> str:
    if block["id"] in seen:
        raise OCFError("circular reusable-template substitution")
    text = block["working"]["text"]
    ref = block["working"].get("template_ref")
    if ref:
        template = load_block(workspace, ref)
        if template["semantic"] != block["semantic"]:
            raise OCFError("template substitution cannot redefine semantics")
        block_origins(workspace, ref)
        text = working_text(workspace, template, release=release, seen=seen + (block["id"],))
    if release:
        approval, edit = block["release"], block["working"]
        unchanged = text == block["source"]["text"]
        if (edit["review_status"] == "reviewed_unchanged" and not unchanged) or (
            edit["review_status"] == "reviewed_modified" and unchanged
        ):
            raise OCFError(
                "release blocked: review missing/stale; status contradicts current wording"
            )
        if (
            edit["review_status"] not in REVIEWED
            or edit["review_sha256"] != fingerprint(text)
            or not edit["reviewer"]
            or approval["status"] != "approved"
            or approval["text_sha256"] != fingerprint(text)
            or approval["rights"] not in RIGHTS
            or not approval["rights_evidence"]
            or not approval["reviewer"]
        ):
            raise OCFError(
                "release blocked: review, approval, rights or text hash is missing/stale"
            )
        if any(c["status"] == "pending" for c in edit["corrections"]):
            raise OCFError("release blocked: pending transcript correction")
    return text


def block_origins(workspace: Path, key: str) -> list[dict]:
    """Validate substitution origins against snapshots, not editable checksums alone."""
    result = []
    for path in sorted((workspace / "functions").glob("*.yaml")):
        raw = load_yaml_file(path)
        if any(b["ref"] == key for b in raw.get("blocks", [])):
            doc = load_function(workspace, path.stem)
            for occurrence in doc["blocks"]:
                if occurrence["ref"] == key:
                    result.append(
                        {
                            "function_id": doc["function_id"],
                            "source": doc["source"],
                            "start_line": occurrence["start_line"],
                            "end_line": occurrence["end_line"],
                            "inserted": occurrence.get("inserted", False),
                        }
                    )
    if not result:
        raise OCFError("template substitution has no validated source/working origin")
    return result


def substitution_origins(workspace: Path, block: dict, seen: tuple = ()) -> list[dict]:
    if block["id"] in seen:
        raise OCFError("circular reusable-template substitution")
    ref = block["working"].get("template_ref")
    if not ref:
        return []
    return [{"ref": ref, "origins": block_origins(workspace, ref)}] + substitution_origins(
        workspace, load_block(workspace, ref), seen + (block["id"],)
    )


def diff(workspace: Path, function_id: str, filter_name: str | None = None) -> dict:
    doc = load_function(workspace, function_id)
    rows = []
    for occurrence in doc["blocks"]:
        block = load_block(workspace, occurrence["ref"])
        text = working_text(workspace, block)
        source = block["source"]["text"]
        category = "unchanged"
        if occurrence.get("inserted"):
            category = "inserted-ocf-only"
        elif block["working"].get("template_ref"):
            category = "reusable-template-substitution"
        elif text != source:
            category = "removed" if not text else "modified"
            if any(c["status"] == "applied" for c in block["working"]["corrections"]):
                category = "transcript-correction-and-edits"
        rows.append(
            {
                **occurrence,
                "category": category,
                "source": doc["source"],
                "source_text": source,
                "working_text": text,
                "review_status": block["working"]["review_status"],
                "review_current": block["working"]["review_status"] in REVIEWED
                and block["working"]["review_sha256"] == fingerprint(text),
                "substitution_origins": substitution_origins(workspace, block),
                "corrections": block["working"]["corrections"],
                "flags": block["working"]["flags"],
                "working_file": f"blocks/{block['id']}.yaml",
                "unified_diff": "".join(
                    difflib.unified_diff(
                        source.splitlines(True),
                        text.splitlines(True),
                        fromfile="SOURCE",
                        tofile="WORKING",
                    )
                ),
            }
        )
    return {
        "function_id": function_id,
        "source_status": doc["source_status"],
        "previous_candidates": doc["previous_candidates"],
        "blocks": [row for row in rows if matches_filter(row, filter_name)],
    }


def matches_filter(row: dict, name: str | None) -> bool:
    if name == "changed":
        return row["category"] != "unchanged"
    if name == "unreviewed":
        return not row["review_current"]
    if name == "uncertain":
        return row["review_status"] == "transcript_uncertain"
    if name == "function-specific":
        return not row["reusable"]
    if name == "reusable":
        return row["reusable"]
    return True


def mark_review(
    workspace: Path,
    function_id: str,
    block_id: str,
    status: str,
    reviewer: str,
    *,
    rights: str | None = None,
    rights_evidence: str | None = None,
) -> None:
    doc = load_function(workspace, function_id)
    occurrence = next((b for b in doc["blocks"] if b["id"] == block_id), None)
    if not occurrence or not reviewer.strip():
        raise OCFError("a known block and named human reviewer are required")
    block = load_block(workspace, occurrence["ref"])
    text = working_text(workspace, block)
    unchanged = text == block["source"]["text"]
    if rights is None:
        if (
            status == "reviewed_unchanged"
            and not unchanged
            or status == "reviewed_modified"
            and unchanged
        ):
            raise OCFError("review status contradicts source/working comparison")
        block["working"].update(
            review_status=status, reviewer=reviewer, review_sha256=fingerprint(text)
        )
        block["release"]["status"] = "pending"
    else:
        if (
            rights not in RIGHTS
            or not rights_evidence
            or not rights_evidence.strip()
            or block["working"]["review_status"] not in REVIEWED
            or block["working"]["review_sha256"] != fingerprint(text)
        ):
            raise OCFError(
                "release requires current human text review and explicit rights evidence"
            )
        block["release"].update(
            status="approved",
            rights=rights,
            rights_evidence=rights_evidence,
            reviewer=reviewer,
            text_sha256=fingerprint(text),
        )
        working_text(workspace, block, release=True)
    block["working"]["history"].append(
        {
            "action": "approval" if rights else "review",
            "status": status,
            "reviewer": reviewer,
            "date": current_date(),
            "text_sha256": fingerprint(text),
        }
    )
    validate(block, "block")
    save(workspace / "blocks" / f"{block['id']}.yaml", block)


def preview(workspace: Path, function_id: str, *, release: bool = False) -> dict:
    doc = load_function(workspace, function_id)
    if not doc["blocks"]:
        raise OCFError("source unavailable: no exact historical wording to preview")
    chunks = [(b, load_block(workspace, b["ref"])) for b in doc["blocks"]]
    # No timing in editorial files. This export view can be handed to the existing
    # composer/rendering engine after approval; speech-end anchors measure anew.
    timeline = []
    for occurrence, block in chunks:
        text = working_text(workspace, block, release=release)
        if not text:
            continue
        event = {
            "id": occurrence["id"],
            "semantic": occurrence["semantic"],
            "text": text,
            "timing": {"anchor": "speech-end"},
        }
        if timeline:
            event.update(after=timeline[-1]["id"], offset=0)
        else:
            event["at"] = 0
            event["timing"]["anchor"] = "start"
        timeline.append(event)
    return {
        "schema_version": "1.0",
        "title": f"{function_id} {'RELEASE' if release else 'WORKING REVIEW'}",
        "function_id": function_id,
        "timeline": timeline,
        "source": {
            "format": "ocf-timed-yaml",
            "filename": doc["source"]["file"],
            "sha256": doc["source"]["sha256"],
            "notes": [
                "Source-derived expression; not OCF-original.",
                "Explicitly approved release"
                if release
                else "Local unreviewed WORKING preview; not release",
            ],
            "metadata": {
                "editorial_blocks": [
                    {
                        "id": occurrence["id"],
                        "source_ref": occurrence["ref"],
                        "start_line": occurrence["start_line"],
                        "end_line": occurrence["end_line"],
                        "substitution_origins": substitution_origins(workspace, block),
                    }
                    for occurrence, block in chunks
                ]
            },
        },
    }


def insert(
    workspace: Path,
    function_id: str,
    block_id: str,
    before: str,
    semantic: str,
    text: str,
    reviewer: str,
) -> None:
    """Explicit human insertion; no historical source range is invented."""
    doc = load_function(workspace, function_id)
    if (
        not re.fullmatch(r"b[0-9]{3}", block_id)
        or not reviewer.strip()
        or not text
        or semantic not in {value[0] for value in ROLES.values()}
        or any(b["id"] == block_id for b in doc["blocks"])
    ):
        raise OCFError(
            "insertion requires unique block ID, known semantic family, text and reviewer"
        )
    position = next((i for i, b in enumerate(doc["blocks"]) if b["id"] == before), None)
    if position is None:
        raise OCFError("unknown insertion anchor")
    key = fingerprint(function_id + ":" + block_id + "\0" + semantic)
    block = {
        "schema_version": "1.0",
        "id": key,
        "semantic": semantic,
        "source": {"text": "", "text_sha256": fingerprint("")},
        "working": {
            "text": text,
            "review_status": "needs_review",
            "reviewer": None,
            "review_sha256": None,
            "flags": ["ocf-only-insertion"],
            "corrections": [],
            "history": [
                {
                    "action": "insert",
                    "reviewer": reviewer,
                    "date": current_date(),
                    "text_sha256": fingerprint(text),
                }
            ],
        },
        "release": {
            "status": "pending",
            "rights": "unknown",
            "rights_evidence": None,
            "reviewer": None,
            "text_sha256": None,
        },
    }
    doc["blocks"].insert(
        position,
        {
            "id": block_id,
            "ref": key,
            "role": "ocf-only",
            "semantic": semantic,
            "reusable": False,
            "inserted": True,
            "start_line": 0,
            "end_line": 0,
        },
    )
    validate(block, "block")
    validate(doc, "function")
    save(workspace / "blocks" / f"{key}.yaml", block, overwrite=False)
    save(workspace / "functions" / f"{function_id}.yaml", doc)


def dashboard(workspace: Path, filter_name: str | None = None) -> dict:
    rows = []
    for path in sorted((workspace / "functions").glob("*.yaml")):
        doc = load_function(workspace, path.stem)
        counts = Counter(
            {
                name: 0
                for name in (
                    "blocks",
                    "changed",
                    "unchanged",
                    "uncertain",
                    "reusable",
                    "function-specific",
                    "reviewed",
                    "unreviewed",
                    "template_substitutions",
                    "flagged",
                    "release_approved",
                    "release_pending",
                    "rights_unknown",
                    "rights_review_required",
                    "rights_restricted",
                    "rights_verified_redistributable",
                    "rights_user_cleared",
                )
            }
        )
        for occurrence in doc["blocks"]:
            block = load_block(workspace, occurrence["ref"])
            text = working_text(workspace, block)
            changed = text != block["source"]["text"]
            reviewed = block["working"]["review_status"] in REVIEWED and block["working"][
                "review_sha256"
            ] == fingerprint(text)
            counts.update(
                {
                    "blocks": 1,
                    "changed": int(changed),
                    "unchanged": int(not changed),
                    "uncertain": int(block["working"]["review_status"] == "transcript_uncertain"),
                    "reusable": int(occurrence["reusable"]),
                    "function-specific": int(not occurrence["reusable"]),
                    "reviewed": int(reviewed),
                    "unreviewed": int(not reviewed),
                    "template_substitutions": int(bool(block["working"].get("template_ref"))),
                    "flagged": int(bool(block["working"]["flags"])),
                }
            )
            try:
                working_text(workspace, block, release=True)
                counts["release_approved"] += 1
            except OCFError:
                counts["release_pending"] += 1
            counts["rights_" + block["release"]["rights"]] += 1
        if filter_name is None or counts[filter_name]:
            rows.append(
                {
                    "function_id": doc["function_id"],
                    "source_availability": doc["source_availability"],
                    "source_status": doc["source_status"],
                    "skeletonization_status": doc["skeletonization_status"],
                    "counts": dict(counts),
                }
            )
    totals = Counter()
    for row in rows:
        totals.update(row["counts"])
    return {"schema_version": "1.0", "functions": rows, "totals": dict(totals)}


def variants(workspace: Path) -> dict:
    families = defaultdict(dict)
    for path in sorted((workspace / "functions").glob("*.yaml")):
        doc = load_function(workspace, path.stem)
        for occurrence in doc["blocks"]:
            if not occurrence["reusable"]:
                continue
            block = load_block(workspace, occurrence["ref"])
            group = families[occurrence["semantic"]].setdefault(
                block["source"]["text_sha256"], {"text": block["source"]["text"], "occurrences": []}
            )
            group["occurrences"].append(
                {
                    "function_id": doc["function_id"],
                    "block_id": occurrence["id"],
                    "source": doc["source"],
                    "start_line": occurrence["start_line"],
                    "end_line": occurrence["end_line"],
                }
            )
    result = []
    for semantic, groups in sorted(families.items()):
        baseline = next(iter(groups.values()))["text"]
        entries = []
        for key, group in groups.items():
            score = difflib.SequenceMatcher(None, baseline, group["text"], autojunk=False).ratio()
            entries.append(
                {
                    "text_sha256": key,
                    "occurrences": group["occurrences"],
                    "comparison": "exact"
                    if group["text"] == baseline
                    else "minor-candidate"
                    if score >= 0.9
                    else "material-candidate",
                    "similarity_informational_only": score,
                    "diff": "".join(
                        difflib.unified_diff(
                            baseline.splitlines(True), group["text"].splitlines(True)
                        )
                    ),
                }
            )
        result.append(
            {
                "semantic": semantic,
                "exact_text_groups": entries,
                "review": "Candidate segmentation and difference significance require human review; no preferred variant selected.",
            }
        )
    return {"families": result}


def add_parser(sub) -> None:
    group = sub.add_parser("content", help="local source-first editorial workflow")
    leaves = group.add_subparsers(dest="content_kind", required=True)
    for name in (
        "skeletonize",
        "diff",
        "dashboard",
        "variants",
        "review",
        "approve",
        "preview",
        "insert",
    ):
        leaf = leaves.add_parser(name)
        leaf.add_argument("--workspace", type=Path, default=Path(".ocf-authoring"))
        if name == "skeletonize":
            leaf.add_argument("--source-root", type=Path, required=True)
            leaf.add_argument("--function")
        elif name not in ("dashboard", "variants"):
            leaf.add_argument("id")
        if name in ("review", "approve"):
            leaf.add_argument("--block", required=True)
            leaf.add_argument("--reviewer", required=True)
            if name == "review":
                leaf.add_argument(
                    "--status",
                    required=True,
                    choices=[
                        "inherited",
                        "needs_review",
                        "reviewed_unchanged",
                        "reviewed_modified",
                        "transcript_uncertain",
                        "blocked",
                    ],
                )
            else:
                leaf.add_argument("--rights", choices=sorted(RIGHTS), required=True)
                leaf.add_argument("--rights-evidence", required=True)
        if name in ("preview", "dashboard", "variants"):
            leaf.add_argument("--output", type=Path)
        if name == "preview":
            leaf.add_argument("--release", action="store_true")
        if name == "insert":
            leaf.add_argument("--block", required=True)
            leaf.add_argument("--before", required=True)
            leaf.add_argument(
                "--semantic", choices=sorted({v[0] for v in ROLES.values()}), required=True
            )
            leaf.add_argument("--text-file", type=Path, required=True)
            leaf.add_argument("--reviewer", required=True)
        if name in ("dashboard", "diff"):
            leaf.add_argument(
                "--filter",
                choices=["changed", "unreviewed", "uncertain", "function-specific", "reusable"],
            )
        leaf.add_argument("--json", action="store_true")


def run(args) -> int:
    require_local_output(args.workspace)
    if args.content_kind == "skeletonize":
        from .content import CONTENT_DIR
        from .indexes import load_all_functions

        records = [r for r in load_all_functions() if not args.function or r.id == args.function]
        if not records:
            raise OCFError("unknown function")
        result = {
            "skeletonized": skeletonize(args.source_root, args.workspace, records, CONTENT_DIR)
        }
    elif args.content_kind == "diff":
        result = diff(args.workspace, args.id, args.filter)
    elif args.content_kind == "dashboard":
        result = dashboard(args.workspace, args.filter)
    elif args.content_kind == "variants":
        result = variants(args.workspace)
    elif args.content_kind == "insert":
        with args.text_file.open(encoding="utf-8", newline="") as handle:
            text = handle.read()
        insert(args.workspace, args.id, args.block, args.before, args.semantic, text, args.reviewer)
        result = {"function_id": args.id, "block": args.block, "action": "insert"}
    elif args.content_kind in ("review", "approve"):
        mark_review(
            args.workspace,
            args.id,
            args.block,
            getattr(args, "status", "approved"),
            args.reviewer,
            rights=getattr(args, "rights", None),
            rights_evidence=getattr(args, "rights_evidence", None),
        )
        result = {"function_id": args.id, "block": args.block, "action": args.content_kind}
    else:
        result = preview(args.workspace, args.id, release=args.release)
        if args.output:
            require_local_output(args.output)
            write_text_atomic(args.output, yaml_safe_dump(result), overwrite=False)
    if args.content_kind in ("dashboard", "variants") and args.output:
        # Variant diffs contain reference expression; keep them in the local
        # editorial workspace, not runtime/locales or public generated indexes.
        if args.content_kind == "variants" and not args.output.resolve().is_relative_to(
            args.workspace.resolve()
        ):
            raise OCFError("source variant output must stay inside the local workspace")
        write_text_atomic(
            args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n", overwrite=False
        )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.content_kind == "diff":
        for row in result["blocks"]:
            print(
                f"{row['id']} {row['role']} [{row['category']}; {row['review_status']}]\n{row['unified_diff'] or row['source_text']}"
            )
    elif args.content_kind == "preview":
        print("\n".join(event["text"] for event in result["timeline"]))
    elif args.content_kind == "dashboard":
        for row in result["functions"]:
            print(f"{row['function_id']} {row['source_status']} {row['counts']}")
        print("Totals:", result["totals"])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
