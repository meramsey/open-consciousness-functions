# Optional local MCP and developer jobs

OCF's CLI, schemas, wizards and application services remain authoritative.
The optional MCP adapter provides compact discovery, bounded diagnostics and
asynchronous jobs; it does not implement another renderer. It uses the official
Python MCP SDK (`mcp==1.28.1`) over **stdio only**, without a network listener,
authentication service, database or paid API. This developer integration requires
a source checkout. Core OCF works without the SDK.

## Install and start

From the repository root, using Python 3.11+ in your local environment:

```bash
python -m pip install -e '.[mcp]'
python scripts/ocf.py mcp
```

The startup command speaks MCP on stdin/stdout; use a client rather than typing
ordinary commands into it. SDK logs go to stderr. The equivalent installed entry
is `python -m ocf_tools.mcp_server`. Development/test dependencies remain a
separate `python -m pip install -r requirements-dev.txt` installation.

CLI fallback uses the exact same adapters and job store:

```bash
python scripts/ocf.py dev ocf_project_overview
python scripts/ocf.py dev ocf_get_function --arguments '{"function_id":"OCF-FND-002"}'
python scripts/ocf.py dev ocf_get_workflow --arguments '{"name":"render-audition"}'
python scripts/ocf.py dev ocf_get_session_plan --arguments '{"function_id":"OCF-SLP-005","stages":true}'
python scripts/ocf.py dev ocf_validate_function --arguments '{"function_id":"OCF-FND-002"}'
python scripts/ocf.py dev ocf_run_tests --arguments '{"paths":["tests/test_loader_contracts.py"]}'
```

JSON quoting above is for POSIX shells; in PowerShell use the same single-quoted
JSON, and in cmd.exe escape inner double quotes or use an MCP client.

## Tool contract

- `ocf_project_overview`, `ocf_list_functions`, `ocf_get_function`,
  `ocf_get_schema`, `ocf_get_workflow`, `ocf_get_audio_defaults`,
  `ocf_get_session_plan`: read-only discovery. No narration text by default.
- `ocf_validate_function`, `ocf_validate_commands`, `ocf_validate_locale`:
  existing validators with paginated diagnostics. Locale checks explicitly
  include cross-pack invariants. `ocf_final_validation` starts full validation.
- `ocf_select_tests`: a conservative dependency map, not a correctness proof.
  Voice/cache/artifact-name edits have focused mappings; unknown/shared-schema,
  template and locale changes require an explicit full-suite request.
- `ocf_run_tests`: explicit paths/node IDs or `full=true`; one or two workers.
  No arbitrary pytest options, scripts, shell fragments or Python evaluation.
- `ocf_check_generated`: checks source plans and generated indexes as a job;
  `generate=true` deliberately regenerates plans through the existing API.
- `ocf_plan_audio`: selected-voice and engine preflight; estimates are explicitly
  word-rate estimates, not measured duration or financial cost.
- `ocf_start_audio_render`: explicit single-function start, verified bulk-render
  resume/cache behavior, unique output paths. It never selects all functions.
- `ocf_inspect_narration_sources(function_id, manifest, locale, offset, limit)`:
  read-only source coverage through the existing narration resolver. The manifest
  is a workspace-relative JSON/YAML file, at most 2 MiB. Event summaries omit
  narration text and paginate by event; semantic units have compact source counts.
- `ocf_validate_recordings(function_id, manifest, locale, idempotency_key)`:
  explicit `narration-validate` job. Validates the whole chosen source manifest,
  including unselected catalog checksums and selected text bindings, then measures
  each selected original once. Results include compact PCM metrics, source counts,
  and paginated diagnostics. Originals are preserved; no transcript verification,
  processing, listening approval or release approval is inferred.
- `ocf_start_narration_render(function_id, manifest, locale, voice, pacing,
  idempotency_key, mix_profile)`: explicit `narration-render` job calling the existing complete
  session renderer with `narration_sources`. Voice is optional for recorded-only
  rendering; an optional workspace-relative `mix_profile` selects explicit
  linked-stereo ducking/headroom/limiter processing and participates in job identity.
  Output is unique at `renders/jobs/<job-id>/` within the workspace;
  no output path or executable can be supplied through this tool.
- `ocf_inspect_voice_capabilities(probe_gpu=false)`: read-only local adapter and
  package metadata using the CLI capability service. No GPU query or torch import
  by default. Explicit `probe_gpu=true` uses the existing two-second NVIDIA query.
- `ocf_plan_voice_training(backend="piper", dataset=null)`: preserves backend-only
  calls and optionally checks a workspace-relative JSON dataset (at most 2 MiB),
  returning compact readiness/quality counts. GPU probing stays disabled here.
  Training remains unsupported until a verified adapter exists. Profile import
  remains the explicit `ocf voice import-profile` CLI workflow; MCP advertises no
  train, clone or profile-import start tool.
- `ocf_get_job_status`, `ocf_get_job_result`, `ocf_cancel_job`: persistent job
  lifecycle, bounded results and cooperative cancellation of owned processes.
- `ocf_verify_audio`: verifies contained artifact sizes/checksums against an
  audition manifest; codec decode happens during the renderer's publication.
- `ocf_package_release`: existing release service; artwork must be supplied
  under the workspace. Defaults to preview; real packaging requires
  `confirmed=true`. A successful package does not infer rights clearance.
- `ocf_cache_diagnostics`, `ocf_cache_clean`: process counters/storage usage and
  explicit cleanup preview. Deletion requires `dry_run=false, confirmed=true`
  and only removes old, validly owned speech-cache entries.

Pagination defaults to 10 entries (diagnostics 20), maximum 50. `offset`,
`next_offset`, `total` and `truncated` make omission explicit. Function field
selection and `previous_hash` support changed-only responses. Responses exceeding
32 KiB request a narrower scope instead of dumping large data. Job results over
16 KiB return a local artifact reference. Full narration/audio and raw environment
variables are never discovery output. Error responses include codes and actions.

Resources: `ocf://overview`, `ocf://functions`, `ocf://schemas`,
`ocf://audio-defaults`, `ocf://documentation`, `ocf://validation`,
`ocf://artifacts`. The `workflow` prompt accepts the versioned workflow names in
`docs/workflows.json`; it links canonical guides rather than duplicating them.

## Job lifecycle and limits

Media extensions reuse the same executor: `ocf_generate_artwork_preview`,
`ocf_start_voice_audition`, and `ocf_validate_voice_dataset` return persistent
job IDs and artifact references, never binary data. `ocf_list_artwork_themes`,
`ocf_inspect_brand`, `ocf_validate_theme`, `ocf_list_voice_profiles`,
`ocf_plan_voice_training`, and `ocf_inspect_release_artwork` provide bounded
metadata. Training planning reports unsupported status; no unverified training
start tool is advertised. MCP artwork jobs select registered themes; custom
file/font rendering remains an explicit CLI workflow. Dataset and narration
manifests must be inside the workspace. Job identities hash the manifest and
every referenced recording's actual bytes (including unselected recordings,
dataset WAVs, consent records when present, and `session_stem.file` when declared).
Missing dataset WAVs have explicit missing identities, so recording them after
enqueue also invalidates the request. Execution checks identity again and fails
changed inputs instead of implicitly rendering or validating newer audio.

Records/logs live under `.ocf-work/logs/jobs/<job-id>/`; cache/audio remains
under the standard workspace. `OCF_WORK_DIR` honors the existing validated
override. One executor and at most eight queued/running jobs bound resource use.
Each job has state, creation/start/completion timestamps, phase progress,
heartbeat, log and result paths. Jobs are separate processes and survive an MCP
client disconnect. The execution process owns the single-executor lease and
maintains its heartbeat even if its supervisor is interrupted. A six-hour
supervisor limit stops the owned process tree. If the supervisor is lost,
an already-running service may finish before cancellation is observed at its
service boundary; it retains the executor lease meanwhile.
Captured execution logs are capped at 4 MiB with explicit truncation metadata;
output continues to be drained. At 256 retained job records, new starts refuse
until the operator archives reviewed records. No automatic history deletion occurs.

Starts validate an explicit operation allowlist and typed fields. Paths are
contained, normalized and checked against symlink escapes; no shell is used.
Concurrent duplicate active requests return the existing job. An explicit
idempotency key returns its prior job, including failures, and rejects changed
inputs. Test collection/configuration and canonical runtime data are included
in content identities; queued work refuses inputs changed since enqueue.
Retrying a failure requires a deliberate new start/key. Completed render
resume rechecks every artifact before reuse. Interrupted/stale workers report
failure rather than restarting automatically. Inspect retained artifacts before
retrying. Cancellation is requested first; `canceled` appears only after the
worker stops the owned process tree. Completed jobs are never reclassified as
canceled. No tool overrides a client's host permission policy.

Speech cache is content-addressed, PCM/checksum-verified and capped at 2 GiB;
the separately bounded DSP stem cache uses verified engine/preset/seed/duration
identity and is selected by `ocf_cache_clean` with `kind="dsp"` (default is `tts`).
new writes bypass at capacity. No automatic cache eviction or workspace cleanup
occurs. A cache entry preserves one realized waveform; it does not assert that
an unseeded TTS backend produces identical samples on regeneration. Parser caching
is process-local, bounded to 128 small exact-content
entries, with deep copies on return; files are still read so changed inputs
invalidate naturally. No mutable catalog or validation-success singleton exists.

## Client configuration

The shapes below were checked against the official client documentation. They
are setup examples, not claims that all three client applications were run.
Launch clients from the repository root and use its virtual-environment Python.
On Windows replace `.venv/bin/python` with `.venv/Scripts/python.exe`.
No configuration below grants blanket tool permissions.

OpenCode project `opencode.json` (merge with your existing configuration):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ocf": {
      "type": "local",
      "command": [".venv/bin/python", "scripts/ocf.py", "mcp"],
      "enabled": true
    }
  }
}
```

Quit and restart OpenCode after changing configuration. Set `enabled: false`
to disable this server; existing CLI workflows remain available.

The repository now supplies a working project-local entry in
`.opencode/opencode.json`: `python scripts/start_ocf_mcp.py`. The launcher
selects `.venv/bin/python` or `.venv/Scripts/python.exe`. Native OpenCode
1.18.35 connection and tool/job execution were exercised; see the
[milestone baseline](releases/OCF_BRAND_VOICE_BASELINE.md). This is separate
from SDK protocol verification and does not claim native Claude/Codex testing.

Claude Code, from the checkout root:

```bash
claude mcp add --transport stdio --scope project ocf -- .venv/bin/python scripts/ocf.py mcp
claude mcp get ocf
```

Codex project `.codex/config.toml`:

```toml
[mcp_servers.ocf]
command = ".venv/bin/python"
args = ["scripts/ocf.py", "mcp"]
enabled = true
```

Use `/mcp` or the client's server inspector to discover tools. If startup fails,
check the working directory, interpreter, editable installation and SDK extra.
If a tool reports a missing optional engine, use `voice doctor`/`doctor`; OCF
does not install engines/models at server startup. Keep tokens and private
environment values out of committed client configuration.

Authoritative syntax references:

- [Official Python SDK v1.28.1](https://github.com/modelcontextprotocol/python-sdk/tree/v1.28.1)
- [OpenCode configuration schema](https://opencode.ai/config.json)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Codex MCP](https://developers.openai.com/codex/mcp)
