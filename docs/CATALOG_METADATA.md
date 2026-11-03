# Function discovery metadata

The existing `locales/en-US/OCF-…-Title.yaml` files are the only editable
authority for tags, common uses and optional relationship proposals. Registry
identity, approved cues and narration are not changed by discovery metadata.
New wording is **draft**, not previously reviewed, not a new spoken command,
and not a claim of medical or other efficacy. Function version numbers and
approval receipts are not invented for these additions.

## Tag vocabulary

Tags use the existing `localizedValue` contract. In en-US their concise display
values are lower-case, hyphen-separated concepts, also usable as normalized
search identifiers. They do not add a second stable-ID registry or imply that
other languages must display English identifiers. The generated index derives
the actual vocabulary and assignments from the active YAML, never this document.

Canonical terminology for this draft editorial pass:

- Thinking: attention, concentration, thinking, mental-clarity, numbers, memory,
  learning, choices, reflection, discernment, insight.
- Inner experience: inner-awareness, visualization, imagination, visual-memory,
  sensory-awareness, hearing, smell, taste, touch, dreams.
- Self-direction: intention, self-direction, habits, motivation, action,
  confidence, expression, communication, empathy.
- Well-being intentions: calm, relaxation, emotional-balance, letting-go,
  comfort, balance, renewal, transitions, body-awareness, circulation, breathing,
  nourishment, eating-choices, sexual-awareness.
- Activity and rest: movement, coordination, energy, rest, sleep, wakefulness,
  surroundings, temperature, safety.
- Function management: release, function-lifecycle.

These are descriptive facets, not diagnoses or promises. A tag is justified by
the function's existing description or narration, not merely by its title.

## Review boundaries

The six directional associations in `guide-review-001.json` remain approved,
optional and nonreciprocal. Their explanations are retained exactly. Draft tags
and common uses are useful discovery aids, but must retain their status in
machine views and be labeled as draft in human-facing guides.

Additional optional relationship suggestions belong in the source function's
localized YAML, not another editable relationship database. They require human
review before becoming approved guidance. A suggestion never authorizes audio
stacking, a prerequisite, a new activation procedure or a medical treatment.

Each `relationships.proposals` entry has an explicit draft status, optional
dependency, relation type (`related`, `complementary`, `suggested-before` or
`suggested-after`), target ID, rationale and description evidence for both
endpoints. Evidence hashes cover the exact existing localized descriptions.
Changes to either description require a fresh editorial evidence check; no
automatic factual approval follows. All current proposals explicitly decline
reciprocal behavior. A prerequisite is deliberately not a permitted proposal
type. No learning-order suggestion is added merely to fill a field.

To review a suggestion, inspect both source definitions, confirm direction and
wording with a human, preserve that approval's provenance, then move the same
target/rationale into the appropriate canonical relationship field. Do not
change `status` to bypass approval checks. Existing reviewed directional links
continue to require their existing review ledger.

`functions list --tag memory --search study --rich --json` filters the localized
catalog without selecting activation. API/MCP `ocf_list_functions` supports
the same `tag` and `query` facets. Rich details and generated JSON retain the
localized value/status objects. The master JSON's capabilities include both
canonical relationships and a separate proposals array. Human-readable guides
label draft metadata and separate draft relationship maps from reviewed links.

## Stub-free historical paths

The 65 unlisted predecessor references have been removed from active en-US
storage, not from history. `locale_history.read_logical(root, logical_path)`
resolves these exact identities through pinned
`function-content/editorial/historical-resource-map-006.json` and the unchanged
004/005 migration ledgers. Callers then choose their original predecessor
projection depth. Do not use filesystem reads for virtual historical paths.

The map preserves archive paths, original byte hashes, old stub hashes and
owning ledgers. It does not make a missing active manifest resource historical.
Every archive read verifies exact bytes without newline normalization; unknown
missing paths, traversal, symlinks, collisions and drift fail closed. A present
modified stub cannot be hidden by the archive. Active `LocaleCatalog` loading
still requires actual manifest-listed files.

Empathize reused a historical logical path before the 58-file rename. The
additional immutable 006 snapshot preserves its exact pre-enrichment bytes;
historical projection permits only discovery tags, common uses and proposals
to differ. All other fields must match before projecting to the unchanged
004/005 archives. No prior lock, ledger or baseline was rewritten.

Old migration writers remain frozen historical operations; their fixture
tests still exercise original stub publication. They are not rerun to perform
this cleanup. Current readers use the verified virtual map instead.

The noneditable fingerprint baseline in
`function-content/editorial/catalog-metadata-baseline-006.json` protects titles,
descriptions, commands, narration and reviewed relationships from accidental
changes during this pass; it contains no competing editable wording.
