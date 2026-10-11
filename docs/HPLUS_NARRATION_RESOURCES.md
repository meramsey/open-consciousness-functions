# HPlus narration source of truth

The standard session is `audio/templates/sessions/OCF-TPL-SESSION-HPLUS-STANDARD-001.yaml`.
Its shared wording lives only in the canonical locale resources below. Templates
hold semantic events, timing and resource keys, never copies of this wording.

| Reused section | Canonical editable file |
| --- | --- |
| Body comfort | `locales/en-US/hplus-body-comfort.yaml` |
| Transmutation Box | `locales/en-US/hplus-transmutation-box.yaml` |
| Progressive relaxation | `locales/en-US/hplus-relaxation.yaml` |
| Focus 10 induction and return-ready | `locales/en-US/hplus-focus10.yaml` |
| Focus 11 opening and learning explanation | `locales/en-US/hplus-focus11-open.yaml` |
| Focus 11 consolidation and close | `locales/en-US/hplus-focus11-close.yaml` |
| Focus 20 entry | `locales/en-US/hplus-focus20.yaml` |
| Twenty-to-one waking return | `locales/en-US/hplus-waking-return.yaml` |

Each function has one locale resource file, named
`locales/<locale>/hplus-<FUNCTION-ID>.yaml`. It owns only the keys
`hplus.function.<lowercase-function-id>.opener`, `.function-body`, and `.closer`.
The same body key supplies both Focus 11 passes and both Focus 20 underlay passes.
All 55 functions now have an English review file, linked in
[English HPlus function review](HPLUS_FUNCTION_REVIEW.md). Of 39 source-available
functions, 28 have all three opener/body/closer extents selected directly from
their transcripts and 11 have historical source gaps. Sixteen additional files
contain the user's proposed reconstruction wording. Four source gaps also have
separate OCF-authored opener/closer suggestions, giving **48 files with all three
review slots populated**; the Access to Information closer remains pending approval.
Attention,
Circulation and Sleep retain their initial file selections. Entry status remains
`draft` for human wording review; a translatable candidate does not authenticate
its transcript or certify its efficacy claims.

The sixteen historical source-unavailable records remain unavailable and planned
reimplementation targets. Their English files now contain **user-proposed
reconstruction drafts**, selected from the supplied clean scripts in
`references/HumanPlusTranscripts/`. They are not recovered historical transcripts.
The separate proposal recipe records input hashes, exact document headers and
opener/body/closer line extents in `function-content/hplus-proposed-review-selections.yaml`.
Identity was checked against document titles and listed legacy commands, not
inferred from filenames. Sensory: Touch uses the clean Version 2; annotated
variants remain local comparison material. Sleep Easy's unknown catalogue number
is not filled in. Canonical commands and frozen Sleep Easy pilot wording remain
unchanged. Missing spoken sections in the ten incomplete transcripts still fail
clearly during composition.
Access to Energy also preserves its distinct source-specific access-close command
in a separate review entry; the standard template does not consume that extra
entry automatically. Some final passages are exploration/integration handoffs
rather than waking closers; the per-file notes identify these cases.

## Rights and provenance

The user stated in this authoring conversation: “all rights are now cleared by
lawyer so lets get the templates locked in”. This is recorded as **user_cleared**
for the selected shared wording and migrated function candidates. The lawyer's
identity, legal documents and license terms were not supplied; this record is
the user's attestation, not an independent legal finding. Shared wording had
already been human-approved and the instruction authorizes its reusable resource
selection. Function-specific wording review and finished audio release remain
separate from rights clearance.

Source authentication remains unverified. Source locators (local references are
not runtime dependencies):

- Attention: `+Transcripts From available tapes/Attention/Attention.txt`, SHA-256
  `0e9869897f01910a35cc33455545226ac6fff63a3f6432770726962a3e08e0e5`.
  Shared body comfort 2–7 (human OCF identity edit); box 8–11 (human
  Transmutation Box edit); Focus 10 12–23; Focus 11 opening 24–30; close 51–58;
  return-ready 58; Focus 20 59–69; waking return 70–83.
  Function-specific opener 1–2 with shared preparation separated, body 31–50,
  closer 84–86.
- Circulation: `+Transcripts From available tapes/Circulation/Circulation.txt`,
  SHA-256 `58c4daf1bd74356fe33220bf855593fe546ff58b9cd30496c8e373690eb3dc38`;
  partial transcript. Opener 2, body 47–74, closer 161–166. The existing preview's
  generic consolidation at 75–79 is supplied by the shared close, not duplicated
  in the function resource.
- Sleep: `+Transcripts From available tapes/Sleep/Sleep.txt`, SHA-256
  `0cc14bfba521241845bb953fb31ffdc29140bd4e34b63cd102845d01068a61fd`.
  Opener 7–8, body 72–116, closer 315–317.
- Progressive relaxation: exact user-provided wording, segmented by body part
  at the user's latest direction. Historical source match is unverified. No
  missing counts are inserted. Assertive total-relaxation assurances and
  anatomical/physiological claims remain review flags, not established outcomes.

Segmentation preserves words and punctuation; a split inside a source-wrapped
line may introduce a new line break. There is no additional spoken breath or
whole-body section: the final whole-body event is a silent pacing marker.
The approved Focus 11 explanation follows the open transition, avoiding an
extra learning section that would duplicate it. The waking passage is one
utterance followed by a silent ordinary-waking completion marker.

## Compose and translate

For initial source extent decisions see `function-content/hplus-review-selections.yaml`.
It is an import recipe, not the current wording source of truth. The offline
preparer verifies local source hashes and creates only missing files:

```bash
PYTHONPATH=scripts python3 scripts/tools/prepare_hplus_function_review.py --write
```

To populate untouched status-only placeholders from the supplied proposals:

```bash
PYTHONPATH=scripts python3 scripts/tools/prepare_hplus_function_review.py --apply-proposals --write
```

The explicit proposal option replaces only the original status-only placeholders;
existing narration and human edits are preserved. Prefatory material, production
directions and shared script passages are not included in the three function
entries. Proposed words and punctuation are retained, including legacy command
spellings. Input timing suggestions are not measured timing or verified evidence.
Edit the locale file directly for wording review and translation; reference
files stay immutable.

```bash
python3 scripts/ocf.py session compose \
  --template OCF-TPL-SESSION-HPLUS-STANDARD-001 \
  --function OCF-FND-002 --locale en-US --output /tmp/attention-review.yaml
```

`--function` supplies missing ordinary slots by stable locale keys. Explicit
text slots remain available for local working edits. Keyed slots stay keyed in
the unresolved composed document; locale resolution records the supplying file.

For another locale, create the corresponding resource files under
`locales/<locale>/`, register them in that locale's `manifest.yaml`, and retain
the same keys. Translate whole entries. Leave untranslated keys absent; strict
spoken resolution must fail rather than silently use English. Record translator
and review status in the locale manifest. Entry `version` and pack
`semantic_version` follow `locales/README.md`; semantic edits require translation
review. Timing must be measured anew for each locale and voice.

These resources lock the reusable text organization, not measured audio timing.
Optional affirmation, resonant tuning and Energy Ball remain disabled and
unauthored for this selection. The older Preparation Learning RC1 and listening
comparison assets retain their existing resources.
