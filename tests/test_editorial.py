"""Synthetic source-first authoring contracts; no native engines or corpus input."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import wave
from types import SimpleNamespace

import pytest
import yaml
from ocf_tools import editorial
from ocf_tools.cli import main
from ocf_tools.transcript import apply_render_timing, export_lrc, export_srt
from ocf_tools.utils import OCFError
from ocf_tools.voice import render_narration
from tools.build_package_data import stage_data

SOURCE = (
    "Prépare yourself — café.\r\n"
    "Your nonphysical spirit will certainly heal everything.\r\n"
    "Visualize a bright violet sphere.\r\n"
    "Return gently; fin.\r\n"
)
FLAGS = ["metaphysical", "assertive", "visual"]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def test_human_insertion_has_no_invented_source_range(authoring):
    f = authoring()
    editorial.insert(
        f.workspace,
        f.id,
        "b900",
        "b002",
        "function.command.rehearsal",
        "A new human-authored trial.",
        "Human editor",
    )
    rows = editorial.diff(f.workspace, f.id)["blocks"]
    inserted = next(row for row in rows if row["id"] == "b900")
    assert inserted["category"] == "inserted-ocf-only"
    assert inserted["source_text"] == ""
    assert inserted["start_line"] == inserted["end_line"] == 0
    assert inserted["working_text"] == "A new human-authored trial."
    assert "A new human-authored trial." in str(editorial.preview(f.workspace, f.id))
    with pytest.raises(OCFError, match="release blocked"):
        editorial.preview(f.workspace, f.id, release=True)
    with pytest.raises(OCFError, match="unique block"):
        editorial.insert(
            f.workspace, f.id, "b900", "b002", "function.command.rehearsal", "x", "Human"
        )


def test_diff_filters_and_immutable_semantic_identity(authoring):
    f = authoring()
    assert not editorial.diff(f.workspace, f.id, "changed")["blocks"]
    specific = editorial.diff(f.workspace, f.id, "function-specific")["blocks"]
    assert specific and all(not row["reusable"] for row in specific)
    occurrence, block = block_at(f)
    block["semantic"] = "different.english-label"
    store_block(f, block)
    with pytest.raises(OCFError, match="semantic identity changed"):
        editorial.load_function(f.workspace, f.id)


def write_yaml(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


@pytest.fixture
def authoring(tmp_path, monkeypatch):
    """Build fake review/evidence sidecars around complete UTF-8 source bytes."""
    monkeypatch.setattr(editorial, "current_date", lambda: "2026-01-02")
    source_root = tmp_path / "immutable"
    source_root.mkdir()
    content_root = tmp_path / "content"
    workspace = tmp_path / ".ocf-authoring"

    def make(
        function_id="OCF-TST-001",
        text=SOURCE,
        *,
        availability="available",
        evidence_class="source_transcript",
        skeletonize=True,
    ):
        raw = text.encode("utf-8")
        filename = f"{function_id}.txt"
        (source_root / filename).write_bytes(raw)
        count = len(text.splitlines(keepends=True))
        review = {
            "source_extent": {
                "file": filename,
                "source_sha256": sha(raw),
                "start_line": 1,
                "end_line": count,
            },
            "claim_categories": FLAGS.copy(),
            "sections": {
                "preparation": {
                    "status": "supported",
                    "locators": [{"file": filename, "start_line": 1, "end_line": 1}],
                },
                "main": {
                    "status": "supported",
                    "locators": [{"file": filename, "start_line": 2, "end_line": count - 1}],
                },
                "handoff": {
                    "status": "supported",
                    "locators": [{"file": filename, "start_line": count, "end_line": count}],
                },
                "association": {"status": "not-present"},
                "consolidation": {"status": "not-applicable"},
            },
        }
        evidence = {
            "sources": [{"path": filename, "sha256": sha(raw), "evidence_class": evidence_class}]
        }
        record = SimpleNamespace(id=function_id, source_availability=availability)
        write_yaml(
            content_root / "specifications" / f"{function_id}.yaml", {"analysis_review": review}
        )
        write_yaml(content_root / "evidence" / f"{function_id}.yaml", evidence)
        fixture = SimpleNamespace(
            id=function_id,
            record=record,
            raw=raw,
            review=review,
            evidence=evidence,
            source_root=source_root,
            content_root=content_root,
            workspace=workspace,
        )
        if skeletonize:
            editorial.skeletonize(source_root, workspace, [record], content_root)
        return fixture

    return make


def block_at(fixture, index=0):
    occurrence = editorial.load_function(fixture.workspace, fixture.id)["blocks"][index]
    return occurrence, editorial.load_block(fixture.workspace, occurrence["ref"])


def store_block(fixture, block):
    write_yaml(fixture.workspace / "blocks" / f"{block['id']}.yaml", block)


def review_block(fixture, index=0, status="reviewed_unchanged"):
    occurrence, _ = block_at(fixture, index)
    editorial.mark_review(
        fixture.workspace, fixture.id, occurrence["id"], status, "Synthetic editor"
    )


def approve_block(fixture, index=0, **kwargs):
    occurrence, _ = block_at(fixture, index)
    options = {"rights": "user_cleared", "rights_evidence": "Synthetic rights attestation"}
    options.update(kwargs)
    editorial.mark_review(
        fixture.workspace, fixture.id, occurrence["id"], "approved", "Synthetic approver", **options
    )


def test_exact_utf8_crlf_source_working_snapshot_and_flags(authoring):
    f = authoring()
    doc = editorial.load_function(f.workspace, f.id)
    assert doc["source"] == {
        "file": f"{f.id}.txt",
        "sha256": sha(f.raw),
        "evidence_class": "source_transcript",
        "line_count": 4,
    }
    assert doc["source_status"] == "transcript_unverified"
    assert doc["skeletonization_status"] == "candidate"
    assert [(b["start_line"], b["end_line"]) for b in doc["blocks"]] == [(1, 1), (2, 3), (4, 4)]
    source, working = [], []
    for occurrence in doc["blocks"]:
        block = editorial.load_block(f.workspace, occurrence["ref"])
        source.append(block["source"]["text"])
        working.append(block["working"]["text"])
        assert block["source"]["text_sha256"] == sha(source[-1].encode("utf-8"))
        assert block["working"]["review_status"] == "inherited"
        assert block["working"]["flags"] == [
            "source-authentication-unverified",
            "candidate-section-boundary",
            "accessibility-review-required",
            *FLAGS,
        ]
        assert block["release"]["status"] == "pending"
    assert "".join(source).encode("utf-8") == f.raw
    assert "".join(working).encode("utf-8") == f.raw
    snapshot = yaml.safe_load((f.workspace / "sources" / f"{sha(f.raw)}.yaml").read_text())
    assert snapshot == {"text": SOURCE, "sha256": sha(f.raw)}
    assert (f.source_root / f"{f.id}.txt").read_bytes() == f.raw
    assert all(
        row["category"] == "unchanged" for row in editorial.diff(f.workspace, f.id)["blocks"]
    )
    assert doc["sections"]["association"] == "absent"
    assert doc["sections"]["consolidation"] == "not_applicable"
    assert doc["sections"]["purpose"] == "unknown"


@pytest.mark.parametrize("tamper", ["block", "block-and-hash", "snapshot", "semantic", "range"])
def test_immutable_source_tampering_rejected(authoring, tamper):
    f = authoring()
    occurrence, block = block_at(f)
    if tamper.startswith("block"):
        block["source"]["text"] += "tampered\r\n"
        if tamper == "block-and-hash":
            block["source"]["text_sha256"] = sha(block["source"]["text"].encode("utf-8"))
        store_block(f, block)
    elif tamper == "snapshot":
        write_yaml(
            f.workspace / "sources" / f"{sha(f.raw)}.yaml",
            {"text": SOURCE.replace("café", "changed"), "sha256": sha(f.raw)},
        )
    elif tamper == "semantic":
        block["semantic"] = "function.instruction"
        store_block(f, block)
    else:
        doc = editorial.load_function(f.workspace, f.id)
        doc["blocks"][0]["start_line"] = 2
        write_yaml(f.workspace / "functions" / f"{f.id}.yaml", doc)
    with pytest.raises(OCFError, match="immutable source|source wording or semantic|contiguous"):
        editorial.load_function(f.workspace, f.id)


@pytest.mark.parametrize(
    "text,corrections,category",
    [
        ("Human edit — retain meaning.\r\n", [], "modified"),
        ("", [], "removed"),
        (
            "Corrected transcript.\r\n",
            [
                {
                    "original": "Prépare",
                    "proposed": "Prepare",
                    "status": "applied",
                    "reason": "Synthetic correction",
                }
            ],
            "transcript-correction-and-edits",
        ),
    ],
)
def test_human_working_edits_diff_without_rewriting_source(authoring, text, corrections, category):
    f = authoring()
    _, block = block_at(f)
    original = copy.deepcopy(block["source"])
    block["working"].update(text=text, corrections=corrections)
    store_block(f, block)
    row = editorial.diff(f.workspace, f.id)["blocks"][0]
    assert row["category"] == category
    assert row["working_text"] == text
    assert row["source_text"] == original["text"]
    assert "--- SOURCE" in row["unified_diff"] and "+++ WORKING" in row["unified_diff"]
    assert row["flags"] == block["working"]["flags"]
    assert editorial.load_block(f.workspace, block["id"])["source"] == original
    review_block(f, status="reviewed_modified")
    assert block_at(f)[1]["working"]["review_sha256"] == sha(text.encode("utf-8"))


def test_reviewed_unchanged_is_distinct_from_inherited_and_approval(authoring):
    f = authoring()
    assert block_at(f)[1]["working"]["review_status"] == "inherited"
    review_block(f)
    block = block_at(f)[1]
    assert block["working"]["text"] == block["source"]["text"]
    assert block["working"]["review_status"] == "reviewed_unchanged"
    assert block["working"]["reviewer"] == "Synthetic editor"
    assert block["working"]["history"] == [
        {
            "action": "review",
            "status": "reviewed_unchanged",
            "reviewer": "Synthetic editor",
            "date": "2026-01-02",
            "text_sha256": block["source"]["text_sha256"],
        }
    ]
    assert block["release"]["status"] == "pending"
    with pytest.raises(OCFError, match="release blocked"):
        editorial.working_text(f.workspace, block, release=True)


@pytest.mark.parametrize(
    "changed,status", [(False, "reviewed_modified"), (True, "reviewed_unchanged")]
)
def test_review_status_must_match_text_comparison(authoring, changed, status):
    f = authoring()
    if changed:
        _, block = block_at(f)
        block["working"]["text"] += "Human addition."
        store_block(f, block)
    with pytest.raises(OCFError, match="contradicts"):
        review_block(f, status=status)


@pytest.mark.parametrize(
    "reviewed,evidence", [(False, "Synthetic evidence"), (True, None), (True, " ")]
)
def test_approval_requires_current_review_and_nonempty_rights_evidence(
    authoring, reviewed, evidence
):
    f = authoring()
    if reviewed:
        review_block(f)
    before = (f.workspace / "blocks" / f"{block_at(f)[1]['id']}.yaml").read_bytes()
    with pytest.raises(OCFError, match="current human text review and explicit rights evidence"):
        approve_block(f, rights_evidence=evidence)
    assert (f.workspace / "blocks" / f"{block_at(f)[1]['id']}.yaml").read_bytes() == before


@pytest.mark.parametrize("rights", ["unknown", "restricted", "review_required"])
def test_uncleared_rights_reject_approval_and_release(authoring, rights):
    f = authoring()
    review_block(f)
    with pytest.raises(OCFError, match="explicit rights evidence"):
        approve_block(f, rights=rights)
    approve_block(f)
    _, block = block_at(f)
    block["release"]["rights"] = rights
    store_block(f, block)
    with pytest.raises(OCFError, match="release blocked"):
        editorial.working_text(f.workspace, block, release=True)
    assert editorial.working_text(f.workspace, block) == block["source"]["text"]


def test_current_approval_release_preview_and_stale_edits(authoring):
    f = authoring()
    for index in range(3):
        review_block(f, index)
        approve_block(f, index)
    release = editorial.preview(f.workspace, f.id, release=True)
    assert "".join(e["text"] for e in release["timeline"]) == SOURCE
    assert "Explicitly approved release" in release["source"]["notes"]
    _, block = block_at(f)
    assert block["release"]["text_sha256"] == block["working"]["review_sha256"]
    block["working"]["text"] += "Fresh human edit."
    store_block(f, block)
    with pytest.raises(OCFError, match="missing/stale"):
        editorial.preview(f.workspace, f.id, release=True)
    with pytest.raises(OCFError, match="current human text review"):
        approve_block(f)
    review_block(f, status="reviewed_modified")
    assert block_at(f)[1]["release"]["status"] == "pending"
    approve_block(f)
    assert editorial.preview(f.workspace, f.id, release=True)["timeline"][0]["text"].endswith(
        "Fresh human edit."
    )


def test_pending_transcript_correction_blocks_release_without_rewriting(authoring):
    f = authoring()
    _, block = block_at(f)
    block["working"]["corrections"] = [
        {
            "original": "Prépare",
            "proposed": "Prepare",
            "status": "pending",
            "reason": "Human must decide",
        }
    ]
    store_block(f, block)
    review_block(f)
    with pytest.raises(OCFError, match="pending transcript correction"):
        approve_block(f)
    assert block_at(f)[1]["working"]["text"] == SOURCE.splitlines(keepends=True)[0]
    assert block_at(f)[1]["release"]["status"] == "pending"


def test_template_substitution_preserves_semantic_trace_and_diff(authoring):
    f = authoring()
    template_f = authoring("OCF-TST-002", SOURCE.replace("Prépare yourself", "Settle yourself"))
    occurrence, block = block_at(f)
    _, template = block_at(template_f)
    block["working"]["template_ref"] = template["id"]
    store_block(f, block)
    row = editorial.diff(f.workspace, f.id)["blocks"][0]
    assert row["category"] == "reusable-template-substitution"
    assert row["semantic"] == occurrence["semantic"] == template["semantic"]
    assert row["ref"] == block["id"]
    assert row["source"]["sha256"] == sha(f.raw)
    assert row["source_text"] == block["source"]["text"]
    assert row["working_text"] == template["working"]["text"]
    assert row["substitution_origins"][0]["origins"][0]["function_id"] == template_f.id
    assert row["substitution_origins"][0]["origins"][0]["source"]["sha256"] == sha(template_f.raw)
    assert "-Prépare yourself" in row["unified_diff"]
    assert "+Settle yourself" in row["unified_diff"]
    assert [e["semantic"] for e in editorial.preview(f.workspace, f.id)["timeline"]] == [
        b["semantic"] for b in editorial.load_function(f.workspace, f.id)["blocks"]
    ]
    review_block(f, status="reviewed_modified")
    with pytest.raises(OCFError, match="release blocked"):
        approve_block(f)
    review_block(template_f)
    approve_block(template_f)
    approve_block(f)
    assert (
        editorial.working_text(f.workspace, block_at(f)[1], release=True)
        == template["working"]["text"]
    )
    _, template = block_at(template_f)
    template["working"]["text"] += "Changed shared template."
    store_block(template_f, template)
    with pytest.raises(OCFError, match="missing/stale"):
        editorial.working_text(f.workspace, block_at(f)[1], release=True)


@pytest.mark.parametrize("problem", ["cycle", "semantic-mismatch"])
def test_template_cycle_and_semantic_mismatch_rejected(authoring, problem):
    f = authoring()
    _, block = block_at(f)
    if problem == "cycle":
        block["working"]["template_ref"] = block["id"]
        match = "circular reusable-template"
    else:
        block["working"]["template_ref"] = block_at(f, 1)[1]["id"]
        match = "cannot redefine semantics"
    store_block(f, block)
    with pytest.raises(OCFError, match=match):
        editorial.diff(f.workspace, f.id)


@pytest.mark.parametrize("raw", [b"", SOURCE.encode("utf-8")])
def test_unavailable_source_rejects_raw_and_has_no_historical_preview(authoring, raw):
    f = authoring(availability="unavailable")
    with pytest.raises(OCFError, match="cannot inherit historical wording"):
        editorial.build_skeleton(f.id, "unavailable", f.review, f.evidence, raw)
    doc = editorial.load_function(f.workspace, f.id)
    assert doc["source"] is None and doc["blocks"] == []
    assert doc["source_status"] == "unavailable"
    assert doc["skeletonization_status"] == "source_unavailable"
    assert not (f.workspace / "sources").exists()
    assert not (f.workspace / "blocks").exists()
    assert editorial.diff(f.workspace, f.id)["blocks"] == []
    with pytest.raises(OCFError, match="no exact historical wording"):
        editorial.preview(f.workspace, f.id)


@pytest.mark.parametrize(
    "kind,change",
    [
        ("block", "unexpected-field"),
        ("block", "invalid-review"),
        ("function", "unexpected-field"),
        ("function", "unavailable-with-source"),
    ],
)
def test_editorial_schemas_reject_invalid_contract_data(authoring, kind, change):
    f = authoring()
    data = block_at(f)[1] if kind == "block" else editorial.load_function(f.workspace, f.id)
    if change == "unexpected-field":
        data["timing"] = {"at": 10}
    elif change == "invalid-review":
        data["working"]["review_status"] = "automatically_approved"
    else:
        data["source_availability"] = "unavailable"
    with pytest.raises(OCFError, match="editorial schema"):
        editorial.validate(data, kind)


def test_partial_transcript_is_uncertain_without_changing_text(authoring):
    f = authoring(evidence_class="partial_source_transcript")
    assert editorial.load_function(f.workspace, f.id)["source_status"] == "partial_transcript"
    assert block_at(f)[1]["working"]["review_status"] == "transcript_uncertain"
    assert editorial.dashboard(f.workspace, "uncertain")["totals"]["uncertain"] == 3
    assert "".join(e["text"] for e in editorial.preview(f.workspace, f.id)["timeline"]) == SOURCE


@pytest.mark.parametrize(
    "function_id,candidates",
    [
        (
            "OCF-FND-002",
            ["audio/scripts/attention-ocf.yaml", "docs/drafts/attention-wording-review.md"],
        ),
        (
            "OCF-FND-004",
            [
                "audio/templates/sessions/OCF-TPL-SESSION-PILOT-RELAX-001.yaml",
                "locales/en-US/functions.yaml",
            ],
        ),
        (
            "OCF-SEN-001",
            [
                "audio/templates/sessions/OCF-TPL-SESSION-PILOT-HEARING-001.yaml",
                "locales/en-US/functions.yaml",
            ],
        ),
        (
            "OCF-SLP-005",
            [
                "audio/templates/sessions/OCF-TPL-SESSION-PILOT-SLEEP-EASY-001.yaml",
                "locales/en-US/functions.yaml",
            ],
        ),
    ],
)
def test_previous_candidates_retained_for_comparison(authoring, function_id, candidates):
    f = authoring(function_id)
    assert editorial.load_function(f.workspace, f.id)["previous_candidates"] == candidates
    assert editorial.diff(f.workspace, f.id)["previous_candidates"] == candidates
    assert not (f.workspace / "audio").exists()


@pytest.mark.parametrize(
    "problem,match",
    [
        ("hash", "checksum mismatch"),
        ("extent", "complete available transcript"),
        ("locator", "outside source extent"),
        ("mockup", "transcript, not a mockup"),
        ("utf8", "must be UTF-8"),
    ],
)
def test_bad_source_identity_extent_and_evidence_rejected(authoring, problem, match):
    f = authoring(skeletonize=False)
    raw = f.raw
    if problem == "hash":
        raw += b"changed"
    elif problem == "extent":
        f.review["source_extent"]["end_line"] = 3
    elif problem == "locator":
        f.review["sections"]["main"]["locators"][0]["end_line"] = 5
    elif problem == "mockup":
        f.evidence["sources"][0]["evidence_class"] = "mockup"
    else:
        raw = b"\xff\r\n"
        f.review["source_extent"]["source_sha256"] = sha(raw)
        f.evidence["sources"][0]["sha256"] = sha(raw)
    with pytest.raises(OCFError, match=match):
        editorial.build_skeleton(f.id, "available", f.review, f.evidence, raw)


@pytest.mark.parametrize("escape", ["relative", "absolute", "symlink"])
def test_source_path_escape_fails_before_workspace_writes(authoring, tmp_path, escape):
    f = authoring(skeletonize=False)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(f.raw)
    if escape == "relative":
        path = "../outside.txt"
    elif escape == "absolute":
        path = str(outside)
    else:
        (f.source_root / "linked.txt").symlink_to(outside)
        path = "linked.txt"
    f.review["source_extent"]["file"] = path
    write_yaml(f.content_root / "specifications" / f"{f.id}.yaml", {"analysis_review": f.review})
    with pytest.raises(OCFError, match="path escapes its root"):
        editorial.skeletonize(f.source_root, f.workspace, [f.record], f.content_root)
    assert not f.workspace.exists()


def test_workspace_inside_immutable_source_root_rejected(authoring):
    f = authoring(skeletonize=False)
    with pytest.raises(OCFError, match="outside immutable source root"):
        editorial.skeletonize(f.source_root, f.source_root / "working", [f.record], f.content_root)
    assert not (f.source_root / "working").exists()


@pytest.mark.parametrize("customization", ["reviewed", "edited"])
def test_regeneration_idempotent_but_customized_blocks_never_overwritten(authoring, customization):
    f = authoring()
    before = {p.relative_to(f.workspace): p.read_bytes() for p in f.workspace.rglob("*.yaml")}
    assert editorial.skeletonize(f.source_root, f.workspace, [f.record], f.content_root) == [f.id]
    assert {
        p.relative_to(f.workspace): p.read_bytes() for p in f.workspace.rglob("*.yaml")
    } == before
    if customization == "reviewed":
        review_block(f)
    else:
        _, block = block_at(f)
        block["working"]["text"] += "Human customization."
        store_block(f, block)
    customized = {p.relative_to(f.workspace): p.read_bytes() for p in f.workspace.rglob("*.yaml")}
    with pytest.raises(OCFError, match="refusing to overwrite customized"):
        editorial.skeletonize(f.source_root, f.workspace, [f.record], f.content_root)
    assert {
        p.relative_to(f.workspace): p.read_bytes() for p in f.workspace.rglob("*.yaml")
    } == customized


@pytest.mark.parametrize("failure", ["changed-source", "customized-existing"])
def test_whole_batch_preflight_leaves_no_partial_writes(authoring, failure):
    first = authoring(skeletonize=False)
    second = authoring("OCF-TST-002", skeletonize=failure == "customized-existing")
    if failure == "changed-source":
        (second.source_root / f"{second.id}.txt").write_bytes(second.raw + b"changed")
        before = {}
        match = "checksum mismatch"
    else:
        review_block(second)
        before = {
            p.relative_to(first.workspace): p.read_bytes() for p in first.workspace.rglob("*.yaml")
        }
        match = "refusing to overwrite customized"
    with pytest.raises(OCFError, match=match):
        editorial.skeletonize(
            first.source_root, first.workspace, [first.record, second.record], first.content_root
        )
    assert {
        p.relative_to(first.workspace): p.read_bytes() for p in first.workspace.rglob("*.yaml")
    } == before
    assert not (first.workspace / "functions" / f"{first.id}.yaml").exists()


@pytest.mark.integration
def test_preview_measures_speech_end_and_exports_original_semantics(authoring, tmp_path):
    f = authoring()
    doc = editorial.preview(f.workspace, f.id)
    original = copy.deepcopy(doc)
    assert doc["timeline"][0]["at"] == 0
    assert [e.get("after") for e in doc["timeline"]] == [None, "b001", "b002"]
    assert all(e["timing"] == {"anchor": "speech-end"} for e in doc["timeline"][1:])
    texts = [e["text"].strip() for e in doc["timeline"]]
    durations = dict(zip(texts, [0.5, 1.25, 0.75]))
    seen = []

    def render_cue(text):
        seen.append(text)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(8000)
            writer.writeframes(b"\x01\x00" * int(durations[text] * 8000))
        return buffer.getvalue()

    meta = render_narration(
        doc,
        tmp_path / "preview.wav",
        backend={"backend": "espeak-ng"},
        sample_rate=8000,
        render_cue=render_cue,
    )
    assert seen == texts
    assert [c["at"] for c in meta["cue_stats"]] == [0, 0.5, 1.75]
    assert [c["duration"] for c in meta["cue_stats"]] == [0.5, 1.25, 0.75]
    assert [e["id"] for e in meta["event_timing"]] == ["b001", "b002", "b003"]
    assert [e["end"] for e in meta["event_timing"]] == [0.5, 1.75, 2.5]
    view = apply_render_timing(doc, {"narration_timing": {"cues": meta["cue_stats"]}})
    assert doc == original
    assert [e["semantic"] for e in view["timeline"]] == [e["semantic"] for e in doc["timeline"]]
    assert view["source"] == doc["source"]
    srt, lrc = export_srt(view), export_lrc(view)
    assert "00:00:00,500 --> 00:00:01,750" in srt
    assert "00:00:01,750 --> 00:00:02,500" in srt
    assert "[00:00.50]" in lrc and "[00:01.75]" in lrc
    for text in [
        "Prépare yourself — café.",
        "Your nonphysical spirit will certainly heal everything.",
        "Visualize a bright violet sphere.",
        "Return gently; fin.",
    ]:
        assert text in srt and text in lrc
    assert all("dsp" not in e and "auditory_cue" not in e for e in doc["timeline"])
    assert "Hz" not in srt and "Hz" not in lrc


def test_bulk_dashboard_and_variants_exact_groups_informational_only(authoring):
    fixtures = [
        authoring(),
        authoring("OCF-TST-002"),
        authoring("OCF-TST-003", SOURCE.replace("café", "cafe")),
        authoring(
            "OCF-TST-004",
            SOURCE.replace(
                "Prépare yourself — café.", "A completely different opening instruction."
            ),
        ),
    ]
    f = fixtures[0]
    review_block(f)
    approve_block(f)
    _, block = block_at(f, 1)
    block["working"]["text"] += "Human edit."
    store_block(f, block)
    dashboard = editorial.dashboard(f.workspace)
    assert [r["function_id"] for r in dashboard["functions"]] == [v.id for v in fixtures]
    assert dashboard["totals"] == {
        "blocks": 12,
        "changed": 1,
        "unchanged": 11,
        "uncertain": 0,
        "reusable": 8,
        "function-specific": 4,
        "reviewed": 2,
        "unreviewed": 10,
        "template_substitutions": 0,
        "flagged": 12,
        "release_approved": 2,
        "release_pending": 10,
        "rights_user_cleared": 2,
        "rights_unknown": 10,
        "rights_review_required": 0,
        "rights_restricted": 0,
        "rights_verified_redistributable": 0,
    }
    assert [r["function_id"] for r in editorial.dashboard(f.workspace, "changed")["functions"]] == [
        "OCF-TST-001"
    ]
    assert editorial.dashboard(f.workspace, "uncertain")["functions"] == []
    before = {p.relative_to(f.workspace): p.read_bytes() for p in f.workspace.rglob("*.yaml")}
    families = {v["semantic"]: v for v in editorial.variants(f.workspace)["families"]}
    assert set(families) == {"preparation.orientation.begin", "session.return.begin"}
    preparation = families["preparation.orientation.begin"]
    groups = preparation["exact_text_groups"]
    assert [g["comparison"] for g in groups] == ["exact", "minor-candidate", "material-candidate"]
    assert [[o["function_id"] for o in g["occurrences"]] for g in groups] == [
        ["OCF-TST-001", "OCF-TST-002"],
        ["OCF-TST-003"],
        ["OCF-TST-004"],
    ]
    for group in groups:
        for occurrence in group["occurrences"]:
            source_f = next(v for v in fixtures if v.id == occurrence["function_id"])
            assert occurrence["source"]["sha256"] == sha(source_f.raw)
            assert (occurrence["start_line"], occurrence["end_line"]) == (1, 1)
    assert groups[0]["similarity_informational_only"] == 1.0
    assert groups[0]["diff"] == ""
    assert 0.9 <= groups[1]["similarity_informational_only"] < 1
    assert groups[2]["similarity_informational_only"] < 0.9
    assert "no preferred variant selected" in preparation["review"]
    assert len(families["session.return.begin"]["exact_text_groups"]) == 1
    assert {
        p.relative_to(f.workspace): p.read_bytes() for p in f.workspace.rglob("*.yaml")
    } == before


@pytest.mark.integration
def test_synthetic_cli_skeletonize_and_json_diff(authoring, monkeypatch, capsys):
    from ocf_tools import content, indexes

    f = authoring(skeletonize=False)
    monkeypatch.setattr(content, "CONTENT_DIR", f.content_root)
    monkeypatch.setattr(indexes, "load_all_functions", lambda: [f.record])
    assert (
        main(
            [
                "content",
                "skeletonize",
                "--source-root",
                str(f.source_root),
                "--workspace",
                str(f.workspace),
                "--function",
                f.id,
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {"skeletonized": [f.id]}
    assert main(["content", "diff", f.id, "--workspace", str(f.workspace), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert "".join(b["working_text"] for b in result["blocks"]).encode("utf-8") == f.raw
    assert all(b["review_status"] == "inherited" for b in result["blocks"])


@pytest.mark.parametrize("contaminated", [False, True])
def test_package_staging_excludes_exact_authoring_source_even_from_existing_target(
    tmp_path, contaminated
):
    root, target = tmp_path / "checkout", tmp_path / "staged"
    write_yaml(root / "functions" / "OCF-TST-001.yaml", {"id": "OCF-TST-001"})
    write_yaml(root / ".ocf-authoring" / "sources" / "exact.yaml", {"text": SOURCE})
    write_yaml(root / ".ocf-authoring" / "blocks" / "working.yaml", {"working": {"text": SOURCE}})
    if contaminated:
        write_yaml(target / ".ocf-authoring" / "sources" / "exact.yaml", {"text": SOURCE})
        write_yaml(
            target / ".ocf-authoring" / "blocks" / "working.yaml", {"working": {"text": SOURCE}}
        )
    report = stage_data(root, target)
    assert (target / "functions" / "OCF-TST-001.yaml").is_file()
    assert not (target / ".ocf-authoring").exists()
    assert all(".ocf-authoring" not in path for path in report["included"])
    assert all(
        SOURCE.encode("utf-8") not in p.read_bytes() for p in target.rglob("*") if p.is_file()
    )
    assert (
        yaml.safe_load((root / ".ocf-authoring" / "sources" / "exact.yaml").read_text())["text"]
        == SOURCE
    )


def test_staging_removes_previously_eligible_citation_only_files(tmp_path):
    root, target = tmp_path / "root", tmp_path / "staged"
    template = root / "audio/templates/sessions/session.yaml"
    write_yaml(template, {"origin": "original-ocf"})
    stage_data(root, target)
    assert (target / "audio/templates/sessions/session.yaml").exists()
    write_yaml(template, {"origin": "reference-derived"})
    stale = target / "function-content/bindings/OCF-FND-002.yaml"
    write_yaml(stale, {"private": "citation-only"})
    stage_data(root, target)
    assert not stale.exists()
    assert not (target / "audio/templates/sessions/session.yaml").exists()


def test_staging_does_not_follow_private_source_symlink(tmp_path):
    root, target = tmp_path / "root", tmp_path / "staged"
    private = root / ".ocf-authoring/source.yaml"
    write_yaml(private, {"text": "Private source wording"})
    linked = root / "functions/private.yaml"
    linked.parent.mkdir()
    try:
        linked.symlink_to(private)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")
    report = stage_data(root, target)
    assert "functions/private.yaml" not in report["included"]
    assert not (target / "functions/private.yaml").exists()


def test_shared_template_source_cannot_be_tampered_through_consumer(authoring):
    f = authoring()
    t = authoring("OCF-TST-002", SOURCE.replace("Prépare yourself", "Settle yourself"))
    _, consumer = block_at(f)
    _, template = block_at(t)
    consumer["working"]["template_ref"] = template["id"]
    store_block(f, consumer)
    template["source"]["text"] = "Changed supposedly immutable source"
    template["source"]["text_sha256"] = editorial.fingerprint(template["source"]["text"])
    store_block(t, template)
    with pytest.raises(OCFError, match="source wording"):
        editorial.diff(f.workspace, f.id)


def test_stale_review_appears_in_unreviewed_filter(authoring):
    f = authoring()
    review_block(f)
    assert "b001" not in [
        b["id"] for b in editorial.diff(f.workspace, f.id, "unreviewed")["blocks"]
    ]
    _, block = block_at(f)
    block["working"]["text"] += "Human edit after review"
    store_block(f, block)
    assert "b001" in [b["id"] for b in editorial.diff(f.workspace, f.id, "unreviewed")["blocks"]]


def test_inserted_semantics_cannot_change_after_text_review(authoring):
    f = authoring()
    editorial.insert(
        f.workspace, f.id, "b900", "b002", "function.command.rehearsal", "New wording", "Human"
    )
    doc = editorial.load_function(f.workspace, f.id)
    occurrence = next(b for b in doc["blocks"] if b["id"] == "b900")
    chunk = editorial.load_block(f.workspace, occurrence["ref"])
    occurrence["semantic"] = chunk["semantic"] = "function.future-use"
    store_block(f, chunk)
    write_yaml(f.workspace / "functions" / f"{f.id}.yaml", doc)
    with pytest.raises(OCFError, match="inserted semantic identity"):
        editorial.load_function(f.workspace, f.id)
