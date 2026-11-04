"""Fail-closed discovery, locale isolation and migration publication boundaries."""

import json
from contextlib import contextmanager
from copy import deepcopy

import pytest
from ocf_tools import function_authority_migration as migration
from ocf_tools import function_catalog as catalog
from ocf_tools.utils import OCFError, yaml_safe_dump
from test_complete_function_authority import fixture

pytestmark = pytest.mark.unit


def pack(root, locale, data, *, filename="function.yaml"):
    directory = root / "locales" / locale
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.yaml").write_text(
        yaml_safe_dump({"resources": [{"file": filename, "domain": "function"}]}),
        encoding="utf-8",
    )
    if filename == "function.yaml":
        (directory / filename).write_text(yaml_safe_dump(data), encoding="utf-8")
    return directory


@pytest.mark.parametrize("name", ["../outside.yaml", "nested/function.yaml", "x\\file.yaml"])
def test_discovery_rejects_nonlocal_resource_paths(tmp_path, name):
    pack(tmp_path, "en-US", {}, filename=name)
    with pytest.raises(OCFError, match="unsafe function catalog resource"):
        catalog.resources(tmp_path)


@pytest.mark.parametrize("node", ["manifest", "resource", "directory"])
def test_discovery_rejects_symlinked_authority(tmp_path, node):
    directory = pack(tmp_path, "en-US", {})
    path = {
        "manifest": directory / "manifest.yaml",
        "resource": directory / "function.yaml",
        "directory": directory,
    }[node]
    target = tmp_path / "retained"
    path.rename(target)
    try:
        path.symlink_to(target, target_is_directory=node == "directory")
    except OSError:
        pytest.skip("symlinks unavailable on this platform")
    with pytest.raises(OCFError, match="unsafe function catalog"):
        catalog.resources(tmp_path)


@pytest.mark.parametrize(
    "identity,locale", [(None, "en-US"), (12, "en-US"), ("bad", "en-US"), ("OCF-COG-001", "es")]
)
def test_discovery_rejects_malformed_or_foreign_identity(tmp_path, identity, locale):
    pack(tmp_path, "en-US", {"function_id": identity, "locale": locale})
    with pytest.raises(OCFError, match="inconsistent function catalog identity"):
        catalog.resources(tmp_path)


def test_discovery_ignores_other_domains_and_revisions_and_sorts_ids(tmp_path):
    directory = pack(tmp_path, "en-US", {})
    rows = [
        {"domain": "ui", "file": "absent.yaml"},
        {"domain": "function", "revision": "old", "file": "absent.yaml"},
    ]
    for identity in ["OCF-COG-002", "OCF-COG-001"]:
        name = identity + ".yaml"
        rows.append({"domain": "function", "file": name})
        (directory / name).write_text(
            yaml_safe_dump({"function_id": identity, "locale": "en-US"}), encoding="utf-8"
        )
    (directory / "manifest.yaml").write_text(yaml_safe_dump({"resources": rows}), encoding="utf-8")
    assert [data["function_id"] for _, data in catalog.resources(tmp_path)] == [
        "OCF-COG-001",
        "OCF-COG-002",
    ]


@pytest.mark.parametrize("mutation", ["unknown", "drift", "valid"])
def test_localized_loading_checks_identity_and_structure_before_projection(
    tmp_path, monkeypatch, mutation
):
    canonical = fixture()
    canonical.update(locale="en-US", schema_version="2.0")
    local = deepcopy(canonical)
    local.update(locale="es", title={"text": "Título local"})
    if mutation == "unknown":
        local["function_id"] = "OCF-COG-999"
    elif mutation == "drift":
        local["narration"]["sequence"][0]["repetitions"] += 1
    pack(tmp_path, "en-US", canonical)
    pack(tmp_path, "es", local)
    projected = []

    def project(data, path, root):
        projected.append(data)
        return data

    monkeypatch.setattr(catalog, "project", project)
    if mutation == "valid":
        assert catalog.load_functions(tmp_path, "es") == [local]
        assert projected[0]["title"]["text"] == "Título local"
    else:
        with pytest.raises(OCFError, match="inconsistent canonical structural identity"):
            catalog.load_functions(tmp_path, "es")
        assert projected == []


def test_projection_rejects_mismatched_historical_identity(tmp_path, monkeypatch):
    from ocf_tools import locale_history

    monkeypatch.setattr(locale_history, "read_logical", lambda *args: "id: OCF-COG-002")
    with pytest.raises(OCFError, match="historical function identity"):
        catalog.project(
            {"function_id": "OCF-COG-001", "historical_record": "old.yaml"},
            tmp_path / "local.yaml",
            tmp_path,
        )


@pytest.mark.parametrize("corrupt", ["archive", "old", "locale", "predecessor"])
def test_migration_verification_rejects_changed_bytes(tmp_path, corrupt):
    for name, raw in {
        "archive": b"old",
        "old": b"old",
        "locale": b"new",
        "predecessor": b"before",
    }.items():
        (tmp_path / name).write_bytes(raw)
    ledger = {
        "files": {"old": {"archive": "archive", "sha256": migration.sha(b"old")}},
        "locale_files": {
            "locale": {
                "archive": "predecessor",
                "before_sha256": migration.sha(b"before"),
                "after_sha256": migration.sha(b"new"),
            }
        },
    }
    (tmp_path / corrupt).write_bytes(b"tampered")
    with pytest.raises(OCFError, match="drift"):
        migration.verify(tmp_path, ledger)


def test_migration_rejects_other_checkout_without_writing(tmp_path):
    with pytest.raises(OCFError, match="do not mix checkout identities"):
        migration.build(tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("duplicate", [True, False])
def test_migration_requires_exact_unique_baseline(tmp_path, monkeypatch, duplicate):
    from types import SimpleNamespace

    from ocf_tools import locale, models

    monkeypatch.setattr(migration, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(locale, "LocaleCatalog", lambda: None)
    monkeypatch.setattr(
        models, "function_from_dict", lambda data, path: SimpleNamespace(id="OCF-COG-001")
    )
    directory = tmp_path / "functions"
    directory.mkdir()
    for name in ["one.yaml", "two.yaml"] if duplicate else ["one.yaml"]:
        (directory / name).write_text("id: OCF-COG-001", encoding="utf-8")
    with pytest.raises(
        OCFError,
        match="duplicate structural" if duplicate else "exact complete 58-function baseline",
    ):
        migration.build(tmp_path)
    assert not (tmp_path / "function-content").exists()


def test_completeness_reports_missing_local_words_but_ignores_historical_commands():
    canonical = fixture()
    historical = deepcopy(canonical["activation"])
    historical["command_id"] = "OCF-CMD-COG-001-OLD"
    historical["control"]["availability"] = "historical-lookup"
    canonical["secondary_commands"].append(historical)
    local = deepcopy(canonical)
    local["title"] = {}
    local["secondary_commands"] = []
    local["localization"]["contract_sha256"] = catalog.contract_hash(canonical)
    result = catalog.completeness(local, canonical)
    assert result == {"status": "partial", "missing": ["title"], "outdated_contract": False}


def test_absent_manifest_is_not_english_fallback(tmp_path):
    pack(tmp_path, "en-US", fixture())
    assert catalog.resources(tmp_path, "es") == []


def test_historical_path_lookup_requires_registered_identity(tmp_path):
    from ocf_tools.locale_history import logical_function_path

    with pytest.raises(OCFError, match="no historical function path"):
        logical_function_path(tmp_path, "OCF-COG-999")


def test_migration_checks_semantic_equivalence_even_with_matching_hashes(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from ocf_tools import locale_history

    data = {"historical_record": "functions/old.yaml"}
    raw = yaml_safe_dump(data).encode()
    (tmp_path / "local.yaml").write_bytes(raw)
    (tmp_path / "before.yaml").write_bytes(b"old")
    ledger = {
        "files": {},
        "locale_files": {
            "local.yaml": {
                "archive": "before.yaml",
                "before_sha256": migration.sha(b"old"),
                "after_sha256": migration.sha(raw),
            }
        },
    }
    monkeypatch.setattr(
        migration, "project", lambda *args: SimpleNamespace(data={"id": "OCF-COG-002"})
    )
    monkeypatch.setattr(locale_history, "read_logical", lambda *args: "id: OCF-COG-001")
    with pytest.raises(OCFError, match="equivalence failure: id"):
        migration.verify(tmp_path, ledger)


def test_migration_lease_contention_precedes_build(tmp_path, monkeypatch):
    from ocf_tools import dev_jobs

    @contextmanager
    def unavailable(*args, **kwargs):
        assert kwargs == {"wait": False}
        yield False

    monkeypatch.setattr(dev_jobs, "lock", unavailable)
    with pytest.raises(OCFError, match="owns the lease"):
        migration.apply(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_migration_preserves_conflicting_archive_before_publication(tmp_path, monkeypatch):
    from ocf_tools import dev_jobs

    @contextmanager
    def available(*args, **kwargs):
        yield True

    archive = tmp_path / "function-content/archive"
    archive.parent.mkdir()
    archive.write_bytes(b"retain this")
    monkeypatch.setattr(dev_jobs, "lock", available)
    monkeypatch.setattr(
        migration,
        "build",
        lambda root: ({}, {"function-content/archive": b"expected", "locales/new.yaml": b"new"}),
    )
    with pytest.raises(OCFError, match="preserve conflicting migration archive"):
        migration.apply(tmp_path)
    assert archive.read_bytes() == b"retain this"
    assert not (tmp_path / "locales").exists()
    assert not (tmp_path / migration.LEDGER).exists()


@pytest.mark.parametrize("apply", [True, False])
def test_migration_cli_selects_explicit_apply_or_read_only_preview(monkeypatch, capsys, apply):
    import sys

    monkeypatch.setattr(sys, "argv", ["migration", *(["--apply"] if apply else [])])
    monkeypatch.setattr(migration, "apply", lambda: {"status": "applied"})
    monkeypatch.setattr(migration, "build", lambda: ({"files": {"one": {}}}, {"one": b"data"}))
    migration.main()
    result = json.loads(capsys.readouterr().out)
    assert result == (
        {"status": "applied"} if apply else {"status": "dry-run", "functions": 1, "writes": 1}
    )
