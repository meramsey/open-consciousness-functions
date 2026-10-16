# Optional OCF language server

OCF supplies a local stdio language server for YAML and JSON authoring. It uses
the same JSON Schemas, command validators, locale pack loader and template,
pacing and theme inheritance services as the CLI. Unsaved documents are overlays;
the server does not write them. This is an OCF data server, not a Python server.

## Install and start

From a checkout using Python 3.11 or newer:

```bash
python -m pip install -e ".[lsp]"
ocf lsp --capabilities
ocf-lsp --stdio
```

The last command starts JSON-RPC over stdin/stdout and waits for an editor client.
`ocf lsp --stdio` and `python -m ocf_tools.lsp_server --stdio` are equivalent entry
points. Use the executable from the environment where the extra is installed;
on Windows this is typically `.venv/Scripts/ocf-lsp.exe`, and on POSIX
`.venv/bin/ocf-lsp`. Do not run an interactive shell command inside the protocol
stream. Logs go to stderr. CLI validation and MCP work without this extra.

## Editor configuration

These examples use `ocf-lsp` on the editor's PATH. A client must provide the
checkout root through `rootUri` or `workspaceFolders`; `--workspace PATH` fixes
one root explicitly. Paths containing spaces are individual process arguments.

### Neovim 0.11+

```lua
vim.lsp.config('ocf', {
  cmd = { 'ocf-lsp', '--stdio' },
  filetypes = { 'yaml', 'json' },
  root_markers = { 'pyproject.toml', '.git' },
  init_options = { diagnosticsDebounceMs = 150 },
})
vim.lsp.enable('ocf')
```

Enable this configuration for OCF workspaces. Neovim's standard hover, definition,
references, completion and symbol actions then use the advertised capabilities.

### Emacs Eglot

```elisp
(with-eval-after-load 'eglot
  (add-to-list 'eglot-server-programs
               '((yaml-mode yaml-ts-mode json-mode json-ts-mode)
                 . ("ocf-lsp" "--stdio"))))
```

Run `M-x eglot` in an OCF project buffer. Scope the configuration to the OCF
project if other projects use a general YAML or JSON server.

### Other clients, including VS Code extensions

Configure a stdio client with executable `ocf-lsp`, arguments `["--stdio"]`,
document selectors `yaml` and `json`, and the checkout workspace folder. VS Code
does not provide a generic executable setting for arbitrary LSP servers: use a
client extension capable of launching a stdio server. The core repository does
not install an extension or change editor settings automatically. The examples
above are configuration examples; automated verification exercises the protocol
itself, not native editor UIs.

## Methods and diagnostics

`ocf lsp --capabilities` lists the current implemented method manifest. Standard
methods cover incremental synchronization, diagnostics, completion, hover,
definition, references, document symbols and workspace symbols. UTF-8, UTF-16
and UTF-32 positions are supported through client negotiation. Saved-file watch
notifications invalidate caches; changes to open dependency buffers revalidate
open dependents after the configured debounce.

Schema errors include a JSON pointer in diagnostic `data.pointer`. Semantic
diagnostics reuse existing command and timed-narration rules. Requested spoken
locales use the existing same-language regional fallback rules; locale pack
identity and declared resources use the existing pack loader. Unknown private
voice identifiers are warnings because private setup may be unavailable. Other
unknown indexed references are errors. Generated plans carry an advisory to
regenerate through `audio plan`. Diagnostics are authoring feedback, not human
review, speech-content verification or release approval.

Source spans identify scalar values and keys. Errors in inherited configuration
may be reported at the child document's start; follow `extends` to inspect the
parent. Aliases use their anchor source locations. Files outside recognized
routes can declare a registered OCF `$schema` ID or use an initialization map:

```json
{
  "diagnosticsDebounceMs": 150,
  "schemaAssociations": {
    "examples/my-template.yaml": "session-template.schema.json"
  }
}
```

Associations name schemas shipped with OCF. Remote schemas are never fetched.
An unrecognized YAML/JSON file receives parse diagnostics but no guessed contract.

## Read-only migration preview

Automatic rename is not advertised. The custom request `ocf/renamePreview`
returns suggestions and contained reference locations, never a `WorkspaceEdit`:

```json
{
  "textDocument": {"uri": "file:///YOUR_CHECKOUT/functions/foundation/attention.yaml"},
  "position": {"line": 1, "character": 5},
  "newName": "OCF-FND-099",
  "offset": 0,
  "limit": 100
}
```

Use a real local document URI and a position on its identifier. Results are
`PROPOSED — NOT IMPLEMENTED`; they report collisions and pagination. Reference
scope includes indexed configuration scalars/keys and literal Python source
occurrences. Dynamic constructors are not evaluated. Local/composed event
renames require composition-aware marker review and are rejected by this preview.
Approval, compatibility aliases, generated outputs, localization and recorded
markers remain part of a separate explicitly authorized migration.

`ocf/indexStatus` reports roots, refresh counts and measured last-index duration.
An unchanged index avoids re-parsing, while saved stat changes and buffer changes
invalidate it. No performance claim is inferred from these counters.

## Boundaries and verification

- Local file URIs and at most eight explicit contained workspace roots; symlink
  targets and inherited file reads must remain within the selected root.
- At most 2 MiB per document, 30,000 expanded representation nodes, depth 64,
  1,500 indexed files and 100 open overlays per root. Inheritance has a 32-read
  budget per analysis; debounce is configurable from 0 to 1,000 milliseconds.
- Index only known metadata folders, session plans and direct Python sources in
  `scripts/ocf_tools`, `scripts/tools` and `tests`. Private voice profile metadata
  under `.ocf-work/cache/voices/profiles` may be resolved locally. Reference
  corpora, audio payloads, models, caches and build trees are not broadly indexed.
- No shell execution, HTTP listener, rendering, dataset processing or filesystem
  writes. The server never imports indexed Python files.
- Protocol tests launch the actual optional server and exercise framing,
  initialize/shutdown, unsaved diagnostics, navigation, completion, containment
  and read-only previews. Native editor UI behavior needs client-side testing.

```bash
python -m pytest tests/test_authoring.py tests/test_lsp_protocol.py
python scripts/ocf.py validate --all --json
```

The second command retains ordinary repository validation and provides structured
CLI issues. See [development](AGENT_DEVELOPMENT.md), [MCP](MCP.md) and
[documentation navigation](README.md) for the complementary interfaces.
