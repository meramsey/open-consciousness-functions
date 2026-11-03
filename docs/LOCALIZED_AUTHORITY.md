# Staged localized function authority migration

This migration covers the complete 58-function catalog, not one function per
pull request. It changes data organization, not approved speech or command
behavior. Partial locales remain partial; no translation is invented.

## L0: authority and generator trace

The stable registry is `functions/`: identities, command IDs, command structure,
domain IDs, source availability, historical aliases and evidence references.
Localized words currently also exist there and in locale resources. They must
not be removed from the registry until every localized consumer has migrated.

The live key-based resolver is `LocaleCatalog` in `scripts/ocf_tools/locale.py`.
Locale manifests select the active resources. `commands.yaml`,
`activation-cues.yaml`, `original-draft-ui.yaml`, `original-draft-cues.yaml`,
`intuition-ui.yaml` and `intuition-cues.yaml` contain localized function and
command metadata. Not every field in these files belongs to a function: shared
UI strings must remain available. The existing function resource files contain
canonical narration entries, including optional entries not referenced by the
current playback sequence.

| Data | Current consumer path | Eventual editable owner |
| --- | --- | --- |
| Stable IDs, command grammar, domains | `indexes.load_all_functions` → `models.function_from_dict` | Global registry |
| Titles and descriptions | `LocaleCatalog.resource` → `command_docs._function_document`; `generators.row_for` still reads registry properties | Localized function YAML |
| Display and spoken cues | `commands.localized_cue` → `cue_templates.value` → `LocaleCatalog.resource` | Localized function YAML, stable command references |
| Command labels, usage, explanations | `command_docs._localized` → `LocaleCatalog.resource` | Localized function YAML |
| Narration and cue substitutions | `LocaleCatalog.raw_resource/resource` → `session`/`transcript`/`voice` | Localized function YAML, unchanged stable keys |
| Tags and common uses | Registry fields consumed by discovery and guides | Approved localized function fields |
| Companion relationships | Global `companions`, approved `guide_review.relationships`, locale descriptions | Structural edges stay global; localized words move |
| Learning order | Existing guide assembly and foundation ordering | Existing guide architecture; no invented per-function order |
| CLI and API/MCP metadata | `discovery`, `agent_api.list_functions/get_function`, command index | Resolver-backed localized fields |
| Function/command indexes | `generators.build_function_index_data`, `command_docs.build_command_index` | Generated outputs, never edited authorities |
| Audio plans and cache text | `planning`, `complete_session`, strict locale/cue resolution before voice segmentation | Effective speech and explicit voice/configuration identity |
| Album and track metadata | `audition_exports`, `release` | Resolver-backed localized fields plus explicit narrator profile |
| Guides, handbook, PDF, ZIP | `listening_guides`, `listener_text`, `listener_packages`, command documents | Generated outputs |
| Rights, provenance, approval, revisions | `function-content/`, editorial successor ledgers, entry versions | Structured historical/editorial records |

`function-index.json`, `function-index.csv`, `function-command-index.json`,
`FUNCTION_INDEX.md`, the command index/quick reference, function sheets and
session plans are generated outputs. An index remaining fresh is necessary but
does not by itself prove all consumers use the new authority.

## L1: consolidate without renaming or retiring sources

`python -m ocf_tools.localized_migration` previews the complete catalog.
`--output` writes an isolated workspace preview. `--activate` consolidates the
metadata at the existing narration resource paths, preserving their narration
domain during this stage. It does not remove resource files or old metadata
keys. Titles, descriptions and cue words are actual localized values, not
opaque pointers to another registry.

The first 55 files retain their `hplus-OCF-*.yaml` names. The three original
function resources retain their existing `original-OCF-*.yaml` names. The prior
Empathize pilot remains preserved while its original path receives the same
staged metadata as the other functions. No catalog-wide filename migration has
occurred. L2 must deliberately activate the consolidated metadata and migrate
all consumers; L3 may then retire verified redundant authorities. L4 handles
readable filename suffixes only after those gates pass.

The consolidation ledger stores exact predecessor bytes, original notes and
per-entry raw/resolved hashes. Narration sections outside the playback sequence
are retained. Rerunning the consolidation is a no-op; interrupted writes can
resume only from recorded preimages or exact outputs. Unknown edits fail closed
and are never overwritten.

## Historical compatibility

`locale_history.before_consolidation` projects exact checked predecessor bytes
before older historical adapters. The existing localized-resource pilot ledger
is preserved unchanged. HPLUS-015 and every other immutable defaults lock remain
unchanged. `audio_defaults.configuration_lock` uses the checked historical
resource bytes for structural consolidations, never a new baseline fabricated
to make a migration pass. Historical candidate and Options validators inspect
their original metadata as well as the current protected speech.

Generated cue-preview banners are unnecessary in consolidated YAML because the
real metadata is present. Their exact predecessor comments remain in the ledger.
Human listening, rights clearance and publication approval remain separate from
schema, speech-equivalence and historical-fingerprint validation.

## L2 preparation: field-source trace

`LocaleCatalog.function_field_sources` provides a read-only trace for an active
localized function resource. Each literal value has its logical YAML filename
and an unambiguous JSON pointer into that document. Narration keys, cue versions,
secondary commands, relationships, tags and uses use the same trace mechanism.
The method refuses opaque registry-reference values rather than falsely claiming
that their words came from the locale file. Locale fallback is disabled unless
explicitly requested. Adding this interface does not activate staged resources,
retire old metadata or migrate any generated consumer by itself.

The isolated complete-catalog activation fixture compares every resolved cue
and all 175 narration entries with the current catalog. It also verifies title
propagation to the command index without changing the global record. Existing
cue versions are copied exactly; formerly unversioned resources do not acquire
an invented `1.0.0` version. This fixture is not activation of the live catalog.

## L2: live literal YAML authority

`python -m ocf_tools.localized_activation` previews the complete activation;
`--apply` registers the existing 58 resource paths as function resources without
renaming or removing files. `metadata_entries` preserves the 49 additional
function-specific lifecycle and procedure keys. Approved relationship descriptions
retain their stable keys in their owning function resource and are checked against
the existing approved structural edges. No new relationship is inferred.

The manifest marks predecessor keys as superseded compatibility inputs and
fingerprints their original parsed resource mapping. Those retained files cannot
silently override the function YAML: changing them fails closed. Their remaining
shared UI and unrelated keys remain active. Retirement is a later stage, not an
automatic side effect of activating localized values.

Master function and command indexes, CLI discovery, API/MCP presentation and guide
titles/search/PDF bookmarks read the same locale resolver. Narration-first planning
already resolves titles and speech through that resolver. Speech-cache keys still
depend on effective spoken bytes and voice/configuration, not locale filenames.
`function-field-sources.json` is generated from the live catalog and records the
source YAML and attribute pointer for every localized field; it is not editable.

The checked authority-003 predecessor layer is applied before consolidation-002
and pilot-001 historical readers. None of those committed predecessor records or
HPLUS-015 defaults is rewritten. Current speech, cue versions and all 175 function
entries remain independently compared with the pre-consolidation baseline.

## L3: retire superseded editable words, preserve exact historical inputs

`python -m ocf_tools.localized_retirement --apply` retires the previously declared
615 superseded keys across seven compatibility resources. The 99 shared keys
that still have legitimate consumers are retained in three explicitly shared UI
resources. No structural function/command identities, rights records or existing
editorial/defaults ledgers are deleted.

Exact predecessor resources, the prior manifest and the unlisted Empathize pilot
are archived under `function-content/editorial/historical-locales/004/`. Their old
logical paths contain only generated historical references, not localized values
or active function definitions. Active manifests never register these references.
The checked retirement-004 projection restores original bytes before older
historical readers, including pilot-001's original path identity. Reapplying the
retirement is a no-op only when all outputs and archives still match; unknown
edits and shared overrides fail closed and are not overwritten.

Publication prepares archives and new shared resources first, atomically switches
the manifest, then retires inactive predecessor words. This preserves a complete
active pack throughout the operation. Historical validation and present-day locale
resolution remain deliberately separate. Readable function renaming is still L4;
this stage keeps all 58 current function filenames unchanged.

## L4: stable-ID-first readable filenames

`python -m ocf_tools.localized_filenames` emits the deterministic 58-function
path map. `--apply` stages every target with unchanged bytes, records exact
predecessor archives, switches the manifest only when all targets exist, then
replaces inactive old paths with word-free historical references. A shared
migration lease prevents competing migrations. Existing destinations are never
overwritten except the separately hash-verified historical Empathize reference;
its earlier identity remains reproducible through both checked archive layers.

All 58 active en-US filenames now use `OCF-…-Readable-Title.yaml`. Lookup still
uses the stable ID inside the document, not a title suffix. The suffix is NFC,
casefold collisions are rejected, Windows-invalid/reserved names are handled,
and UTF-8 component lengths are bounded. Partial locales remain partial.

The filename-005 map records original logical paths and unchanged content hashes.
HPLUS-015 and original narration fingerprints continue to resolve their exact
predecessor bytes; their locks are not rewritten to accept new filenames. Current
readers, cue previews, authoring metadata and generated field-source traces use
the manifest-selected filename. Older physical paths are compatibility references
only and are never registered as duplicate active definitions.
