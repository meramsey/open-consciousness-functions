"""Offline proposals cannot become a second function authority."""

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.integration
SPEC = importlib.util.spec_from_file_location(
    "hplus_review_import_integration",
    Path(__file__).resolve().parents[1] / "scripts/tools/prepare_hplus_function_review.py",
)
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


@pytest.fixture
def importer(tmp_path, monkeypatch):
    sources = tmp_path / "sources"
    sources.mkdir()
    raw = b"Specific opener.\nSpecific body.\nSpecific closer.\n"
    (sources / "fixture.txt").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    function = SimpleNamespace(
        id="OCF-COG-001",
        source_availability="available",
        data={
            "legacy": {"name": "FIXTURE", "commands": ["PLUS-FIXTURE"]},
            "content": {
                "specifications": {
                    "analysis_review": {
                        "source_extent": {
                            "file": "fixture.txt",
                            "source_sha256": digest,
                            "start_line": 1,
                            "end_line": 3,
                        }
                    }
                },
                "evidence": {
                    "sources": [
                        {
                            "path": "fixture.txt",
                            "sha256": digest,
                            "evidence_class": "source_transcript",
                        }
                    ]
                },
            },
        },
    )
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "selections": {
                    function.id: {
                        "slots": {
                            slot: [{"start_line": n, "end_line": n}]
                            for n, slot in enumerate(review.SLOTS, 1)
                        },
                        "missing": {},
                        "notes": [],
                    }
                },
            }
        )
    )
    monkeypatch.setattr(review, "load_all_functions", lambda: [function])
    return SimpleNamespace(
        sources=sources,
        output=tmp_path / "proposals",
        plan=plan,
        function=function,
        target=tmp_path / "proposals/OCF-COG-001.review-proposal.json",
    )


def run(f, write=True, **kwargs):
    return review.prepare(f.sources, f.output, f.plan, write=write, **kwargs)


def test_dry_run_then_idempotent_proposal_never_installs_resources(importer):
    f = importer
    before = json.dumps(f.function.data, sort_keys=True)
    run(f, False)
    assert not f.output.exists()
    run(f)
    original = f.target.read_bytes()
    run(f)
    assert f.target.read_bytes() == original
    data = json.loads(original)
    assert data["authority"] == "none"
    assert data["release_status"] == "pending-human-review"
    assert not {"domain", "locale", "entries", "function_id"} & data.keys()
    assert len(data["candidate_entries"]) == 3
    assert list(f.output.iterdir()) == [f.target]
    assert json.dumps(f.function.data, sort_keys=True) == before


def test_reimport_preserves_human_wording_and_refuses_changed_inputs(importer):
    f = importer
    run(f)
    data = json.loads(f.target.read_text())
    next(iter(data["candidate_entries"].values()))["text"] = "Human edit."
    f.target.write_text(json.dumps(data))
    before = f.target.read_bytes()
    with pytest.raises(ValueError, match="human edits"):
        run(f)
    assert f.target.read_bytes() == before


def test_hash_mismatch_fails_before_any_output_is_written(importer):
    (importer.sources / "fixture.txt").write_text("Changed source.")
    with pytest.raises(OCFError, match="checksum mismatch"):
        run(importer)
    assert not importer.output.exists()


@pytest.mark.parametrize("root", ["locales/en-US", "function-content", "brand", "audio/scripts"])
def test_runtime_output_rejected_before_reading_sources(importer, root):
    importer.output = review.REPO_ROOT / root
    with pytest.raises(OCFError, match="packaged runtime"):
        run(importer)


def test_output_symlink_into_runtime_rejected(importer):
    importer.output.symlink_to(review.REPO_ROOT / "locales/en-US", target_is_directory=True)
    with pytest.raises(OCFError, match="packaged runtime"):
        run(importer)


def test_source_and_output_must_not_overlap(importer):
    importer.output = importer.sources / "proposals"
    with pytest.raises(ValueError, match="immutable source"):
        run(importer)


@pytest.mark.parametrize("path", ["../outside.txt", "/outside.txt"])
def test_source_escape_rejected_before_output(importer, path):
    importer.function.data["content"]["specifications"]["analysis_review"]["source_extent"][
        "file"
    ] = path
    with pytest.raises(OCFError, match="escapes its root"):
        run(importer)
    assert not importer.output.exists()


@pytest.fixture
def proposal_importer(importer):
    f = importer
    f.function.source_availability = "unavailable"
    f.function.data["content"] = {}
    f.plan.write_text(yaml.safe_dump({"schema_version": "1.0", "selections": {}}))
    raw = (
        "FIXTURE (test) — RECONSTRUCTED SCRIPT\nPLUS-FIXTURE\nCLEAN RECORDING SCRIPT\n"
        "Proposed opener.\nProposed body.\nProposed closer.\nEND OF RECONSTRUCTED SCRIPT\n"
    ).encode()
    (f.sources / "proposal.txt").write_bytes(raw)
    f.proposal_plan = f.sources / "proposals.yaml"
    f.proposal_plan.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "selections": {},
                "proposals": {
                    f.function.id: {
                        "input": {
                            "file": "proposal.txt",
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "header": raw.decode().splitlines()[0],
                        },
                        "selection": {
                            "slots": {
                                slot: [{"start_line": n, "end_line": n}]
                                for n, slot in enumerate(review.SLOTS, 4)
                            },
                            "missing": {},
                            "notes": [],
                        },
                    }
                },
            }
        )
    )
    return f


def test_proposals_remain_unavailable_and_pending_without_promoting_wording(proposal_importer):
    f = proposal_importer
    run(f, False, proposal_plan=f.proposal_plan)
    assert not f.output.exists()
    run(f, proposal_plan=f.proposal_plan)
    data = json.loads(f.target.read_text())
    assert data["source_status"] == "unavailable"
    assert data["release_status"] == "pending-human-review"
    assert all(entry["status"] == "draft" for entry in data["candidate_entries"].values())
    before = f.target.read_bytes()
    run(f, proposal_plan=f.proposal_plan)
    assert f.target.read_bytes() == before
    assert f.function.source_availability == "unavailable"


def test_proposal_hash_failure_preserves_existing_draft(proposal_importer):
    f = proposal_importer
    run(f, proposal_plan=f.proposal_plan)
    before = f.target.read_bytes()
    (f.sources / "proposal.txt").write_text("Changed proposal.")
    with pytest.raises(ValueError, match="proposal hash changed"):
        run(f, proposal_plan=f.proposal_plan)
    assert f.target.read_bytes() == before


def test_batch_preflights_every_destination_before_writing(importer, monkeypatch):
    from copy import deepcopy

    f = importer
    second = deepcopy(f.function)
    second.id = "OCF-COG-002"
    plan = yaml.safe_load(f.plan.read_text())
    plan["selections"][second.id] = deepcopy(plan["selections"][f.function.id])
    f.plan.write_text(yaml.safe_dump(plan))
    f.output.mkdir()
    edited = f.output / "OCF-COG-002.review-proposal.json"
    edited.write_text('{"human": "edit"}')
    monkeypatch.setattr(review, "load_all_functions", lambda: [f.function, second])
    with pytest.raises(ValueError, match="human edits"):
        run(f)
    assert not f.target.exists()
    assert edited.read_text() == '{"human": "edit"}'
