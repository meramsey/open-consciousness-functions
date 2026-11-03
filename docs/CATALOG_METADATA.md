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

The noneditable fingerprint baseline in
`function-content/editorial/catalog-metadata-baseline-006.json` protects titles,
descriptions, commands, narration and reviewed relationships from accidental
changes during this pass; it contains no competing editable wording.
