# Background Audio

How OCF integrates optional generated background beds via **Farfield**,
**SBaGenX**, and operator-supplied **reference-master** beds.

## Separation requirement

- A **background preset is not a function**.
- A **background preset is not a training script**.
- A **training script is not an audio render**.

They are modeled independently:

- one function may use several different backgrounds;
- one background can be reused by several functions;
- audio implementations reference backgrounds by `OCF-BG-*` id.

## Farfield

[Farfield](https://github.com/txus/farfield) is an **optional external
synthesis engine**. OCF:

- detects it on PATH (`ocf audio check-engine`);
- invokes only its **public CLI** (`farfield list`, `farfield describe`,
  `farfield render`);
- never hardcodes undocumented internal APIs;
- does **not** vendor Farfield source by default;
- degrades gracefully with installation guidance when it is absent.

If a stable Python API is documented upstream in the future, an adapter may be
added — until then the CLI wrapper is the contract.

### Preset resolution

`farfield render` accepts only a **session YAML path** — it has no built-in
name lookup — and Farfield's wheel deliberately ships no presets at all (its
`RECORD` has zero preset entries). They live only in the source checkout.
A preset may therefore be named rather than pathed, and OCF searches, in order:

1. `OCF_FARFIELD_PRESETS_DIR` (`os.pathsep`-separated), when set;
2. `audio/background/presets/farfield/` — the presets OCF commits;
3. `audio/background/presets/` — OCF-authored compositions;
4. `<farfield source checkout>/presets` — an extension tier, located via the
   install's PEP 610 `direct_url.json`.

The committed tier outranks the checkout on purpose: a build must be
reproducible from the repository alone, and the checkout differs between
machines and Farfield versions. `OCF_FARFIELD_PRESETS_DIR` only *raises*
priority — the committed tier always stays in the chain, so an override can
shadow a preset but never make a committed one unreachable.

The committed Farfield directory contains 19 pinned upstream mirrors and three
historical contribution aliases. The external-checkout tier is not needed to
build. `OCF-BG-0001` resolves its OCF-authored composition through its manifest.
A name that resolves nowhere fails the
build when `strategy: required`, reporting every directory searched.

Resolution order in `_farfield_preset_file`, most preferred first:

| Order | Input | Behavior |
|---|---|---|
| 1 | an explicit path | used verbatim, never redirected |
| 2 | a background id (`OCF-BG-0007`) or bare name (`focus-10`) | searched across the chain above |
| 3 | a background manifest's `preset.file` | used when the name matched nothing |

## SBaGenX

[SBaGenX](https://github.com/lm7137/SBaGenX) (a GPL-2.0 fork of SBaGen+,
originally SBaGen by uazu.net) is a second **optional background engine** that
generates binaural, isochronic and monaural beat beds from `.sbg` sequence
files or built-in programs (`-p drop|slide|sigmoid|curve`). OCF:

- detects it on PATH (`ocf audio check-engine`);
- invokes only its **public CLI** (`sbagenx -h`, `sbagenx -D FILE`,
  `sbagenx -SE -Wo OUT FILE`);
- does **not** vendor SBaGenX source; GPL provenance is recorded in manifests;
- selects it per-manifest with `engine: sbagenx`;
- degrades gracefully with installation guidance when it is absent.

SBaGenX renders are deterministic (no entropy), so `render.seed` stays `null`
with `render.deterministic: true`. Binaural content requires headphones and is
covered by each manifest's `headphone_notice`.

## Reference-master

`reference-master` is a **process engine** rather than a synthesis engine: it
assembles an even-timbre bed from **operator-supplied reference masters** that
live outside the repository (citation-only, never vendored). OCF:

- resolves the reference files relative to the repository root
  (`reference.source`, e.g. `F10 V4 Volume Adjusted.flac`);
- decodes via **ffmpeg** (the only hard requirement; `_decode_to_s16le`);
- splices excerpts from a second source into time windows
  (`reference.splices[].source`, `slice_start`, `slice_length`,
  `target_start`, `crossfade`), gain-matching each splice to the bed RMS with
  linear crossfades (e.g. the F11 access excerpt at 6:31-11:58 in
  `OCF-BG-0004`);
- truncates the composite bed to the narration duration;
- when ffmpeg or the reference files are missing, degrades gracefully with a
  `reference-master-unavailable (narration only)` message for optional
  strategies (required strategies raise `OCFError`).

The reference-master engine avoids synthetic-beat generation for attention
material and is what `OCF-BG-0004` uses, and what `OCF-BG-0011` builds on with
an OCF-authored arc plus the OCF-authored Focus-11 access state.

## Canonical Focus-state sequence

The Focus 11 Access Channel background program is:

```text
Focus 10  ->  Focus 11  ->  Focus 10
  pre-access   access window   return
```

**Focus 3 is not part of it.** Focus 3 may serve as an optional
induction/preparation mechanism in the preparation layer; it must not redefine
the Focus 11 background program.

The following is a historical fixed-timeline reference-master example, not the
current complete-session timing default. Complete sessions bind the Focus 11
window to explicit entry/programming/exit events, with Focus 10 through opening,
preparation, sleep, return and closer, existing 25-second transitions and a
10-second ending fade. The four body passes and configured -24 dB sleep underlay
are unchanged; a Focus number never implies a new frequency or Focus 20 DSP.

`focus_sequence` in a background manifest records this progression in a
language-independent, machine-readable form, so a locale change cannot alter it:

```yaml
focus_sequence:
- state: focus-10
  role: pre-access
- state: focus-11
  role: access-channel
  start_s: 391.0    # 6:31, access window opens
  end_s: 770.0      # 12:50, access window closes
  crossfade_s: 30
- state: focus-10
  role: return
```

`focus-3` is deliberately absent from the schema's allowed states, so a
manifest cannot reintroduce it. Those three timing values are the measured ones
from the `OCF-BG-0011` splice; no other boundaries are asserted, because the
bed is trimmed to the narration length.

Earlier metadata described a `focus-3 -> focus-10 -> focus-3` arc for
`OCF-BG-0001`. That framing was wrong and is superseded — see its provenance
notes. `OCF-BG-0001` now directly renders the OCF-composed Farfield session
`audio/background/presets/attention-focus-10-11-10.yaml`. It layers the
Focus-11 groups over the continuing Focus-10 groups during the access window.
`OCF-BG-0011` remains the reference-master alternative.
`tests/test_focus_sequence.py` fails if Focus 3 returns.

## Where preset files live

`preset.file` in a manifest is a path relative to the repository root, and both
`describe-background` and `render-background` pass that file to the engine.
So a manifest can point at a preset that lives anywhere OCF can commit it:

| Location | Purpose |
| -------- | ------- |
| `audio/background/presets/farfield/*.yaml` | OCF-committed Farfield presets |
| `audio/background/presets/sbagenx/*.sbg` | OCF-committed SBaGenX sequences |
| `presets/farfield/`, `presets/sbagenx/` | staging copies prepared for upstream contribution; not referenced by manifests |

`OCF-BG-0005`–`OCF-BG-0010` are the Focus-11 family (Farfield `a`/`b`/`c` and
SBaGenX `a`/`b`/`c`), and all six point at the committed mirrors. Keeping the
mirrors inside `audio/background/presets/` means a build does not depend on
anything outside the repository, whether or not upstream merges the
contribution. If a preset is never merged upstream, nothing here needs to
change: a name that only the committed copy carries still resolves in the
committed tier of the search path above.

PR 1 was merged at upstream commit
`019fb804f3b274359e13e8cc9ca3b8fcaf9701f3`, incorporating maintainer review
`b6201835640cdbe13c96e43d68c839c8ac701942`. That snapshot has **19** presets.
The 22 files in `audio/background/presets/farfield/` comprise those 19 exact
mirrors plus three historical `focus-11-a/b/c.yaml` aliases. Two additional
OCF compositions live in the parent directory; three nonruntime staging copies
live in `presets/farfield/`. None was deleted to match upstream's count.

The reproducible [inventory](../audio/background/farfield-inventory.json) records
paths, SHA-256 bytes, source revisions, classifications and current fidelity.
Frozen alias bytes retain their historical metadata; their current provenance is
**best-effort**, not independently measured by Farfield. The selected background
and immutable defaults locks are unchanged. Engine version `0.1.0` does not
identify preset bytes or guarantee support for this classification.

The three contributed named presets now carry upstream's `best-effort` category:

- `focus-11-gamma-pink`: contributed SAM interpretation with evidentiary limits.
- `focus-11-gamma-theta-pink`: continuous arrangement of a reportedly intermittent
  theta pair; the recommendation of the pure variant does not change OCF selection.
- `focus-11-older-flac`: separate recording and reconstruction, not newer SAM evidence.

`sam-gamma.yaml` retains its existing synthesis while acknowledging the contributed
claim. All four updates change descriptive metadata only. Upstream attribution
and terms are retained in `audio/background/FARFIELD-NOTICE` and
`audio/background/FARFIELD-LICENSE`. A merge or fidelity tier is neither efficacy
evidence nor release/rights approval.

### Explicit verification and optional engine setup

Ordinary builds never fetch or synchronize upstream. Offline inventory check:

```bash
python -m ocf_tools.farfield_inventory
```

Maintainers can explicitly refresh from a local checkout containing the pinned
commit; every declared synthesis field must match before metadata is updated:

```bash
python -m ocf_tools.farfield_inventory --refresh-from .ocf-work/farfield-followup-upstream
```

Use a separate optional engine environment, preserving any running installation:

```bash
python -m venv .ocf-work/farfield-followup-env
.ocf-work/farfield-followup-env/bin/python -m pip install "farfield @ git+https://github.com/txus/farfield@019fb804f3b274359e13e8cc9ca3b8fcaf9701f3"
.ocf-work/farfield-followup-env/bin/farfield describe audio/background/presets/farfield/focus-11-gamma-pink.yaml
```

On Windows use the environment's `Scripts/python.exe` and `Scripts/farfield.exe`.
Select that environment's executable directory on the child process PATH when
rendering. Use the workspace environment resolver for child temporary/cache
paths. Test the actual `describe` command: older engines reject `best-effort`,
sometimes even with a zero exit status. OCF diagnoses that response; never
relabel the preset `measured-tape` to satisfy an older parser. User preset
overrides still take priority. Metadata changes invalidate full preset-byte
identities even when acoustic inputs match; old artifact provenance is not new
verification.

### Analysis follow-up boundary

The maintainer requested the original newer recording's 16:00–27:00 window,
using mid/side complex projection and JSON evidence. At the pinned revision,
README describes that estimator, but `farfield.analysis` contains only
`sam_signature` (IPD/mono-envelope diagnostics), not the report's complex
sideband phase-versus-pan decomposition. These are different methods. Request
the exact estimator/script and settings before claiming the requested analysis.
Synthetic controls must include phase modulation, amplitude panning, a binaural
pair and insufficient evidence. No original-recording result is inferred from
generated presets. Real-source JSON remains local pending explicit source mapping
and sharing review; the older-FLAC recording remains separate.

The SBaGenX sequences use `-R 10` (recalculation rate 10). The much larger
`-R 1000` value makes `sbagenx` abort with a floating-point exception, so the
committed mirrors must keep the supported rate.

## Manifest (`schemas/background-audio.schema.json`)

Key fields: `engine` (`farfield | sbagenx | reference-master | custom | none`),
`engine_source.repository`, `preset.file`, `reference` (`source`, optional
`splices[]`), `render.output`, `render.seed`, `render.deterministic`,
`usage.functions`, `usage.audio_implementations`, `provenance`, `safety`
(headphone notice, driving warning), `license`.

Deterministic renders record a seed so CI/community can reproduce output;
SBaGenX renders are deterministic by construction (seed stays `null`);
reference-master beds are deterministic given fixed source files
(`render.deterministic: true`).

## CLI

```bash
./scripts/ocf audio check-engine
./scripts/ocf audio list-background
./scripts/ocf audio describe-background OCF-BG-0001
./scripts/ocf audio describe-background OCF-BG-0002 --engine sbagenx
./scripts/ocf audio render-background OCF-BG-0001 --output custom.wav
./scripts/ocf audio render-background OCF-BG-0002 --engine sbagenx --output bed.wav
./scripts/ocf audio render-background OCF-BG-0004 --engine reference-master --output bed.wav
```

`render-background` and `describe-background` accept
`--engine farfield|sbagenx|reference-master`. A preset's manifest `engine` is
honored automatically when no `--engine` flag is passed (the default `farfield`
acts as "auto"); an explicit `--engine` overrides the manifest. When an engine
or its prerequisites are missing, these print the same helpful guidance instead
of crashing.

## Safety

- Presets set `headphone_notice` and `driving_warning`.
- OCF promises **no** psychoacoustic or health effects.
- Rendered files live under `audio/background/rendered/` (gitignored).
