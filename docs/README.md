# Documentation map

Start with [the project README](../README.md). Pick one workflow rather than
loading the entire documentation tree:

- Author a function: [lifecycle](FUNCTION_LIFECYCLE.md), then
  [source-first narration](SOURCE_FIRST_AUTHORING.md).
- Translate: [localization](LOCALIZATION.md) and [locale packs](../locales/README.md).
- Plan and audition: [bulk sessions](BULK_SESSIONS.md), then
  [audio pipeline](AUDIO_PIPELINE.md).
- Choose a voice: [community voices](COMMUNITY_VOICES.md).
- Import/record/compare private voices: [voice workflows](VOICE_WORKFLOWS.md).
- Use existing audio as speech: [recorded narration](RECORDED_NARRATION.md),
  including complete marked stems; mix sources with [hybrid narration](HYBRID_NARRATION.md).
- Inspect cloning support/profile portability: [voice capabilities](VOICE_CLONING.md).
  Prepare external recording imports: [training datasets](VOICE_TRAINING.md).
- Brand, UI themes and album covers: [original candidates](BRANDING.md).
  The supplied Cosmic Path 0.3.0 kit has an offline comparison gallery and
  SHA-256 import verification; it remains a human-review candidate.
- Configure intentional session variants: [override precedence](SESSION_OVERRIDES.md).
- Understand state audio: [semantic DSP](SEMANTIC_DSP.md) and
  [background audio](../audio/background/README.md).
- Package: [verified releases](AUDIO_PIPELINE.md#final-release-packages).
- Develop: [agent guide](AGENT_DEVELOPMENT.md), [testing](TEST_COVERAGE.md),
  [contributing](../CONTRIBUTING.md).
- Automate: [local MCP and jobs](MCP.md), with the CLI as the fallback.
- Edit YAML/JSON with diagnostics and navigation: [optional OCF LSP](LSP.md).
- Find checked CLI/MCP/schema examples: [interface library](../examples/README.md).

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
