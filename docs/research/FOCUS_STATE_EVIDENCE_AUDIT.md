# Focus Ten evidence gate and Focus Eleven variant provenance

Audit baseline: OCF RC1 commit `061b2989ef13aca213112965d640fa43a036ec4a`.
Historical audit status at creation: **source/window verification blocked**.
Continuation: supplied V4-short excerpts now have direct
[measurements and a labelled candidate](V4_SHORT_MEASUREMENTS.md).
The old-source identity/offset questions below remain unresolved; the new
short excerpts supply an independent time axis rather than resolving them.
RC1 narration, sessions, localization, commands, cues and DSP selections are
preserved. This report records existing evidence; it is not fresh signal analysis.

## Evidence classifications

| Classification | What it establishes | What it does not establish |
| --- | --- | --- |
| Source metadata verified | Local bytes/checksum, duration, format and channel count | Recording lineage, Focus-state identity, clean sustained-state boundaries |
| Prior measurement record | What the cited analysis measured on its own named source/windows | Fresh verification here or matching offsets in another transfer |
| Measured-reference reconstruction | Independently synthesized representation using recorded measurements | Every parameter is measured, or the render is an original source recording |
| Derived parameter | Arithmetic, fitting, idealization or calibration based on evidence | A directly observed recording value |
| Design-selected/experimental asset | An authored recipe, schedule, amplitude target or alternate for audition | Evidence that its components define a canonical sustained state |
| Historical/semantic metadata | Recorded consumers, choices, event identity and ordering | Acoustic source identification or validation of a DSP implementation |

In particular, preset `fidelity: measured-tape`/`measured-mss` labels do not
turn normalization targets, fitted bed levels, temporal arrangements or retained
mastering artifacts into measurements. The inventory records mixed provenance
explicitly rather than assigning one blanket “measured” status to a whole asset.

## Stop-gate finding

The local `F10 V4 Volume Adjusted.flac` probes as **3600.000000 seconds**,
44.1 kHz, stereo, 24-bit FLAC. `OCF-BG-0004` describes its reference as
**3900 seconds**. The Farfield tape measurements describe a **1938.5-second**
Free Flow 10 transfer, while the MSS measurements describe a **2622.05-second**
MP3 remaster. These are not interchangeable time axes.

No source hash/verified edit map ties either measured source's windows to the
available 3600-second V4 file. The recorded 30-minute Focus Ten WAVs are syntheses,
not independent reference recordings. Original audio matching the two Farfield
measurement records was not found in the OCF checkout or the documented Farfield
source checkout. `references/uploads/` contains only its placeholder file.

The stop gate is triggered: clean acoustic blocks in a different source cannot
be relabelled confirmed sustained Focus Ten in V4. A filename and an operator
reference-master description alone do not establish induction/sustain/exit
boundaries or validate all source variants. No arbitrary V4 FFT windows were
selected and no replacement DSP was invented.

## Source identity and provenance

| Source | Availability / identity | Recorded/claimed reference windows | Confidence / suitability |
| --- | --- | --- | --- |
| `F10 V4 Volume Adjusted.flac` | Local, gitignored; 3600s / 44.1kHz / stereo / 24-bit | None verified for this checksum | Metadata high confidence; content lineage and sustained-state segmentation pending-source-review |
| Older Gateway Free Flow 10 transfer | Prior Farfield measurement record: 1938.5s; original audio not found | Clean acoustic blocks listed below, not verified against a local matching source | Documented measurements, not independently remeasured here |
| Earlier longer transfer of that same tape | `bed-results.json` records an 80s-longer transfer, superseded by the 1938.5s copy | No edit map or original file identified | Do not transfer offsets by guessing where the extra time was inserted |
| MSS3D Freeflow 10 remaster | Prior Farfield measurement record: 2622.05s / 48kHz / stereo / 320kbps CBR MP3; original not found | Six voice-free windows listed below | Detailed prior evidence; requires source identity and state-boundary confirmation before this implementation |
| `F11 V4.flac` | Local, gitignored; 3468.186939s / 44.1kHz / stereo / 24-bit | OCF reference splice: 2850–3177s | F11 reference, not a Focus Ten source; older archive's 414–747s window is not proven to belong to this exact checksum |
| Newer F11 MP3 | Archive describes 44.1kHz / stereo / 320kbps and reports user-confirmed 960–1620s | 16:00–27:00 according to that record | Original file/hash not identified here; variant distinction is explicit in archives/history |

Local recording SHA-256 identities:

- F10 V4: `18c71de3fa72e3252147fc9d3cae2f360304fcc4ef45ce5f96cca4590a4bb02a`.
- F11 V4: `6d0feff8c0e02282b8d8098d1eda126029159a56f8b1b447527a7e80f8c3312e`.

The duration mismatch is reported rather than silently rewriting historical
reference provenance. Existing manifests may describe earlier local artifacts.

## Complete artifact inventory

See [machine-readable inventory](focus-state-source-inventory.csv) for source
windows, consumers and canonical-use dispositions.

- **Measured-reference reconstructions:**
  `audio/background/presets/farfield/focus-10.yaml` and `focus-10-mss.yaml`.
  Neither is a native canonical OCF sustained-state manifest. Both encode
  session-scale schedules, with disclosed idealizations/design choices.
- **Generated tone beds:** OCF `audio/background/rendered/focus-10-stem.wav`
  and Farfield checkout `focus-10.wav` both probe as 1800s / 48kHz / stereo /
  signed 24-bit PCM. They cannot serve as original measurement references.
- **Authored session composite:** `attention-focus-10-11-10.yaml`, consumed
  by `OCF-BG-0001`. It layers F11 into an Attention-specific F10 reconstruction;
  391/770s, 30s overlaps and the -6.7dB composition gain are not a new F10
  measurement. Its header says only segment 3 is reused, while its actual YAML
  retains all five upstream sections (with section 3 split). Inspect actual
  data rather than relying on that inaccurate shorthand.
- **Experimental/design-selected beat arc:** `attention-focus-arc.sbg`,
  `OCF-BG-0002`, and synthetic `attention-focus-bed-sbagenx.wav`: one 200Hz
  carrier with 10→16→10Hz beat schedule. It explicitly does not define the
  Focus-state identity. It is not measured sustained Focus Ten evidence.
- **Historical composites:** `OCF-BG-0003` / `attention-focus-bed-v2.wav`,
  `OCF-BG-0004` / `attention-focus-bed-v3.wav`, and `OCF-BG-0011` combine
  reference or synthetic beds with F11. These are consumers/recipes, not
  independent Focus Ten sources. `attention-focus-bed.wav` is explicitly a
  retained superseded Focus-3-based historical artifact in `OCF-BG-0001`.
- **Legacy induction artifact:** `focus-3-stem.wav` is not Focus Ten evidence
  and does not establish a required preparatory state.
- **SBaGenX:** no standalone Focus Ten `.sbg` was found. OCF has the Attention
  arc plus F11 a/b/c files; staging copies under `presets/sbagenx/` are F11 only.
- **Research notes/data:** documented installed Farfield checkout
  `/home/mike/Documents/dev/farfield/docs/tape-analysis/` contains `report.md`,
  `results.json`, `bed-results.json`, `mss-report.md`, `mss-results.json`, and
  F21 supporting comparisons. These are absent from OCF's own `docs/`.
  Farfield research data carries CC0; the engine/presets remain external source
  material and are not vendored by this audit.
- **Tests:** Farfield `test_presets_measured.py`, `test_bed_acceptance.py`,
  `test_mss_acceptance.py`, `test_presets_mss.py`, and library tests verify
  reconstructions against recorded numbers. OCF `test_focus_sequence.py`,
  Farfield integration tests and locale-render tests verify IDs, file resolution
  and old Attention splice timing, not original Focus Ten recordings.
- **Documentation/consumers:** `BACKGROUND_AUDIO.md`, generated background
  index, `USER_GUIDE.md`, Attention function history and `OCF-AUDIO-0001`
  document these uses. RC1 only declares semantic Focus Ten; V1 expressly
  supplies no F10 DSP. Semantic event presence is not acoustic evidence.

## Prior window evidence, not windows analyzed in this audit

**Older 1938.5s transfer:** `results.json` records the A/B/C full-stack clean
acoustic blocks 480–600, 600–720, 840–960, 960–1080 and 1200–1320s. The
360–480s block overlaps component entrances (B starts ~350s, C ~420s).
720–840 and 1080–1200s have higher recorded broadband activity and need
contamination review rather than automatic pooling. 0–120, 240–360 and the
last ~1920s onward blocks contain voice/music. A exits around 1370s and C
around 1570s; later B-only material is a different layer configuration.
`bed-results.json` uses **1200–1900s** for bed measurements, which crosses those
layer exits and must not be treated as one stationary full-stack state.

**MSS 2622.05s source:** recorded voice-free windows are **500–620, 700–820,
1100–1220, 1500–1620, 1700–1820 and 2100–2220s**. The recorded body has
ground+delta and theta through 480–2480s, then theta-only 2480–2500s.
Intro music is 260–400s; closing music 2570–2600s. Eighteen recorded narration
spans occur from 127–2602s. These exact offsets are useful candidates on a
matching source, not validated offsets for the local V4 bed.

**Fresh sustained-state windows analyzed here: none.** Metadata and existing
reports were inspected, and source identities hashed; no new spectral or
phase/AM/SAM measurement is being claimed.

## What the existing measurements say

| Component | Older tape record | MSS remaster record | Confidence for this audit |
| --- | --- | --- | --- |
| Low structure | A: L99.98/R104.03Hz median; beat ~4.05Hz, drifting ~4.12→3.89 | Ground L48.850/R49.150Hz, 0.300Hz split; delta L97.2484/R98.7492Hz, 1.5008Hz split | Prior measured values; not locally reverified |
| Other pairs | B: L298.63/R302.48Hz, ~3.85Hz split; C: L497.01/R493.31Hz, ~-3.70Hz signed R−L | Theta low/high 193.9976/197.9982, 244.9410/248.9422, 291.6647/295.6651Hz; ~4.001Hz | Prior measured values; no common fixed recipe established |
| Orientation | A/B right high; C left high | Theta members counter-rotate every 30s; cannot describe one permanently higher ear | Render sign relationships documented, not guessed |
| Modulation | B common-ear tremolo ~0.58→0.48Hz, index ~0.22; second harmonics ~-29dB | Ground per-ear 0.25/0.50Hz tremolo, index ~0.83; theta amplitude rotation; delta crossfeed | Distinct topologies; do not replace amplitude rotation with SAM |
| SAM | No defining shared-carrier SAM family documented for this tape | Mid/side analysis reports SAM absent/bounded; 40Hz exit beats are not SAM | Not proof that all other possible F10 sources lack SAM |
| Bed | Brown-like slope ~-22dB/decade; coherent bed below ~4kHz, ~145µs L lead, independent hiss above ~6kHz | Shaped low-frequency hump ~88Hz, decorrelated bed, panned texture ~7.5s, common-mode swell | Separate measured versus fitted preset parameters are explicit |
| Persistence | Layer entrances/exits and independent drift; full program is not one static state | Ground/delta + rotating theta dominate body; other Focus-layer triads absent | Prior schedules, not verified V4 state annotations |

Existing evidence supports **materially different constructions**, not merely
mastering differences. The MSS report explicitly says the earlier F10 recipe
was rebuilt. It remains insufficient to infer a production generation/date or
one cross-source canonical OCF design without matched original audio/window review.
No psychoacoustic purpose is deduced from the numeric rates.

## F11 175/179 provenance: a clear variant-selection mismatch

### Documented sustained-state versus alternate distinction

| Role in the earlier evidence | Existing preset/manifest | Signal structure | Level/persistence qualification |
| --- | --- | --- | --- |
| Recommended canonical **newer** F11 reference reconstruction | `focus-11-gamma-pink.yaml`; OCF alias `focus-11-b.yaml`, `OCF-BG-0006` | Three closed-path 40Hz antiphase-SAM families at 256.869, 323.625 and 384.875Hz; no 175/179 pair | Pink-bed -7.4dB is audition-calibrated; exact source mastering is not recovered |
| Theta-enhanced audition alternate | `focus-11-gamma-theta-pink.yaml`; OCF alias `focus-11-c.yaml`, `OCF-BG-0007` | Same SAM families plus L175/R179Hz conventional 4Hz pair at configured group level -7dB | Source pair was intermittent; the preset's continuous 30-minute presence is an alternate arrangement/design choice |
| Separate older F11 reconstruction | `focus-11-older-flac.yaml`; OCF alias `focus-11-a.yaml`, `OCF-BG-0005` | Conventional ~4Hz and ~7.4Hz pairs, not the newer SAM stack | Different recorded source/window; not a substitute selected merely because its filename also says F11 |

“Canonical” in the first row describes the **earlier documented recommendation**.
The present OCF consumer mapping still selects the second row for V1. This
report exposes that disagreement; it does not itself change configuration,
rename/delete compatibility aliases, or make a new runtime canonical selection.

### Trace through archives and Git history

1. `focus11-farfield-updated.zip` explicitly recommends
   `focus-11-gamma-pink.yaml` as the canonical sustained newer F11 state,
   from the confirmed **960–1620s** window. It explicitly calls
   `focus-11-gamma-theta-pink.yaml` an alternate because 175/179Hz is not
   continuously dominant. Pink-bed -7.4dB is audition-calibrated, not recovered
   mastering. The theta-enabled YAML schedules the pair persistently for 30min:
   that is the alternate's arrangement, not measured persistence.
2. Farfield commit **`c0596d2`**, 2026-09-29 18:47:27 -04:00, adds both presets.
   Its theta preset says **“audition variant rather than the canonical
   sustained-state preset.”** This is the earliest tracked introduction found;
   ZIP member dates do not prove the absolute moment of authorship.
3. Farfield **`5ff8869`**, 2026-09-29 19:12:22 -04:00, fixes noise/pair syntax
   and shortens notes, retaining the same theta topology. It does not newly
   introduce the pair. `focus11-farfield-fixed-bed.zip` still recommends pure SAM.
4. OCF bootstrap **`6d35e94`**, 2026-09-30 18:43:40 -04:00, imports alias
   `focus-11-c.yaml` with internal name `focus-11-gamma-theta-pink` and registers
   it as **canonical** in `OCF-BG-0007`. Prior uncommitted alias history is not
   available. Attention's dated 2026-09-29 history also records choosing
   gamma+theta+pink; it supplies no measurement-based justification for making
   the intermittent component canonical.
5. RC1 V1 development manifest at `/tmp/opencode/OCF-Preparation-Learning-en-US-RC1-dev-audition-061b298/render-manifest.yaml`
   explicitly selects `OCF-BG-0007` / `focus-11-c.yaml`, thereby inheriting this
   persistent alternate. The external development runner made that choice;
   RC1 semantic session data does not name this Farfield preset.

`OCF-BG-0007` lists the correct carriers and includes the pair, but its
“intermittent” wording omits that the preset renders it continuously, and its
canonical designation conflicts with the earlier recommended pure state.
OCF tests enforce `OCF-BG-0007`→`focus-11-c.yaml` resolution, **not** the pair's
frequencies, duty cycle or canonical measurement status. The a/b/c SBaGenX
variant also explicitly calls c alternate; b/c approximate SAM rather than
providing Farfield's actual topology.

**Evidence-based disposition:** recommend the already existing pure-SAM
`OCF-BG-0006` / `focus-11-b.yaml` (equivalent to `focus-11-gamma-pink.yaml`) for
canonical newer F11 selection, preserving c/theta-enhanced as an explicitly
named alternate. This audit does not change those mappings because the Focus
Ten source-confidence stop gate is active. Do not delete historical consumers.

Audit input fingerprints, useful for locating the exact records reviewed:

- `focus11-farfield-updated.zip`: `5cefcd8f3c9d874612390387cc4e1617ed3ba1112658e9c1bb0dccb035a028bf`.
- `focus11-farfield-fixed-bed.zip`: `469f8c2b3a756e094f7fd25f4e88e3ed4c2d88400899adb1a4cf74c7fcd0efa1`.
- Committed `focus-11-b.yaml`: `d9e87888d2ed92851e6beba78ea5a4895e1298a99c799318398b65154ee132aa`.
- Committed `focus-11-c.yaml`: `f201452248fcc6a177b8a95c66ab7ce89b75cdb3ae46fa0b7d149a707dbb45bc`.

Hashes identify artifacts; they do not establish source-state semantics or
promise a TTS/audio rebuild produces identical bytes.

## Inputs needed to continue

1. Identify the available 3600s F10 V4 recording's origin, generation/session
   purpose and any editing/resampling/concatenation relative to measured sources.
   Resolve the 3900-versus-3600 discrepancy without guessing an offset.
2. Supply a matching original older 1938.5s transfer and/or MSS 2622.05s recording
   with hashes, or confirm which different local reference is to be measured.
3. Confirm exact sustained Focus Ten intervals from source-review context,
   excluding induction/exit/other states; the MSS voice-free windows above are
   candidates, not automatic semantic confirmation.
4. Then verify multiple subwindows for lines, ear orientation, drift, amplitudes,
   sidebands, AM/PM separation, bed slope/rolloff, coherence and mid/side behavior.

Design/preset choices, onset alternatives A/B/C, continuous F10↔F11 morphs,
generic semantic DSP dispatch and V2 are deferred. Spectral stationarity alone
cannot determine which pre-state portion should be labelled Focus Ten. The
V1 narration stem and measured ledger should be reused unchanged in V2 to
isolate DSP differences, since fresh TTS is not bit-exact.
