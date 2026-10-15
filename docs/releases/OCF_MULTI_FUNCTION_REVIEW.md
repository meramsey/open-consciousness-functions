# Representative multi-function audio review

The actual bindings for Recall (OCF-COG-006), Circulation (OCF-BOD-002),
Think Fast (OCF-COG-007; cognition in the catalog), and Sleep Easy (OCF-SLP-005)
all explicitly select the shared complete locked template. Each validated four
body passes, continuous default Focus 10, Focus 11 programming, return to
Focus 10 and a waking-return stage. No category name selected a different ending.
Function-specific alternatives now require explicit validated overrides;
none were automatically applied to these canonical bindings.

## Real short excerpts

`audio review-sessions` synthesized the first two complete sentences of each
function's opener/body/closer using Piper OCF-VOICE-0002. This is exact sentence
selection for review, not narration editing or a complete session:

- Circulation: 47.406 s.
- Recall: 45.746 s.
- Think Fast: 41.311 s.
- Sleep Easy: 47.337 s.

WAVs and comparison metadata are local under
`.ocf-work/renders/category-review-20261015T121925-cfc1d8a6/`.
These excerpts are speech-only; they do not claim DSP verification.

## Bounded full-session sample

One full Recall Piper/Farfield render completed in approximately 9 min 26 s.
Persistent job: `37658b35b64b491da440497b2d7e93e9`.
Duration: 2,298.051 s (38:18.051), stereo 44.1 kHz, 37 spoken segments,
765.054 s measured speech, zero clipped samples. Background continuity/state
windows and artifact checksums passed the renderer's checks. Speech cache:
39 hits, 146 misses, zero invalidations/bypasses. Human listening approval
remains unset. This run uses the locked default, not a newly approved variant.

Output directory beneath `.ocf-work/renders/auditions/`:
`OCF-COG-006-en-US-OCF-VOICE-0002-complete-session/OCF-COG-006-20261015T121951-5aa80f3f`.
`ocf_verify_audio` independently rechecked all published artifact hashes/sizes.

## Native OpenCode cancellation

A separate native OpenCode MCP run explicitly started Sleep Easy job
`32f308af723b4ed7b40bf7edba52b92b`, requested cancellation, polled terminal
`canceled`, and retrieved the result. No completed session was claimed for
that canceled job. Retained diagnostics remain local. No unbounded render batch
or human editorial/listening approval was performed.
