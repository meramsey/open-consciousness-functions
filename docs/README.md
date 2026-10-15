# Documentation map

Start with [the project README](../README.md). Pick one workflow rather than
loading the entire documentation tree:

- Author a function: [lifecycle](FUNCTION_LIFECYCLE.md), then
  [source-first narration](SOURCE_FIRST_AUTHORING.md).
- Translate: [localization](LOCALIZATION.md) and [locale packs](../locales/README.md).
- Plan and audition: [bulk sessions](BULK_SESSIONS.md), then
  [audio pipeline](AUDIO_PIPELINE.md).
- Choose a voice: [community voices](COMMUNITY_VOICES.md).
- Understand state audio: [semantic DSP](SEMANTIC_DSP.md) and
  [background audio](../audio/background/README.md).
- Package: [verified releases](AUDIO_PIPELINE.md#final-release-packages).
- Develop: [agent guide](AGENT_DEVELOPMENT.md), [testing](TEST_COVERAGE.md),
  [contributing](../CONTRIBUTING.md).
- Automate: [local MCP and jobs](MCP.md), with the CLI as the fallback.

`documentation-index.json` inventories tracked Markdown, schemas, CLI help and
wizard source. It records content fingerprints, references, audiences and
machine-audit findings. Historical research, release checkpoints and draft
designs are retained as history; they do not override current commands or
constitute current verification. A machine inventory is not a claim of human
semantic review of every document.

Regenerate with `python -m ocf_tools.doc_inventory` after editable installation,
or `PYTHONPATH=scripts python -m ocf_tools.doc_inventory` on POSIX. Use `--check`
to verify freshness. `workflows.json` is a compact, versioned navigation index
shared by CLI-facing developer tools and MCP prompts, not a second execution API.
