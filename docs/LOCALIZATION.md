# Localization, Language Fallback, and Language-Aware TTS

Status: **implemented** (v0.4). Shipped by `ocf locale …`, `ocf session
compose --locale`, `ocf transcript export --locale`, `ocf voice render
--locale`, and `ocf audio build --locale`. The data model landed with
[`proposals/draft/ocfp-0001-semantic-narration-keys-and-locale-packs.md`](../proposals/draft/ocfp-0001-semantic-narration-keys-and-locale-packs.md);
`locales/README.md` is the authoring reference.

Listener-facing content follows the [OCF Narration Standard — English](NARRATION_STANDARD.md).
The [migration inventory](NARRATION_MIGRATION.md) identifies existing material
awaiting the separately approved narration-writing phase.

The pipeline is **language-independent by structure**: one session definition
describes what happens and when, and the words a listener hears come from a
locale pack resolved at render time. The binaural/SAM/background DSP and the
timeline are never duplicated per language.

## Explicit localized spoken cues

Source-English `commands[].spoken` in function YAML is authoritative. The existing
en-US cue resources are checked compatibility copies. Localized languages retain
their own reviewed realizations. [Symbolic cue templates](SYMBOLIC_CUES.md) resolve
through the same LocaleCatalog before segmentation and audio/source selection;
raw templates and effective speech have separate hashes.

The approved English primary cues are explicitly bound through each stable
command's optional `localization.spoken_cue_key`. The separate
`localization.display_cue_key` resolves the exact display spelling, while
`label_key` continues to describe the command role. No cue is constructed from
a translated title or role label. Existing unbound records remain compatible
and report `unbound`; they are not silently given a spoken-cue approval.

The complete narration resource is registered in the en-US manifest:

```yaml
schema_version: '1.0'
locale: en-US
domain: narration
entries:
  commands.ocf-cmd-exp-001-primary.spoken-cue:
    text: Plus Manifest
    status: reviewed
    version: 1.0.0
    notes: English terminology approved in OCF-EDITORIAL-TITLE-CUES-001; listening and release approval remain separate.
```

`commands.localized_cue` uses the existing `LocaleCatalog`: UI display fallback
is labeled, and spoken lookup is strict across languages. A declared missing or
wrong-domain spoken binding fails strict resolution; catalog browsing instead
reports `requires-locale-review`, without an English spoken substitute. The
existing same-language regional parent fallback remains available. Text is
preserved as Unicode, with no generic word-count or English-token matching rule.

See the [source-English terminology sheet](releases/OCF_EN_US_TERMINOLOGY.md).
Spanish is still a partial fixture and requires terminology review against the
changed source; no translations or historical Spanish versions were overwritten.
Each future locale must decide its own complete title/cue pair and Plus-prefix
treatment. Title, explicit cue and actual teaching must be reviewed together;
resource availability is not language/editorial approval.

## What this is not

### Stable-ID function resource migration (in progress)

The current migration pilot is `OCF-EMO-003-Empathize.yaml`; it is not completion
of the 58-function migration. A registry-driven preview can be generated without
changing active locale manifests, narration, or historical locks:

```bash
PYTHONPATH=scripts python -m ocf_tools.localized_migration
PYTHONPATH=scripts python -m ocf_tools.localized_migration --output .ocf-work/migration-preview
```

The optional output must be a new directory inside the configured workspace.
It contains all 58 proposed function files, real existing English metadata,
separate raw-template/resolved-speech hashes, an old/new path map, and exact
source snapshots (including notes and removed preview comments). It is a
preview only: it does not activate the files or change metadata precedence.
Unreviewed legacy cues remain unbound; no spoken wording is invented.

Historical consumers must retain logical predecessor identities and verify
immutable snapshots before activation. The hash-checked localized-resource
migration ledger projects the pilot's current manifest/cue metadata back to its
exact predecessor for historical checks, while active narration still resolves
through LocaleCatalog. Public defaults, HPLUS-015 bytes, and Spanish content
are not changed by preview generation.

Localization changes words and measured speech duration. **Explicit semantic
anchors remain fixed**; declared speech-end/event-end dependencies follow the
localized render. Reflow is opt-in, not an arbitrary stretching of every track.
Semantic identity, ordering and DSP/cue references are language-independent.
No render-time localization tool rewrites authored sentences or imported source wording.

## The model in one example

A timed event can carry either inline `text` (legacy and still valid) or a
`narration_key` plus its `variables`:

```yaml
- id: e003
  at: 96.0
  narration_key: session.focus-cycle.tenth-state.enter
```

The key is resolved at render time:

```text
session definition            (events, sections, states, timing, gain windows)
   → narration_key            session.focus-cycle.tenth-state.enter
   → locale                   es
   → message                  "Entras ahora en el décimo estado. SOSTÉN."
   → TTS backend              espeak-ng (language retargeted to es)
   → spoken audio             measured per-cue durations in the render manifest
```

The same document rendered with `--locale en-US` speaks English. Nothing in the
document changed but the locale.

## Commands

```bash
ocf locale list                                  # every installed pack + provenance
ocf locale coverage --locale es --domain narration
ocf locale validate                              # schema, contracts, coverage
ocf locale resolve --session TEMPLATE --locale es --output resolved.yaml
ocf locale resolve --file timed.yaml --locale es            # strict
ocf locale resolve --file timed.yaml --locale es --no-strict # explicit fallback
ocf locale pseudo --from en-US                   # review aid, never committed

ocf session compose --template TPL --locale es   # compose straight into a locale
ocf voice list-backends                          # what each backend can speak

ocf transcript export timed.yaml --format srt --locale es
ocf transcript export timed.yaml --format srt --render-manifest OCF-RENDER-*.yaml
ocf voice render timed.yaml --locale es --output narration.wav
ocf audio build OCF-ATT-001 --locale es
```

`ocf locale` output and prompts are themselves localized from the pack, so a
Spanish pack produces Spanish CLI output:

```console
$ ocf locale coverage --locale es --domain narration
Narración es: 17 de 20 claves canónicas habladas
    missing focus.eleven.hold
    missing focus.eleven.release
    missing function.release.command
```

## Fallback

Resolution walks the BCP-47 chain: `es-MX` → `es` → `en-US`.

| Text type                  | Falls back to `en-US`? | Rationale                                |
| -------------------------- | ---------------------- | ---------------------------------------- |
| UI / CLI / validation text | yes                    | A missing label should not block a release |
| Listener narration         | **no**                 | See below                                |

A regional tag with no pack of its own is served by its installed parent
(`es-MX` from `es`): that is the same language to a listener, and regional
overrides are meant to be sparse.

**Strict spoken narration is the rule that matters.** If a keyed line has no
message in the requested locale, resolution raises before anything is rendered:

```text
error: required spoken narration is missing for es: event e002: missing spoken
narration 'focus.eleven.hold' for locale 'es'; consulted es; event e003: missing
spoken narration 'focus.eleven.release' for locale 'es'; consulted es
```

The alternative — dropping the English sentence into a translated session so
the build goes green — produces a session that sounds wrong in a way nobody
notices. `--no-strict` (or `--allow-fallback` on render/export/build) is the
explicit override for draft review. It records provenance per event:

```yaml
narration:
  locale: es
  direction: ltr
  strict: false
  resolved:
    - {id: e001, key: session.focus-cycle.opener, locale: es,   resource_file: narration.yaml}
    - {id: e002, key: focus.eleven.hold,        locale: en-US, resource_file: narration.yaml}
```

so a mixed-language render is always visible in the artifact, never invisible.

## Messages and grammar

Locale packs hold messages, not sentence fragments. The runtime formats a
documented subset of ICU MessageFormat: `{name}`, `plural`, `selectordinal`,
`select`, `#`, `offset:`, `'{...'` quoting, and `\#` escaping. The subset is
ICU-*compatible* in syntax, so a pack can move to a full ICU implementation
later without rewriting messages.

Two rules keep translated output readable:

- **Whole branches only.** `{count, plural, one {# time} other {# times}}` picks
  a complete clause. Word order and inflection live in the message, because a
  language that puts the verb first cannot be assembled from English fragments.
- **Declared variables are exact.** A message declares the variables it uses,
  and a mismatch is a validation error. A line still carrying a stray `{count}`
  fails the build instead of being spoken with the braces.

Plural categories come from compact CLDR rules for the major language families,
with pack-level `plural_rules` overrides. Rules are data and are evaluated in a
sandbox: anything outside the tiny allowed grammar is refused, not executed.

## Language-aware TTS

A render request carries locale, text, voice profile, backend, rate, timing
mode, and pronunciation hints.

- **Backend selection is explicit.** The CLI accepts `--voice` / `--backend`;
  when given, the request is honoured even if a locale-aware default would have
  picked something else.
- **Retargeting, not guessing.** `espeak-ng` is keyed by language, so `--locale
  es` narrows the voice to `es` and records a note when the pinned voice does
  not cover the locale, rather than silently speaking the wrong language.
- **Backends advertise what they can do.** `ocf voice list-backends` reports
  each backend's locale style, pronunciation syntax, and default language
  before you ask for a render:

  ```console
  $ ocf voice list-backends
  espeak-ng: /usr/bin/espeak-ng
      locale: language-region (en-us, pt-br); default language en-us; pronunciation syntax '[[...]]'
  piper: /home/you/.local/bin/piper
      locale: bound to its voice model - a locale needs a matching model; default language en_US; no pronunciation input
  ```

- **Pronunciation hints affect TTS input only.** A pack can carry
  `pronunciation: {espeak-ng: …}` per entry; the hint is applied to the text
  handed to the backend and never to the transcript, the subtitle track, or the
  manifest. A hint written for a backend that cannot use that syntax is ignored
  rather than corrupting the text.

Piper keeps its model language; an incompatible requested language is a
pre-render error. When available, the model's JSON sidecar supplies its actual
language instead of trusting a mislabeled profile. Language-switchable backends
are probed for the requested voice before real speech synthesis.

## Subtitles follow speech, not the source words

A translated line rarely takes the same time as the English one it replaced.
`ocf audio build --locale …` therefore writes measured per-cue durations into the
render manifest:

```yaml
narration_timing:
  mode: fit-soft
  measured: true
  cues:
    - {id: e003, at: 96.0, duration: 4.12}
```

`ocf transcript export --render-manifest OCF-RENDER-….yaml` uses those measured
durations for cue ends instead of estimating from the word count. Semantic
anchors (event ids, section boundaries) are preserved; English word timestamps
are never copied onto translated text.

The render manifest also records `source_ids`, unmodified `display_text`, and
`event_timing` (including semantic/DSP/cue coordination). A grouped utterance is
one subtitle; count splits retain their source identity. SRT, VTT **and LRC**
use actual localized starts when a render manifest is supplied. A manifest's
locale is used by default and a conflicting requested locale is rejected.
Speech-dependent subtitle anchors require measured render data.

Default keyed subtitle export resolves `en-US` (or the document locale) even
without `--locale`. Fixed speech overlaps now fail rather than silently cutting
previous narration. Use `after` plus `timing: {anchor: speech-end}`, or explicitly
set `timing: {policy: reflow}` on an elastic narration event. Numeric
`pause_after` is part of end-dependent timing. Fixed independent markers remain
fixed. See [semantic sessions](SEMANTIC_SESSIONS.md).

Without a render manifest, export falls back to the estimated durations and says
so on stderr.

## Versioning and translation status

Each pack declares `status` (`canonical`, `draft`, `machine`, `reviewed`) and a
`semantic_version`, plus `translation.source_locale` /
`translation.source_semantic_version` / `translation.translator` /
`translation.reviewed_on`.

- A **cosmetic** rewording keeps the major version and updates the entry
  minor/patch revision: no translation goes stale.
- A **semantic** change — different meaning, added or removed variable — bumps
  the major `semantic_version`, and packs built from an older major are reported stale
  until they record the new one.

`ocf locale validate` reports stale translations, unknown keys, variable-contract
drift, message syntax errors, invalid command references, and partial coverage.
A pack is never silently merged over another.

## Validation

```text
ocf locale validate        # packs: schema, provenance, contracts, coverage
ocf validate --all         # also checks keyed documents in the repository
```

Checked automatically:

- a keyed event that *also* carries inline `text` (hard-coded narration);
- unknown narration keys, and keys missing from a pack;
- locale tags that are malformed, unsupported, or served by an unexpected parent;
- stale translations (source semantic version behind);
- variable-contract drift between canonical and derived packs;
- invalid command references in narration text.

Pre-render checks additionally cover command ownership by `function_id`, empty
or required-but-absent narration, unresolved variables/placeholders, malformed
pause directives, structural duplicate narration/cues, semantic resource
references, required pronunciation and incompatible TTS models. Repetition at
different anchors is valid; `intentional_repeat: true` makes deliberate
same-anchor structural repetition explicit (spoken overlaps still need valid
timing). These checks do not judge writing style or hypnotic effectiveness.

The repository's own English scripts under `audio/scripts/` stay inline and are
not flagged: inline `text` remains valid, and the check exists to catch a keyed
event that quietly re-acquires hard-coded English, not to punish legacy data.

## Provenance and attribution

Translations follow the same rules as everything else in the repository:

- A machine or AI draft is `machine`, never `reviewed`, until a speaker of that
  language has checked it.
- Never fabricate a translation. A key you have not translated stays **absent**,
  which fails the strict check and asks for a real translator.
- Imported transcripts remain citation-only. Localization never rewrites source
  wording; it resolves keys into a target locale at render time.
- `locales/es/` in this repository is an explicitly labelled **test fixture**,
  not an authoritative translation.

## Demo

```bash
# 1. Compose the language-independent session.
ocf session compose --template OCF-TPL-SESSION-FOCUS-CYCLE-001 \
  --output /tmp/focus-cycle.yaml

# 2. See it in two languages from one definition.
ocf locale resolve --file /tmp/focus-cycle.yaml --locale en-US | head -20
ocf locale resolve --file /tmp/focus-cycle.yaml --locale es    | head -20

# 2b. Or compose straight into a locale.
ocf session compose --template OCF-TPL-SESSION-FOCUS-CYCLE-001 \
  --locale es --output /tmp/focus-cycle-es.yaml

# 3. Prove the strict spoken rule with the partial fixture.
ocf locale resolve --file tests/fixtures/session-keyed-partial.yaml --locale es
# error: required spoken narration is missing for es: ...

# 4. Render and export one language.
ocf voice render /tmp/focus-cycle.yaml --locale es --output /tmp/es.wav
ocf transcript export /tmp/focus-cycle.yaml --format srt --locale es
```

## Not yet done

- **Function-record translations.** Per-function narration is keyed
  (`function.*`) and localizable today; a translated *function record* (one
  source language plus a list of translations) needs its own schema change.
- **A real ICU runtime.** The subset covers what OCF messages need. Adopting
  PyICU or Babel is a dependency decision for a later proposal.
- **Right-to-left layout.** `direction` is resolved, recorded, and exported in
  provenance, but nothing renders mirrored UI yet.
- **Translator workflow tooling** beyond validation: no diff view, no
  per-language review queue.
- **Broad hard-coded-English scanning** of inline-only legacy documents.
