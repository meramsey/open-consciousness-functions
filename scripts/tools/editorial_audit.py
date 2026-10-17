"""Read-only editorial recommendations; this tool has no rename/apply operation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ocf_tools.commands import command_view  # noqa: E402
from ocf_tools.indexes import load_all_functions, load_yaml_file  # noqa: E402
from ocf_tools.paths import REPO_ROOT, work_root, workspace_run  # noqa: E402
from ocf_tools.utils import OCFError, sha256_of_file, write_text_atomic  # noqa: E402
from tools.check_hplus_narration_integrity import check, narration_texts  # noqa: E402

SOURCE_COMMIT = "301471df6b446b8f6eadf67797b163cb0d14cd00"
PROPOSAL = "PROPOSED — NOT IMPLEMENTED"
STATES = {
    "KEEP",
    "OPTIONAL IMPROVEMENT",
    "RECOMMENDED RENAME",
    "NEEDS SOURCE REVIEW",
    "NEEDS HUMAN DECISION",
}

# Deliberately curated recommendations, not an algorithm that rewrites vocabulary.
# state, proposed activation, alternatives, rationale, optional title, priority.
DECISIONS = {
    "OCF-AUT-001": (
        "KEEP",
        "PLUS-AUTOMATE",
        ["PLUS-AUTO ACT"],
        "AUTOMATE states the learned-action goal directly; See-Be is much less discoverable. Distinguish learned automatic performance from future-condition programming.",
        "Automatic Action",
        "medium",
    ),
    "OCF-BOD-001": (
        "RECOMMENDED RENAME",
        "PLUS-BRAIN FLOW",
        ["PLUS-FLOW BETTER"],
        "Name the brain-related target explicitly; FLOW BETTER and FLOW SMOOTH are easily confused without a body target. This names an intended operation, not proven vascular repair.",
        "Brain Flow",
        "high",
    ),
    "OCF-BOD-002": (
        "KEEP",
        "PLUS-FLOW SMOOTH",
        ["PLUS-CIRCULATE"],
        "Smooth flow is short and positive. Keep its whole-body circulation scope distinct from Brain Flow and mental flow states.",
        None,
        "low",
    ),
    "OCF-BOD-003": (
        "KEEP",
        "PLUS-COMFORT",
        ["PLUS-EASE DISCOMFORT"],
        "COMFORT is a clear constructive outcome and a substantial usability improvement over a numeric mnemonic; do not conflate it with temporary numbing and its release procedure.",
        "Comfort",
        "low",
    ),
    "OCF-BOD-004": (
        "NEEDS HUMAN DECISION",
        "PLUS-CLEAN CLEAR",
        ["PLUS-DETOX", "PLUS-BODY CLEAR"],
        "CLEAN CLEAR bridges the actual spoken association and describes the intended cleansing operation; decide the retained body-cleansing intent before changing DETOX. A purely psychological redefinition is not a cosmetic rename.",
        "Body Clarity",
        "high",
    ),
    "OCF-BOD-005": (
        "NEEDS SOURCE REVIEW",
        "PLUS-SATISFIED, SUPPLIED",
        ["PLUS-EAT MORE / PLUS-EAT LESS"],
        "The preserved main installation is incomplete. SATISFIED/SUPPLIED could encode different appetite directions; do not invent a directional pair from the title alone. Separate appetite from Nutricia's food-energy utilization intent.",
        "Appetite Choice",
        "high",
    ),
    "OCF-BOD-006": (
        "OPTIONAL IMPROVEMENT",
        "PLUS-HEART BETTER",
        ["PLUS-HEART, BETTER, BETTER"],
        "The organ target is clear; removing repetition can shorten activation, but repetition may be part of the learned association. Do not narrow heart renewal into only heart-rate steadiness without a separate purpose decision.",
        "Heart Renewal",
        "medium",
    ),
    "OCF-BOD-007": (
        "NEEDS HUMAN DECISION",
        "PLUS-BALANCE PRESSURE",
        ["PLUS-PRESSURE BALANCE", "PLUS-BALANCE-BLOODPRESSURE"],
        "Current spelling compresses multiple spoken words and blurs phrase boundaries. Decide whether the independent function retains explicit blood-pressure intent or a materially different experiential objective.",
        "Pressure Balance",
        "high",
    ),
    "OCF-BOD-008": (
        "NEEDS HUMAN DECISION",
        "PLUS-IMMUNE READY",
        ["PLUS-ALERT, DESTROY"],
        "IMMUNE READY is a clearer positive target than generic ALERT/DESTROY and avoids confusing ordinary alertness. Retaining immune-system intent versus redesigning readiness requires an explicit decision.",
        "Immune Readiness",
        "high",
    ),
    "OCF-BOD-009": (
        "RECOMMENDED RENAME",
        "PLUS-BREATHE BETTER",
        ["PLUS-BREATH BETTER"],
        "BREATHE is the natural spoken verb and already appears in reviewed narration; BREATH is the noun. A registry correction could align the phrase without rewriting that speech, but still needs command approval.",
        "Breathe Better",
        "high",
    ),
    "OCF-BOD-010": (
        "RECOMMENDED RENAME",
        "PLUS-NOURISH MORE",
        ["PLUS-NOURISH LESS", "PLUS-FOOD MORE / PLUS-FOOD LESS"],
        "The extracted intent is food-energy absorption/use, not merely appetite. NOURISH distinguishes it from Eat/No Eat; approve both directional modes together and do not silently redefine the underlying claims.",
        "Nourishment",
        "high",
    ),
    "OCF-BOD-011": (
        "NEEDS HUMAN DECISION",
        "PLUS-HORMONE BALANCE",
        ["PLUS-EQUALIZE-HARMONIZE", "PLUS-EASE TRANSITION"],
        "Passages and the abstract verb pair conceal the hormonal-transition context. HORMONE BALANCE states that intent; EASE TRANSITION would be a different experiential framing and must not be assumed equivalent.",
        "Hormonal Transitions",
        "medium",
    ),
    "OCF-BOD-012": (
        "KEEP",
        "PLUS-SEX MORE",
        ["PLUS-SEX LESS"],
        "The paired personal-arousal directions are concise and meaningful. Keep them self-directed, retain exact legacy GREATER/LESSER records, and do not change magnitudes for uniformity.",
        None,
        "low",
    ),
    "OCF-BOD-013": (
        "KEEP",
        "PLUS-BALANCE, HEAL",
        ["PLUS-TUNE UP"],
        "The two positive operations fit the intended targeted body-balancing practice. HEAL need not be reflexively weakened in proposed intention language; intended outcome and established efficacy remain separate.",
        "Body Tune-Up",
        "low",
    ),
    "OCF-BOD-014": (
        "KEEP",
        "PLUS-REGENERATE",
        ["PLUS-BUILD, LIVE"],
        "REGENERATE is already a distinctive OCF-native intended outcome. Preserve the reviewed legacy-form association and source-unavailable provenance rather than inventing recovered historical wording.",
        None,
        "low",
    ),
    "OCF-BOD-015": (
        "NEEDS HUMAN DECISION",
        "PLUS-NUMB",
        ["PLUS-COMFORT QUICK"],
        "NUMB names the documented temporary de-tuning intent precisely. COMFORT QUICK would change scope and overlap Comfort. Make the temporary application and its explicit PLUS-RELEASE procedure clear before preferring a new name.",
        "Temporary Numbing",
        "high",
    ),
    "OCF-COG-001": (
        "OPTIONAL IMPROVEMENT",
        "PLUS-ACCESS INFO",
        ["PLUS-RETRIEVE"],
        "Access to a personal information/experience library overlaps Recall. ACCESS INFO may improve distinction, but neither name establishes information accuracy or an external knowledge source.",
        "Information Access",
        "medium",
    ),
    "OCF-COG-002": (
        "KEEP",
        "PLUS-CALCULATE",
        ["PLUS-NUMBERS"],
        "CALCULATE is a natural, memorable action. A descriptive title is clearer than the Buy/By the Numbers pun without changing the cue or its broader numerical-memory purpose.",
        "Mental Calculation",
        "low",
    ),
    "OCF-COG-003": (
        "OPTIONAL IMPROVEMENT",
        "PLUS-CONTEMPLATE",
        ["PLUS-OPEN", "PLUS-OPEN SPACE"],
        "CONTEMPLATE identifies the goal more distinctly than generic OPEN. If adopted, retain the explicit PLUS-CLOSED closing role unless separately approved; do not invent a new close command or strip the greater-self context.",
        None,
        "medium",
    ),
    "OCF-COG-004": (
        "KEEP",
        "PLUS-IMPRINT",
        ["PLUS-IMPRINT, IMPRINT"],
        "IMPRINT clearly identifies deliberate encoding. The separate PLUS-RECALL retrieval record is functional reuse, not a duplicate activation to delete.",
        None,
        "low",
    ),
    "OCF-COG-005": (
        "KEEP",
        "PLUS-OPTIONS",
        ["PLUS-OPTIONS, CHOICES"],
        "OPTIONS directly evokes alternatives and is concise. Distinguish selected possibilities from verified predictions without flattening the intended contemplative approach.",
        None,
        "low",
    ),
    "OCF-COG-006": (
        "KEEP",
        "PLUS-RECALL",
        ["PLUS-REMEMBER"],
        "RECALL is a strong, specific retrieval cue and is intentionally shared with Imprint retrieval. Clarify experience recall versus Information Access through purpose documentation, not arbitrary vocabulary churn.",
        None,
        "low",
    ),
    "OCF-COG-007": (
        "KEEP",
        "PLUS-THINK",
        ["PLUS-THINK FAST"],
        "The existing short cue is strong and explicitly protected by the current contract. No MORE/LESS rewrite or superficial title matching is warranted.",
        None,
        "low",
    ),
    "OCF-COM-001": (
        "KEEP",
        "PLUS-SPEAK UP",
        ["PLUS-EXPRESS"],
        "Natural spoken phrasing, a recognizable title and clear communication intent already align.",
        None,
        "low",
    ),
    "OCF-EMG-001": (
        "NEEDS HUMAN DECISION",
        "PLUS-CONTROL, BALANCE, RESTORE",
        ["PLUS-INJURY CARE"],
        "The three verbs express a purposeful sequence rather than gratuitous length. Decide retained injury-response and conditional automatic-operation intent; RESTORE alone would collide with Restorative Sleep and lose scope.",
        "Injury Response",
        "high",
    ),
    "OCF-EMG-002": (
        "NEEDS SOURCE REVIEW",
        "PLUS-CLEAR, REMOVE",
        ["PLUS-TOXIC RESPONSE"],
        "The two-word procedure is coherent, but the available brochure/reconstruction does not authenticate a full historical recording. Decide the independent toxic-exposure intent; do not relabel it as generic emotional clearing.",
        "Toxic Exposure Response",
        "high",
    ),
    "OCF-EMO-001": (
        "KEEP",
        "PLUS-LET GO",
        ["PLUS-RELEASE EMOTION"],
        "A familiar positive release phrase already matches the intended selected-emotion operation. Keep it distinct from function suspension.",
        None,
        "low",
    ),
    "OCF-EMO-002": (
        "RECOMMENDED RENAME",
        "PLUS-OFFLOAD",
        ["PLUS-CLEAR", "PLUS-FADE, FADE"],
        "OFFLOAD identifies reducing a selected recurring mental/emotional load better than generic CLEAR. Preserve selective salience reduction; do not imply erasing memory or automatically change the FADE association.",
        "Offload",
        "medium",
    ),
    "OCF-EMO-003": (
        "RECOMMENDED RENAME",
        "PLUS-EMPATHIZE",
        ["PLUS-PROFILE, PROFILE"],
        "EMPATHIZE is a more natural, outcome-oriented cue than repetitive profiling jargon. Empathic intention must remain distinct from verified mind-reading or diagnosis.",
        "Empathy",
        "high",
    ),
    "OCF-EXP-001": (
        "NEEDS HUMAN DECISION",
        "PLUS-MANIFEST",
        ["PLUS-CREATE", "PLUS-CHANGE", "PLUS-PROGRAM"],
        "The extracted procedure selects a desired future condition and completion time. MANIFEST best fits retained manifestation intent; CREATE is broader; CHANGE is the closest concise bridge to current speech but is underspecified. Practical goal rehearsal would be a separate purpose redesign.",
        "Future Pattern",
        "high",
    ),
    "OCF-EXP-002": (
        "RECOMMENDED RENAME",
        "PLUS-INSULATE",
        ["PLUS-ZONE", "PLUS-THERMAL COMFORT"],
        "The actual described intent is a temperature-comfort field, not general protection from unwanted influence. INSULATE restores functional specificity and bridges the spoken cue. Preserve distinct CANCEL and RELEASE roles.",
        "Thermal Comfort",
        "high",
    ),
    "OCF-FND-001": (
        "KEEP",
        "PLUS-ENERGIZE",
        ["PLUS-ACCESS ENERGY"],
        "ENERGIZE is a clear positive cue. Distinguish experiential access/direction of an energy reserve from a restorative nap; preserve the separate Release Eleven Access resource and command.",
        None,
        "low",
    ),
    "OCF-FND-002": (
        "KEEP",
        "PLUS-FOCUS",
        ["PLUS-ATTEND"],
        "The current cue is clear, short and explicitly protected. Keep it; a historical label does not justify an unnecessary rename.",
        None,
        "low",
    ),
    "OCF-FND-003": (
        "KEEP",
        "PLUS-RECHARGE",
        ["PLUS-QUICK REST"],
        "RECHARGE naturally communicates the short-rest intended outcome. Preserve the nap/waking mechanics rather than merging it with general energy access or overnight restoration.",
        "Quick Recharge",
        "low",
    ),
    "OCF-FND-004": (
        "KEEP",
        "PLUS-RELAX",
        ["PLUS-RELAX, RELAX"],
        "RELAX is direct and positive. The repeated spoken association remains frozen; no spelling or grammar uniformity requires changing it.",
        None,
        "low",
    ),
    "OCF-FND-005": (
        "KEEP",
        "PLUS-RESET",
        ["PLUS-REFRESH"],
        "RESET is memorable for changing a selected tired/low pattern. Correct purpose documentation should distinguish it from neutralizing every function; do not silently change the actual energetic/confident intent.",
        None,
        "medium",
    ),
    "OCF-FND-006": (
        "NEEDS HUMAN DECISION",
        "PLUS-SUSPEND",
        ["PLUS-RELEASE"],
        "SUSPEND more explicitly denotes ending a selected temporary function application without erasing learned knowledge. RELEASE is already a shared scoped primitive; resolve targeting/grouping and compatibility before choosing either.",
        "Suspend Function",
        "high",
    ),
    "OCF-LIF-001": (
        "RECOMMENDED RENAME",
        "PLUS-RELEASE HABIT",
        ["PLUS-NO MORE, NO MORE", "PLUS-CHANGE HABIT"],
        "A positive, specific release cue is clearer than a repeated negative four-word phrase. Do not substitute acquisition of a new habit for reduction of an unwanted one; that would change mechanics.",
        "Release Habit",
        "high",
    ),
    "OCF-PRF-001": (
        "KEEP",
        "PLUS-DO-THIS-NOW",
        ["PLUS-DO THIS NOW"],
        "The phrase is natural and immediately actionable. Hyphens are a representation/spoken-tokenization audit issue, not authorization to normalize an existing command.",
        None,
        "low",
    ),
    "OCF-PRF-002": (
        "RECOMMENDED RENAME",
        "PLUS-CAPABLE",
        ["PLUS-STRONG", "PLUS-EIGHT, GREAT"],
        "CAPABLE better expresses total inner capability and separates it from Strong-Quick's momentary physical-strength intent. Eight-Great is an opaque historical mnemonic.",
        "Inner Capability",
        "medium",
    ),
    "OCF-PRF-003": (
        "KEEP",
        "PLUS-SMOOTH, FAST",
        ["PLUS-COORDINATE"],
        "The paired positive outcomes fit motor coordination. Prefer a clearer title/purpose over changing a strong meaningful cue merely for uniformity.",
        "Coordination",
        "medium",
    ),
    "OCF-PRF-004": (
        "OPTIONAL IMPROVEMENT",
        "PLUS-LIGHT STEP",
        ["PLUS-LIGHT", "PLUS-LIGHTER, LIGHTER"],
        "LIGHT STEP distinguishes moving-foot ease from brightness or a generic light state. Preserve the actual moving-feet condition; do not broaden to all-body levitation or unrelated movement.",
        None,
        "medium",
    ),
    "OCF-PRF-005": (
        "KEEP",
        "PLUS-THIS DAY",
        ["PLUS-SHAPE DAY"],
        "A short personal temporal cue is already meaningful for the morning/day-pattern practice. A verb-first rewrite is optional and not justified solely by stylistic uniformity.",
        None,
        "low",
    ),
    "OCF-PRF-006": (
        "KEEP",
        "PLUS-STRONG QUICK",
        ["PLUS-STRONG-QUICK"],
        "Both intended qualities are explicit and differentiate the momentary emergency application from general capability. Preserve its RELEASE record and do not assume a longer cue is worse merely because the old spelling was hyphenated.",
        None,
        "medium",
    ),
    "OCF-SEN-001": (
        "KEEP",
        "PLUS-HEAR MORE",
        ["PLUS-HEAR LESS"],
        "Meaningful directional hearing controls are already clear. Do not conflate physical/perceived sound with only inner listening; keep the frozen Hearing review separate.",
        "Hearing",
        "low",
    ),
    "OCF-SEN-002": (
        "KEEP",
        "PLUS-SEE BETTER",
        ["No magnitude rewrite proposed"],
        "The exact current cue is strong and explicitly protected. The extracted seeing-system intent is broader than inner visualization; clarify scope separately without rewriting the cue.",
        "Seeing",
        "low",
    ),
    "OCF-SEN-003": (
        "KEEP",
        "PLUS-SMELL MORE",
        ["PLUS-SMELL LESS"],
        "The paired sensory directions are concise and intelligible; preserve historical GREATER/LESSER records as provenance rather than adding new synonyms.",
        "Smell",
        "low",
    ),
    "OCF-SEN-004": (
        "KEEP",
        "PLUS-TASTE MORE",
        ["PLUS-TASTE LESS"],
        "Taste sensitivity is distinct from appetite and food-energy utilization; the current pair communicates that target clearly.",
        "Taste",
        "low",
    ),
    "OCF-SEN-005": (
        "KEEP",
        "PLUS-TOUCH MORE",
        ["PLUS-TOUCH LESS", "PLUS-FEEL TOUCH"],
        "The tactile scope needs a clear usage label, but replacing TOUCH with generic FEEL could increase emotional ambiguity. Keep the existing directional pair.",
        "Touch",
        "low",
    ),
    "OCF-SLP-001": (
        "OPTIONAL IMPROVEMENT",
        "PLUS-RESTORATIVE SLEEP",
        ["PLUS-RESTORE", "PLUS-HEAL, HEAL"],
        "A sleep qualifier makes restoration more distinctive. Retain body-restoration/healing intent as an intended goal if selected; do not reflexively replace it with generic relaxation or imply an established result.",
        None,
        "medium",
    ),
    "OCF-SLP-002": (
        "KEEP",
        "PLUS-SLEEP",
        ["PLUS-20-20"],
        "The title and direct sleep-onset cue align. Preserve the distinct exhalation procedure and desire-dependent waking; do not merge with Sleep Easy or question incubation.",
        None,
        "low",
    ),
    "OCF-SLP-003": (
        "KEEP",
        "PLUS-DREAM",
        ["PLUS-THEME, DREAM, SLEEP"],
        "DREAM is concise and useful for a selected dream pattern. Dream Theme may describe the actual range better than only pleasant dreams, without changing activation.",
        "Dream Theme",
        "low",
    ),
    "OCF-SLP-004": (
        "RECOMMENDED RENAME",
        "PLUS-SLEEP INSIGHT",
        ["PLUS-KNOW", "PLUS-SLEEP, HELP"],
        "The actual intended operation is question/problem incubation and recalled insight on waking, not knowing when to wake. The proposed phrase is distinctive and purpose-specific without claiming answers are factually correct.",
        "Sleep Insight",
        "high",
    ),
    "OCF-SLP-005": (
        "NEEDS HUMAN DECISION",
        "PLUS-SLEEP EASY",
        ["PLUS-QUIET SLEEP"],
        "PLUS-SLEEP EASY is the actual registry canonical phrase and matches the title; Plus Quiet Sleep is the actual reviewed speech. Prefer keeping the recognizable title/canonical pair unless distinct adverse-setting semantics justify Quiet Sleep; explicitly decide the bridge before any speech change.",
        None,
        "high",
    ),
    "OCF-SLP-006": (
        "KEEP",
        "PLUS-AWAKE",
        ["PLUS-ONE, AWAKE, ALERT, ONE, ONE"],
        "AWAKE directly names the essential temporary alertness goal. Do not revive an opaque five-token mnemonic merely for historical consistency, or broaden a temporary application into continuous use.",
        None,
        "low",
    ),
}


def normalized(phrase):
    return tuple(re.findall(r"[\w]+", phrase.casefold()))


def historical_report():
    """Read the artifact revision, without restamping its earlier evidence SHA."""
    recorded_at = "21e63ac6f8bf5a7bce9506f033330df967aa4f97"
    result = workspace_run(
        ["git", "show", recorded_at + ":docs/releases/OCF_COMMAND_NAMING_RECOMMENDATIONS.json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def canonical_audit():
    records = sorted(load_all_functions(), key=lambda item: item.id)
    if set(DECISIONS) != {record.id for record in records}:
        raise OCFError("editorial decisions must cover every canonical function exactly")
    previous = historical_report()
    if any(
        sha256_of_file(REPO_ROOT / name) != checksum
        for name, checksum in previous["source_sha256"].items()
    ):
        raise OCFError(
            "historical editorial audit input drift; run it at its matching source checkpoint or use the current approved-cue report"
        )
    owners = defaultdict(list)
    for record in records:
        for command in record.command_records:
            row = command_view(record, command)
            owners[normalized(row["phrase"])].append(
                {"function_id": record.id, "command_id": command.id, "role": command.role}
            )
    functions, commands, sources = [], [], {}
    for record in records:
        state, proposed, alternatives, rationale, title, priority = DECISIONS[record.id]
        assert state in STATES
        spec_path = REPO_ROOT / "function-content/specifications" / f"{record.id}.yaml"
        binding_path = REPO_ROOT / "function-content/bindings" / f"{record.id}.yaml"
        resource_path = REPO_ROOT / "locales/en-US" / f"hplus-{record.id}.yaml"
        spec, binding, resource = map(load_yaml_file, (spec_path, binding_path, resource_path))
        sections = spec.get("analysis_review", {}).get("sections", {})
        current = [command_view(record, command) for command in record.command_records]
        spoken = []
        phrases = {row["phrase"] for row in current}
        phrases.update(
            row["observed_phrase"]["text"] for row in current if row.get("observed_phrase")
        )
        for key, entry in resource["entries"].items():
            text = entry if isinstance(entry, str) else entry["text"]
            matches = set()
            for phrase in phrases:
                words = normalized(phrase)
                if not words:
                    continue
                pattern = r"\b" + r"[\s,\-]+".join(re.escape(word) for word in words) + r"\b"
                matches.update(match.group() for match in re.finditer(pattern, text, re.IGNORECASE))
            spoken.append(
                {
                    "resource_key": key,
                    "version": entry.get("version") if isinstance(entry, dict) else None,
                    "exact_activation_fragments": sorted(matches),
                    "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                }
            )
        collisions = [
            row for row in owners.get(normalized(proposed), []) if row["function_id"] != record.id
        ]
        shared = {
            row["phrase"]: owners[normalized(row["phrase"])]
            for row in current
            if len(owners[normalized(row["phrase"])]) > 1
        }
        command_rows = []
        for row in current:
            decision = "Retain current scoped role; no alias/release/retrieval status change is implemented."
            if row["role"] == "activation" and row["designation"] == "primary":
                decision = rationale
            command_rows.append(
                {
                    **row,
                    "audit_status": PROPOSAL,
                    "recommendation": state if row["designation"] == "primary" else "KEEP",
                    "rationale": decision,
                    "lexical_post_prefix_words": len(normalized(row["phrase"])[1:]),
                    "shared_phrase_owners": owners[normalized(row["phrase"])],
                }
            )
        commands.extend(command_rows)
        matching_candidate = [
            entry["resource_key"]
            for entry in spoken
            if any(
                normalized(fragment) == normalized(proposed)
                for fragment in entry["exact_activation_fragments"]
            )
        ]
        impact = "No wording or IDs changed. "
        if proposed == record.canonical_command:
            impact += "No activation rewrite is proposed; resolve any existing spoken-form/registry distinction explicitly. A proposed display-title change does not authorize changing a spoken opener/title. "
        elif matching_candidate:
            impact += (
                "The candidate already matches an actual reviewed spoken fragment in "
                + ", ".join(matching_candidate)
                + "; registry alignment alone does not imply a speech rewrite. "
            )
        else:
            impact += "The proposed cue is not matched in the current declared/spoken cue fragments; approve a deliberate association/bridge plan before changing body/closer words. "
        impact += "Any actual wording change requires human review, affected recording re-versioning/re-recording and new measured timing. Existing text hashes do not verify what a recording says."
        functions.append(
            {
                "function_id": record.id,
                "function_title": record.canonical_name,
                "current_command": record.canonical_command,
                "other_commands": command_rows[1:],
                "all_command_records": command_rows,
                "function_purpose": {
                    "registry": record.purpose_summary,
                    "extracted_intent": sections.get("purpose", {}).get(
                        "summary", "not established"
                    ),
                    "family": spec.get("analysis_review", {}).get("family"),
                    "evidence_note": "Intended/documentary operation, not empirically established effectiveness.",
                },
                "clarity_assessment": rationale,
                "proposed_command": proposed,
                "proposed_title": title,
                "alternatives": alternatives,
                "rationale": rationale,
                "conflict_risk": {
                    "proposed_exact_other_owners": collisions,
                    "current_shared_phrases": shared,
                    "level": "high"
                    if collisions or state.startswith("NEEDS")
                    else "medium"
                    if shared or state != "KEEP"
                    else "low",
                },
                "narration_impact": impact,
                "observed_narration": spoken,
                "lifecycle": record.data["lifecycle"],
                "mechanics": {
                    key: sections.get(key, {}).get("summary", "not established")
                    for key in ("main", "association", "future_use", "suspend_cancel_reset")
                },
                "aliases": record.data["aliases"],
                "legacy": record.data["legacy"],
                "compatibility": record.data["compatibility"],
                "recommendation": state,
                "priority": priority,
                "status": PROPOSAL,
                "source_references": [
                    record.path.relative_to(REPO_ROOT).as_posix(),
                    spec_path.relative_to(REPO_ROOT).as_posix(),
                    binding_path.relative_to(REPO_ROOT).as_posix(),
                    resource_path.relative_to(REPO_ROOT).as_posix(),
                    f"audio/session-plans/en-US/{record.id}.json",
                ],
                "session_usage": {
                    "default_template": binding.get("default_session_template"),
                    "sequence": binding.get("narration_plan", {}).get("sequence", []),
                },
                "pronunciation_impact": "Compare actual spoken forms, punctuation and numeral expansion; new phoneme hints are a separate reviewed change. Never infer phrase authority from typography.",
                "command_review_status": record.command_review,
                "source_availability": record.source_availability,
            }
        )
        for path in (record.path, spec_path, binding_path, resource_path):
            sources[path.relative_to(REPO_ROOT).as_posix()] = sha256_of_file(path)
    return {
        "schema_version": "1.0",
        "source_commit": SOURCE_COMMIT,
        "status": PROPOSAL,
        "implemented": False,
        "counts": {
            "functions": len(functions),
            "command_records": len(commands),
            "protected_entries": len(narration_texts()),
            "classifications": dict(Counter(row["recommendation"] for row in functions)),
        },
        "functions": functions,
        "commands": commands,
        "source_sha256": sources,
    }


def tracked_snapshot():
    result = workspace_run(
        ["git", "ls-tree", "-r", "--name-only", SOURCE_COMMIT],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    names = [
        name
        for name in result.stdout.splitlines()
        if Path(name).suffix.lower()
        not in {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".wav",
            ".flac",
            ".mp3",
            ".m4a",
            ".ogg",
            ".opus",
            ".zip",
            ".pdf",
            ".ttf",
            ".otf",
            ".woff",
            ".woff2",
            ".onnx",
        }
        and not name.startswith(("ReusablePrompts/", "references/HumanPlusTranscripts/"))
    ]
    output = workspace_run(
        ["git", "cat-file", "--batch"],
        input="".join(f"{SOURCE_COMMIT}:{name}\n" for name in names).encode(),
        capture_output=True,
        check=True,
        cwd=REPO_ROOT,
    ).stdout
    cursor = 0
    for name in names:
        end = output.index(b"\n", cursor)
        header = output[cursor:end].split()
        size = int(header[-1])
        cursor = end + 1
        raw = output[cursor : cursor + size]
        cursor += size + 1
        if b"\0" in raw:
            continue
        try:
            yield name, raw.decode("utf-8")
        except UnicodeDecodeError:
            continue


def category(path, line, token):
    if token.startswith("hplus."):
        return "protected resource key"
    if token.startswith("OCF-") or token == "human-plus-function":
        return "active implementation identifier"
    if path.startswith("references/"):
        return "user-supplied reference"
    if "source_system" in line or "unaffiliated" in line or "attribution" in line.casefold():
        return "external attribution"
    if (
        path.startswith(
            (
                "function-content/evidence/",
                "function-content/specifications/",
                "docs/releases/",
                "docs/research/",
                "legacy/",
            )
        )
        or "provenance" in line.casefold()
    ):
        return "historical provenance"
    if re.search(r"^\s*(?:name|title)\s*:", line):
        return "human-readable active label"
    if path.startswith(("tests/", "docs/", "schemas/")):
        return "compatibility reference"
    return "historical provenance"


def neutral_target(identifier):
    explicit = {
        "OCF-TPL-SESSION-HPLUS-STANDARD-001": "OCF-TPL-SESSION-FUNCTION-LEARNING-STANDARD-001",
        "OCF-TPL-SESSION-HPLUS-LOCKED-001": "OCF-TPL-SESSION-FUNCTION-LEARNING-LOCKED-001",
        "OCF-PACING-HPLUS-STANDARD-001": "OCF-PACING-FUNCTION-LEARNING-STANDARD-001",
        "OCF-PACING-HPLUS-LOCKED-001": "OCF-PACING-FUNCTION-LEARNING-LOCKED-001",
        "OCF-DSP-HPLUS-STANDARD-DRAFT-001": "OCF-DSP-F10-BED-F11-ACCESS-STANDARD-DRAFT-001",
        "OCF-DSP-HPLUS-LOCKED-001": "OCF-DSP-F10-BED-F11-ACCESS-LOCKED-001",
        "OCF-AUDIO-DEFAULTS-HPLUS-001": "OCF-AUDIO-DEFAULTS-FUNCTION-LEARNING-002",
        "human-plus-function": "guided-function-learning",
    }
    if identifier in explicit:
        return explicit[identifier]
    if identifier.startswith("OCF-TPL-STAGE-HPLUS-"):
        target = identifier.replace("-HPLUS-", "-SHARED-")
        return (
            target.replace("-FOCUS-TWENTY-ENTER-", "-SLEEP-ENTRY-")
            .replace("-FOCUS-TWENTY-CLOSE-", "-SLEEP-CLOSE-")
            .replace("-TUNING-", "-RESONANT-TUNING-")
            .replace("-RELAXATION-", "-PROGRESSIVE-RELAXATION-")
        )
    if identifier.startswith("hplus.function."):
        return identifier.removeprefix("hplus.")
    if identifier.startswith("hplus.optional."):
        return identifier.replace("hplus.optional.", "session.optional.", 1)
    for old, new in (
        ("hplus.shared.focus10.return.", "session.shared.focus-ten.return."),
        ("hplus.shared.focus10.", "session.shared.focus-ten.induction."),
        ("hplus.shared.focus11.open", "session.shared.focus-eleven.access.open"),
        ("hplus.shared.focus11.close", "session.shared.focus-eleven.access.close"),
        ("hplus.shared.focus11.ready", "session.shared.focus-eleven.access.ready"),
        ("hplus.shared.focus20.enter", "session.shared.sleep.entry"),
        ("hplus.shared.waking.begin", "session.shared.waking.return"),
        ("hplus.shared.body-comfort", "session.shared.preparation.body-comfort"),
        ("hplus.shared.transmutation-box.", "session.shared.preparation.transmutation-box."),
        ("hplus.shared.relaxation.", "session.shared.relaxation."),
    ):
        if identifier.startswith(old):
            return identifier.replace(old, new, 1)
    return None


def _path_mappings(files):
    rows = []
    for entry in files:
        old = entry["path"]
        path = Path(old)
        proposed = None
        if old.startswith("locales/en-US/hplus-OCF-"):
            proposed = old.replace("/hplus-OCF-", "/function-OCF-")
        elif old == "locales/en-US/hplus-focus20.yaml":
            proposed = "locales/en-US/session-shared-sleep-entry.yaml"
        elif old == "locales/en-US/hplus-focus10.yaml":
            proposed = "locales/en-US/session-shared-focus-ten.yaml"
        elif old.startswith("locales/en-US/hplus-focus11-"):
            proposed = old.replace("hplus-focus11-", "session-shared-focus-eleven-")
        elif old.startswith("locales/en-US/hplus-"):
            proposed = old.replace("/hplus-", "/session-shared-", 1)
        elif (
            old.startswith(("audio/templates/", "audio/background/state-profiles/"))
            and "HPLUS" in path.stem
        ):
            mapped = neutral_target(path.stem)
            if mapped:
                proposed = path.with_name(mapped + path.suffix).as_posix()
        elif old == "schemas/hplus-review-selection.schema.json":
            proposed = "schemas/source-review-selection.schema.json"
        elif old == "scripts/tools/check_hplus_narration_integrity.py":
            proposed = "scripts/tools/check_narration_integrity.py"
        elif old == "tests/fixtures/hplus-narration-text-baseline.json":
            proposed = "tests/fixtures/narration-text-baseline.json"
        elif old == "audio/defaults/OCF-AUDIO-DEFAULTS-HPLUS-001.json":
            proposed = "audio/defaults/OCF-AUDIO-DEFAULTS-FUNCTION-LEARNING-002.json"
        if proposed:
            rows.append(
                {
                    "old": old,
                    "proposed": proposed,
                    "status": PROPOSAL,
                    "implemented": False,
                    "risk": "high",
                    "decision": "Create a reviewed successor and retain the immutable old file; prove exact key/path/text equivalence"
                    if "baseline" in old or "/defaults/" in old
                    else "Update actual manifest/schema/import consumers together; no automatic move or alias",
                }
            )
    return rows


def identifier_audit():
    pattern = re.compile(
        r"OCF-[A-Z0-9-]*HPLUS[A-Z0-9-]*|hplus(?:\.[a-z0-9_-]+)+|human-plus-function|HPLUS|H-Plus|human-plus|human_plus|Human Plus",
        re.IGNORECASE,
    )
    occurrences, files, identifiers, definitions = [], [], set(), set()
    for path, text in tracked_snapshot():
        file_rows = []
        for number, line in enumerate(text.splitlines(), 1):
            for match in pattern.finditer(line):
                token = match.group()
                row = {
                    "path": path,
                    "line": number,
                    "column": match.start() + 1,
                    "token": token,
                    "category": category(path, line, token),
                    "excerpt": line.strip()[:240],
                }
                occurrences.append(row)
                file_rows.append(row)
                if token.startswith(("OCF-", "hplus.")) or token == "human-plus-function":
                    identifiers.add(token)
        if file_rows:
            files.append(
                {
                    "path": path,
                    "occurrences": len(file_rows),
                    "categories": dict(Counter(row["category"] for row in file_rows)),
                }
            )
        if Path(path).suffix in {".json", ".yaml", ".yml"}:
            try:
                from ocf_tools.utils import yaml_safe_load

                data = yaml_safe_load(text)
                if isinstance(data, dict):
                    if isinstance(data.get("id"), str):
                        definitions.add(data["id"])
                    if isinstance(data.get("entries"), dict):
                        definitions.update(data["entries"])
            except (ValueError, OCFError, yaml.YAMLError):
                pass
    mappings = []
    for old in sorted(identifiers):
        target = neutral_target(old)
        if target is None:
            # Partial dynamic namespace constructors are inventory, not invented definitions.
            continue
        exact = [row for row in occurrences if row["token"] == old]
        mappings.append(
            {
                "old": old,
                "proposed": target,
                "status": PROPOSAL,
                "implemented": False,
                "risk": "critical"
                if "DEFAULTS" in old
                else "high"
                if old.startswith("hplus.")
                else "medium",
                "defined_in_snapshot": old in definitions,
                "target_collision": target in definitions,
                "affected_files": sorted({row["path"] for row in exact}),
                "compatibility": "Explicit reviewed source-map/fingerprint migration for real recorded consumers; no automatic or perpetual alias"
                if old.startswith("hplus.")
                else "Successor baseline, never overwrite old lock"
                if "DEFAULTS" in old
                else "Versioned manifest migration; aliases only for demonstrated external consumers",
            }
        )
    return {
        "schema_version": "1.0",
        "source_commit": SOURCE_COMMIT,
        "status": PROPOSAL,
        "implemented": False,
        "scope": "All tracked UTF-8 implementation/data/docs text in source commit; no binary assets or untracked/private reference corpora read",
        "text_occurrences": len(occurrences),
        "files_affected": len(files),
        "categories": dict(Counter(row["category"] for row in occurrences)),
        "mappings": mappings,
        "path_mappings": _path_mappings(files),
        "files": files,
        "occurrences": occurrences,
    }


def command_markdown(data):
    lines = [
        "# OCF command and function naming audit",
        "",
        f"**{PROPOSAL}. No command, title, narration or approval status was changed.**",
        "",
        f"Source checkpoint: `{SOURCE_COMMIT}`. Audited {data['counts']['functions']} functions and {data['counts']['command_records']} structured command records. The {data['counts']['protected_entries']} protected entries remain unchanged.",
        "",
        "## Decision summary",
        "",
        "| Function | Current cue | Candidate cue | Recommendation | Priority |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in data["functions"]:
        lines.append(
            f"| {row['function_id']} | {row['current_command']} | {row['proposed_command']} | {row['recommendation']} | {row['priority']} |"
        )
    lines += [
        "",
        "## Review principles",
        "",
        "Names below describe intended operations, not empirically established effectiveness. Preserve confident, constructive, consciousness-oriented intention and actual activation/persistence mechanics. Do not automatically paraphrase or add distancing to reviewed narration. Any material purpose change is a separate human decision, not a naming cleanup.",
        "",
        "Historical aliases remain evidence and real learned/recorded compatibility inputs where actually used; no new aliases are implemented. Do not retain permanent aliases solely for hypothetical consumers. Exact registry phrases, observed speech and procedure roles are distinct. Hyphen/space/comma spelling does not establish spoken-word count or pronunciation.",
        "",
        "## High-priority cross-function decisions",
        "",
        "- Mobius West: `PLUS-PROGRAM` is current; `Plus Change Change` is spoken. Evaluate MANIFEST, CREATE and CHANGE against desired future condition plus completion time. MANIFEST is the conditional leading candidate if that manifestation intent is retained; a practical goal-rehearsal redesign is not assumed equivalent.",
        "- Sleep Easy: `PLUS-SLEEP EASY` is current canonical metadata and matches the title. `Plus Quiet Sleep` is actual reviewed body/closer speech; `PLUS-QUIET, SLEEP` is the legacy phrase. Keeping Sleep Easy is the default recommendation; an explicit bridge or a deliberate Quiet Sleep choice needs human review. Do not alter current speech. Distinguish adverse/unfamiliar-setting sleep from ordinary Sleep and the frozen safe-rest pilot.",
        "- Purpose discrepancies needing review: Mobius West (future condition, not merely breaking loops), Zoning (temperature comfort, not generic unwanted influence), Nutricia (food-energy use, not appetite), Wake/Know (sleep problem incubation, not wake-time selection), Reset (energetic/confident pattern change, not a global neutral reset), Seeing/Hearing (do not silently equate physical and inner perception).",
        "- Shared phrases: `PLUS-RECALL` is Imprint retrieval and Recall activation. RELEASE forms occur in selected-function suspension and local release roles. Keep explicit function/role targeting; do not globally redirect them or confuse `Plus Release Eleven Access` with every release.",
        "- Keep `PLUS-THINK`, `PLUS-FOCUS` and `PLUS-SEE BETTER`. MORE/LESS belongs to the actual adjustable modes; do not impose it on historical cue families.",
        "",
        "## Narration recommendations — audit only",
        "",
        "For each approved future cue, review its exact opener/body/closer occurrences and deliberate association teaching. A candidate instruction such as “Use Plus Sleep Easy as your chosen activation phrase” is a NEW proposal, not source wording and not inserted here. Preserve breath placement, repetitions where meaningful, selected targets, closing/releasing roles and the difference between permanent learned availability and temporary application. Voice re-recording and fresh timing follow actual text changes. Separate editorial flags from protected wording; no automatic originalization, hedging or migration is authorized.",
        "",
        "## Complete function audit",
        "",
    ]
    for row in data["functions"]:
        phrases = "; ".join(
            f"`{c['id']}` — `{c['phrase']}` ({c['role']}, {c['designation']})"
            for c in row["other_commands"]
        )
        phrases = (
            (phrases or "No separate secondary/mode/release records")
            + "; legacy phrase fields: "
            + json.dumps(row["legacy"]["commands"])
            + "; alias phrase fields: "
            + json.dumps(row["aliases"]["commands"])
            + ". Repeated storage is not an extra command record."
        )
        observed = "; ".join(
            f"`{entry['resource_key']}`: {', '.join('`' + phrase + '`' for phrase in entry['exact_activation_fragments']) or 'no exact registered/declared cue fragment matched'}"
            for entry in row["observed_narration"]
        )
        lifecycle = row["lifecycle"]
        fields = [
            ("FUNCTION ID", row["function_id"]),
            ("FUNCTION TITLE", row["function_title"]),
            ("CURRENT COMMAND", row["current_command"]),
            ("OTHER COMMANDS", phrases),
            (
                "FUNCTION PURPOSE",
                f"Registry: {row['function_purpose']['registry']} Documentary intent: {row['function_purpose']['extracted_intent']}",
            ),
            ("CLARITY ASSESSMENT", row["clarity_assessment"]),
            ("PROPOSED COMMAND", f"{row['proposed_command']} — {PROPOSAL}"),
            ("ALTERNATIVES", "; ".join(row["alternatives"])),
            ("RATIONALE", row["rationale"]),
            (
                "CONFLICT RISK",
                f"{row['conflict_risk']['level']}; exact candidate owners outside this function: {json.dumps(row['conflict_risk']['proposed_exact_other_owners'])}; current shared roles: {json.dumps(row['conflict_risk']['current_shared_phrases'])}",
            ),
            ("NARRATION IMPACT", row["narration_impact"]),
            ("RECOMMENDATION", row["recommendation"]),
            ("PRIORITY", row["priority"]),
            (
                "CURRENT REVIEW / SOURCE STATUS",
                row["command_review_status"] + " / " + row["source_availability"] + "; unchanged",
            ),
            (
                "TITLE PROPOSAL",
                (row["proposed_title"] + " — " + PROPOSAL)
                if row["proposed_title"]
                else "Keep current title",
            ),
            (
                "ACTIVATION / PERSISTENCE / RELEASE",
                f"{lifecycle['activation']} / {lifecycle['persistence']} / {json.dumps(lifecycle['release'])}. Learned availability and effect duration are not interchangeable.",
            ),
            ("MECHANICS", "; ".join(key + ": " + value for key, value in row["mechanics"].items())),
            ("NARRATION ACTIVATION / CLOSING", observed),
            ("VOICE IMPLICATIONS", row["pronunciation_impact"]),
            ("SESSION / RESOURCES", json.dumps(row["session_usage"], ensure_ascii=False)),
            ("SOURCE REFERENCES", "; ".join("`" + path + "`" for path in row["source_references"])),
        ]
        lines += (
            [f"### {row['function_id']} — {row['function_title']}", ""]
            + [f"- **{key}:** {value}" for key, value in fields]
            + [""]
        )
    lines += [
        "## Machine-readable companion",
        "",
        "[All recommendations, all 97 current command records, source fingerprints and scoped roles](OCF_COMMAND_NAMING_RECOMMENDATIONS.json). This report is not a command registry and is never consumed by session rendering.",
        "",
    ]
    return "\n".join(lines)


def identifier_markdown(data):
    lines = [
        "# OCF identifier neutralization audit",
        "",
        f"**{PROPOSAL}. No active identifier, alias, source key or locked baseline was changed.**",
        "",
        f"Snapshot `{SOURCE_COMMIT}`: {data['text_occurrences']} text occurrences in {data['files_affected']} tracked files. Scope: {data['scope']}. Path spellings are represented by affected-file names, not silently added to text-match totals.",
        "",
        "## Classification totals",
        "",
    ]
    lines += [f"- {name}: {count}" for name, count in sorted(data["categories"].items())]
    lines += [
        "",
        "## Design decisions and real dependencies",
        "",
        "Prefer function-learning names for the shared shell, role-specific shared narration keys, and F10-bed/F11-access names for the actual DSP policy. Do not name these F20 DSP: logical sleep/return semantics are distinct from the continuous Focus 10 bed. Existing generic cue-bearing Focus 11 stages are not interchangeable with these centrally paced narration stages.",
        "",
        "The proposed `OCF-AUDIO-DEFAULTS-FUNCTION-LEARNING-002` is a SUCCESSOR baseline, not a cosmetic rewrite of the immutable 104-file lock. Current checking uses selected module constants and is not a general multi-baseline verifier. First decide how independently runnable legacy-baseline verification should work; keep old bytes and approval metadata.",
        "",
        "The 177-entry text fixture uses filename::resource-key identity. Renaming a key/path changes that identity even with identical text. Prove a bijective approved mapping and exact text hashes before deliberate fixture migration. Preserve the separate FND-001 access-close resource and all locked shared resources outside that particular fixture.",
        "",
        "All hplus.function bodies, protected shared wording, logical semantics, composed event IDs, pacing roles, body pass counts, gains, 25-second transitions, 10-second fade and preset hashes remain untouched. A neutral identifier does not convert reference-derived material into original-OCF authorship.",
        "",
        "## Complete stable-identifier proposals",
        "",
        "| Current identifier | Proposed identifier — NOT IMPLEMENTED | Risk | Real compatibility strategy |",
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| `{row['old']}` | `{row['proposed']}` | {row['risk']} | {row['compatibility']} |"
        for row in data["mappings"]
    ]
    lines += [
        "",
        "## File/path proposals — not executed",
        "",
        "| Current path | Proposed path | Decision |",
        "| --- | --- | --- |",
    ]
    lines += [
        f"| `{row['old']}` | `{row['proposed']}` | {row['decision']} |"
        for row in data["path_mappings"]
    ]
    lines += [
        "",
        "Optional stage references lacking authored locale definitions remain unresolved, not fabricated. Partial namespace constructors and broader HPLUS prose appear in the occurrence inventory; they are not invented concrete resource definitions. Historical provenance, external attribution and user-supplied references should retain their accurate historical wording.",
        "",
        "## Migration order — only after explicit approval",
        "",
        "1. Approve exact ID/key/path maps, purpose-neutral labels and the successor-baseline strategy; collision-check registered targets.",
        "2. Capture old wording hashes, all-event IDs, composition, pacing, effective F10/F11 policy and locked dependency hashes.",
        "3. Introduce reviewed successor leaf resources/stages without changing speech, provenance or event IDs; update parent/child references and executable composition discriminators together.",
        "4. Update function binding default and allowed-template lists plus narration plan/resource references. Keep real custom/pilot alternatives.",
        "5. Explicitly migrate recorded manifests' event/resource/unit targets and optional session fingerprints only after text/event/timing equivalence. All-event stems still require every boundary; never guess or add silence.",
        "6. Create a deliberate NEW lock revision, retain the previous immutable baseline, regenerate plans through the generator, and reject stale full-session resume receipts.",
        "7. Update CLI, MCP, LSP/editor completion/navigation and examples together. New LSP protocol identifiers should be OCF-native and read current canonical IDs until migration is approved; no HPLUS-specific protocol IDs are proposed.",
        "8. Keep unchanged low-level speech/recording caches where their actual byte/config keys still match. Do not delete auditions or relabel old receipts as new verification.",
        "",
        "## Compatibility decisions",
        "",
        "Real compatibility is needed for known recorded-resource mappings, complete-stem fingerprints, immutable defaults, exported configuration and measured session receipts. Prefer an explicit, versioned, read-only migration preview and user-reviewed rewrite for these artifacts. Temporary lookup aliases are justified only for demonstrated external consumers and need a defined lifetime; do not implement blanket permanent aliases for hypothetical users. Historical evidence files are retained, not redirected or renamed as active implementation.",
        "",
        "## Required tests",
        "",
        "- Bijective old/new resource path/key mapping preserving every protected text hash, including access-close.",
        "- Composition equivalence after normalizing ONLY approved identity fields; exact event IDs, anchors, semantics, timing, gains and DSP selections remain equal.",
        "- Strict recorded-only coverage, hybrid fallback, unit-index validity, ambiguity rejection, old-target rejection and reviewed remapping with unchanged audio hashes.",
        "- Correct fingerprint changes, invalidation of stale full-session receipts, and legitimate low-level cache reuse.",
        "- New lock dependency completeness; no silent loss from HPLUS-specific file globs. Old baseline remains independently auditable.",
        "- CLI/MCP/LSP parity, source definitions/references, Windows/POSIX paths, examples freshness, locale validation and all 55 source-plan checks.",
        "",
        "## Affected files",
        "",
        "| File | Text occurrences | Classification counts |",
        "| --- | --- | --- |",
    ]
    lines += [
        f"| `{row['path']}` | {row['occurrences']} | {json.dumps(row['categories'])} |"
        for row in data["files"]
    ]
    lines += [
        "",
        "## Complete occurrence inventory",
        "",
        "[Every counted occurrence with file, line, column, token, category and bounded excerpt; all mapping proposals and collision flags](OCF_IDENTIFIER_NEUTRALIZATION_RECOMMENDATIONS.json). No private/untracked reference corpus was read. Metadata-note discrepancies and purpose/wording changes require separate editorial review; a naming migration must not conceal them.",
        "",
    ]
    return "\n".join(lines)


def reports():
    failures = check()
    if failures:
        raise OCFError("protected narration drift: " + " | ".join(failures))
    commands, identifiers = canonical_audit(), identifier_audit()
    return {
        "OCF_COMMAND_NAMING_AUDIT.md": command_markdown(commands),
        "OCF_COMMAND_NAMING_RECOMMENDATIONS.json": json.dumps(
            commands, ensure_ascii=False, indent=2
        )
        + "\n",
        "OCF_IDENTIFIER_NEUTRALIZATION_AUDIT.md": identifier_markdown(identifiers),
        "OCF_IDENTIFIER_NEUTRALIZATION_RECOMMENDATIONS.json": json.dumps(
            identifiers, ensure_ascii=False, indent=2
        )
        + "\n",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="generate audit reports only; never apply recommendations",
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "docs/releases")
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    if not any(
        output.is_relative_to(root.resolve()) for root in (REPO_ROOT / "docs/releases", work_root())
    ):
        raise OCFError("audit output must stay in docs/releases or the local OCF workspace")
    files = reports()
    if args.write:
        for name, text in files.items():
            write_text_atomic(output / name, text)
    fresh = all(
        (output / name).is_file() and (output / name).read_text(encoding="utf-8") == text
        for name, text in files.items()
    )
    print(
        json.dumps(
            {"status": PROPOSAL, "reports": list(files), "fresh": fresh, "implemented": False}
        )
    )
    return 0 if fresh or not args.check else 1


if __name__ == "__main__":
    raise SystemExit(main())
