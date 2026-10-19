# Approved Options spoken successor

The user explicitly approved **Plus Options** for `OCF-COG-005`, retaining display
`PLUS-OPTIONS` and stable primary identity `OCF-CMD-COG-005-PRIMARY`. The former
**Plus Options Choices** remains discovery-only historical vocabulary. No
secondary command is introduced; procedures, modes, persistence and behavior
are unchanged.

The immutable [successor ledger](../function-content/editorial/options-001.json)
retains exact checkpoint files, predecessor raw and resolved speech, all changed
resource hashes, generated plan dependencies and the other 175 protected hashes.
Two body occurrences and one closer occurrence change through `{{ cue.primary }}`;
the opener and all unrelated resolved narration are byte-identical. Old narration
notes retain their historical review context; this successor records the new
decision separately. Changed resource versions are body 1.2.0 and closer 1.3.0.

`options_successor.py` verifies the current files and the explicit approved speech
delta before projecting the exact predecessor for older structural and editorial
verifiers. The old ledgers, baselines and engineering locks are not rewritten.
Baseline 006 and audio defaults 009 succeed baseline 005 and defaults 008. Only
the Options narration dependency changes in the lock; Focus DSP and pacing stay
identical. The new lock digest requires regeneration of production plans.

The one-shot `scripts/tools/create_options_successor.py` uses the pinned
`e4226aac3feac72d62049314f807175175717a48` checkpoint, refuses changed inputs and
refuses to overwrite existing successor evidence. It is not a generic rebaseline
or candidate-approval command. Future approved edits require a new explicit
versioned successor with their own scope and predecessor evidence.

Normal resolved text fingerprints reject old Options recordings, including hybrid
sources with TTS fallback. Speech cache keys change with resolved text. Existing
recordings and audio artifacts are retained; no old speech is relabelled. Re-record
changed speech and validate exact bindings before rendering. This editorial cue
approval does not establish listening or finished-session release approval.

```bash
python scripts/tools/check_hplus_narration_integrity.py
python scripts/ocf.py functions preview OCF-COG-005 --locale en-US
python scripts/ocf.py functions lookup 'Plus Options Choices' --json
```
