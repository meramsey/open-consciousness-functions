# New editorial candidates

All four presented candidates received explicit full editorial approval and one
final batch implementation confirmation. Their exact approved narration is active;
Intuition is now registered. The original draft snapshots remain immutable review
evidence. See the [approval successor](EDITORIAL_BATCH_APPROVAL.md).
Registration, validation and preview do not establish scientific, listening or
release approval. The 55 historical functions and their 177 protected narration
entries remain a separate integrity cohort.

## Review inventory

| Candidate | Identity | Narration | Procedure and status |
| --- | --- | --- | --- |
| Manifest revision | OCF-EXP-001 | [Exact supplied snapshot](../function-content/editorial/candidates/manifest-v2.en-US.yaml), versions 1.2.0 / 2.0.0 / 1.3.0 | Approved revision active; predecessor preserved. Existing Plus Manifest procedure retained. |
| Dissolve | OCF-EXP-003 | [Exact supplied snapshot](../function-content/editorial/candidates/dissolve.en-US.yaml), all 1.0.0 | Approved: select pattern, inhale deeply, gently hold, cue in the mind, exhale slowly and easily. |
| Intuition | OCF-EXP-006 | [Exact approved snapshot](../function-content/editorial/candidates/intuition.en-US.yaml), all 1.0.0 | [Registered authority](../functions/experimental/intuition.yaml); new body, closer and procedure explicitly approved. |
| Clear Zone | OCF-EXP-005 | [Exact supplied snapshot](../function-content/editorial/candidates/clear-zone.en-US.yaml), all 1.0.0 | Approved: easy inhale, selected cue in the mind, natural exhale; all three stable identities retained. |

The source snapshot comments retain the author's original provisional-ID wording.
The [integration record](../function-content/editorial/candidates-001.json)
records subsequent allocation separately. Dissolve and Clear Zone retain the
proposed IDs. The existing allocator chooses max registered suffix plus one;
after EXP-005 this is EXP-006. EXP-004 is not treated as reserved. Intuition was
collision-checked before its explicitly approved registration; its staged
definition is retained as immutable predecessor evidence.

## Explicit preview

Read the [full inline review](EDITORIAL_CANDIDATE_REVIEW.md) for all four
complete authored templates and resolved spoken texts, command procedures,
provenance notes and the Manifest predecessor comparison.

Run from the repository root with the supported Python environment:

```bash
PYTHONPATH=scripts python -m ocf_tools.editorial_candidates manifest-v2
PYTHONPATH=scripts python -m ocf_tools.editorial_candidates dissolve
PYTHONPATH=scripts python -m ocf_tools.editorial_candidates clear-zone
PYTHONPATH=scripts python -m ocf_tools.editorial_candidates intuition
python scripts/ocf.py functions candidates
python scripts/ocf.py functions candidates intuition --preview
python scripts/ocf.py dev ocf_inspect_candidates --arguments '{"candidate":"clear-zone","preview":true}'
```

This returns exact resolved snapshot text, independent raw-template/resolved-text
hashes and an unmeasured semantic structure using the existing locked template,
pacing and DSP profiles. Each body has four passes. There is no synthesis or
promotion. Current discovery reports the explicit approval separately from each
historical snapshot's draft status. Standard locale resolution and production
rendering still require reviewed cues and approved narration. All 58 current
functions have production source plans; future unapproved drafts remain gated.

Source-English titles and spoken cues belong to function YAML. Locale
copies must agree. Draft review uses the same symbolic scanner and stable
command selector as production; it labels proposed realizations as draft and
does not mutate review status. Only en-US candidates are supplied.
Spanish remains partial; no English speech fallback or translated approval is
inferred.

## Clear Zone mode review

Automatic is the intended baseline. Primary `OCF-CMD-EXP-005-PRIMARY` strengthens
or restores it. `OCF-CMD-EXP-005-OBSERVE` pauses only outward intention, preserving
calm awareness. `OCF-CMD-EXP-005-SUSPEND` pauses the entire application while
ordinary awareness and natural bodily responses remain intact. Modes are
mutually exclusive. Either override ends at normal sleep onset, loss of
consciousness or deliberate primary invocation. Relaxation, Focus labels and
hearing a cue in narration are not triggers. These are instructional descriptions,
not software sensors or physiological controls. Physical repellency and disease
protection are not established.

## Intuition: approved original wording

The exact opener, complete new body and concise closer are available together in
the [candidate wording authority](../function-content/editorial/candidates/intuition.en-US.yaml).
The opener is the previously supplied sentence. All body and closer wording is
newly AI-authored, not historical material. The complete presented wording and
procedure subsequently received explicit human approval in this batch.

Approved activation procedure:

1. Bring one question or situation into awareness.
2. Think or say Plus Intuition in the mind.
3. Allow a quiet moment to notice what arises.
4. Consider its meaning and choose a response with care and discernment.

No breath hold, prescribed breathing pattern or eye closure is proposed.
Ongoing beneficial development is the intended baseline; the cue reinforces
deliberate deeper understanding. Impressions remain optional and are not proof
of external facts or access to anyone's private thoughts.

## Authoring and generated views

Author source-English cues in the linked registered function definition. Intuition's
staged `intuition.function.yaml` is immutable predecessor evidence. Keep
locale copies aligned with their function authority. Existing supplied snapshots
are immutable review evidence; new wording requires a versioned candidate rather
than overwriting a supplied snapshot. Preserve their original status `draft`,
provenance notes and stable command IDs. Active copies have status `reviewed`
under the separately recorded approval; historical rights are not inferred.

Refresh generated working views and the inline document with:

```bash
PYTHONPATH=scripts python -m ocf_tools.cue_headers --write
PYTHONPATH=scripts python -m ocf_tools.editorial_review
PYTHONPATH=scripts python -m ocf_tools.editorial_review --check
```

The `candidates/working/` YAML files are generated readable views of those
snapshots, not a second editable authority. Headers expose title, locale, source
definition, exact stable command identities and proposed spoken cues. Missing
cue bindings are visible diagnostics. LSP cue navigation opens function authority
and identifies draft status. CLI and MCP discovery are compact by default;
explicit preview includes full raw and resolved speech without synthesis.

After explicit approval, create a controlled editorial successor recording exact
predecessor files, raw/resolved speech and hashes, allowed substitutions and
unchanged protected entries. Update active resource versions/bindings only within
the approved scope; retain predecessor ledgers and recordings. Regenerate affected
headers, indexes and plans, and validate normal recording fingerprints. Listening
and release approval remain separate. The [Options successor](OPTIONS_SUCCESSOR.md)
is a scoped spoken-text example, not a blanket promotion tool.
