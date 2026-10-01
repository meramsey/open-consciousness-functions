# Narration migration inventory

Audit baseline: WIP checkpoint `b987946`. This inventory records dispositions;
it does not serve as a narration source. The architecture was approved through
`4093063`; Phase 8A supplied the original en-US Preparation Learning review
draft, editorially revised in Phase 8B and approved through Phase 8C as
**OCF Preparation Learning en-US RC1**.
Routine Preparation and Function Installation final wording remain gated.

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
| `audio/templates/sessions/OCF-TPL-SESSION-LEARN-001.yaml` original bridge | REWRITE; EXTRACT TO LOCALIZATION | Three automatic-learning statements repaired in Phase 8A using draft localized resources. Remaining bridge review is pending; slot contracts are retained. |
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

These original-OCF placeholder statements have been replaced in
`audio/templates/sessions/OCF-TPL-SESSION-LEARN-001.yaml` by localized draft
resources. The old quotations below are retained only as this migration record:

| Existing statement | Conflict |
| --- | --- |
| “This function is being installed beneath conscious effort.” | Implies involuntary or automatic installation |
| “Every word is received easily by your mind.” | Asserts an internal experience and guaranteed reception |
| “All that you have absorbed is being integrated beneath awareness.” | Implies automatic learning/integration beneath awareness |

Replacements in `locales/en-US/functions.yaml`:

- `function.learning.attend`: listener-selected attention and making sense of material.
- `function.learning.rehearse`: deliberate skill practice, recognition and repetition.
- `function.learning.reflect`: rest, later recall and intentional use.

The rest of the historical OCF-owned shell still requires a separately approved
review; this is not the final Function Installation rewrite. Imported Attention
wording and contributor slots were not rewritten.

## Preparation Learning review draft

`locales/en-US/preparation-learning.yaml` contains original draft resources,
bound only in `OCF-TPL-SESSION-PREP-LEARN-001`. Phase 8B condenses explanation
into practice, strengthens the learning count, and adds quiet time; it does
did not itself mark narration canonical; RC1 wording was subsequently approved.
Shared stages contain identities,
ordering and provisional pauses, not English. The routine and function-install
drafts do not automatically acquire the teaching narration.

See the [complete listener preview](drafts/preparation-learning.en-US.listener.md)
and [separate developer view](drafts/preparation-learning.en-US.developer.md).
Both are generated views, not alternate wording sources. “Focus Container” is
the replaceable display term used in this draft. No real translations, final
cue sounds or production audio have been created.

## Terminology review

Setting-aside of distractions is a durable semantic concept. “Energy Conversion
Box” is a changeable listener-facing term, not a required schema identifier.
Focus 11 working-state practice is a durable concept; “Access Channel” is also
under terminology review. Existing compatible IDs remain valid.

All TBD decisions in the [narration standard](NARRATION_STANDARD.md) remain open.
The exact cue-design TODO in `TIMED_TRANSCRIPTS.md` remains unchanged.
