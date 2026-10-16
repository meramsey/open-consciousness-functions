"""Read-only, source-pinned editorial review; writes only companion proposals.

Uses the existing catalog, locale resolver, composer and earlier curated audit.
It never applies vocabulary, resolves private recordings, or invokes audio engines.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ocf_tools.commands import command_view  # noqa: E402
from ocf_tools.complete_session import build_complete_session_plan  # noqa: E402
from ocf_tools.indexes import load_all_functions  # noqa: E402
from ocf_tools.locale import LocaleCatalog, iter_events  # noqa: E402
from ocf_tools.paths import REPO_ROOT, workspace_run  # noqa: E402
from ocf_tools.utils import OCFError, write_text_atomic  # noqa: E402
from tools.title_cue_decisions import (  # noqa: E402
    PAIR_OVERRIDES,
    SECONDARY_PROPOSALS,
    TEACHING,
    UNRESOLVED,
)

SOURCE = "fb66fbce11dd3d71e57fac4d5784365128d41c82"
STATUS = "PROPOSED — NOT IMPLEMENTED"
PREFIX = "OCF_TITLE_CUE_REVIEW"
CLASSES = (
    "KEEP — TITLE, CUE, AND TEACHING ALREADY CONSISTENT",
    "KEEP CUE — ALIGN TITLE OR NARRATION",
    "RENAME TITLE/CUE — UPDATE TEACHING",
    "RESOLVE PURPOSE OR MODES BEFORE NAMING",
    "NEEDS HUMAN DECISION",
)


def words(value):
    """English screening only: preserves word order, repetitions and digits."""
    return tuple(re.findall(r"\w+", value.casefold()))


def mentions(text, phrases):
    """Keep literal evidence; a shorter phrase inside a longer one is not teaching."""
    found = []
    for phrase in sorted(set(phrases)):
        tokens = re.findall(r"\w+", phrase)
        if not tokens:
            continue
        pattern = r"(?<!\w)" + r"[\s,\-]+".join(map(re.escape, tokens)) + r"(?!\w)"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            found.append(
                {
                    "phrase": phrase,
                    "surface": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
    for row in found:
        row["nested"] = any(
            other["start"] <= row["start"]
            and other["end"] >= row["end"]
            and (other["start"], other["end"]) != (row["start"], row["end"])
            for other in found
        )
        row["excerpt"] = text[max(0, row["start"] - 150) : row["end"] + 160]
    return sorted(found, key=lambda row: (row["start"], -row["end"], row["phrase"]))


def node_fields(node):
    return {key.value: value for key, value in node.value}


def resource_evidence(path, phrases):
    """Use YAML scalar marks, not searching normalized text back into a file."""
    root = yaml.compose(path.read_text(encoding="utf-8"))
    entries = node_fields(node_fields(root)["entries"])
    rows = []
    for key, entry in entries.items():
        scalar = entry if isinstance(entry, yaml.ScalarNode) else node_fields(entry)["text"]
        if scalar.style != "|" and (
            "\n" in scalar.value or scalar.end_mark.line != scalar.start_mark.line
        ):
            raise OCFError(
                f"physical-line evidence requires a literal block or single-line scalar: {path}::{key}"
            )
        text = scalar.value
        first_line = scalar.start_mark.line + (2 if scalar.style in ("|", ">") else 1)
        found = mentions(text, phrases)
        for item in found:
            item["line"] = first_line + text[: item["start"]].count("\n")
        rows.append(
            {
                "key": key,
                "phase": key.rsplit(".", 1)[-1],
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "line": first_line,
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "mentions": found,
            }
        )
    return rows


def git(*args):
    return workspace_run(["git", *args], cwd=REPO_ROOT, capture_output=True, check=True).stdout


def source_snapshot(commit):
    """Bounded tracked UTF-8 snapshot; never open untracked/user reference corpora."""
    try:
        commit = (
            git("rev-parse", "--verify", "--end-of-options", f"{commit}^{{commit}}")
            .decode()
            .strip()
        )
    except subprocess.CalledProcessError as exc:
        raise OCFError(
            "pinned source commit unavailable; use a checkout containing its history"
        ) from exc
    names = git("ls-tree", "-r", "--name-only", commit).decode().splitlines()
    names = [
        name
        for name in names
        if not name.startswith(
            ("references/", "ReusablePrompts/", "brand/imports/", "brand/versions/")
        )
        and Path(name).suffix.lower()
        in {".py", ".json", ".yaml", ".yml", ".md", ".toml", ".txt", ".sh", ".ps1"}
    ]
    raw = workspace_run(
        ["git", "cat-file", "--batch"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        input="".join(f"{commit}:{name}\n" for name in names).encode(),
    ).stdout
    result, cursor = {}, 0
    for name in names:
        end = raw.index(b"\n", cursor)
        size = int(raw[cursor:end].split()[-1])
        cursor = end + 1
        body = raw[cursor : cursor + size]
        cursor += size + 1
        try:
            result[name] = body.decode("utf-8")
        except UnicodeDecodeError:
            continue
    return commit, result


def ensure_source(snapshot, paths):
    hashes = {}
    for name in sorted(set(paths)):
        actual = (REPO_ROOT / name).read_text(encoding="utf-8")
        if actual != snapshot.get(name):
            raise OCFError(
                f"source differs from pinned commit: {name}; preserve edits and use an isolated checkout"
            )
        hashes[name] = hashlib.sha256(actual.encode()).hexdigest()
    return hashes


def identifier_review(snapshot):
    inherited = json.loads(
        snapshot.get(
            "docs/releases/OCF_IDENTIFIER_NEUTRALIZATION_RECOMMENDATIONS.json", '{"mappings": []}'
        )
    )
    successors = {row["old"]: row["proposed"] for row in inherited["mappings"]}
    pattern = re.compile(
        r"OCF-[A-Z0-9-]*HPLUS[A-Z0-9-]*|hplus(?:\.[a-z0-9_-]+)+|human-plus-function|HPLUS|H-Plus|human-plus|human_plus|Human Plus",
        re.I,
    )
    rows = []
    for path, text in sorted(snapshot.items()):
        for number, line in enumerate(text.splitlines(), 1):
            for match in pattern.finditer(line):
                token = match.group()
                kind = (
                    "immutable imported/versioned material"
                    if path.startswith(("audio/defaults/", "tests/fixtures/hplus-narration"))
                    else "protected identity"
                    if token.startswith("hplus.")
                    else "historical provenance/attribution"
                    if path.startswith(
                        (
                            "docs/releases/",
                            "docs/research/",
                            "legacy/",
                            "function-content/evidence/",
                            "function-content/specifications/",
                        )
                    )
                    or "source_system" in line
                    or "attribution" in line.lower()
                    else "technical compatibility reference"
                    if path.startswith(("tests/", "schemas/"))
                    else "active OCF implementation"
                )
                rows.append(
                    {
                        "path": path,
                        "line": number,
                        "column": match.start() + 1,
                        "token": token,
                        "classification": kind,
                    }
                )
    by_token = defaultdict(list)
    by_file = defaultdict(list)
    for row in rows:
        by_token[row["token"]].append(row)
        by_file[row["path"]].append(row)

    def locators(evidence):
        locations = defaultdict(set)
        for row in evidence:
            locations[row["path"]].add(row["line"])
        return [{"path": path, "lines": sorted(lines)} for path, lines in sorted(locations.items())]

    paths = []
    for path in sorted(snapshot):
        target = None
        if path.startswith("locales/en-US/hplus-OCF-"):
            target = path.replace("/hplus-OCF-", "/function-OCF-", 1)
        elif path.startswith("audio/templates/") and "HPLUS" in Path(path).stem:
            proposed = successors.get(Path(path).stem)
            if proposed:
                target = str(Path(path).with_name(proposed + Path(path).suffix)).replace("\\", "/")
        elif path == "schemas/hplus-review-selection.schema.json":
            target = "schemas/source-review-selection.schema.json"
        elif path == "scripts/tools/check_hplus_narration_integrity.py":
            target = "scripts/tools/check_narration_integrity.py"
        elif path == "tests/fixtures/hplus-narration-text-baseline.json":
            target = "tests/fixtures/narration-text-baseline-v2.json"
        if target:
            paths.append(
                {
                    "current": path,
                    "proposed_successor": target,
                    "decision": "Explicit successor only; preserve original identity/hash and update actual consumers together",
                }
            )
    return {
        "scope": "Pinned tracked source text; binary assets, immutable brand imports and all references/ReusablePrompts excluded without opening. User-owned reference occurrences deliberately unmeasured.",
        "counts": dict(Counter(row["classification"] for row in rows)),
        "text_occurrences": len(rows),
        "file_inventory": [
            {
                "path": path,
                "occurrences": len(items),
                "classifications": dict(Counter(row["classification"] for row in items)),
            }
            for path, items in sorted(by_file.items())
        ],
        "path_mappings": paths,
        "mappings": [
            {
                "current": token,
                "proposed_successor": successors[token],
                "evidence": locators(evidence),
                "decision": "Preserve immutable original; deliberate successor and explicit bijective mapping only after approval",
            }
            for token, evidence in sorted(by_token.items())
            if token in successors
        ],
        "user_owned_reference": "Excluded by policy, preserved; no fabricated count or mechanical renaming.",
    }


def guard_sources(snapshot):
    """Check the bounded canonical dependency closure, including added files."""
    roots = (
        "functions",
        "locales",
        "function-content",
        "schemas",
        "audio/templates",
        "audio/stages",
        "audio/slots",
        "audio/defaults",
        "audio/background/state-profiles",
    )
    expected = {
        name
        for name in snapshot
        if name.startswith(tuple(root + "/" for root in roots))
        and Path(name).suffix in {".yaml", ".yml", ".json"}
    }
    actual = {
        path.relative_to(REPO_ROOT).as_posix()
        for root in roots
        for path in (REPO_ROOT / root).rglob("*")
        if path.is_file() and path.suffix in {".yaml", ".yml", ".json"}
    }
    if actual != expected:
        raise OCFError(
            "canonical dependency inventory differs from pinned source: "
            + ", ".join(sorted(actual ^ expected))
        )
    for name in expected:
        if not (REPO_ROOT / name).resolve().is_relative_to(REPO_ROOT.resolve()):
            raise OCFError("canonical dependency escapes checkout: " + name)
        if name.startswith("audio/templates/") and (REPO_ROOT / Path(name).stem).exists():
            raise OCFError("template shadow in repository root: " + Path(name).stem)
    return ensure_source(snapshot, expected)


def build(commit=SOURCE):
    commit, snapshot = source_snapshot(commit)
    hashes = guard_sources(snapshot)
    # Public template lookup considers relative paths: anchor it at the verified
    # checkout, never at an operator's unrelated current directory.
    with contextlib.chdir(REPO_ROOT):
        return _build(commit, snapshot, hashes)


def _build(commit, snapshot, hashes):
    # Reuse the committed earlier curated proposal without importing dirty drafts.
    earlier = json.loads(snapshot["docs/releases/OCF_COMMAND_NAMING_RECOMMENDATIONS.json"])
    prior = {row["function_id"]: row for row in earlier["functions"]}
    records = sorted(load_all_functions(), key=lambda record: record.id)
    if set(TEACHING) != {record.id for record in records} or set(prior) != set(TEACHING):
        raise OCFError(
            "contextual review must cover the actual catalog exactly; review new identities explicitly"
        )
    catalog = LocaleCatalog()
    all_commands = {
        record.id: [command_view(record, command) for command in record.command_records]
        for record in records
    }
    phrases = {
        value
        for rows in all_commands.values()
        for row in rows
        for value in (row["phrase"], row.get("observed_phrase", {}).get("text", ""))
    } | {row[0] for row in TEACHING.values()}
    inputs, functions, commands = [], [], []
    for record in records:
        old = prior[record.id]
        taught, context = TEACHING[record.id]
        title, cue = old.get("proposed_title") or record.canonical_name, old["proposed_command"]
        alternatives, reason = [], old["rationale"]
        if record.id in PAIR_OVERRIDES:
            title, cue, alternatives, reason = PAIR_OVERRIDES[record.id]
        if record.id == "OCF-EXP-001":
            alternatives = [
                {
                    "title": "Create",
                    "cue": "PLUS-CREATE",
                    "note": "Broader than future-condition manifestation; preserve completion-time instruction if chosen.",
                }
            ]
        if record.id == "OCF-SLP-005":
            alternatives = [
                {
                    "title": "Quiet Sleep",
                    "cue": "PLUS-QUIET SLEEP",
                    "note": "Aligns current complete teaching, retains unfamiliar-condition scope.",
                }
            ]
        resources = resource_evidence(
            REPO_ROOT / f"locales/en-US/hplus-{record.id}.yaml", phrases | {cue}
        )
        complete = [
            dict(item, resource_key=res["key"], phase=res["phase"], path=res["path"])
            for res in resources
            for item in res["mentions"]
            if words(item["phrase"]) == words(taught) and not item["nested"]
        ]
        phases = {item["phase"] for item in complete}
        if not {"function-body", "closer"} <= phases:
            raise OCFError(f"reviewed complete cue missing from body/closer: {record.id}")
        metadata_matches = words(record.canonical_command or "") == words(taught)
        # Explicit spoken realization may explain typography, never arbitrary word merging.
        primary = next(row for row in all_commands[record.id] if row["designation"] == "primary")
        observed = primary.get("observed_phrase", {})
        if record.id == "OCF-BOD-007":
            metadata_matches = observed.get("text") == taught
        category = (
            CLASSES[3]
            if record.id in UNRESOLVED
            else CLASSES[4]
            if record.id == "OCF-SLP-005"
            else CLASSES[1]
            if words(cue) == words(taught)
            and (cue != record.canonical_command or title != record.canonical_name)
            else CLASSES[2]
            if cue != record.canonical_command
            else CLASSES[1]
            if title != record.canonical_name or not metadata_matches
            else CLASSES[0]
        )
        title_cue_reason = (
            reason
            if record.id in PAIR_OVERRIDES
            else (
                "Title and cue name the same selected operation; a concise verb, outcome or contextual mode can reinforce an umbrella title without copying it. "
                + reason
            )
        )
        evidence = []
        for name in old["source_references"]:
            if name not in snapshot:
                continue
            inputs.append(name)
            evidence.append({"path": name, "line": 1})
        # Locate actual declaration fields, not a bare path-only citation.
        definition = record.path.relative_to(REPO_ROOT).as_posix()
        for number, line in enumerate(snapshot[definition].splitlines(), 1):
            if line.strip().startswith(
                ("primary:", "name:", "summary:", "- id:", "command_review:", "persistence:")
            ):
                evidence.append({"path": definition, "line": number, "text": line.strip()})
        plan = build_complete_session_plan(record.id, locale="en-US")
        bindings = [
            {
                "event_id": event["id"],
                "narration_key": event.get("narration_key"),
                "variables": event.get("variables", {}),
                "stem_marker_required": True,
            }
            for event in iter_events(plan["template_plan"])
        ]
        composed = []
        for key in sorted({event["narration_key"] for event in bindings if event["narration_key"]}):
            entry, resolution = catalog.resource(key, "en-US", domain="narration", fallback=False)
            name = f"locales/{resolution.origin_locale}/{entry.file}"
            inputs.append(name)
            composed.append(
                {
                    "key": key,
                    "file": name,
                    "text_sha256": hashlib.sha256(entry.text.encode()).hexdigest(),
                }
            )
        command_rows = []
        for command in all_commands[record.id]:
            observed_text = command.get("observed_phrase", {}).get("text")
            evidence_phrases = {command["phrase"], observed_text} - {None}
            hits = [
                dict(item, resource_key=res["key"], phase=res["phase"], path=res["path"])
                for res in resources
                for item in res["mentions"]
                if item["phrase"] in evidence_phrases and not item["nested"]
            ]
            proposed, secondary_reason = SECONDARY_PROPOSALS.get(
                command["id"],
                (
                    command["phrase"],
                    "Retain this scoped mode/control pending paired review; historical lookup alone grants no new active alias.",
                ),
            )
            if command["designation"] == "primary":
                proposed, secondary_reason = cue, reason
            status = (
                "complete-phrase-present; contextual role reviewed in function note"
                if hits
                else "not-independently-taught-in-function-resource"
            )
            keys = set(command.get("procedure", {}).get("evidence_keys", []))
            if command.get("observed_phrase", {}).get("narration_key"):
                keys.add(command["observed_phrase"]["narration_key"])
            separate = []
            for key in sorted(keys - {res["key"] for res in resources}):
                entry, resolution = catalog.resource(
                    key, "en-US", domain="narration", fallback=False
                )
                name = f"locales/{resolution.origin_locale}/{entry.file}"
                inputs.append(name)
                found = [
                    res for res in resource_evidence(REPO_ROOT / name, phrases) if res["key"] == key
                ]
                separate.extend(found)
            if any(
                not item["nested"] and item["phrase"] in evidence_phrases
                for res in separate
                for item in res["mentions"]
            ):
                status = "complete-phrase-present-in-separately-bound-control-resource; not a composed event by implication"
            command_rows.append(
                {
                    **command,
                    "proposed_phrase": proposed,
                    "proposal_status": STATUS,
                    "decision": secondary_reason,
                    "teaching_finding": status,
                    "evidence": hits,
                    "separate_evidence": separate,
                    "lookup_vs_active": "Preserve current runtime role; future historical-only lookup needs specific approval, no automatic spoken compatibility lesson.",
                }
            )
        commands.extend(command_rows)
        functions.append(
            {
                "function_id": record.id,
                "current_title": record.canonical_name,
                "current_metadata_cue": record.canonical_command,
                "exact_taught_cue": taught,
                "current_purpose": record.purpose_summary,
                "documentary_intent": old["function_purpose"]["extracted_intent"],
                "recommended_title": title,
                "recommended_primary_cue": cue,
                "alternatives": alternatives,
                "secondary_modes_controls": [
                    {
                        key: command[key]
                        for key in (
                            "id",
                            "phrase",
                            "role",
                            "designation",
                            "proposed_phrase",
                            "teaching_finding",
                        )
                    }
                    for command in command_rows
                    if command["designation"] != "primary"
                ],
                "historical_lookup": {
                    "legacy": record.data["legacy"],
                    "aliases": record.data["aliases"],
                    "former_ocf_title": record.canonical_name,
                },
                "pair_reason": reason,
                "title_cue_relationship_or_exception": title_cue_reason,
                "contextual_review": context,
                "metadata_teaching_consistent": metadata_matches,
                "teaching_disposition": "Preserve complete taught cue; metadata/title alignment only"
                if words(cue) == words(taught)
                else "New spoken association requires explicit body/reinforcement/closer approval",
                "narration_locations": resources,
                "complete_taught_evidence": complete,
                "localization": {
                    "function_bindings": record.documentation,
                    "locale": "en-US",
                    "policy": "LocaleCatalog remains authoritative; per-locale explicit title/cue/teaching terminology, no universal prefix or word boundaries.",
                },
                "technical_impact": {
                    "composed_events": bindings,
                    "composed_resources": composed,
                    "bindings": old["session_usage"],
                    "recordings": "Private manifests/stems not inspected. Review event/resource/unit mappings and every composed nonspoken marker; preserve originals. No recording relabeling.",
                    "cache": "Any changed text/locale/voice needs matching fresh fingerprints, recordings/TTS and measured timing; do not rewrite old receipts/immutable locks.",
                    "generated": "Regenerate indexes, command guides and plans only after approved active changes; generated references are current metadata, not proof of taught speech.",
                    "rendered_transcripts": "No new render. Source composition resolved without engines; recorded speech and final rendered transcripts unverified.",
                },
                "classification": category,
                "status": STATUS,
                "current_review_status": record.command_review,
                "source_availability": record.source_availability,
                "lifecycle": record.data["lifecycle"],
                "evidence": evidence,
                "decision_needed": "Approve paired title/cue, scope clarification and explicit body/reinforcement/closer association plan; approve controls together. No narration replacement text selected.",
            }
        )
    input_roots = (
        "schemas/",
        "audio/templates/",
        "audio/background/state-profiles/",
        "audio/defaults/",
        "function-content/command-procedures",
    )
    inputs.extend(name for name in snapshot if name.startswith(input_roots))
    hashes.update(ensure_source(snapshot, inputs))
    collision_groups = defaultdict(list)
    for row in commands:
        collision_groups[words(row["proposed_phrase"])].append(
            {
                "function_id": row["function_id"],
                "command_id": row["id"],
                "role": row["role"],
                "phrase": row["proposed_phrase"],
            }
        )
    collisions = [
        {
            "english_screen_words": list(key),
            "owners": owners,
            "assessment": "Related Imprint retrieval/Recall activation: retain distinct procedures and selected targets"
            if key == words("PLUS-RECALL")
            else "Selected temporary-application control: explicit target required; not ability erasure"
            if key == words("PLUS-RELEASE")
            else "Historical/duplicate role or mode overlap: inspect identities; no alias is newly activated",
        }
        for key, owners in sorted(collision_groups.items())
        if len(owners) > 1
    ]
    return {
        "status": STATUS,
        "source_commit": commit,
        "inherited_proposal": {
            "path": "docs/releases/OCF_COMMAND_NAMING_RECOMMENDATIONS.json",
            "file_commit": commit,
            "declared_evidence_commit": earlier.get("source_commit"),
            "use": "Earlier unapproved editorial starting points, not fresh primary evidence; complete teaching/context reviewed separately in this revision.",
        },
        "working_tree_scope": "Canonical inputs checked against pinned committed source, no working-tree data changes incorporated. Earlier committed recommendations are starting proposals; this companion adds independent recommendations. Existing uncommitted audit/search/localization proposals preserved and not imported.",
        "review_method": "All 55 source-English bodies/closers reviewed by contextual investigation. Literal code-point offsets, YAML source lines and original excerpts retained. English case/separator screening only: no number expansion, reordering, stemming or pronunciation inference. Nested phrases excluded; occurrence is not automatic teaching approval.",
        "counts": {
            "functions": len(functions),
            "commands": len(commands),
            "classifications": dict(Counter(row["classification"] for row in functions)),
            "metadata_teaching_mismatches": sum(
                not row["metadata_teaching_consistent"] for row in functions
            ),
        },
        "functions": functions,
        "commands": commands,
        "collision_review": collisions,
        "collision_limits": "No current unrelated-primary duplicate identified by English word screening. Prefix ambiguity (Sleep/Sleep Insight, Release/Release Eleven Access), near sound (Flow Better/Flow Smooth, Breath/Breathe), and role reuse require whole-phrase listening/local-language review; no acoustic verification or universal normalization claimed.",
        "source_sha256": hashes,
        "identifiers": identifier_review(snapshot),
    }


def render(data):
    header = [
        f"Status: {STATUS}.",
        "",
        f"Source commit: `{data['source_commit']}`.",
        "",
        data["working_tree_scope"],
        "",
    ]
    lines = [
        "# Complete title–cue decision sheet — companion revision",
        "",
        *header,
        "## Priority decisions",
        "",
        "1. Manifest / PLUS-MANIFEST: preserve future condition and completion time; CREATE is broader.",
        "2. Sleep Easy / PLUS-SLEEP EASY: current complete teaching is Plus Quiet Sleep; approve association decision with unfamiliar-condition scope and unchanged breathing.",
        "3. Food Energy Use / PLUS-USE FOOD ENERGY, paired PLUS-RETAIN LESS EXCESS: resolve asymmetric utilization/retention, not appetite or Nourish Less.",
        "4. Release / PLUS-RELEASE: retain contextual selected-application ending; Contemplation retains the explicit OPEN/CLOSED reciprocal operation.",
        "5. Inner Power / PLUS-INNER POWER: preserve total-self scope; Habit Freedom / PLUS-FREE THIS HABIT distinguishes lasting habit change from temporary release.",
        "",
        "## Complete catalog",
        "",
        "Intended capabilities below are not experimentally demonstrated outcomes. Existing approvals are reported, not granted/revoked by this proposal. See JSON for every command, exact excerpt, source hash and composed marker.",
        "",
    ]
    for row in data["functions"]:
        lines += [
            f"### {row['function_id']} — {row['current_title']}",
            "",
            f"- Current: {row['current_title']} / `{row['current_metadata_cue']}`; complete taught cue: **{row['exact_taught_cue']}**.",
            f"- Preferred: **{row['recommended_title']} / {row['recommended_primary_cue']}**. {row['classification']}. {STATUS}.",
            f"- Purpose: {row['current_purpose']} Documentary intent: {row['documentary_intent']}",
            f"- Procedure / retained scope / discrepancies: {row['contextual_review']}",
            f"- Pair reason / exception: {row['title_cue_relationship_or_exception']}",
            f"- Teaching disposition: {row['teaching_disposition']}.",
            f"- Alternatives: {json.dumps(row['alternatives'], ensure_ascii=False) if row['alternatives'] else 'None needed.'}",
            f"- Historical lookup: {row['historical_lookup']['legacy']['name']}; former OCF title {row['current_title']}; historical phrases {json.dumps(row['historical_lookup']['legacy']['commands'], ensure_ascii=False)}. Lookup does not grant active cues.",
            f"- Review/source: {row['current_review_status']} / {row['source_availability']}; lifecycle {json.dumps(row['lifecycle'])}.",
        ]
        locations = sorted(
            {
                f"{item['path']}:{item['line']} ({item['phase']})"
                for item in row["complete_taught_evidence"]
            }
        )
        lines += [
            "- Exact teaching evidence: " + "; ".join(locations) + ".",
            "- Modes / controls: "
            + (
                "; ".join(
                    f"{cmd['id']} `{cmd['phrase']}` ({cmd['role']}) → proposed `{cmd['proposed_phrase']}`; {cmd['teaching_finding']}"
                    for cmd in row["secondary_modes_controls"]
                    if cmd["designation"] != "primary"
                )
                or "No separate mode/control records; do not invent one."
            ),
            "- Collision/localization: whole phrases and role/selected target govern; see cross-catalog review. Review title, cue, purpose, controls and narration as one per-locale terminology set using stable IDs; prefix policy remains undecided.",
            "- Migration: review all resource locations and composed bindings in JSON, recorded event/resource/unit mappings and whole-session markers. Fresh changed-text receipts/timing; preserve recordings and immutable locks; regenerate references only after approval.",
            f"- Decision: {row['decision_needed']}",
            "",
        ]
    lines += ["## Collision and ambiguity review", "", data["collision_limits"], ""]
    lines += [
        f"- {' '.join(group['english_screen_words'])}: {group['assessment']}; "
        + ", ".join(owner["command_id"] + " (" + owner["role"] + ")" for owner in group["owners"])
        for group in data["collision_review"]
    ]
    teaching = [
        "# Exact teaching-consistency report",
        "",
        *header,
        data["review_method"],
        "",
        "This is source-text/context verification, not ASR, listening or historical authentication. A body repetition uses the same bound source; repeated count does not establish a shorter phrase. Generated indexes describe metadata; no new rendered speech was inspected.",
        "",
    ]
    for row in data["functions"]:
        teaching += [
            f"## {row['function_id']}",
            "",
            f"Metadata: `{row['current_metadata_cue']}`. Complete teaching: **{row['exact_taught_cue']}**. Consistent: {row['metadata_teaching_consistent']}.",
            "",
            row["contextual_review"],
            "",
        ]
        for item in row["complete_taught_evidence"]:
            teaching += [
                f"- `{item['path']}:{item['line']}` / `{item['resource_key']}` / offsets {item['start']}:{item['end']}: {json.dumps(item['excerpt'], ensure_ascii=False)}"
            ]
        teaching += [""]
    ident = [
        "# OCF-native identifier successor proposal — companion",
        "",
        *header,
        "## Scope and dependency decisions",
        "",
        data["identifiers"]["scope"],
        "",
        "Classifications: " + json.dumps(data["identifiers"]["counts"], sort_keys=True) + ".",
        "",
        "- Active templates/pacing: use FUNCTION-LEARNING and SHARED role names; retain inheritance and all repetition/pacing values.",
        "- DSP: F10-BED-F11-ACCESS describes policy, not semantic state identity; do not rename sleep semantics as a DSP onset.",
        "- Defaults: OCF-AUDIO-DEFAULTS-FUNCTION-LEARNING-002 is a successor; old lock/hash manifest remains immutable and independently verifiable. No baseline approval implied.",
        "- Protected narration keys/locale filenames: function.<stable-id>.<role> and session.shared.<role> are proposed identities; prove a bijective old-file/key → successor map with identical text before approval. Keep imported/versioned baselines unchanged.",
        "- Bindings/generated plans and recorded manifests/stems: migrate exact event/resource/unit references together; preserve originals, speaker/provenance and every nonspoken marker. Rebuild text/config receipts; never relabel old speech or hashes.",
        "- Python/schema/CLI/MCP/LSP/tests: migrate actual lookup constructors, resource pointers, definition/reference indexes, cache identities and integrity fixture consumers together. Surface compatibility is explicit and time-bounded only for real consumers.",
        "- Historical attribution, evidence, immutable imports and user references remain labeled history; identifier changes never confer original authorship or rights.",
        "",
        "## Proposed mappings",
        "",
        "The JSON companion carries per-token file/line evidence and classifications, including schemas, Python, CLI/MCP/LSP, tests, bindings and generated references. This is a decision inventory, not a mechanical replacement script.",
        "",
    ]
    ident += [
        f"- `{row['current']}` → `{row['proposed_successor']}`. {row['decision']}."
        for row in data["identifiers"]["mappings"]
    ]
    return {
        f"{PREFIX}.md": "\n".join(lines).rstrip() + "\n",
        f"{PREFIX}.json": json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        "OCF_EXACT_TEACHING_REVIEW.md": "\n".join(teaching).rstrip() + "\n",
        "OCF_IDENTIFIER_SUCCESSOR_PROPOSAL.md": "\n".join(ident).rstrip() + "\n",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", default=SOURCE)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "docs/releases")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = build(args.source_commit)
        files = render(data)
        for name, text in files.items():
            path = args.output / name
            if args.check:
                if not path.is_file() or path.read_text(encoding="utf-8") != text:
                    raise OCFError(f"companion report stale: {path}")
            else:
                write_text_atomic(path, text)
        print(
            json.dumps(
                {
                    "source_commit": data["source_commit"],
                    "status": STATUS,
                    "counts": data["counts"],
                    "files": list(files),
                },
                ensure_ascii=False,
            )
        )
        return 0
    except (OCFError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
