# OCF candidate asset sources

See [branding and independent themes](../docs/BRANDING.md).
`identity.json` owns geometry/version/attribution; `themes/` owns palettes;
`surfaces.json` independently selects UI, cover and documentation themes.
Generate SVG/PNG variants with `ocf artwork brand`. These are original
review candidates, not a user-approved final public identity.

The baseline remains in `identity.json` and `candidates/`. The independently
versioned refinement is in `versions/0.2.0/`, with a
[responsive comparison gallery](versions/0.2.0/gallery/index.html). Refined
themes are opt-in; they do not change the existing surface defaults.

The supplied Cosmic Path kit is registered at `versions/0.3.0/identity.json`.
Its [comparison gallery](versions/0.3.0/gallery/index.html) retains cinematic
references alongside unchanged SVG/PNG companions and previous 0.2.0 artwork.
`ocf artwork import-review` verifies the pinned manifest and every supplied file.
The `ocf-cosmic-dark/light/minimal` themes are opt-in unapproved candidates.
