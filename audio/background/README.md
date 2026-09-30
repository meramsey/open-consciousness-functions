# Background audio

Optional, generated background beds for OCF training scripts. See
`docs/BACKGROUND_AUDIO.md` for the full design.

## Layout

| Path         | Purpose                                             |
| ------------ | --------------------------------------------------- |
| `presets/`   | Engine preset definitions (e.g. Farfield YAML)      |
| `manifests/` | `OCF-BG-*` manifest records (YAML)                  |
| `rendered/`  | Generated output files (gitignored)                 |

## Key rules

- A **background preset is not a function** and **not a training script**.
- One function may use several backgrounds; one background may serve several
  functions.
- The optional engine is [Farfield](https://github.com/txus/farfield); OCF
  only speaks its public CLI and degrades gracefully when it is absent.
- No psychoacoustic or health effects are promised.

## CLI

```bash
./scripts/ocf new background        # register a manifest
./scripts/ocf audio check-engine
./scripts/ocf audio list-background
./scripts/ocf audio describe-background OCF-BG-0001
./scripts/ocf audio render-background OCF-BG-0001 --output out.wav
```