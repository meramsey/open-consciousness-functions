"""Batch migration preview scope, speech equivalence, and safe publication."""

import hashlib
import json
from types import SimpleNamespace

import pytest
from ocf_tools import localized_migration as migration
from ocf_tools.indexes import load_all_functions
from ocf_tools.locale import LocaleCatalog
from ocf_tools.utils import OCFError, yaml_safe_load


@pytest.fixture(scope="module")
def batch():
    return migration.build_batch()


@pytest.mark.integration
def test_batch_covers_all_registered_functions_without_authoring_speech(batch):
    records = load_all_functions()
    catalog = LocaleCatalog()
    assert batch["count"] == len(records) == 58
    assert len(batch["files"]) == len(batch["mapping"]) == 58
    owners = {record.id: record for record in records}
    for row in batch["mapping"]:
        owner = owners[row["function_id"]]
        data = yaml_safe_load(batch["files"][row["destination"]])
        assert data["function_id"] == owner.id
        assert data["title"]["text"] == owner.canonical_name
        assert row["destination"].startswith("locales/en-US/" + owner.id + "-")
        assert len(data["secondary_commands"]) == len(owner.command_records) - 1
        assert "# BEGIN GENERATED CUE PREVIEW" not in batch["files"][row["destination"]]
        for key, value in data["entries"].items():
            original = catalog.raw_resource(key, "en-US", domain="narration", fallback=False)[0]
            resolved = catalog.resource(key, "en-US", domain="narration", fallback=False)[0]
            assert value["text"] == original.text
            assert (
                hashlib.sha256(value["text"].encode()).hexdigest()
                == (row["raw_template_sha256"][key])
            )
            assert (
                hashlib.sha256(resolved.text.encode()).hexdigest()
                == (row["resolved_text_sha256"][key])
            )
            assert "notes" not in value
    for name, source in batch["historical_source_snapshots"].items():
        assert hashlib.sha256(source["text"].encode()).hexdigest() == source["sha256"]
        assert source["text"] == (migration.REPO_ROOT / name).read_text(encoding="utf-8")


@pytest.mark.integration
def test_batch_preserves_unbound_legacy_cues_without_inventing_spoken_text(batch):
    appetite = next(row for row in batch["mapping"] if row["function_id"] == "OCF-BOD-012")
    data = yaml_safe_load(batch["files"][appetite["destination"]])
    legacy = next(
        row for row in data["secondary_commands"] if row["command_id"].endswith("LEGACY-01")
    )
    assert legacy["display_cue"]["text"]
    assert "spoken_cue" not in legacy


@pytest.mark.integration
def test_stage_batch_publishes_preview_only_and_refuses_overwrite(batch, tmp_path, monkeypatch):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    destination = tmp_path / "preview"
    receipt = migration.stage_batch(batch, destination)
    assert receipt["count"] == 58
    assert "preview-only" in receipt["status"]
    assert json.loads((destination / "migration.json").read_text())["count"] == 58
    for name, digest in receipt["output_sha256"].items():
        raw = (destination / name).read_bytes()
        assert not raw.startswith(b"\n")
        assert hashlib.sha256(raw).hexdigest() == digest
    with pytest.raises(OCFError, match="already exists"):
        migration.stage_batch(batch, destination)
    with pytest.raises(OCFError, match="inside OCF_WORK_DIR"):
        migration.stage_batch(batch, tmp_path.parent / "outside")


@pytest.mark.unit
def test_batch_refuses_invalid_source_catalog(tmp_path):
    class InvalidCatalog:
        problems = ["duplicate localized definition"]

    with pytest.raises(OCFError, match="duplicate localized definition"):
        migration.build_batch(tmp_path, records=[], catalog=InvalidCatalog())


@pytest.mark.unit
def test_stage_batch_refuses_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("OCF_WORK_DIR", str(tmp_path))
    with pytest.raises(OCFError, match="escapes stage"):
        migration.stage_batch({"files": {"../../escape.yaml": "no"}}, tmp_path / "preview")
    assert not (tmp_path / "escape.yaml").exists()


@pytest.fixture
def source(tmp_path, monkeypatch):
    locale = tmp_path / "locales/en-US"
    locale.mkdir(parents=True)
    (locale / "manifest.yaml").write_text("locale: en-US\n", encoding="utf-8")
    (locale / "fixture.yaml").write_text(
        "entries:\n  fixture.opener:\n    text: Exact wording.\n", encoding="utf-8"
    )
    command = SimpleNamespace(id="OCF-CMD-EMO-003-PRIMARY", designation="primary", localization={})
    owner = SimpleNamespace(
        id="OCF-EMO-003",
        command_records=[command],
        data={
            "documentation": {
                "title_key": "fixture.title",
                "short_description_key": "fixture.description",
            },
            "narration": {"sequence": [{"key": "fixture.opener"}]},
        },
    )

    class Catalog:
        problems = []

        def resource(self, key, *args, **kwargs):
            return SimpleNamespace(
                file="fixture.yaml", text="Exact wording.", status="reviewed", version="1.0.0"
            ), None

        raw_resource = resource

        def require(self, locale):
            return SimpleNamespace(localized_function_files={})

    monkeypatch.setattr(migration, "relationships", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        migration,
        "localized_cue",
        lambda *args, **kwargs: {
            "display_cue": "PLUS-EMPATHIZE",
            "spoken_cue": "Plus Empathize",
            "binding_status": "resolved",
        },
    )
    return tmp_path, owner, Catalog()


@pytest.mark.unit
def test_batch_rejects_duplicate_ids_and_destination_collision(source):
    root, owner, catalog = source
    with pytest.raises(OCFError, match="duplicate localized function filename"):
        migration.build_batch(root, records=[owner, owner], catalog=catalog)
    target = root / "locales/en-US/OCF-EMO-003-Exact-wording.yaml"
    target.write_text("existing operator data", encoding="utf-8")
    with pytest.raises(OCFError, match="destination already exists"):
        migration.build_batch(root, records=[owner], catalog=catalog)
    assert target.read_text() == "existing operator data"


@pytest.mark.unit
def test_batch_rejects_unreviewed_primary_and_invalid_metadata(source, monkeypatch):
    root, owner, catalog = source
    owner.command_records = []
    with pytest.raises(OCFError, match="missing primary command"):
        migration.build_batch(root, records=[owner], catalog=catalog)
    owner.command_records = [
        SimpleNamespace(id="OCF-CMD-EMO-003-PRIMARY", designation="primary", localization={})
    ]
    monkeypatch.setattr(
        migration,
        "localized_cue",
        lambda *a, **kw: {"display_cue": "PLUS-EMPATHIZE", "binding_status": "unbound"},
    )
    with pytest.raises(OCFError, match="not reviewed"):
        migration.build_batch(root, records=[owner], catalog=catalog)


@pytest.mark.unit
def test_batch_refuses_source_path_escape(source, monkeypatch):
    root, owner, catalog = source
    monkeypatch.setattr(
        catalog, "resource", lambda *a, **kw: (SimpleNamespace(file="../../../outside.yaml"), None)
    )
    with pytest.raises(OCFError, match="source escapes"):
        migration.build_batch(root, records=[owner], catalog=catalog)


@pytest.mark.unit
def test_batch_validates_structured_metadata_schema(source):
    root, owner, catalog = source
    owner.data["tags"] = ["unstructured"]
    with pytest.raises(OCFError, match="OCF-EMO-003"):
        migration.build_batch(root, records=[owner], catalog=catalog)


@pytest.mark.unit
def test_preview_cli_and_empty_metadata_boundary(tmp_path, monkeypatch, capsys):
    batch = {"count": 0, "mapping": [], "files": {}, "status": "preview-only"}
    monkeypatch.setattr(migration, "build_batch", lambda: batch)
    published = []
    monkeypatch.setattr(migration, "stage_batch", lambda data, dest: published.append((data, dest)))
    assert migration.main([]) == 0
    assert published == []
    assert migration.main(["--output", str(tmp_path / "preview")]) == 0
    assert published == [(batch, tmp_path / "preview")]
    assert "preview-only" in capsys.readouterr().out
    with pytest.raises(OCFError, match="empty localized metadata"):
        migration._literal(SimpleNamespace(text=" "))
