# Brand, voice and multi-function milestone baseline

Verified start: `ffbcec5f4bfd5d4e2a07a9d9bcab039fc4166bbb`, synchronized
`main`. Existing untracked reference/prompt directories were preserved.
The catalog has 55 functions and 97 structured command records; 55 en-US
source plans and the shared engineering lock remain authoritative.

## Native OpenCode verification

OpenCode 1.18.35 connected to the existing stdio server using the project-local
launcher in `.opencode/opencode.json`. `opencode mcp list` reported connected.
A bounded headless run using the discovered free `opencode/mimo-v2.6-flash-free`
model exercised overview, function/default/plan lookup, command validation,
focused test start/status/result and audio preflight. The test job returned
11 passed, 0 skipped. Provider-reported cost was zero for that run. Raw events
remain in `.ocf-work/logs/opencode-mcp-native.jsonl`; no reference corpus was
read or transmitted. The model's prose summary omitted one repetition group;
the authoritative tool response correctly reported two programming plus two
sleep passes. Tool results, not agent paraphrases, are the verification record.

The existing SDK integration additionally verifies resource/prompt discovery.
Native Claude Code/Codex interfaces were not exercised. Restart OpenCode after
editing configuration. The launcher chooses the checkout's `.venv` interpreter
on POSIX/Windows; no globally installed OCF/MCP package is required.

## Representative functions and local capabilities

- OCF-COG-006 Recall: cognition.
- OCF-BOD-002 Circulation: body.
- OCF-COG-007 Think Fast: cognition in the actual catalog.
- OCF-SLP-005 Sleep Easy: sleep.

All four currently bind the same complete locked template explicitly. Ending
and repetition policy must come from those bindings, not their category names.

Local GPU: NVIDIA RTX 3060 Laptop, 6 GiB VRAM. Python environment has no Torch
training stack or user-supplied authorized recording dataset. Existing Piper
inference is available. No cloning/training success or listening approval is
claimed. Private datasets/models remain outside committed runtime assets.
