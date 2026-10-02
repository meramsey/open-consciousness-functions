# Authoring / content / platform foundation baseline

Audio checkpoint: `d838290` (following `b65f4c5`, `995dc24`, `b233575`).
Baseline suite:366 passing tests; `make check`0errors/7warnings, fresh indexes;
Markdown links and whitespace passed. TD-001 retains15 inherited ruff findings.
The local default Python is3.9.6 despite the declared supported minimum3.11:
local passing results are not a claim of supported-platform certification.

Reviewed boundaries: schemas first; function metadata separate from commands,
localized semantic narration, stage composition, measured voice timing, cues and
DSP; indexes generated from YAML; optional engines invoked through public CLI.
Authoritative docs reviewed: `AGENTS.md`, `CONTRIBUTING.md`, architecture,
authoring/narration, semantic sessions, localization, audio standard, user guide,
roadmap, schemas, voice/build/CLI/test entrypoints and build tooling.

The main architecture is retained. Several older status paragraphs are stale:
stage composition and semantic cue bindings are shipped, cue playback is not;
semantic DSP is now shipped; dedicated `ocf preparation` remains unshipped.
Function Installation and Routine Preparation final narration remain unauthored.
The function index preserves all55 mappings but lacks rich session/locale/voice
capability discovery. CI currently tests Python3.11/3.12 on Linux only.

Known portability limits requiring work: stdlib WAV_EXTENSIBLE support differs
by Python version; external engines and model locations vary by OS; repository
data resolution uses source-layout paths and needs an installed-package audit.
No macOS/Windows run has been performed here. No container/bootstrap/user-audio
implementation is claimed by this baseline. Coverage policy must distinguish
unit-only coverage from the existing combined test suite.

Corpus location resolves to repository-relative `references/HumanPlusTranscripts/`
in this environment (not an existing filesystem-root `/references/` directory).
Inputs are untracked operator reference files. Do not edit or commit them.
`ReusablePrompts/` is unrelated pre-existing untracked user work and is preserved.
