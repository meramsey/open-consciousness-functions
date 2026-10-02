"""Read full local corpus objects; publish hashes/counts/relationships, never wording."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from ocf_tools.corpus import candidate_locators, classify  # noqa: E402
from ocf_tools.transcript import parse_transcript  # noqa: E402
from ocf_tools.utils import OCFError  # noqa: E402


def content_hash(text: str, fmt: str) -> str:
    parsed = parse_transcript(text, fmt=fmt)
    words = re.findall(
        r"\w+(?:['’-]\w+)*", " ".join(event.text for event in parsed.events).casefold()
    )
    return hashlib.sha256(" ".join(words).encode()).hexdigest()


def analyze(root: Path, inventory: dict) -> dict:
    files = []
    groups = defaultdict(list)
    grammar = defaultdict(Counter)
    census = Counter()
    known = defaultdict(list)
    for row in inventory["files"]:
        known[row["sha256"]].append(row["path"])
    for row in inventory["files"]:
        path = root / row["path"]
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise OCFError(f"reference changed since inventory: {row['path']}; review separately")
        result = {
            "sha256": row["sha256"],
            "path": row["path"],
            "function_id": row["function_id"],
            "evidence_class": row["evidence_class"],
            "content_sha256": None,
            "inspection": "binary metadata only",
        }
        fmt = row["source_type"]
        if fmt in ("txt", "srt", "lrc", "vtt"):
            text = data.decode("utf-8-sig", errors="replace")
            result["content_sha256"] = content_hash(text, fmt)
            groups[(row["function_id"], result["content_sha256"])].append(row["sha256"])
            result["inspection"] = (
                "complete text read; structure candidate census, not manual semantic approval"
            )
            if fmt == "txt" and row["evidence_class"] in (
                "source_transcript",
                "partial_source_transcript",
            ):
                markers = candidate_locators(text)
                result["candidate_categories"] = sorted(
                    name for name, lines in markers.items() if lines
                )
                for category in result["candidate_categories"]:
                    grammar[category]["source_functions_with_candidate"] += 1
                result["word_count"] = len(text.split())
        elif fmt == "pdf":
            executable = shutil.which("pdftotext")
            if executable:
                process = subprocess.run(
                    [executable, "-layout", str(path), "-"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if process.returncode == 0:
                    text = process.stdout
                    result["inspection"] = (
                        "complete extracted PDF text read; source text not redistributed"
                    )
                    headings = [
                        name
                        for name, pattern in {
                            "command": r"function\s+command",
                            "description": r"(?:general|function)\s+description",
                            "purpose": r"\bpurpose\s*:",
                            "application": r"application",
                            "notes": r"notes",
                        }.items()
                        if re.search(pattern, text, re.I)
                    ]
                    result["heading_categories"] = headings
                    if "command" in headings and (
                        "description" in headings or "purpose" in headings
                    ):
                        result["evidence_class"] = "secondary_description"
                        result["classification_basis"] = (
                            "command and purpose/description headings in extracted PDF; pamphlet candidate, not transcript authentication"
                        )
                else:
                    result["inspection"] = "PDF extraction failed; classification remains unknown"
        elif fmt == "zip":
            members = []
            with zipfile.ZipFile(path) as archive:
                for item in archive.infolist():
                    if item.is_dir():
                        continue
                    if item.file_size > 16 * 1024 * 1024:
                        members.append(
                            {"name": item.filename, "inspection": "oversized member; not expanded"}
                        )
                        continue
                    member = archive.read(item)
                    digest = hashlib.sha256(member).hexdigest()
                    suffix = Path(item.filename).suffix.lower()
                    evidence = "unknown"
                    if suffix in (".txt", ".md"):
                        evidence = classify(
                            Path(Path(item.filename).name),
                            member.decode("utf-8-sig", errors="replace"),
                        )[0]
                    members.append(
                        {
                            "name": item.filename,
                            "sha256": digest,
                            "bytes": len(member),
                            "evidence_class": evidence,
                            "equal_local_files": known.get(digest, []),
                        }
                    )
            result["members"] = members
            result["inspection"] = (
                "ZIP members hashed/read in memory; never extracted to filesystem"
            )
        census[result["evidence_class"]] += 1
        files.append(result)
    relationships = [
        {
            "function_id": function_id,
            "content_sha256": digest,
            "representations": sorted(set(hashes)),
            "independent_authentication": False,
        }
        for (function_id, digest), hashes in groups.items()
        if len(set(hashes)) > 1
    ]
    return {
        "schema_version": "1.0",
        "method": "case-folded word sequence after format parsing; punctuation/layout ignored, never semantic or historical equivalence",
        "files": files,
        "content_equivalence_groups": relationships,
        "classification_counts": dict(census),
        "grammar_candidates": dict(grammar),
        "independently_authenticated_recordings": 0,
        "semantic_extraction_status": "partial; candidate patterns require source review",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--inventory", type=Path, default=ROOT / "docs/research/humanplus-corpus-inventory.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.root.resolve()):
        raise OCFError(
            "derived relationship report must remain outside the read-only reference corpus"
        )
    result = analyze(args.root, json.loads(args.inventory.read_text(encoding="utf-8")))
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "files": len(result["files"]),
                "classification_counts": result["classification_counts"],
                "content_groups": len(result["content_equivalence_groups"]),
                "grammar_candidates": result["grammar_candidates"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
