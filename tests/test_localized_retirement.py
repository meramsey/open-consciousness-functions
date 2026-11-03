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
    assert report["retirement_candidates"] == []
    assert report["retired_key_count"] == 0
    assert all(
        row["file"]
        not in {"locales/en-US/" + value["file"] for value in report["active_functions"].values()}
        for row in report["retirement_candidates"]
    )
    assert retirement_plan(locale="es")["active_function_count"] == 0


@pytest.mark.integration
def test_retired_catalog_matches_exact_predecessor_without_duplicate_authority():
    from ocf_tools.locale import LocaleCatalog
    from ocf_tools.locale_history import before_structural, historical_resources, read_logical
    from ocf_tools.localized_retirement import LEDGER, REPO_ROOT
    from ocf_tools.utils import yaml_safe_load

    def historical_reader(path):
        name = path.relative_to(REPO_ROOT).as_posix()
        return yaml_safe_load(before_structural(REPO_ROOT, name, read_logical(REPO_ROOT, name)))

    names = historical_resources(REPO_ROOT)
    predecessor = LocaleCatalog(
        REPO_ROOT / "locales",
        reader=historical_reader,
        exists=lambda path: path.is_file() or path.relative_to(REPO_ROOT).as_posix() in names,
    )
    current = LocaleCatalog()
    assert predecessor.problems == current.problems == []
    for locale in current.locales():

        def values(catalog):
            return {
                key: (entry.text, entry.version, entry.status, entry.domain)
                for key, entry in catalog.require(locale).entries.items()
            }

        assert values(predecessor) == values(current)
    ledger = json.loads((REPO_ROOT / LEDGER).read_text())
    assert ledger["retired_key_count"] == 615
    assert len(ledger["created_resources"]) == 3
    assert not any(
        row.get("superseded_keys") for row in current.require("en-US").manifest["resources"]
    )
    assert len(current.require("en-US").localized_functions) == 58


@pytest.mark.unit
def test_apply_retires_words_preserves_shared_values_and_exact_archives(tmp_path, monkeypatch):
    from ocf_tools import locale_history
    from ocf_tools.localized_retirement import LEDGER, apply_retirement

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    path, manifest = source(tmp_path)
    original = path.read_bytes()
    result = apply_retirement(tmp_path)
    assert result["keys"] == 1 and result["shared_resources"] == 1
    stub = yaml.safe_load(path.read_text())
    assert stub["kind"] == "immutable-historical-locale-reference" and "entries" not in stub
    archive = tmp_path / stub["archive"]
    assert archive.read_bytes() == original
    shared = yaml.safe_load(path.with_name("shared-compat.yaml").read_text())
    assert shared["entries"] == {"shared.label": "Required shared UI"}
    active = yaml.safe_load(path.with_name("manifest.yaml").read_text())
    assert active["resources"][0]["file"] == "shared-compat.yaml"
    assert not any("superseded_keys" in row for row in active["resources"])
    monkeypatch.setattr(locale_history, "RETIREMENT_SHA256", sha((tmp_path / LEDGER).read_text()))
    assert apply_retirement(tmp_path)["status"] == "already-retired; no writes"
    assert (
        locale_history.before_structural(tmp_path, "locales/en-US/compat.yaml", path.read_text())
        == original.decode()
    )
    archive.write_text("tampered archive")
    with pytest.raises(OCFError, match="archive drift"):
        locale_history.before_structural(tmp_path, "locales/en-US/compat.yaml", path.read_text())


@pytest.mark.unit
def test_apply_does_not_overwrite_an_unrelated_shared_destination(tmp_path, monkeypatch):
    from ocf_tools.localized_retirement import LEDGER, apply_retirement

    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path / "work"))
    path, manifest = source(tmp_path)
    original = path.read_bytes()
    path.with_name("shared-compat.yaml").write_text("user data")
    with pytest.raises(OCFError, match="refusing to overwrite"):
        apply_retirement(tmp_path)
    assert path.read_bytes() == original
    assert not (tmp_path / LEDGER).exists()
