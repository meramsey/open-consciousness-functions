"""Offline review importer integration with synthetic source files."""

import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

pytestmark = pytest.mark.integration
SPEC = importlib.util.spec_from_file_location(
    "hplus_review_import_integration",
    Path(__file__).resolve().parents[1] / "scripts/tools/prepare_hplus_function_review.py",
)
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


@pytest.fixture
def importer(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    (workspace / "functions").mkdir(parents=True)
    sources = tmp_path / "sources"
    sources.mkdir()
    output = tmp_path / "en-US"
    output.mkdir()
    raw = b"Specific opener.\nSpecific body.\nSpecific closer.\n"
    (sources / "fixture.txt").write_bytes(raw)
    record = {
        "function_id": "OCF-COG-001",
        "source_availability": "available",
        "source_status": "transcript_unverified",
        "source": {
            "file": "fixture.txt",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "line_count": 3,
        },
    }
    (workspace / "functions/OCF-COG-001.yaml").write_text(yaml.safe_dump(record))
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "selections": {
                    "OCF-COG-001": {
                        "slots": {
                            slot: [{"start_line": line, "end_line": line}]
                            for line, slot in enumerate(("opener", "function-body", "closer"), 1)
                        },
                        "missing": {},
                        "notes": [],
                    },
                },
            }
        )
    )
    (output / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "locale": "en-US",
                "language_name": "English",
                "direction": "ltr",
                "status": "canonical",
                "semantic_version": "1.3.0",
                "resources": [],
            }
        )
    )
    monkeypatch.setattr(
        review,
        "load_all_functions",
        lambda: [
            SimpleNamespace(id="OCF-COG-001", canonical_name="Synthetic fixture"),
        ],
    )
    return workspace, sources, output, plan, tmp_path / "review.md"


def run(inputs, write):
    workspace, sources, output, plan, report = inputs
    return review.prepare(workspace, sources, output, plan, write=write, report_path=report)


def test_dry_run_and_reimport_preserve_human_wording_and_versions(importer):
    _, _, output, _, report = importer
    target = output / "hplus-OCF-COG-001.yaml"
    before = (output / "manifest.yaml").read_bytes()
    run(importer, False)
    assert not target.exists() and not report.exists()
    assert (output / "manifest.yaml").read_bytes() == before
    run(importer, True)
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    data["entries"]["hplus.function.ocf-cog-001.opener"]["text"] = "Human-edited opener."
    target.write_text(yaml.safe_dump(data))
    edited = target.read_bytes()
    manifest = yaml.safe_load((output / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["semantic_version"] = "2.0.0"
    (output / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    run(importer, True)
    assert target.read_bytes() == edited
    manifest = yaml.safe_load((output / "manifest.yaml").read_text(encoding="utf-8"))
    assert len(manifest["resources"]) == 1 and manifest["semantic_version"] == "2.0.0"


def test_hash_mismatch_fails_before_any_output_is_written(importer):
    _, sources, output, _, report = importer
    (sources / "fixture.txt").write_text("Changed source.")
    before = (output / "manifest.yaml").read_bytes()
    with pytest.raises(ValueError, match="source hash changed"):
        run(importer, True)
    assert not (output / "hplus-OCF-COG-001.yaml").exists() and not report.exists()
    assert (output / "manifest.yaml").read_bytes() == before


def test_manifest_domain_conflict_fails_before_creating_the_resource(importer):
    _, _, output, _, _ = importer
    manifest = yaml.safe_load((output / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["resources"] = [{"file": "hplus-OCF-COG-001.yaml", "domain": "ui"}]
    (output / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    with pytest.raises(ValueError, match="manifest domain mismatch"):
        run(importer, True)
    assert not (output / "hplus-OCF-COG-001.yaml").exists()


@pytest.fixture
def proposal_importer(importer, monkeypatch):
    workspace, sources, output, plan, report = importer
    historical = {
        "function_id": "OCF-COG-001",
        "source_availability": "unavailable",
        "source_status": "unavailable",
        "source": None,
    }
    (workspace / "functions/OCF-COG-001.yaml").write_text(yaml.safe_dump(historical))
    plan.write_text(yaml.safe_dump({"schema_version": "1.0", "selections": {}}))
    raw = (
        "FIXTURE (test) — RECONSTRUCTED SCRIPT\nPLUS-FIXTURE\nCLEAN RECORDING SCRIPT\n"
        "Proposed opener.\nProposed body.\nProposed closer.\nEND OF RECONSTRUCTED SCRIPT\n"
    ).encode()
    (sources / "proposal.txt").write_bytes(raw)
    proposal_plan = sources / "proposals.yaml"
    proposal_plan.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "selections": {},
                "proposals": {
                    "OCF-COG-001": {
                        "input": {
                            "file": "proposal.txt",
                            "header": raw.decode().splitlines()[0],
                            "sha256": hashlib.sha256(raw).hexdigest(),
                        },
                        "selection": {
                            "slots": {
                                slot: [{"start_line": line, "end_line": line}]
                                for line, slot in enumerate(
                                    ("opener", "function-body", "closer"), 4
                                )
                            },
                            "missing": {},
                            "notes": [],
                        },
                    },
                },
            }
        )
    )
    target = output / "hplus-OCF-COG-001.yaml"
    target.write_text(yaml.safe_dump(review.resource_for(historical, None, None)[0]))
    manifest = yaml.safe_load((output / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["resources"] = [{"file": target.name, "domain": "ui"}]
    (output / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    monkeypatch.setattr(
        review,
        "load_all_functions",
        lambda: [
            SimpleNamespace(
                id="OCF-COG-001",
                canonical_name="Synthetic fixture",
                data={"legacy": {"name": "FIXTURE", "commands": ["PLUS-FIXTURE"]}},
            )
        ],
    )
    return importer, proposal_plan


def apply_proposal(inputs, write, apply=True):
    importer, proposal_plan = inputs
    workspace, sources, output, plan, report = importer
    return review.prepare(
        workspace,
        sources,
        output,
        plan,
        write=write,
        report_path=report,
        proposal_plan=proposal_plan,
        apply_proposals=apply,
    )


def test_explicit_proposal_upgrade_changes_only_the_placeholder_and_preserves_later_edits(
    proposal_importer,
):
    importer, _ = proposal_importer
    workspace, _, output, _, _ = importer
    target = output / "hplus-OCF-COG-001.yaml"
    original = target.read_bytes()
    historical_bytes = (workspace / "functions/OCF-COG-001.yaml").read_bytes()
    apply_proposal(proposal_importer, True, apply=False)
    assert target.read_bytes() == original
    apply_proposal(proposal_importer, False)
    assert target.read_bytes() == original
    apply_proposal(proposal_importer, True)
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert data["domain"] == "narration"
    manifest = yaml.safe_load((output / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["resources"][0]["domain"] == "narration"
    assert manifest["semantic_version"] == "1.5.0"
    assert (workspace / "functions/OCF-COG-001.yaml").read_bytes() == historical_bytes
    data["entries"]["hplus.function.ocf-cog-001.opener"]["text"] = (
        "Human edit after proposal import."
    )
    target.write_text(yaml.safe_dump(data))
    edited = target.read_bytes()
    apply_proposal(proposal_importer, True)
    assert target.read_bytes() == edited


def test_proposal_import_does_not_overwrite_a_human_edited_status_file(proposal_importer):
    importer, _ = proposal_importer
    _, _, output, _, _ = importer
    target = output / "hplus-OCF-COG-001.yaml"
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    next(iter(data["entries"].values()))["notes"] = "User's own review note."
    target.write_text(yaml.safe_dump(data))
    before = target.read_bytes()
    manifest = (output / "manifest.yaml").read_bytes()
    with pytest.raises(ValueError, match="human edits"):
        apply_proposal(proposal_importer, True)
    assert target.read_bytes() == before
    assert (output / "manifest.yaml").read_bytes() == manifest
