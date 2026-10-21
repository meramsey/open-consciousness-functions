"""Actual optional OCF LSP process: framing, lifecycle and editor capabilities."""

import json

import pytest
from authoring_fixtures import seed
from lsp_client import Client
from ocf_tools.authoring import position_at

pytest.importorskip("pygls")
pytestmark = [pytest.mark.integration, pytest.mark.external_tool]


@pytest.fixture
def client(tmp_path):
    root = tmp_path / "workspace with spaces"
    path = seed(root)
    instance = Client(root, tmp_path / "lsp-stderr.log")
    try:
        initialized = instance.request(
            "initialize",
            {
                "processId": None,
                "rootUri": root.as_uri(),
                "capabilities": {"general": {"positionEncodings": ["utf-16"]}},
                "initializationOptions": {"diagnosticsDebounceMs": 20},
            },
        )
        assert "error" not in initialized, initialized
        instance.send("initialized", {})
        yield instance, path, initialized["result"]["capabilities"]
    finally:
        instance.close()


def open_document(client, path, text, version=1):
    client.send(
        "textDocument/didOpen",
        {
            "textDocument": {
                "uri": path.as_uri(),
                "languageId": "yaml",
                "version": version,
                "text": text,
            }
        },
    )
    return client.receive(
        lambda message: (
            message.get("method") == "textDocument/publishDiagnostics"
            and message["params"].get("version") == version
            and message["params"]["uri"] == path.as_uri()
        )
    )


def test_protocol_capabilities_diagnostics_completions_navigation_and_preview(client):
    rpc, path, capabilities = client
    assert capabilities["textDocumentSync"]["change"] == 2
    assert (
        capabilities["definitionProvider"]
        and capabilities["referencesProvider"]
        and capabilities["documentSymbolProvider"]
    )
    assert not capabilities.get("renameProvider")
    original = path.read_text(encoding="utf-8")
    assert open_document(rpc, path, original)["params"]["diagnostics"] == []
    position = position_at(original, original.index("OCF-FND-002") + len("OCF-FND-"))
    params = {"textDocument": {"uri": path.as_uri()}, "position": position}
    completion = rpc.request("textDocument/completion", params)
    assert "OCF-FND-002" in {item["label"] for item in completion["result"]["items"]}
    hover = rpc.request("textDocument/hover", params)
    assert "Focus" in hover["result"]["contents"]["value"]
    definitions = rpc.request("textDocument/definition", params)
    assert definitions["result"][0]["uri"].endswith("functions/foundation/focus.yaml")
    references = rpc.request(
        "textDocument/references", {**params, "context": {"includeDeclaration": True}}
    )
    assert len(references["result"]) >= 2
    symbols = rpc.request("textDocument/documentSymbol", {"textDocument": {"uri": path.as_uri()}})
    assert any(item["name"] == "speak" for item in symbols["result"])
    workspace = rpc.request("workspace/symbol", {"query": "OCF-VOICE"})
    assert any(item["name"] == "OCF-VOICE-0001" for item in workspace["result"])
    preview = rpc.request("ocf/renamePreview", {**params, "newName": "OCF-FND-099", "limit": 1})
    assert preview["result"]["automatic_rename"] is False and preview["result"]["read_only"]
    assert preview["result"]["next_offset"] == 1
    assert "changes" not in preview["result"]
    denied = rpc.request("textDocument/rename", {**params, "newName": "OCF-FND-099"})
    assert "error" in denied and "result" not in denied
    assert path.read_text(encoding="utf-8") == original


def test_unsaved_incremental_changes_clear_and_republish_without_file_writes(client):
    rpc, path, _capabilities = client
    original = path.read_text(encoding="utf-8")
    open_document(rpc, path, original)
    start = original.index("test.guidance")
    rpc.send(
        "textDocument/didChange",
        {
            "textDocument": {"uri": path.as_uri(), "version": 2},
            "contentChanges": [
                {
                    "range": {
                        "start": position_at(original, start),
                        "end": position_at(original, start + len("test.guidance")),
                    },
                    "text": "test.missing",
                }
            ],
        },
    )
    changed = rpc.receive(
        lambda message: (
            message.get("method") == "textDocument/publishDiagnostics"
            and message["params"].get("version") == 2
        )
    )
    assert any(item["code"] == "narration-unknown-key" for item in changed["params"]["diagnostics"])
    rpc.send(
        "textDocument/didChange",
        {
            "textDocument": {"uri": path.as_uri(), "version": 3},
            "contentChanges": [{"text": original}],
        },
    )
    repaired = rpc.receive(
        lambda message: (
            message.get("method") == "textDocument/publishDiagnostics"
            and message["params"].get("version") == 3
        )
    )
    assert repaired["params"]["diagnostics"] == []
    assert path.read_text(encoding="utf-8") == original
    rpc.send("textDocument/didClose", {"textDocument": {"uri": path.as_uri()}})
    assert (
        rpc.receive(
            lambda message: (
                message.get("method") == "textDocument/publishDiagnostics"
                and message["params"].get("version") is None
            )
        )["params"]["diagnostics"]
        == []
    )


def test_malformed_documents_and_outside_workspace_requests_are_bounded(client, tmp_path):
    rpc, path, _capabilities = client
    errors = open_document(rpc, path, "schema_version: [")
    assert errors["params"]["diagnostics"][0]["code"] == "ocf.parse"
    outside = tmp_path / "private.json"
    outside.write_text(
        json.dumps({"private": "never navigate outside workspace"}), encoding="utf-8"
    )
    response = rpc.request(
        "textDocument/definition",
        {"textDocument": {"uri": outside.as_uri()}, "position": {"line": 0, "character": 0}},
    )
    assert response["error"]["code"] == -32602
    assert "workspace" in response["error"]["message"]
    status = rpc.request("ocf/indexStatus", {})
    assert status["result"]["read_only"] is True


def test_unsaved_locale_dependency_updates_and_close_revalidate_open_transcript(client):
    rpc, path, _capabilities = client
    original = path.read_text(encoding="utf-8")
    open_document(rpc, path, original)
    resource = path.parents[2] / "locales/en-US/narration.yaml"
    text = resource.read_text(encoding="utf-8").replace("test.guidance", "test.revised")
    open_document(rpc, resource, text)
    findings = rpc.receive(
        lambda message: (
            message.get("method") == "textDocument/publishDiagnostics"
            and message["params"]["uri"] == path.as_uri()
            and any(
                item["code"] == "narration-unknown-key" for item in message["params"]["diagnostics"]
            )
        )
    )
    assert findings["params"]["version"] == 1
    # Requests see a dependency's current overlay before the debounce expires.
    rpc.send(
        "textDocument/didChange",
        {
            "textDocument": {"uri": resource.as_uri(), "version": 2},
            "contentChanges": [{"text": resource.read_text(encoding="utf-8")}],
        },
    )
    response = rpc.request(
        "textDocument/definition",
        {
            "textDocument": {"uri": path.as_uri()},
            "position": position_at(original, original.index("test.guidance")),
        },
    )
    assert response["result"][0]["uri"] == resource.as_uri()
    rpc.send("textDocument/didClose", {"textDocument": {"uri": resource.as_uri()}})
    restored = rpc.receive(
        lambda message: (
            message.get("method") == "textDocument/publishDiagnostics"
            and message["params"]["uri"] == path.as_uri()
            and message["params"]["diagnostics"] == []
        )
    )
    assert restored["params"]["version"] == 1


def test_json_unicode_completion_edits_and_schema_properties(client):
    rpc, path, _capabilities = client
    json_path = path.parents[2] / "scratch.json"
    # Associate by recognized shape, avoiding a fabricated schema identifier.
    text = json.dumps(
        {"note": "😀 café", "timeline": [], "source": {}, "function_id": "OCF-FND-"},
        ensure_ascii=False,
    )
    open_document(rpc, json_path, text)
    at = text.index("OCF-FND-") + len("OCF-FND-")
    response = rpc.request(
        "textDocument/completion",
        {
            "textDocument": {"uri": json_path.as_uri()},
            "position": position_at(text, at),
        },
    )
    item = next(row for row in response["result"]["items"] if row["label"] == "OCF-FND-002")
    assert item["textEdit"]["newText"] == "OCF-FND-002"
    assert item["textEdit"]["range"]["start"] == position_at(text, text.index("OCF-FND-"))


def test_workspace_folder_changes_and_saved_watch_refresh(client, tmp_path):
    rpc, path, _capabilities = client
    root = tmp_path / "second-root"
    other = seed(root)
    rpc.send(
        "workspace/didChangeWorkspaceFolders",
        {
            "event": {
                "added": [{"uri": root.as_uri(), "name": "second"}],
                "removed": [],
            }
        },
    )
    text = other.read_text(encoding="utf-8")
    assert open_document(rpc, other, text)["params"]["diagnostics"] == []
    voice = root / "audio/voices/profiles/fixture.yaml"
    voice.write_text(voice.read_text().replace("0001", "0003"), encoding="utf-8")
    rpc.send("workspace/didChangeWatchedFiles", {"changes": [{"uri": voice.as_uri(), "type": 2}]})
    result = rpc.request("workspace/symbol", {"query": "OCF-VOICE-0003"})
    assert len(result["result"]) == 1
    assert result["result"][0]["location"]["uri"] == voice.as_uri()
    rpc.send(
        "workspace/didChangeWorkspaceFolders",
        {
            "event": {
                "added": [],
                "removed": [{"uri": root.as_uri(), "name": "second"}],
            }
        },
    )
    denied = rpc.request(
        "textDocument/definition",
        {
            "textDocument": {"uri": other.as_uri()},
            "position": {"line": 0, "character": 0},
        },
    )
    assert denied["error"]["code"] == -32602
