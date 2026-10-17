"""Evidence-boundary regressions for the independent, proposal-only companion."""

import hashlib
import json
from types import SimpleNamespace

import pytest
from ocf_tools.utils import OCFError
from tools import title_cue_review as review


@pytest.mark.unit
def test_complete_phrase_boundaries_do_not_approve_substrings_or_drop_repetition():
    text = "Historical Plus Options Choices. Plus Imprint Imprint. Plus Options."
    rows = review.mentions(
        text, ["PLUS-OPTIONS", "Plus Options Choices", "PLUS-IMPRINT", "Plus Imprint Imprint", ""]
    )
    short = [row for row in rows if row["phrase"] == "PLUS-OPTIONS"]
    assert [row["nested"] for row in short] == [True, False]
    assert next(row for row in rows if row["phrase"] == "PLUS-IMPRINT")["nested"]
    assert all(text[row["start"] : row["end"]] == row["surface"] for row in rows)
    assert review.mentions("Plus Five Five Five One Five", ["PLUS-55515"]) == []
    assert review.mentions("Plus Breathe Better", ["PLUS-BREATH BETTER"]) == []
    assert review.mentions("Plus Choices Options", ["PLUS-OPTIONS CHOICES"]) == []
    assert review.mentions("notPlus OptionsExtra", ["PLUS-OPTIONS"]) == []


@pytest.mark.unit
def test_yaml_evidence_preserves_original_context_line_and_hash(monkeypatch, tmp_path):
    monkeypatch.setattr(review, "REPO_ROOT", tmp_path)
    path = tmp_path / "narration.yaml"
    path.write_text(
        "entries:\n  sample.function-body:\n    text: |\n      Historical commentary only.\n      Think Plus Options Choices.\n  simple: 'Plus Options'\n",
        encoding="utf-8",
    )
    rows = review.resource_evidence(path, ["Plus Options", "Plus Options Choices"])
    assert rows[0]["line"] == 4
    assert rows[0]["mentions"][0]["line"] == 5
    assert (
        rows[0]["sha256"]
        == hashlib.sha256(b"Historical commentary only.\nThink Plus Options Choices.\n").hexdigest()
    )
    assert rows[1]["mentions"][0]["line"] == 6
    assert "Historical commentary only" in rows[0]["mentions"][0]["excerpt"]
    # Locating the historical mention does not assign an activation/approval role.
    assert "approved" not in rows[0]


@pytest.mark.unit
def test_source_drift_is_rejected_without_rewriting_user_input(monkeypatch, tmp_path):
    monkeypatch.setattr(review, "REPO_ROOT", tmp_path)
    path = tmp_path / "function.yaml"
    path.write_text("human changes\n")
    with pytest.raises(OCFError, match="source differs"):
        review.ensure_source({"function.yaml": "old\n"}, ["function.yaml"])
    assert path.read_text() == "human changes\n"
    assert review.ensure_source({"function.yaml": "human changes\n"}, ["function.yaml"]) == {
        "function.yaml": hashlib.sha256(b"human changes\n").hexdigest()
    }


@pytest.mark.unit
def test_identifier_classification_preserves_locks_and_history():
    result = review.identifier_review(
        {
            "docs/releases/OCF_IDENTIFIER_NEUTRALIZATION_RECOMMENDATIONS.json": json.dumps(
                {
                    "mappings": [
                        {
                            "old": "OCF-AUDIO-DEFAULTS-HPLUS-001",
                            "proposed": "OCF-AUDIO-DEFAULTS-FUNCTION-LEARNING-002",
                        }
                    ]
                }
            ),
            "audio/defaults/lock.json": '"OCF-AUDIO-DEFAULTS-HPLUS-001"',
            "locales/en-US/sample.yaml": "hplus.function.ocf-fnd-001.opener",
            "audio/templates/sample.yaml": "OCF-TPL-SESSION-HPLUS-LOCKED-001",
            "function-content/evidence/sample.yaml": "Human Plus",
            "schemas/example.json": "HPLUS",
            "tests/test_example.py": "human_plus",
        }
    )
    assert {
        key: value
        for key, value in result["counts"].items()
        if key != "historical provenance/attribution"
    } == {
        "immutable imported/versioned material": 1,
        "protected identity": 1,
        "active OCF implementation": 1,
        "technical compatibility reference": 2,
    }
    defaults = next(row for row in result["mappings"] if row["current"].startswith("OCF-AUDIO"))
    assert defaults["proposed_successor"] == "OCF-AUDIO-DEFAULTS-FUNCTION-LEARNING-002"
    assert "Preserve immutable original" in defaults["decision"]


@pytest.mark.unit
def test_suffix_containment_is_not_independent_teaching():
    rows = review.mentions("Plus Quiet Plus Sleep", ["Plus Sleep", "Plus Quiet Plus Sleep"])
    assert next(row for row in rows if row["phrase"] == "Plus Sleep")["nested"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "scalar",
    [
        ">\n      One line.\n      Plus Example.\n",
        '"One line.\\nPlus Example."\n',
        '"One line.\n      Plus Example."\n',
    ],
)
def test_ambiguous_physical_line_mapping_fails_explicitly(monkeypatch, tmp_path, scalar):
    monkeypatch.setattr(review, "REPO_ROOT", tmp_path)
    path = tmp_path / "resource.yaml"
    path.write_text("entries:\n  sample:\n    text: " + scalar)
    with pytest.raises(OCFError, match="physical-line evidence"):
        review.resource_evidence(path, ["Plus Example"])


@pytest.mark.unit
@pytest.mark.parametrize("mutation", ["manifest", "added", "shadow"])
def test_dependency_closure_refuses_manifest_drift_additions_and_shadowing(
    monkeypatch, tmp_path, mutation
):
    monkeypatch.setattr(review, "REPO_ROOT", tmp_path)
    locale = tmp_path / "locales/en-US"
    locale.mkdir(parents=True)
    manifest = locale / "manifest.yaml"
    manifest.write_text("locale: en-US\n")
    templates = tmp_path / "audio/templates"
    templates.mkdir(parents=True)
    template = templates / "OCF-TPL-EXAMPLE.yaml"
    template.write_text("id: OCF-TPL-EXAMPLE\n")
    snapshot = {
        "locales/en-US/manifest.yaml": manifest.read_text(),
        "audio/templates/OCF-TPL-EXAMPLE.yaml": template.read_text(),
    }
    assert review.guard_sources(snapshot)
    if mutation == "manifest":
        manifest.write_text("locale: es\n")
    elif mutation == "added":
        (locale / "new.yaml").write_text("entries: {}\n")
    else:
        (tmp_path / "OCF-TPL-EXAMPLE").write_text("id: shadow\n")
    with pytest.raises(OCFError, match="differs|shadow"):
        review.guard_sources(snapshot)


@pytest.mark.unit
def test_operator_cwd_does_not_supply_composition_inputs(monkeypatch, tmp_path):
    root, elsewhere = tmp_path / "checkout", tmp_path / "elsewhere"
    root.mkdir()
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(review, "REPO_ROOT", root)
    monkeypatch.setattr(review, "source_snapshot", lambda commit: (commit, {}))
    monkeypatch.setattr(review, "guard_sources", lambda snapshot: {})
    monkeypatch.setattr(review, "_build", lambda *a: __import__("pathlib").Path.cwd())
    assert review.build() == root
    assert __import__("pathlib").Path.cwd() == elsewhere


@pytest.mark.unit
def test_missing_history_has_actionable_error_without_network(monkeypatch, capsys):
    import subprocess

    def unavailable(*args):
        raise subprocess.CalledProcessError(128, ["git", "rev-parse"])

    monkeypatch.setattr(review, "git", unavailable)
    assert review.main(["--source-commit", "unavailable", "--check"]) == 1
    assert "pinned source commit unavailable" in capsys.readouterr().err


@pytest.mark.unit
def test_check_mode_is_read_only_and_reports_staleness(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(review, "build", lambda *a: {"source_commit": "test", "counts": {}})
    monkeypatch.setattr(review, "render", lambda data: {"report.json": "{}\n"})
    assert review.main(["--output", str(tmp_path), "--check"]) == 1
    assert list(tmp_path.iterdir()) == []
    assert "stale" in capsys.readouterr().err
    assert review.main(["--output", str(tmp_path)]) == 0
    assert review.main(["--output", str(tmp_path), "--check"]) == 0
    assert (tmp_path / "report.json").read_text() == "{}\n"


@pytest.mark.unit
@pytest.mark.parametrize(
    "mutation", [None, "metadata-conflict", "missing-closer", "new-identity", "separate-control"]
)
def test_source_pinned_review_with_synthetic_catalog(monkeypatch, tmp_path, mutation):
    """An isolated report must retain evidence, targets and nonspoken stem markers."""
    owner = "OCF-FND-006"
    resource = tmp_path / "locales/en-US" / f"hplus-{owner}.yaml"
    resource.parent.mkdir(parents=True)
    text = "entries:\n  fixture.function-body:\n    text: |\n      Select a temporary application. Think Plus Example.\n  fixture.closer:\n    text: |\n      Remember Plus Example.\n"
    if mutation == "missing-closer":
        text = text.replace("Remember Plus Example.", "Remember the procedure.")
    resource.write_text(text)
    control = resource.parent / "control.yaml"
    control.write_text(
        "entries:\n  fixture.access-close:\n    text: |\n      Close the selected access. Think Plus Close Access.\n"
    )
    definition = tmp_path / "function.yaml"
    definition.write_text("canonical:\n  name: Example\n  primary: PLUS-EXAMPLE\n")
    metadata_cue = "PLUS-OTHER" if mutation == "metadata-conflict" else "PLUS-EXAMPLE"
    primary = {
        "id": "primary",
        "function_id": owner,
        "phrase": metadata_cue,
        "designation": "primary",
        "role": "activation",
    }
    rows: list[dict] = [primary]
    if mutation == "separate-control":
        rows.append(
            {
                "id": "control",
                "function_id": owner,
                "phrase": "PLUS-CLOSE ACCESS",
                "designation": "secondary",
                "role": "close",
                "procedure": {"evidence_keys": ["fixture.access-close"]},
            }
        )
    record = SimpleNamespace(
        id=owner,
        path=definition,
        canonical_name="Example",
        canonical_command=metadata_cue,
        purpose_summary="Selected temporary application.",
        documentation={},
        command_review="approved",
        source_availability="unavailable",
        command_records=rows,
        data={
            "legacy": {"name": "Historical Example", "commands": ["PLUS-EXAMPLE"]},
            "aliases": {"names": [], "commands": []},
            "lifecycle": {"persistence": "temporary"},
        },
    )
    old = {
        "function_id": owner,
        "proposed_title": "Example",
        "proposed_command": "PLUS-EXAMPLE",
        "rationale": "Selected application, not learning erasure.",
        "source_references": ["function.yaml", resource.relative_to(tmp_path).as_posix()],
        "function_purpose": {"extracted_intent": "End selected application"},
        "session_usage": {"default_template": "example"},
    }
    snapshot = {
        "function.yaml": definition.read_text(),
        resource.relative_to(tmp_path).as_posix(): text,
        control.relative_to(tmp_path).as_posix(): control.read_text(),
        "docs/releases/OCF_COMMAND_NAMING_RECOMMENDATIONS.json": json.dumps({"functions": [old]}),
    }
    monkeypatch.setattr(review, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(review, "source_snapshot", lambda commit: ("synthetic-source", snapshot))
    monkeypatch.setattr(review, "load_all_functions", lambda: [record])
    monkeypatch.setattr(review, "command_view", lambda record, command: command)
    monkeypatch.setattr(
        review,
        "TEACHING",
        {
            owner if mutation != "new-identity" else "unknown": (
                "Plus Example",
                "Select temporary application; preserve learning.",
            )
        },
    )
    monkeypatch.setattr(review, "PAIR_OVERRIDES", {})
    monkeypatch.setattr(review, "UNRESOLVED", set())
    monkeypatch.setattr(
        review,
        "build_complete_session_plan",
        lambda *a, **k: {
            "template_plan": {
                "timeline": [
                    {"id": "boundary", "at": 0},
                    {"id": "spoken", "at": 1, "narration_key": "fixture.function-body"},
                ]
            }
        },
    )

    def resolve(key, *args, **kwargs):
        assert kwargs["fallback"] is False
        filename = "control.yaml" if key == "fixture.access-close" else resource.name
        return SimpleNamespace(file=filename, text="Fixture narration"), SimpleNamespace(
            origin_locale="en-US"
        )

    monkeypatch.setattr(review, "LocaleCatalog", lambda: SimpleNamespace(resource=resolve))
    if mutation in {"missing-closer", "new-identity"}:
        with pytest.raises(
            OCFError,
            match="missing from body/closer"
            if mutation == "missing-closer"
            else "actual catalog exactly",
        ):
            review.build()
        return
    data = review.build()
    row = data["functions"][0]
    assert row["metadata_teaching_consistent"] is (mutation != "metadata-conflict")
    assert row["technical_impact"]["composed_events"][0] == {
        "event_id": "boundary",
        "narration_key": None,
        "variables": {},
        "stem_marker_required": True,
    }
    assert data["source_commit"] == "synthetic-source"
    assert definition.read_text() == snapshot["function.yaml"]
    if mutation == "separate-control":
        assert data["commands"][1]["teaching_finding"].startswith(
            "complete-phrase-present-in-separately-bound"
        )
        assert not any(
            event["narration_key"] == "fixture.access-close"
            for event in row["technical_impact"]["composed_events"]
        )
    rendered = review.render(data)
    assert "Historical Example" in rendered[review.PREFIX + ".md"]
    assert "synthetic-source" in rendered["OCF_EXACT_TEACHING_REVIEW.md"]


@pytest.mark.integration
def test_companion_covers_catalog_and_never_labels_nested_cue_as_taught():
    with pytest.raises(OCFError, match="differs from pinned source"):
        review.build()
    data = json.loads(
        (review.REPO_ROOT / "docs/releases/OCF_TITLE_CUE_REVIEW.json").read_text(encoding="utf-8")
    )
    _, snapshot = review.source_snapshot(data["source_commit"])
    for name, checksum in data["source_sha256"].items():
        assert hashlib.sha256(snapshot[name].encode()).hexdigest() == checksum
    assert len(data["functions"]) == len(review.TEACHING)
    assert len({row["id"] for row in data["commands"]}) == len(data["commands"])
    by_id = {row["function_id"]: row for row in data["functions"]}
    assert not by_id["OCF-COG-005"]["metadata_teaching_consistent"]
    assert by_id["OCF-COG-005"]["exact_taught_cue"] == "Plus Options Choices"
    assert by_id["OCF-BOD-003"]["classification"] != review.CLASSES[0]
    assert by_id["OCF-BOD-010"]["classification"] == review.CLASSES[3]
    assert by_id["OCF-FND-006"]["recommended_primary_cue"] == "PLUS-RELEASE"
    assert by_id["OCF-COG-003"]["recommended_primary_cue"] == "PLUS-OPEN"
    for row in data["functions"]:
        assert {"function-body", "closer"} <= {e["phase"] for e in row["complete_taught_evidence"]}
        assert row["status"] == review.STATUS
    for command in data["commands"]:
        assert all(not item["nested"] for item in command["evidence"])
    # Generation is deterministic, includes all rows, and does not apply vocabulary.
    outputs = review.render(data)
    assert len(outputs) == 4
    assert json.loads(outputs[review.PREFIX + ".json"])["source_commit"] == review.SOURCE
    assert all(row["function_id"] in outputs[review.PREFIX + ".md"] for row in data["functions"])
    for name, text in outputs.items():
        assert (review.REPO_ROOT / "docs/releases" / name).read_text(encoding="utf-8") == text
