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
        "function_id": "OCF-COG-001", "source_availability": "available",
        "source_status": "transcript_unverified",
        "source": {"file": "fixture.txt", "sha256": hashlib.sha256(raw).hexdigest(), "line_count": 3},
    }
    (workspace / "functions/OCF-COG-001.yaml").write_text(yaml.safe_dump(record))
    plan = tmp_path / "plan.yaml"
    plan.write_text(yaml.safe_dump({"schema_version": "1.0", "selections": {
        "OCF-COG-001": {"slots": {slot: [{"start_line": line, "end_line": line}]
                                  for line, slot in enumerate(("opener", "function-body", "closer"), 1)},
                        "missing": {}, "notes": []},
    }}))
    (output / "manifest.yaml").write_text(yaml.safe_dump({
        "schema_version": "1.0", "locale": "en-US", "language_name": "English",
        "direction": "ltr", "status": "canonical", "semantic_version": "1.3.0", "resources": [],
    }))
    monkeypatch.setattr(review, "load_all_functions", lambda: [
        SimpleNamespace(id="OCF-COG-001", canonical_name="Synthetic fixture"),
    ])
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
    data = yaml.safe_load(target.read_text())
    data["entries"]["hplus.function.ocf-cog-001.opener"]["text"] = "Human-edited opener."
    target.write_text(yaml.safe_dump(data))
    edited = target.read_bytes()
    manifest = yaml.safe_load((output / "manifest.yaml").read_text())
    manifest["semantic_version"] = "2.0.0"
    (output / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    run(importer, True)
    assert target.read_bytes() == edited
    manifest = yaml.safe_load((output / "manifest.yaml").read_text())
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
    manifest = yaml.safe_load((output / "manifest.yaml").read_text())
    manifest["resources"] = [{"file": "hplus-OCF-COG-001.yaml", "domain": "ui"}]
    (output / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    with pytest.raises(ValueError, match="manifest domain mismatch"):
        run(importer, True)
    assert not (output / "hplus-OCF-COG-001.yaml").exists()
