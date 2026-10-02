# Three-function pilot: evidence → operations → independent OCF words

**DRAFT / PILOT / REQUIRES HUMAN CONTENT REVIEW**. No mass conversion.
These are brief ordinary-waking learning/rehearsal prototypes, not full
Preparation/Focus Eleven installations. The session templates are independent
semantic implementations; English resources are in `locales/en-US/functions.yaml`.
Canonical function records, commands, historical availability and all16 planned
legacy-source-unavailable reimplementations are preserved.

## Evidence review and provenance

Complete local files read before writing: Relax.txt (188lines), Sensory
(Hearing).txt (175lines), Sleep_Easy_reconstructed_clean.txt (347lines),
Sleep_Easy_README.md (43lines); Recall.txt (189lines) read as a counterexample.
Fingerprints and source-relative paths are permanently recorded in
`humanplus-corpus-inventory.json`. These reads establish the files' contents,
not independent authentication against recordings. Relax/Hearing have both
apparent introductory and final boundaries but contain obvious ASR artifacts;
historical completeness remains pending-source-review. Recall has a long explicit
gap and no recovered ending in this derivative, so it was rejected as a strong
pilot source. No inserted religious sentence or repeated ASR numbers is silently
normalized into an historical claim.

Sleep Easy has **no genuine target transcript** in this corpus. The mockup
explicitly distinguishes catalogue/command facts, borrowed structural inference,
new connective expression and modern safety notes. Its claimed verified facts
remain secondary assertions until checked against the cited surviving pamphlet.
The mockup's timing/cadence is reconstructed, never reused as measured timing.

## Provisional functional grammar (limited sample)

Observed source sequence: orient to target → practical preparation → temporary
setting-aside → tenth-state entry → learning/opening context → target operation
and command → repeated association/future use → close learning context → return
to tenth state → sleep/consolidation interval → waking return and command reminder.
Target-specific main instructions vary: Relax couples a breath action to release;
Hearing has two opposing modes and persistence until a chosen return. The source
learning/closing shell is largely shared. Source future-use statements include
automatic/whole-system learning claims that OCF does not repeat as established fact.

Repeated ASR tokens do not prove intentional repetition or intelligible underlay.
This is a grammar hypothesis from the reviewed sample, **not a completed
cross-corpus or generation study**. Candidate locators across the remaining
corpus are machine aids, not semantic extraction completed by an author.
Existing function-purpose, command-learning and future-use stages already
represent useful shared operations; reuse them rather than create duplicate shells.
Full preparation/Focus closing remains separate from function learning completion.

## Independent semantic specifications

| Function | Selection rationale | Mental operations | Command semantics | Closer / future behavior |
| --- | --- | --- | --- | --- |
| OCF-FND-004 Relax | Source derivative with target operation and apparent ending | select supported posture; notice effort; reduce one unnecessary effort; compare holding/resting | PLUS-RELAX deliberately recalls the practiced reduction of effort | select a future pause; ordinary-waking handoff; can stop freely |
| OCF-SEN-001 Hearing | Structurally different adjustable two-mode operation | select audible sound; narrow attention; broaden attention; compare; resume ordinary listening | PLUS-HEAR MORE examines sound; PLUS-HEAR LESS reduces its priority, not physical audibility | preserve important signals; stop for practical response; no invented cancel command |
| OCF-SLP-005 Sleep Easy | Legacy source unavailable; explicit reconstructed research bundle | assess actual rest safety; represent unfamiliar setting without requiring an image; choose practical adjustment; rehearse resting without forced sleep | PLUS-SLEEP EASY recalls safety/adjustment/rest routine | prototype ends awake; later sleep use conditional on safe context; no guaranteed sleep |

Learning state is **ordinary-waking**, explicitly an OCF pilot design choice.
No Focus identity is inferred from wording, function title or spectral recipes.
These pilots do not claim to have taught the complete reviewed Preparation
Learning program. Shared end-relative scheduling and48s command-stage pauses
are existing stage design choices, not legacy measured timing. Listener preview
must expose pauses and draft status. No audible state cues or hidden suggestions.

## Claims conversion and originality decisions requiring review

- Relax: automatic physical/nerve-system release becomes deliberate reduction of
  muscular effort. The source's breath hold/candle metaphor is not reproduced.
- Hearing: enhanced frequency range/softest-sound perception becomes voluntary
  allocation of attention. This is a **material reinterpretation**, not evidence
  that attentional practice achieves the source's physiological claims.
- Sleep Easy: guarantees under extreme/adverse conditions become a safe-context
  rest routine. Practical environment changes and voluntary non-striving are OCF
  design inferences, not recovered missing-script operations.
- All: deliberate rehearsal replaces unconscious/whole-cell installation.
  No new command identities, involuntary response, cure, efficacy or mechanism claim.

Original wording was authored from the operation table rather than line-by-line
paraphrase. The prototypes omit source metaphors, stock installation passages,
sleep-count structure and distinctive explanatory expression. Short common
instructions and deliberate canonical command names may naturally overlap.
Independent human originality/style review is still required before acceptance.
Do not use these pilots as mass-authoring stylistic ground truth.

## Live preview commands

```bash
python scripts/ocf.py session compose --template OCF-TPL-SESSION-PILOT-RELAX-001 --locale en-US --output relax-pilot.yaml
python scripts/ocf.py session compose --template OCF-TPL-SESSION-PILOT-HEARING-001 --locale en-US --output hearing-pilot.yaml
python scripts/ocf.py session compose --template OCF-TPL-SESSION-PILOT-SLEEP-EASY-001 --locale en-US --output sleep-easy-pilot.yaml
python scripts/ocf.py voice render relax-pilot.yaml --voice OCF-VOICE-0002 --locale en-US --output relax-pilot.wav
```

Text previews are the resolved YAML documents. Local Piper development voice
previews are in `/tmp/opencode/relax-pilot.wav`, `hearing-pilot.wav`, and
`sleep-easy-pilot.wav`; actual total durations were printed by voice rendering.
These early pilot previews did not retain per-event manifests; subsequent voice
renders now write measured sidecars automatically.
No human listener approval is claimed. Full remaining-corpus semantic extraction, permanent
function-content/provenance schema and rich function index integration are follow-up.
