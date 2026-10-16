"""Core-only capability discovery and optional dependency failure boundaries."""

import builtins

import pytest
from ocf_tools import lsp_server
from ocf_tools.authoring import Document, schema_name
from ocf_tools.paths import REPO_ROOT, SCHEMAS_DIR
from ocf_tools.utils import OCFError


@pytest.mark.unit
def test_missing_extra_gives_actionable_error_without_affecting_discovery(monkeypatch):
    original = builtins.__import__

    def without_sdk(name, *args, **kwargs):
        if name.split(".")[0] in {"pygls", "lsprotocol"}:
            raise ImportError("optional SDK deliberately unavailable")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_sdk)
    assert lsp_server.capabilities()["automatic_rename"] is False
    with pytest.raises(OCFError, match=r"pip install.*\[lsp\]"):
        lsp_server.create_server()


@pytest.mark.unit
def test_schema_associations_never_select_unregistered_paths(tmp_path):
    path = tmp_path / "custom.yaml"
    with pytest.raises(OCFError, match="registered local"):
        schema_name(path, {}, tmp_path, {"*.yaml": "../../outside.json"})
    assert (
        schema_name(path, {}, tmp_path, {"*.yaml": "function.schema.json"})
        == "function.schema.json"
    )


@pytest.mark.unit
def test_deep_representation_is_rejected_before_construction(tmp_path):
    text = "value: " + "[" * 70 + "0" + "]" * 70
    assert "complexity" in Document(tmp_path / "deep.yaml", text).diagnostics[0].message


@pytest.mark.integration
def test_every_builtin_schema_route_resolves_to_a_registered_contract():
    from ocf_tools.authoring import SCHEMAS, SOURCE_FOLDERS

    names = {path.name for path in SCHEMAS_DIR.glob("*.schema.json")}
    assert set(SCHEMAS.values()) <= names
    for folder in SOURCE_FOLDERS:
        for path in (REPO_ROOT / folder).rglob("*"):
            if path.suffix in {".json", ".yaml"} and path.is_file():
                name = schema_name(path, {}, REPO_ROOT)
                assert name is None or name in names
