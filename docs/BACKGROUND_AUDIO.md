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
3. `<farfield source checkout>/presets` — an extension tier, located via the
   install's PEP 610 `direct_url.json`.

The committed tier outranks the checkout on purpose: a build must be
reproducible from the repository alone, and the checkout differs between
machines and Farfield versions. `OCF_FARFIELD_PRESETS_DIR` only *raises*
priority — the committed tier always stays in the chain, so an override can
shadow a preset but never make a committed one unreachable.

All 22 Farfield session presets are currently committed, so tier 3 is not
needed to build and `OCF_BG-0001` (a Focus-10 arc with no preset file of its
own) resolves like any other name. A name that resolves nowhere fails the
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

```
Focus 10  ->  Focus 11  ->  Focus 10
  pre-access   access window   return
```

**Focus 3 is not part of it.** Focus 3 may serve as an optional
induction/preparation mechanism in the preparation layer; it must not redefine
the Focus 11 background program.

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
notes. `OCF-BG-0001` records the canonical sequence but is not directly
renderable (a single Farfield session is a sequential segment list and cannot
express a spliced middle state), so `preset.file` stays null; `OCF-BG-0011` is
the operational realization. `tests/test_focus_sequence.py` fails if Focus 3
returns.

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
change: a name that only the mirror carries still resolves, as the last tier
of the search path above.

That contribution has since landed, and all 22 Farfield session presets are now
committed under `audio/background/presets/farfield/`, byte-identical to
upstream 0.1.0. The repo tier therefore serves every name and the checkout
tier is a convenience, not a dependency.

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