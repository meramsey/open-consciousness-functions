# Bulk session enablement baseline

Starting commit: `db74a9d1b5b85df496987b8d660b3ff5ec1bdd6f` on `main`,
verified equal to remote main. Tag: `ocf-bulk-session-baseline-20261015`.
Untracked `ReusablePrompts/` and `references/HumanPlusTranscripts/` were
preserved separately; they are not part of the committed checkpoint.

Inventory: 55 functions; 55 content bindings; 1 explicit narration plan and
complete default template (Sleep Easy); 54 without these bindings. All 55
`audio.script_status` values are `approved`; all 55 specification
`human_review` values are `required`. There are 10 session templates, 1 pacing
profile, 4 DSP profiles, 1 audio implementation and 3 voice presets. Locale
packs contain 841 en-US and 33 Spanish resources.

The 39 available / 16 unavailable split comes from
`legacy.source_availability`, counted by `validate_legacy_invariants` in
`scripts/ocf_tools/validators.py`. It describes historical source availability,
not missing modern narration or a TTS validation failure. The 16 unavailable
records remain planned reimplementation targets. No source status is migrated.

Linux, Python 3.12.3; pytest 9.1.1, PyYAML 6.0.3, jsonschema 4.26.0,
Ruff 0.17.0, numpy 2.5.4, scipy 1.18.1, soundfile 0.14.0.
Baseline `pytest --durations=30`: **1253 passed, 2 skipped, 552.86 s**;
wall clock 553.32 s; maximum RSS 1,224,140 KiB (GNU time, not aggregate
concurrent-process memory). Raw diagnostics remain in
`.ocf-work/logs/bulk-baseline-pytest.log`.

Slowest work: real background mix 40.94 s; validation CLI 31.67 s;
deterministic index generation 31.59 s; timed-document validation 31.16 s;
index freshness/header checks about 16 s each. Existing markers distinguish
isolated unit contracts from repository integration, audio integration,
external tools, end-to-end and platform tests. Unit subprocess prohibition
remains enforced.

Starting GitHub workflows all succeeded:

- [test](https://github.com/meramsey/open-consciousness-functions/actions/runs/38670525422)
- [lint](https://github.com/meramsey/open-consciousness-functions/actions/runs/38670534058)
- [validate](https://github.com/meramsey/open-consciousness-functions/actions/runs/38670525359)
- [generated-index-check](https://github.com/meramsey/open-consciousness-functions/actions/runs/38670525394)
