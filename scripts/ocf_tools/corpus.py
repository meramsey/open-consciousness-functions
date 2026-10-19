"""Read-only research input inventory; never publish transcript wording."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from pathlib import Path

from .indexes import load_all_functions
from .utils import OCFError

SOURCE_FAMILY = "+Transcripts From available tapes"
CLASSES = (
    "source_transcript",
    "partial_source_transcript",
    "reconstructed_mockup",
    "inferred_missing_function",
    "secondary_description",
    "unknown",
)
TITLE_ALIASES = {
    "brainsupportandmaintenance": "OCF-BOD-001",
    "heartsupportandmaintenance": "OCF-BOD-006",
    "lungsupportandmaintenance": "OCF-BOD-009",
}


def normalized(title: str) -> str:
    return re.sub(
        r"[^a-z0-9]",
        "",
        unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower(),
    )


def classify(relative: Path, text: str | None) -> tuple[str, str, str]:
    """Explicit reconstruction evidence outranks the source-family attestation."""
    if text is None:
        return "unknown", "binary/reference object not content-reviewed", "pending-source-review"
    reconstruction = re.search(
        r"reconstructed.{0,40}(?:script|transcript)|not (?:a |the )?(?:recovered (?:original |archival )?|lost original |original )transcript|research reconstruction|annotated reconstruction",
        text[:12000],
        re.I | re.S,
    )
    if reconstruction and relative.suffix.lower() == ".txt":
        return (
            "reconstructed_mockup",
            "explicit reconstruction statement in file content",
            "reconstruction; historical completeness not applicable",
        )
    if SOURCE_FAMILY in relative.parts and relative.suffix.lower() in (
        ".txt",
        ".srt",
        ".lrc",
        ".vtt",
    ):
        partial = bool(
            re.search(r"^\s*\.{3}\s*$|\[missing\]|\[unintelligible\]", text, re.M | re.I)
        )
        return (
            "partial_source_transcript" if partial else "source_transcript",
            "operator-designated source-derivative corpus; not inferred from apparent fluency",
            "explicit gaps"
            if partial
            else "pending-source-review; apparent boundaries do not prove completeness",
        )
    if relative.suffix.lower() == ".md" or "notes" in relative.stem.lower():
        return (
            "secondary_description",
            "research/context document; not a historical transcript",
            "pending-source-review",
        )
    return "unknown", "no sufficient provenance statement", "pending-source-review"


def candidate_locators(text: str | None) -> dict:
    if text is None:
        return {}
    patterns = {
        "opener": r"function (?:learning )?exercise|to prepare for",
        "main": r"here is (?:your|the) (?:instruction|h.?plus function)|at any (?:time|point).*future|from this moment forward",
        "closer": r"close your .*access channel|end of .*function.*exercise",
        "preparation": r"comfortable|repository box|ten(?:th)? state",
        "command_association": r"say (?:or think |in your mind|in|or)|action signal",
        "future_use": r"future|more you use|more you perform",
        "return": r"wide awake|count.*(?:down to one|twenty)",
    }
    lines = text.splitlines()
    return {
        name: [number for number, line in enumerate(lines, 1) if re.search(pattern, line, re.I)]
        for name, pattern in patterns.items()
    }


def inventory(root: Path) -> dict:
    if not root.is_dir():
        raise OCFError(
            f"reference corpus not found: {root}; supply --root without modifying source files"
        )
    functions = [
        record
        for record in load_all_functions()
        if record.data.get("legacy", {}).get("source_system") == "Monroe H-PLUS"
    ]
    titles = dict(TITLE_ALIASES)
    for function in functions:
        for title in [
            function.data["legacy"]["name"],
            function.data["canonical"]["name"],
            *function.data["aliases"]["names"],
        ]:
            titles[normalized(title)] = function.id
    rows = []
    paths = sorted(path for path in root.rglob("*") if path.is_file())
    for path in paths:
        relative = path.relative_to(root)
        title = relative.parent.name if relative.parent != Path(".") else relative.stem
        data = path.read_bytes()
        text = None
        if path.suffix.lower() in (".txt", ".md", ".srt", ".lrc", ".vtt"):
            text = data.decode("utf-8-sig", errors="replace")
        evidence, basis, completeness = classify(relative, text)
        rows.append(
            {
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "title": title,
                "function_id": titles.get(normalized(title)),
                "source_type": path.suffix.lower().lstrip(".") or "unknown",
                "evidence_class": evidence,
                "classification_basis": basis,
                "completeness": completeness,
                "confidence": "explicit operator family/content; historical accuracy pending",
                "verification": "not independently authenticated against original recording",
                "candidate_locators": candidate_locators(text),
                "related_files": [],
                "uncertainties": [
                    "Candidate line locators require full-text/manual review before conversion",
                    "Source derivatives may contain ASR errors, duplicates, gaps or non-source insertions",
                ]
                if evidence in ("source_transcript", "partial_source_transcript")
                else ["No historical wording or completeness inferred"],
            }
        )
    for row in rows:
        row["related_files"] = [
            other["path"]
            for other in rows
            if other is not row
            and row["function_id"] is not None
            and other["function_id"] == row["function_id"]
        ]
    matrix = []
    for function in functions:
        selected = [row for row in rows if row["function_id"] == function.id]
        matrix.append(
            {
                "function_id": function.id,
                "legacy_name": function.data["legacy"]["name"],
                "canonical_command": function.data["canonical"]["command"]["primary"],
                "legacy_source_availability": function.data["legacy"]["source_availability"],
                "files": [row["path"] for row in selected],
                "source_derivative_available": any(
                    row["evidence_class"] in ("source_transcript", "partial_source_transcript")
                    for row in selected
                ),
                "mockup_available": any(
                    row["evidence_class"] == "reconstructed_mockup" for row in selected
                ),
                "conversion_status": "pending semantic extraction; no wording approval implied",
                "human_review_required": True,
            }
        )
    counts = Counter(row["evidence_class"] for row in rows)
    counts.update(
        {
            "file_count": len(rows),
            "distinct_functions": sum(bool(row["files"]) for row in matrix),
            "target_functions": len(matrix),
            "independently_verified_transcripts": 0,
        }
    )
    return {
        "schema_version": "1.0",
        "root": root.name,
        "counts": dict(sorted(counts.items())),
        "files": rows,
        "functions": matrix,
    }


def markdown(data: dict) -> str:
    lines = [
        "# Human Plus corpus evidence matrix",
        "",
        "GENERATED by `ocf corpus inventory`; no source wording redistributed.",
        "",
        "Source-derivative designation is operator evidence, not independent audio authentication.",
        "All completeness/content decisions require review. Mockups never become source transcripts.",
        "",
        "| ID | Legacy function | Source derivative | Mockup | Files | Review |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for row in data["functions"]:
        lines.append(
            f"| {row['function_id']} | {row['legacy_name']} | {'yes' if row['source_derivative_available'] else 'no'} | {'yes' if row['mockup_available'] else 'no'} | {len(row['files'])} | required |"
        )
    lines += [
        "",
        "## Counts",
        "",
        *[f"- {name}: {value}" for name, value in data["counts"].items()],
        "",
        "PDFs, pictures and ZIPs remain unknown until content-specific review; they are fingerprinted, not unpacked into runtime content.",
    ]
    return "\n".join(lines) + "\n"
