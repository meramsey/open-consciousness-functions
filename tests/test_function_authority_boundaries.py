"""Fail-closed discovery, locale isolation and migration publication boundaries."""

from copy import deepcopy

import pytest
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


def test_manifest_cannot_hide_an_unregistered_function_definition(tmp_path):
    pack(tmp_path, "en-US", {"function_id": "OCF-COG-001", "locale": "en-US"})
    (tmp_path / "locales/en-US/duplicate.yaml").write_text(
        yaml_safe_dump(
            {
                "schema_version": "2.0",
                "domain": "function",
                "function_id": "OCF-COG-002",
                "locale": "en-US",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OCFError, match="unregistered duplicate function definition"):
        catalog.resources(tmp_path)


def test_manifest_discovery_ignores_malformed_unregistered_nonfunction_yaml(tmp_path):
    directory = pack(
        tmp_path,
        "en-US",
        {"function_id": "OCF-COG-001", "locale": "en-US"},
    )
    (directory / "other-domain.yaml").write_text(": invalid: [", encoding="utf-8")

    assert [data["function_id"] for _, data in catalog.resources(tmp_path)] == ["OCF-COG-001"]


def test_manifest_discovery_rejects_symlinked_unregistered_yaml(tmp_path):
    directory = pack(
        tmp_path,
        "en-US",
        {"function_id": "OCF-COG-001", "locale": "en-US"},
    )
    target = tmp_path / "unregistered.yaml"
    target.write_text("domain: ui\n", encoding="utf-8")
    link = directory / "unregistered.yaml"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")

    with pytest.raises(OCFError, match="unsafe unregistered function catalog resource"):
        catalog.resources(tmp_path)


def test_manifest_discovery_ignores_invalid_yaml_owned_by_another_domain(tmp_path):
    directory = pack(
        tmp_path,
        "en-US",
        {"function_id": "OCF-COG-001", "locale": "en-US"},
    )
    (directory / "other-domain.yaml").write_text(": invalid: [", encoding="utf-8")

    assert [data["function_id"] for _, data in catalog.resources(tmp_path)] == ["OCF-COG-001"]


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


def test_projection_rejects_missing_canonical_metadata(tmp_path):
    with pytest.raises(OCFError, match="canonical function record metadata is incomplete"):
        catalog.project({"function_id": "OCF-COG-001"}, tmp_path / "local.yaml", tmp_path)


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


def test_projection_resolves_declared_lifecycle_scope_description_keys():
    from ocf_tools.function_catalog import project, resources
    from ocf_tools.paths import REPO_ROOT

    path, data = next(
        item for item in resources(REPO_ROOT) if item[1]["function_id"] == "OCF-AUT-001"
    )
    projected = project(data, path, REPO_ROOT)
    scope = projected.data["lifecycle"]["scopes"]["capability"]

    assert (
        scope["description_key"] == "functions.ocf-aut-001.lifecycle.scopes.capability.description"
    )
    assert scope["description"] == data["metadata_entries"][scope["description_key"]]["text"]
    without_key = deepcopy(data)
    without_key["lifecycle"]["scopes"]["capability"].pop("description_key")
    projected_without_key = project(without_key, path, REPO_ROOT)
    assert "description" not in projected_without_key.data["lifecycle"]["scopes"]["capability"]
