# Structured Function Commands — Compatibility Design

Status: implementation design for Milestone 2. This document records the
architecture and migration boundaries before schema or runtime changes.

## Current authoritative data

- `functions/<domain>/*.yaml` is the authoritative registry for function IDs,
  canonical primary phrases, mode phrases, legacy commands, aliases, lifecycle,
  and source availability.
- `schemas/function.schema.json` constrains those fields. `FunctionRecord` in
  `scripts/ocf_tools/models.py` exposes `canonical_command`, `command_modes`,
  `legacy_commands`, and the function lifecycle fields.
- `scripts/ocf_tools/validators.py` checks canonical command syntax, unique
  primary phrases, compatibility metadata, and the 55/39/16 registry invariant.
- `scripts/ocf_tools/generators.py` already derives the function index, legacy
  command maps, and command-review report from the function records.
- `LocaleCatalog` loads resources declared by locale manifests. UI strings may
  fall back through the locale chain to en-US; spoken narration remains strict
  by default (`scripts/ocf_tools/locale.py`).

There are 55 primary phrases, 10 mode phrases, 30 command-alias entries, and no
currently populated `lifecycle.release.command` values. The old fields must
remain readable and retain their current text.

## Proposed compatible record extension

Add an optional structured `commands` array to each function record. It is a
metadata layer over phrase fields already in that function record, not a second
phrase registry. Each row will contain:

- globally unique, stable command ID and the owning `function_id`;
- a typed `phrase_ref` to the existing primary, a mode identified through a
  stable mode ID, an existing lifecycle release phrase, a legacy alias, or a
  separately identified special phrase when no existing field can own it;
- role and primary/secondary designation;
- an effect-scope reference to the function lifecycle, not a copied lifecycle
  value;
- optional ordered-procedure reference and a narrowly scoped override;
- release/cancellation relationship IDs;
- localized UI keys for command label, purpose/usage, and explanation;
- optional documentation visibility and ordering.

Mode IDs will be stored alongside the existing `canonical.command.modes` array
so a structured record refers to a stable mode identity rather than relying on
an unprotected numeric position. If there is no evidence for a procedure or
effect relationship, the field stays unspecified. Legacy commands and aliases
remain in their existing fields and are shown separately as compatibility
phrases, not silently promoted to canonical activation commands. Where an
approved narration explicitly speaks a phrase different from the canonical
phrase, the guide will identify the narration key and the observed phrase as a
separate script form; it will not silently substitute it for the canonical.

The function ID scopes command IDs: the same phrase (for example `PLUS-RELEASE`)
can have different command identities and roles on different functions. The
canonical phrase remains stored once in its existing source field; the command
record points to it. A special phrase with no existing source field gets one
explicit phrase owner and a provenance reference rather than a second copy in
the command record. If an approved script speaks a different legacy or
transcribed form, the command may carry a separate **observed spoken form** with
its narration-key provenance and an explicit noncanonical relationship. That
form never replaces the canonical phrase.

## Procedure and localization data

Reusable ordered semantic procedures will live in a small procedure catalog,
separate from command identity. A function command can reference a catalog
procedure and optionally provide an explicit full-step override. Step operations
will be a constrained vocabulary (such as choose intention, close eyes, inhale,
hold, think/say command, command during exhalation, exhale, breathe normally,
release a temporary application). A missing or conflicting instruction is
omitted or marked unresolved; no default breathing sequence is inferred.

Procedure operation labels and function/command titles, descriptions, and usage
explanations will resolve from a locale `ui` resource. This uses existing
`LocaleCatalog` UI fallback and records fallback origin in generated output.
Canonical command phrases are identifiers/metadata and are never translated.
No command documentation key is placed in `narration.yaml`, so command-guide
fallback cannot weaken the strict spoken-narration rule.

## Generated views and CLI compatibility

Extend `FunctionRecord` with structured command accessors while retaining the
existing `canonical_command`, `command_modes`, `legacy_commands`, and
`release_command` accessors. `ocf functions list/describe --rich --json` will add
the structured command view without changing the existing default JSON shape.

Add deterministic products to the existing `build-index` flow:

1. Complete function/command index.
2. One reference sheet per function.
3. Printable quick-reference Markdown.
4. Machine-readable JSON for applications.

All products resolve localized UI text from locale resources; English remains
generatable even when another locale has no command-guide translations. Generator
outputs are checked for freshness by `build-index --check`.

## Migration evidence and unresolved cases

Populate primary and mode rows from current registry fields. Add special release,
cancellation, or access-close rows only when existing lifecycle metadata or
approved narration supports the role and sequence. Preserve historical names and
phrases byte-for-byte. A specifically approved migration can demote
superseded primary aliases to `availability: historical-lookup`; those records
retain stable IDs but do not appear in active guides or activation listings.

Known conflicts to carry explicitly rather than silently decide:

- Sleep Easy now consistently teaches `Plus Sleep Easy` under the explicit
  approved migration. `Plus Quiet Sleep` is preserved in historical evidence;
  source availability remains unavailable, and no listening approval is inferred.
- Insulate's narration distinguishes `Plus Cancel` (end the current
  adjustment) from `Plus Release` (place Insulate on hold). The registry has
  `PLUS-CANCEL` as a mode but no release phrase in `lifecycle.release.command`.
- Access to Energy's `Plus Release Eleven Access` is a distinct access-channel
  close cue in approved narration, not the function's primary activation phrase.
- `PLUS-RELEASE` is also a canonical primary phrase for the separate Release
  function. Command IDs therefore must remain function-scoped.
- Several approved function narrations retain a phrase represented by a legacy
  command while the registry has a different canonical phrase, including
  De-Discomfort, Regenerate, Short Fix, Restorative Sleep, Sleep, Sweet Dreams,
  and Stay Awake. These are cross-layer differences, not permission
  to rename registry commands or rewrite reviewed text. Preserve both records
  and show their source/role distinction in the guide.
- Contemplation's `PLUS-CLOSED` and Imprint's `PLUS-RECALL` are secondary modes
  with different purposes; neither should be flattened into an interchangeable
  generic release command.

These unresolved semantics remain visible in command metadata and generated
guides until a human decision is recorded. They do not block generation of the
known canonical and compatibility data.

A phrase comparison of approved English resources against the registry also
found canonical-versus-script wording that must be surfaced, not harmonized.
Examples include De-Discomfort (`PLUS-COMFORT` vs “Plus Five Five Five One
Five”), Hypertension
(`PLUS-BALANCE-BLOODPRESSURE` vs “Plus Balance Blood Pressure”), Regenerate (`PLUS-REGENERATE`
vs “Plus Build Live”), and the source-spoken forms for Nutricia, Sex Drive,
Imprint, Restorative Sleep, Sleep, Sweet Dreams, and Stay Awake. Some are represented by
preserved legacy aliases; others are script-only spelling/wording distinctions.
Migration must record the source basis and relationship for each, or leave it
unresolved when the current metadata and approved wording do not establish one.

## Implementation checkpoints

A. This architecture and compatibility design.
B. Optional schema fields, typed models, reference resolution, and focused schema
   and loader tests.
C. Metadata migration for justified canonical, mode, release, cancellation, and
   special command records; verify all old fields and phrases remain unchanged.
D. Locale UI keys, fallback provenance, deterministic guides/cards/index/JSON,
   and backward-compatible CLI exposure.
E. Failure-path and compatibility tests, full supported-Python suite, integrity
   check for all 177 narration texts, `make check`, and lint/format review.

No function command phrases, procedures, locale strings, or generated outputs are
changed by this design checkpoint.
