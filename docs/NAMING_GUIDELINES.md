# Naming Guidelines

## Functions

- Canonical names are human-readable, sentence-case: `Attention`, `Think Fast`.
- Slugs are kebab-case and stable: `think-fast`, `emergency-injury`.
- IDs are permanent: `OCF-CognitiveDomain-…`.

## Commands

Covered fully in `COMMAND_GRAMMAR.md`. Summary:

- one meaningful word after `PLUS` is preferred;
- two words are acceptable (`PLUS-SLEEP EASY` — a single compound idea);
- three words is the exceptional maximum;
- never pad with `NOW`, `SYSTEM`, `FUNCTION`, `ACTIVATE`;
- keep canonical commands ≤ legacy length, normally;
- preserve good legacy words (`THINK`, `FOCUS`, `RECALL`, `ENERGIZE`).

## Domains

| Directory       | ID prefix | Scope                                      |
| --------------- | --------- | ------------------------------------------ |
| `foundation`    | `FND`     | base states: attention, energy, reset, release |
| `cognition`     | `COG`     | thinking, recall, calculation, contemplation|
| `emotion`       | `EMO`     | feeling states and processing              |
| `communication` | `COM`     | expression, speech                         |
| `body`          | `BOD`     | body-directed practices                    |
| `performance`   | `PRF`     | speed, strength, coordination              |
| `sensory`       | `SEN`     | senses and inner perception                |
| `sleep`         | `SLP`     | sleep, dreaming, waking                    |
| `lifestyle`     | `LIF`     | everyday behavior patterns                 |
| `emergency`     | `EMG`     | urgent self-help contexts                  |
| `automation`    | `AUT`     | running states automatically               |
| `experimental`  | `EXP`     | exploratory / legacy oddities              |

File placement matches the **primary domain**; secondary domains are listed in
`classification.secondary_domains`.

## Anti-patterns

- `ACCESS-TO-ENERGY`-style expansion of a good short command;
- `PLUS-SYSTEM-FOCUS-NOW` filler stacking;
- renaming `PLUS-THINK` or `PLUS-FOCUS`;
- `SEE-UP`, `HEAR-DOWN`, `SEX-DOWN` directional variants (use MORE/LESS);
- repurposing a domain word as a filler token.