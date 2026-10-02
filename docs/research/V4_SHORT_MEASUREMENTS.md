# Supplied V4-short measurements and labelled F10 candidate

Evidence class: **measured directly from supplied V4-short reference excerpt**.
This analysis does not identify dates, neurological effects, or offsets in
other recordings. Historical identity discrepancies in the
[earlier audit](FOCUS_STATE_EVIDENCE_AUDIT.md) remain unresolved.

## Reproducible inputs and method

| Input | Duration | Format | SHA-256 |
| --- | --- | --- | --- |
| F10 V4 Volume Adjusted-short.flac | 399.530249s | 44100Hz stereo PCM16 FLAC | `dad8dd1a6e96bc1c1ccb6c42cce3306c1893e4edc749c710fdf36159577a2519` |
| F11 V4-short.flac | 564.588571s | 44100Hz stereo PCM16 FLAC | `3d1cef6a633f85024d90d93a4c42d6ac4eef0d98c0858bbadd18d6a6272e497b` |

Run `scripts/tools/analyze_v4_short.py` with explicit `--f10`, `--f11`,
`--output` paths, using Python with numpy, scipy and soundfile installed.
Reference bytes remain local/citation-only. Derived numeric results are in
[measurements.json](v4-short-data/measurements.json) and adjacent CSV files.

Tone windows: 20s centered at 20, 60, 100, 140, 180, 220, 260, 300, 340s;
edge windows 0–10s and final 10s; long windows 20–140, 140–260, 260–380s.
Hann FFT/log-quadratic interpolation estimates line positions. Complex
projections at nominal frequencies estimate amplitude/phase. Long 120s windows
resolve four complete 30s cycles; the 20s estimates of slow modulation are
not reliable independent measurements. Full-file RMS uses float64 accumulation.

Welch continuum uses 131072-sample windows, locally masks peaks >8dB above a
151-bin median, expands masks by three bins each side, and integrates remaining
uniform bins with excluded bins contributing zero. It does not interpolate
across line holes. Broad/non-detected tones can still contaminate this estimate;
it is an estimate, not an isolated source stem. Fits use averaged third-octave
density over 100–800Hz with a smooth, peak-corrected two-power-law model.

## F10 frequencies, orientation and temporal stability

| Family | Left / right Hz | R−L Hz | Resolved family power relative to 80Hz |
| --- | --- | --- | --- |
| Ground40 (additional directly detected component) | 39.75 / 40.25 | 0.50 | +3.88dB |
| Pair80 | 79.25 / 80.75 | 1.50 | 0dB |
| Pair160 | 158.05 / 161.95 | 3.90 | −4.76dB |
| Pair200 | 198 / 202 | 4.00 | −8.20dB |
| Pair320 | 317.95 / 322.05 | 4.10 | −10.87dB |

All five pairs persist in the measured interior and both edge windows, always
right-high. Ground40 and Pair80 frequency peak-to-peak variation is below
0.00004Hz in the short windows, with carrier-level variation below 0.008dB.
Upper-family estimates vary by up to 0.0062Hz and approximately 3–4dB in
short windows: continuum interference and **periodic amplitude modulation**
contribute; these numbers are not evidence of equivalent oscillator drift.
The 10s edge estimator is still less precise (up to ~0.01Hz displacement).
No measured edge loss of the five-family structure establishes an induction or
exit in this excerpt. Full-file RMS is −17.428L/−16.294R dBFS; complete 5s
windows span ~0.26L/~0.24R dB. This is a sustained acoustic construction,
not proof of a listener's state.

Resolved family powers combine carrier and first ±2Hz/±1⁄30Hz sidebands in
120s windows. They omit higher-order/mixed products, use dB-averaged per-ear
estimates, and are rounded for the candidate. Confidence: high frequency and
orientation; medium-high relative family levels. Narrowband R bias ~1.94dB
is very stable in low families; whether it is intentional mastering is unknown.

## Modulation and phase

Complex sideband ratios `u=upper/carrier`, `l=lower/carrier` distinguish AM
(`u+conj(l)`) from PM (`u−conj(l)`). Closure near ±180° and PM-dominated
ratios show that the ~2Hz structure is **not adequately represented as simple
AM**. Ground40/Pair80 PM index is ~0.063rad, while fractional AM is below
0.001. Their global modulation phases agree near 114° across ears/families.
Upper families have PM estimates ~0.12–0.14rad in long windows and larger
residual AM/phase scatter; continuum contamination makes their exact depths
and shared phase medium-confidence. No independent physiological purpose is
deduced from these rates.

Upper families also show **common-ear 30s AM**: depth ~0.31–0.35, with global
phase ~122° (160), −117° (200), and ~0° (320). Low families do not show comparable
slow AM. This staggered family arrangement is neither opposite-ear SAM nor
counter-rotating amplitude panning. Global phases are referenced to excerpt
sample zero; they are not recovered original session phases. Different-frequency
carrier IPD changes with time/beat; CSV carrier phases must not be treated as
fixed interaural phase offsets.

## Bed and spatial behavior

The main continuum has a broad 160–250Hz hump, strongest third-octave density
around 200Hz, then a steep curved fall. It has notches near the low tones and
complex residual/high-frequency structure. A single pink/brown color law is
inadequate. Masked 20–20kHz RMS is ~−25.98L/−25.97R dBFS in all three windows.
The energy-average 80Hz-family reference gives a rounded −0.8dB bed/tone ratio.

Main-band interaural coherence is high. Delay fits on strong coherent 500–5000Hz
bins yield R-lag −0.080, +0.138, +0.037 microseconds, ~2° phase residual. This
supports a zero-delay shared-bed approximation, not a claim of exactly identical
ears at every frequency: coherence declines around the steep rolloff/notches.

Unconstrained smooth fit: peak262.5Hz, rise+15.3/fall−56.0dB per decade,
RMS residual1.51dB. Farfield supports fall no lower than −48: constrained fit
peak241.1Hz, rise+20.2/fall−48, residual1.57dB. The fitted model peak differs
from the measured third-octave maximum; it is a compromise across 100–800Hz.
Neither fit models the full-band residual structure. Shape fitting, rounded
bed gain and symmetric-ear synthesis are **derived/design choices**.

## Matched F11-short comparison

The supplied F11-short is a different construction from the newer pure-SAM
reference recommendation. In 20–140s, the peak census finds shared ~50Hz with
±0.25Hz neighbors, ~99/99.78Hz, ~198/202, ~257/261, ~298/302, and
~396.25/403.75Hz lines. Several occur in both ears at unequal powers, so a
peak census alone cannot declare a clean ear-exclusive pair topology or SAM.
The ~7.5Hz upper split is materially unlike the newer three shared carriers
at256.869/323.625/384.875Hz with40Hz antiphase PM. Its continuum likewise has
strong coherent regions with near-zero delay fits, with distinct density shape
and levels. The supplied excerpt is comparative evidence, not proof that
newer F11 is wrong or that all F11 generations are acoustically equivalent.

No mapping to the older full-F11 file's time offsets is asserted. Detailed
F11-short modulation decomposition is follow-up research; this census does not
replace the established newer-source variant provenance.

## Candidate and runtime decisions

`OCF-BG-0012` is **V4-derived DEVELOPMENT CANDIDATE**, never universal F10.
It synthesizes all five measured right-high pairs and rounded family levels
with the constrained shaped shared bed. Symmetric ears, initial oscillator
phases, −6dBFS peak, seed0 and development state RMS−18dBFS are OCF choices.
The candidate uses no reference audio at runtime.

Farfield0.1.0 cannot express common-mode PM on different per-ear carriers or
the arbitrary family-staggered AM phases with its existing primitives.
**Both measured modulation arrangements are omitted**, along with exact
notches/high-frequency texture. Their omission makes this useful for testing
state dispatch and dominant spectra, but **not a faithful full reconstruction**.
We do not substitute false2Hz AM, opposite-ear SAM or a new binaural mechanism.
An exact future candidate needs a supported modulation model and separate
acceptance tests; current wording/disclosure must remain until then.

Canonical **newer** F11 selection is corrected to `OCF-BG-0006` pure SAM;
`OCF-BG-0007` remains a theta-enhanced alternate with its continuous175/179 pair
explicitly disclosed. Historical consumers/aliases remain research metadata.
This follows documented source recommendation, not inference from filenames.

Semantic dispatch starts F10 at the explicit `focus-ten.transition` ledger
event; it does not infer onset from induction prose. F10↔F11 crossfade windows
follow measured semantic end-dependent anchors. Curve choice, fallback5s,
state-level RMS calibration and combining different source generations are
OCF audition design choices, **not a measured source transition**.
