# Four-candidate editorial approval

The user reviewed Manifest, Dissolve, Intuition and Clear Zone in that order,
answered **1 — Approve full draft** for each, then explicitly confirmed
**Confirm implementation** for the consolidated batch. The
[immutable successor ledger](../function-content/editorial/approved-candidates-001.json)
pins the exact four candidate snapshots, source checkpoint, verbatim decisions,
predecessor files, live-file hashes and resolved speech hashes. This is editorial
approval, not historical authentication, scientific validation, listening or
finished-session release approval.

## Implemented scope

- Manifest (`OCF-EXP-001`): opener 1.2.0, body 2.0.0 and closer 1.3.0 replace
  the active predecessor through explicit successor evidence. The reviewed
  `Plus Manifest` cue, activation procedure and existing lifecycle metadata stay.
- Dissolve (`OCF-EXP-003`): the exact supplied 1.0.0 narration and procedure are
  approved, retaining deliberate target selection and useful learning.
- Intuition (`OCF-EXP-006`): the supplied opener and new AI-authored body, closer
  and procedure are approved. Its collision-checked staged identity is registered;
  the staged definition and narration remain unchanged historical snapshots.
- Clear Zone (`OCF-EXP-005`): the exact supplied 1.0.0 narration and all three
  command identities are approved, including mutually exclusive overrides and
  the specified restoration conditions. No physical sensors or physiological
  control are implemented.

The [full inline review](EDITORIAL_CANDIDATE_REVIEW.md) shows the exact snapshot
templates and resolved speech, with current approval distinguished from original
draft notes. CLI/MCP discovery and LSP navigation use the registered function
authority. Display cues no longer render as `None` in the review.

## Integrity and planning

Only Manifest's three entries change within the historical 177-entry cohort;
the other 174 are byte-identical, including the approved Options successor.
The nine original-function entries are checked independently against their exact
approved snapshot speech. Baseline 007 succeeds baseline 006. Defaults lock 010
succeeds 009 with only the Manifest narration dependency updated. Profile IDs,
DSP, pacing, mixing, stage order and four body passes remain unchanged.

All 58 registered functions have validated source plans. This does not synthesize
audio. Old Manifest recordings fail normal text-fingerprint compatibility,
including hybrid sources with TTS fallback; originals are retained. Changed
resolved speech also changes synthesis cache identity. No existing recording is
relabelled as matching new speech.

The one-shot `scripts/tools/approve_editorial_candidates.py` is pinned to
`911dbd0f24618091e34e8a816275ab7eabbf97bb`, checks the presented hashes and refuses
existing successor evidence or an Intuition identity collision. It is not a
general promotion command. Future wording changes require new explicit approval
and a scoped successor; prior locks and supplied snapshots must not be rewritten.
