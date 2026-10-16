# Interface examples

Start with the [user guide](../docs/USER_GUIDE.md). This library connects public
interfaces to checked examples without silently running imports, wizards,
renders, deletion, training or packaging.

## Complete interface inventory

[`interfaces.json`](interfaces.json) is generated from the actual CLI parser,
MCP tool registry and resource/prompt declarations, workflow navigation, local
schemas and LSP method manifest. It includes:

- One **parser-only** argument vector per CLI leaf, including wizards. Required
  mutually exclusive options and argument choices are parsed. Optional flags
  appear in each command's usage; ask `ocf GROUP COMMAND --help` for details.
- One **signature/type-only** argument object per MCP tool. A read-only hint is
  discovery metadata, not permission to execute a call. CLI `dev` and MCP use the
  same argument checker and application services.
- Every registered MCP resource, the workflow prompt and all workflow selectors.
- Every schema, pointing either to a public example/fixture, an illustrative
  object in [`contracts.json`](contracts.json), or a runtime JSON command.
- Every OCF LSP method, with [client/protocol examples](../docs/LSP.md).

These checks do not prove that every operation has been executed. `YOUR_*`
arguments, zero hashes, arbitrary illustrative times and the placeholder date
are deliberately nonoperational. The contract bundle is **structural teaching
data**, never a source transcript, approved script, actual recording declaration,
measured stem, training dataset, registered function or release package. Rights,
consent and human review remain unknown/pending; no media is included. Copying a
bundle entry into a real workflow requires its actual provenance, content hashes,
speaker declarations, complete measured markers and relevant human decisions.

## Generate and verify

```bash
python -m ocf_tools.examples
python -m ocf_tools.examples --check
python -m ocf_tools.examples --check --execute-read-only
```

Use an editable core installation (`python -m pip install -e .`). Generation and
`--check` parse all leaf examples, check all tool argument contracts and validate
all static schema examples. Source and example fingerprints make drift visible.
The last command additionally executes a **fixed allowlist** of twelve read-only
discovery/planning/doctor examples and validates the three dynamic schema outputs.
It never dispatches generated placeholders. Doctor may report missing optional
tools without invalidating its report schema. CI runs these checks from a clean
checkout. No HTTP API is registered; stdio MCP and LSP are optional adapters.

## Useful workflows

### Discover, validate and plan without audio engines

```bash
python scripts/ocf.py capabilities --json
python scripts/ocf.py functions describe OCF-FND-002 --rich --json
python scripts/ocf.py validate --all --json
python scripts/ocf.py locale validate --locale en-US
python scripts/ocf.py audio eligibility OCF-FND-002
python scripts/ocf.py audio plan OCF-FND-002 --expand
python scripts/ocf.py narration sources OCF-SLP-005 --locale en-US
```

These inspect committed declarations. A source plan is not audio, source wording
is not approval, and source availability is not TTS eligibility.

### Author with explicit output and review

```bash
python scripts/ocf.py new function
python scripts/ocf.py new session-plan
python scripts/ocf.py build-index --check
```

The first two are **operator workflows**, not executed by the examples checker:
wizards can write records and plans after their normal prompts. Follow
[function lifecycle](../docs/FUNCTION_LIFECYCLE.md) and
[source-first authoring](../docs/SOURCE_FIRST_AUTHORING.md). Never treat proposed
command/identifier audits as permission to rename canonical or protected data.
Use the [read-only title–cue review guide](../docs/EDITORIAL_REVIEW.md) for the
complete source-pinned companion proposals and their evidence boundaries.

The session-plan wizard also has a fixture-backed **executed integration example**:

```bash
python -m pytest tests/test_workflow_examples_execution.py
```

It enters through the real CLI and prompts, composes through the authoritative
generator, and writes only to isolated fixture output. The example verifies
declining without writes, confirmed schema-valid output and shared fingerprints,
release approval remaining false, and refusal to replace a human-owned file
without partial publication. It needs no audio engine. This execution evidence
does not upgrade the new-function parser example or other operator workflows to
executed status.

### Recorded/hybrid speech, private voices and release artwork

Use [recorded narration](../docs/RECORDED_NARRATION.md) for exact event/resource
bindings and complete all-event stems; [hybrid narration](../docs/HYBRID_NARRATION.md)
for explicit fallback; [voice workflows](../docs/VOICE_WORKFLOWS.md) and
[datasets](../docs/VOICE_TRAINING.md) for private imports. Missing recording
coverage must fail rather than infer speech or silently select TTS.

[Session overrides](../docs/SESSION_OVERRIDES.md) documents function/CLI
precedence. [Branding](../docs/BRANDING.md) documents explicit-image and
explicit/implementation/function/default theme precedence. Artwork defaults to
Cosmic Dark; UI and documentation defaults are independent. Packaging requires an
eligible registered implementation and verified artifacts, and successful
packaging is not publication approval.

### Stdio automation and editor integration

```bash
python scripts/ocf.py dev ocf_get_function --arguments '{"function_id":"OCF-FND-002"}'
python scripts/ocf.py dev ocf_get_workflow --arguments '{"name":"plan-all"}'
python scripts/ocf.py lsp --capabilities
```

PowerShell quoting for JSON arguments differs from POSIX shells; the JSON values
in the inventory can also be passed directly by a client without a shell.
[MCP](../docs/MCP.md) explains explicit job starts, polling and cancellation.
[LSP](../docs/LSP.md) explains real incremental diagnostics and read-only rename
previews. Starting either stdio server waits for a protocol client; it is not a
one-shot health check.

## Known data distinction found during verification

The existing `function-content/hplus-review-selections.yaml` contains a historical
zero-line closer sentinel plus a `note` field that the current review-selection
schema does not accept. It is not used as a valid schema example. The contract
bundle demonstrates an explicitly missing selection without inventing a locator.
This is a retained editorial-data inconsistency requiring a deliberate source
review; the example checker does not change that file or relax its schema.
