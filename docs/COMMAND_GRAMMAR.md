# Command Grammar

Commands are spoken cues. Their design is a first-class constraint.

## Syntax

- Every canonical command starts with the `PLUS` prefix: `PLUS-FOCUS`.
- Hyphens join a single token; commas separate spoken words:
  - `PLUS-DO-THIS-NOW` → one spoken word ("DO-THIS-NOW");
  - `PLUS-CONTROL, BALANCE, RESTORE` → three spoken words.
- Canonical commands must not contain spaces as separators; use commas to
  separate spoken words and hyphens inside a spoken word.

## Word-count rules

| Post-`PLUS` spoken words | Status        |
| ------------------------ | ------------- |
| 1                        | Preferred     |
| 2                        | Acceptable    |
| 3                        | Exceptional maximum |
| 4+                       | Needs review / lint warning |

A canonical command should normally be the **same length or shorter** than the
legacy command it replaces. A longer replacement emits a lint warning.

## Vocabulary rules

- **Do not** add filler words: `NOW`, `SYSTEM`, `FUNCTION`, `ACTIVATE`.
- **Do not** invent awkward compounds or gratuitous hyphens.
- **Do not** prepend domain names without reason.
- **Deprecated magnitude words:** `GREATER`, `LESSER`, `ACCELERATE` (use
  `MORE`/`LESS`).

## Directional grammar

Adjustable/sensory magnitude commands use **MORE / LESS**:

```text
PLUS-SEE MORE       PLUS-SEE LESS
PLUS-HEAR MORE      PLUS-HEAR LESS
PLUS-SMELL MORE     PLUS-SMELL LESS
PLUS-TASTE MORE     PLUS-TASTE LESS
PLUS-TOUCH MORE     PLUS-TOUCH LESS
PLUS-SEX MORE       PLUS-SEX LESS
PLUS-FOOD MORE      PLUS-FOOD LESS
```

MORE/LESS is preferred over UP/DOWN or GREATER/LESSER. Directional pairs
should be balanced: a MORE mode implies a LESS mode (a missing pair lints as
`asymmetric-more-less`).

## Preservation policy

Do **not** rename a command merely for uniform vocabulary. Preserve any
command that is short, intuitive, memorable, and clearly tied to its function:

```text
ATTENTION        -> PLUS-FOCUS      THINK FAST   -> PLUS-THINK
IMPRINT          -> PLUS-IMPRINT    RECALL       -> PLUS-RECALL
ACCESS TO ENERGY -> PLUS-ENERGIZE   RECHARGE     -> PLUS-RECHARGE
```

In particular `THINK FAST -> PLUS-THINK` is **canonical and immutable** — never
replace it with `PLUS-QUICKTHINK`, `PLUS-THINK-FAST`, or longer forms.

## Change criteria

A replacement is justified only for a command that is cryptic, arbitrary,
repetitive, disconnected from its function, inconsistent with a useful
pattern, or awkward to remember. Every changed command records:

```yaml
legacy:
  command_status: proposed|normalized|review-required
compatibility:
  state: alias-listed|bridge-trainable|canonical-first|legacy-first
  rationale: "why"
  legacy_commands: ["PLUS-ORIGINAL, ..."]
```

## Linting

`ocf review commands` flags:

- replacements longer than the legacy command;
- more than three post-prefix spoken words;
- duplicate canonical commands (error);
- missing `PLUS` prefix;
- inconsistent/missing MORE/LESS pair;
- changed command without rationale;
- changed command without compatibility metadata;
- deprecated magnitude vocabulary;
- mode asymmetry.

The report is generated to `docs/COMMAND_REVIEW.md`.