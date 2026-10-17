"""Optional pygls stdio adapter over the authoritative OCF authoring services."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from functools import wraps
from pathlib import Path
from types import SimpleNamespace

from .authoring import AuthoringService, offset_at, position_at, schema_at, schema_name, uri_path
from .paths import REPO_ROOT
from .utils import OCFError

FEATURES = {
    "textDocument/didOpen": "Initial unsaved-buffer diagnostics",
    "textDocument/didChange": "Incremental buffer updates and debounced diagnostics",
    "textDocument/didSave": "Refresh saved-document diagnostics",
    "textDocument/didClose": "Clear diagnostics and release overlay",
    "workspace/didChangeWatchedFiles": "Invalidate saved-data indexes and revalidate open buffers",
    "workspace/didChangeWorkspaceFolders": "Contained multi-root workspace selection",
    "textDocument/completion": "Function/resource/locale/template/pacing/DSP/voice/theme and schema-property completions",
    "textDocument/hover": "Read-only canonical metadata and schema documentation",
    "textDocument/definition": "Navigate to contained identifier definitions",
    "textDocument/references": "Find contained configuration and literal Python references",
    "textDocument/documentSymbol": "Document identifier outline",
    "workspace/symbol": "Query workspace identifiers",
    "ocf/renamePreview": "Paginated, read-only global-identifier impact suggestions; never WorkspaceEdit",
    "ocf/indexStatus": "Index boundaries, refresh counts and measured indexing time",
}


def add_arguments(parser):
    parser.add_argument(
        "--stdio", action="store_true", default=True, help="local stdio JSON-RPC only"
    )
    parser.add_argument("--workspace", type=Path, help="optional fixed contained workspace root")
    parser.add_argument(
        "--capabilities",
        action="store_true",
        help="print public methods/limits instead of starting stdio",
    )
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="WARNING"
    )


def capabilities():
    return {
        "transport": "stdio",
        "methods": FEATURES,
        "optional_extra": "lsp",
        "framework": "pygls 2.1.1 / lsprotocol 2025.0.0",
        "automatic_rename": False,
        "filesystem_writes": False,
        "network_listener": False,
        "mcp_required": False,
        "limits": {
            "document_bytes": 2 * 1024**2,
            "indexed_files_per_root": 1500,
            "workspace_roots": 8,
        },
    }


def create_server(*, fixed_root=None):
    try:
        from lsprotocol import types
        from pygls.exceptions import JsonRpcInvalidParams
        from pygls.lsp.server import LanguageServer
        from pygls.workspace import Workspace
    except ImportError as exc:
        raise OCFError(
            "OCF LSP requires the optional extra: python -m pip install -e '.[lsp]'; ordinary CLI/MCP remain independent"
        ) from exc

    server = LanguageServer(
        "OCF", "1.0.0", text_document_sync_kind=types.TextDocumentSyncKind.Incremental
    )
    services = {}
    roots = []
    pending = {}
    associations = {}
    debounce = 0.15

    def set_roots(selected):
        nonlocal roots
        selected = [Path(root).resolve() for root in selected]
        if len(selected) > 8:
            raise OCFError("OCF LSP supports up to eight explicit workspace roots")
        roots = sorted(set(selected), key=lambda root: len(str(root)), reverse=True)
        for root in list(services):
            if root not in roots:
                services.pop(root)

    def service_for(uri):
        path = uri_path(uri)
        root = next((root for root in roots if path.is_relative_to(root)), None)
        if root is None:
            raise OCFError("document is outside the selected workspace roots")
        if root not in services:
            services[root] = AuthoringService(root, associations=associations)
        return services[root]

    class ContainedWorkspace(Workspace):
        def get_text_document(self, uri):
            # Guard the SDK's lazy disk read as well as our own source providers.
            service_for(uri)
            return super().get_text_document(uri)

    def encoding():
        value = getattr(server.protocol.server_capabilities, "position_encoding", None)
        return getattr(value, "value", value) or "utf-16"

    def location(doc, span):
        return types.Location(
            uri=doc.path.as_uri(),
            range=types.Range(
                types.Position(**position_at(doc.text, span.start, encoding())),
                types.Position(**position_at(doc.text, span.end, encoding())),
            ),
        )

    def context(params):
        uri = params.text_document.uri
        service = service_for(uri)
        document = server.workspace.get_text_document(uri)
        if uri in server.workspace.text_documents:
            service.update(uri, document.source)
        return (
            service,
            uri,
            offset_at(document.source, params.position.line, params.position.character, encoding()),
        )

    def request(function):
        @wraps(function)
        def invoke(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except (OCFError, OSError, ValueError, TypeError, KeyError) as exc:
                raise JsonRpcInvalidParams(str(exc)[:1500]) from exc

        return invoke

    @server.feature(types.INITIALIZE)
    def initialize(ls, params):
        nonlocal associations, debounce
        options = (
            params.initialization_options if isinstance(params.initialization_options, dict) else {}
        )
        associations = options.get("schemaAssociations", {})
        if (
            not isinstance(associations, dict)
            or len(associations) > 32
            or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in associations.items()
            )
        ):
            raise JsonRpcInvalidParams(
                "schemaAssociations must be a bounded glob-to-local-schema map"
            )
        value = options.get("diagnosticsDebounceMs", 150)
        if type(value) is not int or not 0 <= value <= 1000:
            raise JsonRpcInvalidParams("diagnosticsDebounceMs must be 0..1000")
        debounce = value / 1000
        selected = (
            [Path(fixed_root)]
            if fixed_root
            else [uri_path(folder.uri) for folder in params.workspace_folders or []]
        )
        if not selected:
            selected = (
                [uri_path(params.root_uri)]
                if params.root_uri
                else [Path(params.root_path)]
                if params.root_path
                else [REPO_ROOT]
            )
        set_roots(selected)
        # pygls creates its workspace before this callback; replace it before
        # accepting buffers so lazy SDK reads use the same containment policy.
        ls.protocol._workspace = ContainedWorkspace(
            params.root_uri,
            types.TextDocumentSyncKind.Incremental,
            params.workspace_folders or [],
            ls.workspace.position_encoding,
        )

    async def publish(uri, version, delay):
        await asyncio.sleep(delay)
        try:
            service = service_for(uri)
            document = server.workspace.get_text_document(uri)
            if document.version != version:
                return
            service.update(uri, document.source)
            findings = service.analyze(uri)
            severity = {
                "error": types.DiagnosticSeverity.Error,
                "warning": types.DiagnosticSeverity.Warning,
                "info": types.DiagnosticSeverity.Information,
            }
            diagnostics = [
                types.Diagnostic(
                    range=types.Range(
                        types.Position(**position_at(document.source, item.start, encoding())),
                        types.Position(**position_at(document.source, item.end, encoding())),
                    ),
                    message=item.message,
                    severity=severity[item.severity],
                    source="ocf",
                    code=item.code,
                    data={"pointer": item.pointer},
                )
                for item in findings
            ]
            server.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics, version=version)
            )
        except (OCFError, OSError, UnicodeError, ValueError, TypeError) as exc:
            server.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(
                    uri=uri,
                    diagnostics=[
                        types.Diagnostic(
                            range=types.Range(types.Position(0, 0), types.Position(0, 1)),
                            message=str(exc)[:1500],
                            code="ocf.workspace",
                            source="ocf",
                            severity=types.DiagnosticSeverity.Error,
                        )
                    ],
                    version=version,
                )
            )

    def schedule(uri, version, delay):
        previous = pending.pop(uri, None)
        if previous:
            previous.cancel()
        task = asyncio.create_task(publish(uri, version, delay))
        pending[uri] = task

        def done(completed):
            if pending.get(uri) is completed:
                pending.pop(uri, None)

        task.add_done_callback(done)

    def synchronize(uri):
        document = server.workspace.get_text_document(uri)
        service_for(uri).update(uri, document.source)

    def revalidate_open(delay):
        # Dependencies (locale resources and inherited profiles) can affect any
        # open document. Analysis is debounced; overlays are synchronized first.
        for document in server.workspace.text_documents.values():
            schedule(document.uri, document.version, delay)

    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    def opened(ls, params):
        synchronize(params.text_document.uri)
        revalidate_open(0)

    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    def changed(ls, params):
        synchronize(params.text_document.uri)
        revalidate_open(debounce)

    @server.feature(types.TEXT_DOCUMENT_DID_SAVE)
    def saved(ls, params):
        synchronize(params.text_document.uri)
        revalidate_open(0)

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    def closed(ls, params):
        uri = params.text_document.uri
        if task := pending.pop(uri, None):
            task.cancel()
        try:
            service_for(uri).close(uri)
        except OCFError:
            pass
        server.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=uri, diagnostics=[])
        )
        revalidate_open(debounce)

    @server.feature(types.WORKSPACE_DID_CHANGE_WATCHED_FILES)
    def watched(ls, _params):
        for service in services.values():
            service._signature = None
            service._cache.clear()
        for document in server.workspace.text_documents.values():
            schedule(document.uri, document.version, debounce)

    @server.feature(types.WORKSPACE_DID_CHANGE_WORKSPACE_FOLDERS)
    def folders(ls, _params):
        if not fixed_root:
            set_roots([uri_path(uri) for uri in server.workspace.folders])

    @server.feature(
        types.TEXT_DOCUMENT_COMPLETION,
        types.CompletionOptions(trigger_characters=[".", ":", "-", '"']),
    )
    @request
    def completion(ls, params):
        service, uri, offset = context(params)
        doc, span, rows = service.completions(uri, offset)
        items = []
        for row in rows:
            value = row.get("value", row["label"])
            quoted = span.start > 0 and doc.text[span.start - 1 : span.start] in ("'", '"')
            if row["kind"] == "cue-symbol":
                insertion = str(value)
            elif row["kind"] == "property":
                following = doc.text[span.end :].lstrip()
                insertion = (
                    row["label"] if following.startswith(('"', "'", ":")) else row["label"] + ": "
                )
            else:
                insertion = (
                    json.dumps(value, ensure_ascii=False)
                    if doc.path.suffix == ".json" and not quoted
                    else str(value)
                )
                if quoted and doc.path.suffix == ".json" and isinstance(value, str):
                    insertion = json.dumps(value, ensure_ascii=False)[1:-1]
            edit = types.TextEdit(
                range=types.Range(
                    types.Position(**position_at(doc.text, span.start, encoding())),
                    types.Position(**position_at(doc.text, span.end, encoding())),
                ),
                new_text=insertion,
            )
            items.append(
                types.CompletionItem(
                    label=row["label"],
                    detail=row["kind"],
                    documentation=row["description"],
                    text_edit=edit,
                    kind=types.CompletionItemKind.Property
                    if row["kind"] == "property"
                    else types.CompletionItemKind.Reference,
                )
            )
        return types.CompletionList(is_incomplete=False, items=items)

    @server.feature(types.TEXT_DOCUMENT_HOVER)
    @request
    def hover(ls, params):
        service, uri, offset = context(params)
        doc, span, definitions = service.definitions_at(uri, offset)
        if not definitions:
            from .validators import _load_schema

            name = schema_name(doc.path, doc.data, service.root, service.associations)
            field = (
                schema_at(_load_schema(name), span.path) if name and name != "json-schema" else {}
            )
            if not field:
                return None
            content = f"{'.'.join(map(str, span.path))}\n{field.get('description') or field.get('title') or str(field.get('type', 'configuration value'))}"
            return types.Hover(
                contents=types.MarkupContent(kind=types.MarkupKind.PlainText, value=content),
                range=location(doc, span).range,
            )
        content = "\n\n".join(
            f"{item.name}\n{item.kind}\n{item.path.relative_to(service.root).as_posix()}\n{item.description}"
            for item in definitions[:5]
        )
        return types.Hover(
            contents=types.MarkupContent(kind=types.MarkupKind.PlainText, value=content),
            range=location(doc, span).range,
        )

    @server.feature(types.TEXT_DOCUMENT_DEFINITION)
    @request
    def definition(ls, params):
        service, uri, offset = context(params)
        _doc, _span, definitions = service.definitions_at(uri, offset)
        return [location(service.document(item.path), item.span) for item in definitions]

    @server.feature(types.TEXT_DOCUMENT_REFERENCES)
    @request
    def references(ls, params):
        service, uri, offset = context(params)
        _doc, span, _definitions = service.definitions_at(uri, offset)
        rows = service.references(
            span.value, include_declarations=params.context.include_declaration
        )
        if len(rows) > 5000:
            raise OCFError("reference set exceeds 5000 locations; use paginated ocf/renamePreview")
        return [location(doc, item) for doc, item in rows]

    @server.feature(types.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    @request
    def symbols(ls, params):
        service = service_for(params.text_document.uri)
        document = server.workspace.get_text_document(params.text_document.uri)
        if document.uri in server.workspace.text_documents:
            service.update(document.uri, document.source)
        service.refresh()
        doc = service.document(service.path(document.uri))
        rows = [
            item
            for values in service.definitions.values()
            for item in values
            if item.path == doc.path
        ]
        seen = {(item.span.start, item.span.end) for item in rows}
        rows += [
            SimpleNamespace(name=span.value, span=span)
            for span in doc.spans
            if span.path
            and span.path[-1] == "id"
            and not span.key
            and (span.start, span.end) not in seen
        ]
        return [
            types.DocumentSymbol(
                name=item.name,
                kind=types.SymbolKind.Key,
                range=location(doc, item.span).range,
                selection_range=location(doc, item.span).range,
            )
            for item in rows
        ]

    @server.feature(types.WORKSPACE_SYMBOL)
    @request
    def workspace_symbols(ls, params):
        rows = []
        for root in roots:
            service = services.setdefault(root, AuthoringService(root, associations=associations))
            service.refresh()
            for name, values in sorted(service.definitions.items()):
                if params.query.casefold() in name.casefold():
                    item = values[0]
                    rows.append(
                        types.WorkspaceSymbol(
                            name=name,
                            kind=types.SymbolKind.Key,
                            location=location(service.document(item.path), item.span),
                            container_name=item.kind,
                        )
                    )
        return rows[:200]

    def value(params, name, default=None):
        return (
            params.get(name, default)
            if isinstance(params, dict)
            else getattr(params, name, default)
        )

    @server.feature("ocf/renamePreview")
    @request
    def preview(ls, params):
        document = value(params, "textDocument")
        uri = value(document, "uri")
        point = value(params, "position")
        service = service_for(uri)
        buffer = server.workspace.get_text_document(uri)
        if uri in server.workspace.text_documents:
            service.update(uri, buffer.source)
        offset = offset_at(
            buffer.source, value(point, "line"), value(point, "character"), encoding()
        )
        result = service.rename_preview(
            uri,
            offset,
            value(params, "newName"),
            offset=value(params, "offset", 0),
            limit=value(params, "limit", 200),
        )
        result["migration_approval"] = False
        return result

    @server.feature("ocf/indexStatus")
    @request
    def index_status(ls, _params):
        return {
            "read_only": True,
            "roots": [
                {
                    "uri": root.as_uri(),
                    "refreshes": service.refreshes,
                    "definitions": len(service.definitions),
                    "index_seconds": service.last_index_seconds,
                }
                for root, service in services.items()
            ],
            "automatic_rename": False,
        }

    @server.feature(types.SHUTDOWN)
    def shutdown(ls, _params):
        for task in pending.values():
            task.cancel()
        pending.clear()

    return server


def run(args):
    if args.capabilities:
        print(json.dumps(capabilities(), ensure_ascii=False, indent=2))
        return 0
    logging.basicConfig(stream=sys.stderr, level=getattr(logging, args.log_level))
    create_server(fixed_root=args.workspace).start_io()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    try:
        return run(parser.parse_args(argv))
    except OCFError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
