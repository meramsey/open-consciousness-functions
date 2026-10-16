# Locale-native title–cue terminology and readiness proposal

Status: PROPOSED — NOT IMPLEMENTED.

Source commit: `fb66fbce11dd3d71e57fac4d5784365128d41c82`.
Canonical inputs are source-pinned in the companion JSON. Existing uncommitted
localization policy, lookup implementation and audit drafts are preserved; this
companion neither imports them nor records approval of their vocabulary.

## Stable identity and reviewed presentation

Function IDs and command IDs identify behavior and role independently of language.
Keep existing narration keys and HPLUS IDs until a separate approved migration.
Use the existing `LocaleCatalog`, BCP-47 normalization and fallback rules.

Each locale's terminology sheet should record function ID, command ID/role,
reviewed title, purpose, complete spoken cue, mode/control labels, pronunciation
guidance, teaching resource keys, exact text hashes, language reviewer and separate
editorial decision. The complete source-English starter glossary is the
`functions` and `commands` arrays in
[the companion recommendations](OCF_TITLE_CUE_REVIEW.json). All proposed values
remain unapproved. Current values and complete taught phrases remain separate.

Whether Plus stays shared, is translated, or has a locale-specific realization
requires explicit per-locale review. Do not concatenate a prefix with a translated
title, impose English word order/count, assume whitespace boundaries, strip
Unicode distinctions or infer pronunciation from hyphens. Review each complete
spoken pair with local grammar and confusability in mind.

## Translation workflow

1. Approve specific source-language title–cue pairs and mode/control decisions.
2. Establish each locale's explicit terminology sheet, including prefix policy.
3. Review local clarity, primary/mode/control collisions and pronunciation.
4. Translate teaching and reinforcement with that terminology and unchanged
   behavior/procedure; retain source provenance and separate editorial flags.
5. Validate whole-cue instruction context and rendered transcripts with measured
   localized timing. Never reuse English timing as a translated measurement.
6. Record language/editorial review independently of generation, renderability,
   rights clearance and release approval. Generated text is not human review.

No production translation or new active vocabulary is selected by this proposal.

## Fallback coherence: additive read-only check

Browsing may use UI fallback and must label origin locale and historical match.
Existing spoken narration resolution is strict across languages, with supported
same-language parent fallback. Do not change those rules or partial-locale fixtures.

A future critical-dependency report should consume the existing resolver's
resolution records for title, purpose, explicit localized spoken-cue identity,
mode/control cues and every required teaching resource. Report missing bindings,
origin locales and cross-language/script mismatches. A complete-session claim
requires a reviewed coherent set; an English command documentation label alone
does not establish a reviewed localized spoken cue.

Same-language regional fallback is not by itself a defect. Script variants and
regional terminology need review too: matching language subtags cannot establish
script or vocabulary coherence. Explicit labeled fallback auditions remain
available, with the fallback disclosed, rather than silently described as complete
localization. This proposal adds no render gate and changes no approved behavior.

## Historical lookup, separate from active teaching

Historical name/phrase → stable function → selected locale's title, purpose and
reviewed cue, with origin locale and historical match clearly labeled. Show any
evolved OCF purpose difference. Search matches never automatically become active
aliases or compatibility lessons. Preserve existing active aliases until their
specific future decisions are approved; no runtime alias removal is proposed here.

## Decisions and dependencies

- Approve the complete source glossary, especially Food Energy Use's asymmetric
  modes, Release's selected application and Contemplation's reciprocal operation.
- Decide an additive explicit spoken-cue localization binding using existing
  command IDs; current `label_key` is documentation, not that approval contract.
- Approve per-locale prefix, pronunciation and complete-phrase comparison policy.
- Before changed wording, inventory recorded event/resource/unit mappings,
  session-stem markers and exact-text/cache receipts. Preserve old artifacts and
  create successor versions rather than rewriting provenance or fingerprints.
