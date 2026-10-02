# OCF Authoring and Narration Standard

Status: canonical authoring contract. Applies to **listener-facing experiential
narration**, including human/AI-assisted new functions and community contributions.
English is the first language pack; the operational principles apply across locales.
This revision does not rewrite approved Preparation Learning RC1 narration.

> OCF provides the structure and cues. The listener provides the experience.

## Separation of responsibilities

| Layer | Responsibility |
| --- | --- |
| Semantics | What happens, event identity, ordering and relationships |
| Narration | How that intent is expressed in a locale |
| DSP | The configured audio/entrainment state and transitions |
| Cues | Optional nonverbal learned signals, resolved by a replaceable profile |
| TTS | Voice/model, pronunciation and measured spoken duration |
| Metadata | Function identity, versions, names, canonical commands and provenance |
| Artwork | Visual presentation; final visual identity remains TBD |

English is a locale, **not the semantic API**. A sentence, sound filename or
carrier frequency cannot define a semantic transition. A subtitle `cue_id` is
not an auditory state cue; an auditory cue is not a function activation command.

## Scope

Use this contract for Preparation Learning, routine preparation blocks,
function installation, Focus-state and working-state instructions, optional
affirmations, resonant-tuning instructions, exit sequences, command learning,
and any wizard-generated experiential narration. Technical documentation,
operator diagnostics and source transcripts are not rewritten in this style.

## Writing principles

### Every sentence performs an operation

Assign each draft sentence one or more editorial purposes: **ORIENT, EXPLAIN,
PREPARE, DIRECT, NOTICE, ASSOCIATE, REHEARSE, CONFIRM, TRANSITION, RETURN**.
**WAIT** normally belongs to a declared silence, not extra narration.
These are authoring annotations, not new runtime event identities. An explanation
earns its place when it makes the next operation clearer. Remove sentences that
only add a meditative atmosphere or repeat reassurance without changing the task.

Prefer **instruction → experience → recognition → association**. Specify what
the listener does and what category of experience they attend to; do not dictate
the experience they must have. Use concrete verbs: select, place, release, attend,
compare, recall, rehearse. Be confident about the operation and modest about its
outcome. Direct instructions are compatible with voluntary participation.

For example, original OCF wording might say: “Choose one sound. Follow it for
three breaths. Then let your attention include the room again.” Each sentence
changes the task. Repeated “you may perhaps find yourself becoming more aware”
obscures both the action and the endpoint.

Establish sensory flexibility once, then use concise representation-neutral
language. A mental construct may be seen, heard, felt, located, described, or
simply understood. Do not enumerate those options in every step. Visualization
is required only when it is genuinely the skill being practiced, with that
requirement and an alternative documented.

Use neutral/secular operational language. “Energy” may mean available effort or
a felt quality; define that use instead of claiming an unseen mechanism. Neither
religious nor anti-religious doctrine is required. A listener's interpretation
may be psychological, metaphorical, contemplative or spiritual without the
exercise asserting one interpretation as fact.

### Original function conversion

Read the complete source before conversion. Extract opener/main/closer operations,
command association, rehearsal, future use and release/return separately from
expression. Write from that semantic specification, not by replacing synonyms
in source sentences. Distinguish experiential instruction, metaphor, learned
association, practical strategy, unsupported mechanism and ambiguous claims.
If operationalizing a claim materially changes the intended function, record
the change and require human content review.

Before acceptance, compare the independent draft against all consulted sources
for distinctive phrases, metaphors and unnecessary passage ordering. Revise from
purpose rather than mechanically changing words. Common functional concepts and
canonical command identities do not license copying distinctive expression.
Reconstruction/mockup material is never recovered historical narration.

Draft pilots remain **DRAFT / PILOT / REQUIRES HUMAN CONTENT REVIEW**. Automated
validation and originality checks support review but do not approve style,
historical authenticity, clinical effects or legal redistribution rights.

- **Permissive suggestion:** invite participation; avoid commands that imply
  involuntary obedience. The listener can adapt, pause, decline or end an exercise.
- **Pacing and leading:** acknowledge what can be noticed now, then suggest a
  small, gradual next step. Do not assert an internal experience has occurred.
- **Utilization:** allow ordinary sensations, thoughts, distractions and varied
  responses to become workable parts of the exercise instead of signs of failure.
- **Sensory flexibility:** support visual or auditory imagining, felt sense,
  spatial sense, conceptual knowing and association. No exercise requires vivid
  mental images; listeners with aphantasia must be able to participate.
- **Positive framing:** describe available actions rather than struggles to
  suppress unwanted thoughts or sensations.
- **Autonomy:** the listener remains in voluntary control. The narrator and
  learned command do not override that control.
- **Consistent anchors:** explain each learned association and rehearse it
  deliberately. Keep opening, ready, closing, completion and activation distinct.
- **Gradual transitions:** provide space to recognize changes without promising
  that every listener experiences the same subjective state.
- **Future pacing:** where useful, invite a voluntary future application and
  rehearsal, without guaranteeing an outcome.
- **Economy after learning:** routine tracks cue learned concepts concisely;
  they do not repeat the complete learning lecture.

Useful phrasing includes “allow”, “notice”, “you may notice”, “you might find”,
“when you're ready”, “whatever comes naturally”, “there's nothing you need to
force”, and “if you choose”. These are options, not a mechanically repeated
formula. Read drafts aloud and revise awkward rhythm, overloaded sentences or
ambiguous references. Do not attempt to score hypnotic effectiveness.

## Claims and experience

Do not write coercive language, guaranteed outcomes, unsupported biological or
medical claims, guaranteed unconscious learning, narrator dependency, or claims
that commands override voluntary control. Focus labels describe subjective
practice conventions, not scientifically verified neurological states. DSP
parameters describe audio, not proof that a listener has reached a state.

Installation means deliberate learning, association and rehearsal in OCF. It
does not assert automatic learning beneath awareness. Existing contrary
statements are listed for replacement in the [migration inventory](NARRATION_MIGRATION.md).

## Learning, routine preparation and function installation

**Preparation Learning** teaches control, temporary setting-aside of
distractions, optional affirmation/tuning concepts, progressive relaxation,
Focus 10 recognition, Focus 11 working-state practice, distinct learned cues,
function/command concepts, voluntary rehearsal and ordinary waking return.

**Routine Preparation** briefly recalls already-learned concepts and prepares
for a function. Optional affirmation and resonant tuning remain composable.

**Function Installation** teaches a particular function's purpose, experiential
rehearsal, optional examples, activation association, deliberate command
rehearsal, future use and return or continuation. Function-specific content is
not forced into universal wording. None of these compositions requires H+
material. Shared stages, not copied sentences or giant duplicate templates,
provide reuse.

## Semantic resources and localization

Author original listener text under `locales/en-US/`, using existing dotted
kebab-case semantic keys. Choose keys for intent rather than exact words;
terminology can change without changing session identities. In particular,
“Energy Conversion Box” and “Access Channel” are terminology-review candidates,
not permanent schema names. Neutral setting-aside and working-state concepts
must remain expressible.

Translate intent, autonomy, pacing, cue associations and the distinction between
suggestion and assertion. Natural target-language phrasing is preferred over
English syntax. Translations record source version, translation version and
review status (`draft`, `machine`, `reviewed`, or `canonical`). Do not mark an AI
draft reviewed without a human speaker's review.

Required spoken resources are checked before TTS. Same-language regional
fallback is permitted; cross-language fallback and retaining cross-language
inline text require an explicit caller/user opt-in. UI fallback is more
permissive. See [localization](LOCALIZATION.md) and [pack authoring](../locales/README.md).

Function `id`, `canonical.name`, and `canonical.command.primary` are already
separate metadata. **Do not translate activation commands automatically.** A
locale may explain their use and supply backend-specific pronunciation hints.
Hints change TTS input only, not command identity or subtitle text. Broader
command localization remains TBD.

Localized speech gets measured timing; it does not inherit English word-level
timestamps. Explicit semantic anchors and narration-dependent anchors must be
distinguished. No translated line may silently be overwritten because the next
English-timed event starts sooner.

## Versioning and provenance

The existing version convention uses **major** revisions for changed meaning
or variable contracts and **minor/patch** revisions for cosmetic wording.
Pack source-semantic versions and entry versions report meaning changes as
potentially stale; punctuation alone does not invalidate translations. Keep
source attribution and translation review information with resources.

Reference material may inform functional structure only. Do not copy or closely
paraphrase H+/Monroe narration into OCF resources. Imported transcripts remain
verbatim and citation-only; contributor/free-form narration is not automatically
rewritten. See [source attribution](SOURCE_ATTRIBUTION.md).

## Explicit TBD decisions

- Focus 10 auditory cue sound.
- Focus 11 opening, ready and closing auditory cue sounds.
- Final session-complete sound.
- Final OCF visual identity.
- Final default affirmation.
- Final oHm/resonant-tuning implementation.
- Broader activation-command localization policy.
- Final production Preparation Learning timing/mastering (en-US RC1 wording is
  approved; its audio remains a development audition).

Cue identities may exist before sounds are designed. No experimental
sounding-bowl frequency or prototype asset is a permanent semantic definition.
