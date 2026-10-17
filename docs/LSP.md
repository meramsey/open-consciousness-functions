# Optional OCF language server

OCF supplies a local stdio language server for YAML and JSON authoring. It uses
the same JSON Schemas, command validators, locale pack loader and template,
pacing and theme inheritance services as the CLI. Unsaved documents are overlays;
the server does not write them. This is an OCF data server, not a Python server.

## Install and start

Embedded [cue symbols](SYMBOLIC_CUES.md) in declared narration templates use the
same resolver as runtime preview. Completion/hover/definition and diagnostics
observe unsaved function and locale buffers. Definitions point to the owning
function's source spoken field; no server or permission reconfiguration is needed.

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

For an unactivated checkout, `python3 scripts/start_ocf_lsp.py --stdio` selects
that checkout's `.venv/bin/python` (POSIX) or `.venv/Scripts/python.exe` (Windows).
The bootstrap can run on an older Python, but the selected virtual environment
must use Python 3.11+. It fails with an installation hint rather than falling back
to a system interpreter. On Windows, use `python scripts/start_ocf_lsp.py --stdio`
if the bootstrap executable is named `python` instead of `python3`.

## OpenCode project integration

The authoritative project settings are in `.opencode/opencode.json`. They retain
MCP and watcher settings and register custom server `ocf` for `.yaml`, `.yml` and
`.json`, using `python3 scripts/start_ocf_lsp.py --stdio` with initialization
`diagnosticsDebounceMs: 150`. OpenCode runs it from the project directory; start
OpenCode with this checkout as its project. The launcher's location determines
the venv independently of shell activation. If Windows only provides `python`,
change just the command's bootstrap executable to `python`.

An LSP object also enables OpenCode's built-in servers. This project explicitly
disables `yaml-ls` and `biome` to avoid overlapping YAML/JSON ownership. Other
installed servers remain available. The project startup launcher suppresses
automatic LSP downloads. OCF's data server never handles `.py` files. The separate
`pyright` registration handles `.py`/`.pyi` using the optional setup below.

### Optional Python navigation with Pyright

Install into the existing project virtualenv, without upgrading other tools:

```bash
.venv/bin/python -m pip install -e ".[python-lsp]"
.venv/bin/python -m pip check
```

On Windows use `.venv/Scripts/python.exe`. The `python-lsp` extra pins
`pyright==1.1.408`. This is the community Python distribution/wrapper of
Microsoft's JavaScript Pyright, not a separate Python implementation. The wheel
includes the JavaScript server. It remains optional for ordinary OCF users and
independent of the OCF data-server `lsp` extra.

Node >=14 must already be on OpenCode's startup PATH. Installation here was
verified with Node 16.14.2; the development-tool CI job explicitly supplies Node
22. Neither OpenCode nor Node is upgraded by this setup. The project launcher
`python3 scripts/start_ocf_python_lsp.py --stdio` first selects the checkout's
venv, resolves its installed Pyright bundle, then launches Node on
`pyright/dist/langserver.index.js`. It never invokes the wrapper's Node/npm
bootstrap and cannot install/download runtime components at startup. Missing
Pyright, its bundled server, or Node produces an actionable stderr error.
The Node server runtime and the Python environment being analyzed are distinct.

POSIX uses exec for process replacement. Windows inherits the protocol handles
through a waiting child process so venv redirectors preserve stdin/stdout and the
actual server exit status. Protocol shutdown is checked on each native CI platform.

The existing `pyright` server ID is overridden rather than duplicated. Its custom
command is needed because `.venv/bin` need not be on an unactivated startup PATH;
the router's PATH is preserved. Windows venv selection uses `Scripts/python.exe`
through the same launcher helper. Where the bootstrap is named only `python`,
change the command's first element just as for the OCF data-server launcher.

`[tool.pyright]` in `pyproject.toml` is the sole project analysis configuration:

- `typeCheckingMode = "basic"`; no previous stronger policy existed. This is
  developer feedback, not a new repository-wide type-check CI gate.
- `pythonVersion = "3.11"` preserves the supported minimum. It does not assert
  that the developer interpreter is 3.11; the current venv uses Python 3.12.
- Relative `venvPath = "."` and `venv = ".venv"` select this checkout's packages
  portably. No Linux-only interpreter path is committed.
- `extraPaths = ["scripts", "tests"]` match the real `ocf_tools` package and test
  helper import layout. Editable installation alone is not assumed sufficient
  for static import resolution.
- Real source/tests are included; scratch, venvs, build/dist, node_modules,
  rendered audio, bytecode and coverage output are excluded from discovery.
  Exclusions are not filesystem security: imported dependencies remain navigable.

OpenCode's `python.analysis.diagnosticMode = "openFilesOnly"` is delivered through
`workspace/configuration`, not merely assumed to be an arbitrary initialize
option. The 1.18.35 client also supplies `workspaceFolders`, which Pyright needs
for reliable project-config discovery. Direct protocol tests emulate those
messages and verify config requests, venv resolution, cross-file navigation and
unsaved diagnostic updates/clearing. Cross-file analysis remains available while
closed-file diagnostics are not published. Ruff retains formatting/lint ownership;
startup performs no edits, formatting or import organization.

Verification of the existing `complete_session.py` found five basic-mode
diagnostics: optional pacing/query arguments and `os.sys` member accesses. These
are separate existing code-quality findings, not a claim that the entire project
is type-clean. No blanket ignores, fake stubs or source exclusions were added.
Missing optional audio/SDK imports in a lean environment should be distinguished
from an incorrectly selected venv; install only the extras needed for that work.

After changing LSP registration, a running OpenCode process needs an operator
restart through `scripts/start_ocf_opencode.py --session SESSION_ID`. Bounded fresh
`debug agent NAME --tool lsp --params JSON` processes can verify Python operations
before that restart without making model calls. Native tool registration in a
fresh process does not retrofit the unchanged interactive process. Do not restart
the separate server service to activate Python in a standalone TUI.

Troubleshooting: check the resolved `lsp.pyright` command and extensions, Node on
the actual startup PATH, the pinned venv package, and Pyright's project-config
discovery. Temporarily set `python.analysis.logLevel` to `Trace` in a diagnostic
client to inspect search paths/configuration requests, then retain normal logging.
Do not add a competing `pyrightconfig.json`; it would override the TOML policy.

```bash
python -m pytest tests/test_ocf_launch.py tests/test_python_lsp.py tests/test_ocf_lsp_launcher.py tests/test_lsp_protocol.py
```

The real Pyright protocol tests skip when this optional tool/Node is absent in an
ordinary environment. The dedicated Python-LSP CI job installs it explicitly and
requires those tests on Linux, macOS and Windows; missing tooling fails that job.

### Start a new OpenCode process

From the checkout, without activating a shell environment:

```bash
python3 scripts/start_ocf_opencode.py --continue
```

On POSIX, `./scripts/start_ocf_opencode.py --continue` is equivalent. On Windows
use `python scripts/start_ocf_opencode.py --continue`. All supplied arguments are
passed as individual arguments to the existing `opencode` on PATH. No executable,
router, provider, credential, network binding or authentication is replaced.
Use `--session SESSION_ID` to resume a specific conversation; diagnostic tool
runs can become the most recent session, so do not assume `--continue` selects
the conversation you intend.

The launcher sets `OPENCODE_EXPERIMENTAL_LSP_TOOL=true` for the new OpenCode
process, and `OPENCODE_DISABLE_LSP_DOWNLOAD=true` to avoid incidental downloads.
It uses the existing OCF workspace resolver for subprocess temporary/cache paths
and preserves the rest of the environment. The specific LSP flag is required by
[OpenCode 1.18.35's tool registry](https://github.com/anomalyco/opencode/blob/v1.18.35/packages/opencode/src/tool/registry.ts)
and [runtime flags](https://github.com/anomalyco/opencode/blob/v1.18.35/packages/opencode/src/effect/runtime-flags.ts).
Setting it in a temporary tool shell, LSP subprocess or MCP environment does not
enable the tool in an already-running parent OpenCode process.

Project permission `lsp: allow` grants the native read-only LSP operations.
The `ocf-investigator` and `ocf-test-reviewer` agents explicitly allow LSP while
retaining their shell, edit, delegation and web denials. The OCF server advertises
no automatic rename or workspace-edit operation.

For an attached client, the environment belongs to the persistent `serve`/`web`
backend. A new conversation or reconnect alone does not update that process.
Prepare its positively identified user-owned startup configuration, then let the
operator restart that backend later with the same arguments/authentication.
Do not restart a backend or interrupt active jobs during setup. A separate
standalone TUI can use the project launcher independently; it does not alter an
already-running service.

### Bounded checks and troubleshooting

Check the installed version's help before using these commands. For OpenCode
1.18.35, these are short-lived diagnostics and make no model calls:

```bash
python3 scripts/start_ocf_opencode.py debug config
python3 scripts/start_ocf_opencode.py debug agent ocf-investigator
python3 scripts/start_ocf_opencode.py debug lsp diagnostics "$PWD/functions/sleep/sleep-easy.yaml"
python3 scripts/start_ocf_opencode.py debug lsp diagnostics "$PWD/schemas/function.schema.json"
python3 scripts/start_ocf_opencode.py debug lsp document-symbols "$(python3 -c 'from pathlib import Path; print(Path("functions/sleep/sleep-easy.yaml").resolve().as_uri())')"
```

Bound diagnostic processes externally (for example, `subprocess.run` with a
timeout); do not start a bare stdio server in a terminal and wait indefinitely.
Keep output private: `debug config` may contain provider secrets. Inspect only its
LSP subsection and relevant permissions, and redirect large JSON directly to a
private file rather than relying on buffered CLI output over a pipe.

`debug agent NAME` can verify `tools.lsp` in a fresh process without a model call.
The installed version also supports `debug agent NAME --tool lsp --params JSON`
for a direct read-only operation; it creates a diagnostic session in history.
For example, `goToDefinition` on Sleep Easy line 45, character 7 resolves its
function-body resource to `locales/en-US/hplus-OCF-SLP-005.yaml`. Native tool
positions are one-based. Programmatically derive file URIs with `Path.as_uri()`;
do not concatenate unescaped filesystem paths into `file://` strings.

An empty LSP status before opening a matching document means **not yet started**,
not necessarily disabled. `lsp: false`, `disabled: true`, environment-injected
configuration, a wrong project directory, a missing bootstrap executable or an
unavailable optional extra can actually prevent a connection. `debug config`
shows the resolved precedence, while document symbols, a cross-file definition
and an invalid unsaved-buffer diagnostic establish real protocol behavior.
Empty diagnostics alone are insufficient. Fresh-process tool verification does
not add a tool to the unchanged current session; interactive verification remains
an operator check after the manual restart.

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
