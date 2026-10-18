# Function authority and strict localized cue references

Function YAML owns source-English identity, exact display/spoken wording, stable
command roles, procedures, persistence and narration bindings. `canonical.name`
and `purpose.summary` remain the English title/purpose authority. Each command
has `spoken` and `spoken_review`; unresolved vocabulary is explicitly null and
unresolved, never invented from an audit recommendation. `narration.sequence`
owns resource keys, roles and repetitions. Existing content bindings are checked
compatibility copies, not a second editable authority.

Reviewed locale resources own their local realization, pronunciation and grammar.
Existing en-US display/spoken resources must exactly agree with function YAML.
This validation prevents two independently editable English authorities. A cue
change requires its reviewed locale copy to be updated deliberately; ordinary
rendering never rewrites it. Labels remain documentation labels, not speech.

## Explicit template contract

This complete resource example uses approved wording with symbolic speech:

```yaml
schema_version: '1.0'
locale: en-US
domain: narration
entries:
  hplus.function.ocf-slp-005.closer:
    status: reviewed
    version: 1.2.1
    cue_template:
      function_id: OCF-SLP-005
      allowed: [cue.primary]
    text: |-
      Think or say in your mind, "{{ cue.primary }}."
```

The function's `narration.sequence` must explicitly authorize this resource key.
Its primary command supplies display `PLUS-SLEEP EASY` and complete speech
`Plus Sleep Easy`. Heart's exact display remains `PLUS-HEART-BETTER`; its complete
speech is `Plus Heart Better`. No global punctuation normalization is performed.

Documented selectors:

- `cue.primary`: exactly one active primary command.
- `cue.mode.increase`, `cue.mode.decrease`: exactly one active command with that role.
- `cue.release`, `cue.cancel`, `cue.close`, `cue.retrieval`, `cue.access_close`:
  the corresponding distinct role, never interchangeable synonyms.
- `cue.id.OCF-CMD-SLP-005-PRIMARY`: an explicit active command of the same owner.
- `function.title`: the localized title, never an activation command.
- Any cue selector may append `.variant.NAME` for an explicitly reviewed variant.
  Source variants live in command `spoken_variants`; other languages bind variant
  names through `localization.spoken_variant_keys`. No variants are invented here.

Surround references with `{{` and `}}`; interior whitespace is permitted.
`allowed` lists exactly the symbols used, without duplicates. Resolution never
uses list position, mutable wording or a legacy query to select a command.
Unknown/malformed references, missing/ambiguous roles, inactive aliases, different
owners, unreviewed/missing locale cues and nested/circular values fail with
function/locale/resource context. Values are inserted once, not evaluated again.

Escape a single literal brace as `\{` or `\}` and a backslash as `\\`.
Unexpanded double delimiters are forbidden in final speech/transcripts. This
small interpolation contract has no Python/Jinja, calls, indexing, environment,
filesystem, shell or network expressions. Symbol templates cannot accept caller
ICU variables. Existing non-symbolic ICU resources retain their existing parser
and variable contracts; literal compatibility resources remain supported.

## One resolution boundary

`LocaleCatalog.resource` resolves declared templates into effective text while
retaining raw-template and command provenance. `raw_resource` is explicitly for
authoring/evidence. Narration-first and composed-session paths consume the same
resolved resource before paragraph/sentence segmentation, pronunciation, TTS,
speech-cache identity and recording fingerprints. Final TTS, recording-selection
and release-transcript boundaries reject unresolved tokens.

Raw-template hashes measure authored representation. Resolved-text hashes measure
effective speech, not punctuation-normalized text. Cue-resource pronunciation
hints and required tokens follow expansion; conflicting hints fail and require
an explicit reviewed variant. Narration-first consumes the function-owned
sequence, while existing content-binding copies are checked for agreement.

Structural conversion of the eleven
already-approved cues changes 22 raw body/closer entries but **zero resolved
protected bytes** across all 177 entries. All four body passes and closers are
tested against the exact predecessor text. No punctuation, whitespace, modes,
breathing, mechanisms, timing configuration or repetition values change.

The structural ledger is
`function-content/editorial/symbolic-cues-001.json`. It retains source commit,
predecessor file content/hashes, exact cue spans and raw/resolved hashes. Earlier
integrity fixtures, approval records and defaults locks remain immutable.
Defaults lock 003 is a content successor with identical engineering profiles and
dependency membership. Unchanged speech and DSP caches remain reusable; future
changed speech invalidates text identities naturally. Selected stale recordings
still fail in recorded-only and hybrid mode; no recorded hashes are rewritten.

## Preview and authoring

All 55 source-English function narration files begin with a generated comment
preview of the current title, display/spoken cues, command identities, secondary
operations and authority path. Edit source-English definitions in function YAML,
not in the comments. Missing reviewed cues are marked unavailable; the preview
does not silently borrow English for another locale. Existing CLI/MCP/LSP
previews continue to use the same strict resolver.

Check with `python -m ocf_tools.cue_headers` (also in `make check`); refresh with
`python -m ocf_tools.cue_headers --write`. Frozen files require an explicit
successor ledger before a changed preview can be written. The initial comment-only
successor is `function-content/editorial/cue-headers-001.json`: exact predecessor
bytes, raw-file hashes and 177 unchanged resolved-text hashes remain checkable.
Defaults lock 007 succeeds immutable 006 with only these comment hashes changed;
all engineering profiles and dependency membership remain identical. Generated
plans only change their defaults-lock references/hashes. No spoken baseline is
replaced and no recording fingerprint is rewritten.

The follow-up `cue-completion-001.json` records 90 additional exact active cue
spans across 51 body/closer entries in 31 function files. Secondary operations
use their own stable command IDs; they are never replaced with `cue.primary`.
All 177 resolved entries remain byte-identical, including reinforcement passages.
Defaults lock 008 succeeds 007 for the changed raw templates. Session plans retain
their resolved-text hashes and update raw-template/defaults provenance separately.
Historical notes/quotations and the separate, unbound Access to Energy
`access-close` entry remain literal.

One explicit technical review item remains: `OCF-COG-005` has null/unresolved
authoritative spoken metadata although its narration contains “Plus Options
Choices”. Its preview says unavailable and its literal teaching is retained;
maintenance does not infer a reviewed cue definition from narration. This does
not reopen the completed naming queue.

```bash
python scripts/ocf.py functions preview OCF-SLP-005 --locale en-US
python scripts/ocf.py dev ocf_get_function --arguments '{"function_id":"OCF-SLP-005","locale":"en-US","preview":true}'
python scripts/tools/check_hplus_narration_integrity.py
```

These previews return raw source, resolved text, resource identities, locale,
repetition bindings and provenance without synthesis. The existing MCP operation
accepts the same optional preview/locale arguments. No new server or transport
is introduced. Restarting an existing client/server is not part of this task;
an already-running adapter may continue advertising its older argument schema.

The existing LSP service completes embedded cue symbols, hovers resolved wording,
navigates to the owning function's spoken field and diagnoses invalid references.
It uses unsaved function/resource buffers through the same locale resolver.
Locale-pack filenames remain `.yaml`; YAML may contain JSON-compatible syntax.

The function wizard asks once for the explicit English spoken cue, alongside
its display cue; it stores that wording only in function YAML. New vocabulary
remains unresolved until reviewed. It assigns stable command IDs and directs
narration authoring to symbolic references rather than literal copies. It does
not invent a programming passage or silently approve generated language.

## Localization and interactive decisions

Source English is not a universal spoken language. Translate surrounding grammar
freely after the terminology sheet is approved, insert the complete reviewed
local cue, and define a reviewed variant when grammar requires one. Plus-prefix
treatment is an explicit per-locale decision; no English word counts or ASCII
word-boundary rules enter generic expansion. Spoken lookup uses existing strict
same-language fallback. Explicit labeled fallback auditions retain provenance;
bad symbolic references fail even when fallback was requested. Spanish remains
partial; no production vocabulary or translation is created here.

The earlier one-function-at-a-time review queue is historical. Naming reviews
and all 18 functional-metadata decisions are completed; current approved
function YAML and successor ledgers own the results. Do not reopen the queue or
treat earlier tentative titles as current proposals. Future explicitly requested
editorial changes require a separately versioned decision/integrity record;
silence, ambiguous responses and technical maintenance do not authorize wording
changes. Local queue records remain under `.ocf-work/` as history.
