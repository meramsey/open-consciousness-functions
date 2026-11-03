"""L3 classification must be data-driven, read-only and historical-safe."""

import json

import pytest
import yaml
from ocf_tools.localized_retirement import retirement_plan, sha
from ocf_tools.utils import OCFError


def source(tmp_path, *, shared=True):
    folder = tmp_path / "locales/en-US"
    folder.mkdir(parents=True)
    data = {
        "schema_version": "1.0",
        "locale": "en-US",
        "domain": "ui",
        "entries": {"functions.ocf-aaa-001.title": "Original title"},
    }
    if shared:
        data["entries"]["shared.label"] = "Required shared UI"
    path = folder / "compat.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    manifest = {
        "locale": "en-US",
        "status": "canonical",
        "resources": [
            {
                "file": path.name,
                "domain": "ui",
                "superseded_keys": ["functions.ocf-aaa-001.title"],
                "compatibility_sha256": sha(json.dumps(data, sort_keys=True, ensure_ascii=False)),
            }
        ],
    }
    (folder / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return path, manifest


@pytest.mark.unit
@pytest.mark.parametrize(
    "shared,decision", [(True, "KEEP_SHARED_RETIRE_SUPERSEDED_KEYS"), (False, "ARCHIVE")]
)
def test_classification_preserves_unique_shared_keys_and_all_source_bytes(
    tmp_path, shared, decision
):
    path, manifest = source(tmp_path, shared=shared)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    report = retirement_plan(tmp_path)
    row = report["retirement_candidates"][0]
    assert row["decision"] == decision
    assert row["remaining_key_count"] == int(shared)
    assert row["retired_key_count"] == 1
    assert report["active_function_count"] == 0  # Never fabricate completeness.
    assert {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


@pytest.mark.unit
def test_changed_compatibility_source_blocks_retirement(tmp_path):
    path, manifest = source(tmp_path)
    path.write_text(path.read_text().replace("Original title", "Changed competing title"))
    with pytest.raises(OCFError, match="compatibility resource drift"):
        retirement_plan(tmp_path)


@pytest.mark.unit
def test_path_traversal_and_duplicate_resources_are_rejected(tmp_path):
    path, manifest = source(tmp_path)
    manifest_path = path.with_name("manifest.yaml")
    manifest["resources"].append(dict(manifest["resources"][0]))
    manifest_path.write_text(yaml.safe_dump(manifest))
    with pytest.raises(OCFError, match="duplicate active"):
        retirement_plan(tmp_path)
    manifest["resources"] = [{"file": "../../escape.yaml", "domain": "ui"}]
    manifest_path.write_text(yaml.safe_dump(manifest))
    with pytest.raises(OCFError, match="unsafe retirement resource"):
        retirement_plan(tmp_path)


@pytest.mark.integration
def test_existing_58_function_catalog_has_only_declared_retirement_candidates():
    report = retirement_plan()
    assert report["active_function_count"] == 58
    assert len(report["retirement_candidates"]) == 7
    assert report["retired_key_count"] == 615
    assert all(
        row["file"]
        not in {"locales/en-US/" + value["file"] for value in report["active_functions"].values()}
        for row in report["retirement_candidates"]
    )
    assert retirement_plan(locale="es")["active_function_count"] == 0
