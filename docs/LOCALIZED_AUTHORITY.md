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
