# Repository presentation candidates

These versioned exports use the supplied 0.3.0 artwork, without redrawing it.
`readme-hero.png` is a native-resolution crop of the cinematic dark-logo reference
with its panel label/border removed. It is not a production cinematic master.
`github-social.png` is the unchanged supplied 1280 × 640 social PNG companion.
The manifest records source/export hashes, crop and candidate provenance.

Formal brand approval remains unset. Reference imagery and companion vectors
are different visual assets; no exact vectorization or high-resolution cinematic
album reproduction is claimed. Originals in the import kit remain untouched.

## Set the GitHub social preview

Repository maintainers can open **Settings → General → Social preview → Edit →
Upload an image**, then select `github-social.png`. Review GitHub's crop preview
before saving. This image is already 1280 × 640 and below GitHub's size limit.
No repository setting was changed by this export or verification command.

Verify with `python scripts/tools/brand_presentation.py --check`. To regenerate
for a new candidate review, use `--write --output .ocf-work/NEW_PRESENTATION_DIR`;
existing export directories are never overwritten.
