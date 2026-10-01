# Narration migration inventory

Audit baseline: WIP checkpoint `b987946`. This inventory records dispositions;
it does not rewrite listener wording. Canonical narration authoring is gated on
approval of the semantic/stage/timing architecture.

## Dispositions

| Disposition | Meaning |
| --- | --- |
| KEEP | Preserve a correct representation or protected source record |
| REWRITE | Original OCF reusable wording requires a later standards-based rewrite |
| EXTRACT TO LOCALIZATION | Move reusable OCF wording/intent out of inline templates or code |
| FUNCTION-SPECIFIC | Remain owned by the particular function/contributor |
| DEPRECATED | Retain for compatibility but do not use as a new canonical default |

Multiple dispositions can apply to different parts of one file.

## Concrete inventory

| File / material | Disposition | Action after architecture approval |
| --- | --- | --- |
| `audio/templates/sessions/OCF-TPL-SESSION-LEARN-001.yaml` original bridge | REWRITE; EXTRACT TO LOCALIZATION | Replace unsupported-learning claims with original voluntary learning/rehearsal resources. Reuse semantic stages; retain slot contracts for compatibility. |
| Same template's twentieth-state/sleep arc | DEPRECATED as universal default | Keep the historical optional workflow available; do not require it for Prep Learning or every function. |
| `locales/en-US/narration.yaml` | KEEP resource architecture; REWRITE content where needed | Review imperatives, assumed outcomes, Focus explanations and opening/closing intent under the new standard. |
| `locales/en-US/functions.yaml` | KEEP parameterized command metadata; REWRITE reusable explanation where needed | Maintain canonical command identity; improve autonomy/rehearsal and function-purpose resources. |
| `OCF-TPL-SESSION-FOCUS-CYCLE-001.yaml` | KEEP keyed demonstration; EXTRACT TO LOCALIZATION already complete | Preserve the demo; do not describe it as full Preparation Learning. |
| `templates/audio-manifest.yaml` safety introduction | EXTRACT TO LOCALIZATION candidate | Provide a reusable resource when spoken; retain inline metadata compatibility. |
| `scripts/ocf_tools/prompts.py` safety-introduction default | EXTRACT TO LOCALIZATION candidate | Resolve a shared resource when generating canonical spoken content. The current field is metadata, not automatically rendered speech. |
| `audio/manifests/OCF-AUDIO-0001.yaml` safety introduction | KEEP historical artifact metadata | Do not rewrite a manifest/checksum to imply an existing master has changed. |
| `audio/scripts/attention.yaml` | KEEP, citation-only | Never rewrite source wording or promote it into OCF resources. |
| `OCF-TPL-SESSION-ATTENTION-001.yaml` | KEEP, reference-derived | Preserve imported/adapted provenance and compatibility; not a reusable original-narration source. |
| `audio/scripts/attention-ocf.yaml` | KEEP generated adapted artifact | Regenerate through composition when needed; never relabel OCF-authored. |
| `audio/slots/attention/focus11.txt` | FUNCTION-SPECIFIC | Contributor text stays verbatim; no automatic rewrite. |
| `locales/es/` | KEEP machine-draft test fixture | Not a reviewed translation; final resources are not mass-translated at this checkpoint. |
| Documentation/scaffold examples and test strings | KEEP technical examples | Do not turn operator documentation into experiential narration. |

## Statements explicitly marked for replacement

These are original-OCF placeholder statements in
`audio/templates/sessions/OCF-TPL-SESSION-LEARN-001.yaml`; no final replacement
is supplied here:

| Existing statement | Conflict |
| --- | --- |
| “This function is being installed beneath conscious effort.” | Implies involuntary or automatic installation |
| “Every word is received easily by your mind.” | Asserts an internal experience and guaranteed reception |
| “All that you have absorbed is being integrated beneath awareness.” | Implies automatic learning/integration beneath awareness |

## Terminology review

Setting-aside of distractions is a durable semantic concept. “Energy Conversion
Box” is a changeable listener-facing term, not a required schema identifier.
Focus 11 working-state practice is a durable concept; “Access Channel” is also
under terminology review. Existing compatible IDs remain valid.

All TBD decisions in the [narration standard](NARRATION_STANDARD.md) remain open.
The exact cue-design TODO in `TIMED_TRANSCRIPTS.md` remains unchanged.
