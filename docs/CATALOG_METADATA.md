# Function discovery metadata

Each `locales/<tag>/OCF-*.yaml` file is the sole authority for that function's
localized title, description, tags, common uses, and relationships. Runtime
discovery and guide-generation views derive from those canonical resources.
There is no separate function metadata or relationship sidecar registry.

## Vocabulary and review boundaries

Tags and common uses are descriptive facets, not diagnoses or promises. Each
locale owns its localized display values and semantic identifiers. Missing
translations remain missing; English speech is not inherited.

Function-specific reviewed relationship explanations live beside the owning
function. The canonical resource also carries hash-only editorial approval
provenance. Optional relationships do not establish sequencing, synergy,
prerequisites, clinical benefit, or audio stacking. Draft proposals remain
explicitly non-authoritative until a human review changes their status.

Discovery normalization uses Unicode normalization, case folding, and
whitespace folding only. It is not an acoustic cue matcher and never selects an
activation target. Historical vocabulary remains separate from active commands.

`functions list --tag memory --search study --rich --json` filters the localized
catalog without selecting activation. API/MCP `ocf_list_functions` supports the
same `tag` and `query` facets. Rich details preserve localized value/status
objects; generated human guides derive from canonical locale data.
