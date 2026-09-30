# Safety Policy

Safety governs every function record, script, audio implementation, and
document.

## Principles

1. **No guarantees.** Nothing in OCF promises a psychological, physiological,
   medical, paranormal, or behavioral result.
2. **Clear levels.** Every function declares a safety level.
3. **Explicit emergency language.** Emergency functions say they do not
   replace emergency services, first aid, poison control, medical evaluation,
   or professional treatment.
4. **Low-friction reporting.** Safety concerns are filed through the dedicated
   issue template or privately via `SECURITY.md`.

## Safety levels

| Level        | Default statement                                                            |
| ------------ | ---------------------------------------------------------------------------- |
| `general`    | Universal self-help framing; no medical relevance figure.                    |
| `health`     | "Self-directed wellness practice; not a substitute for professional medical evaluation or treatment. No guaranteed effects are claimed." |
| `emergency`  | Adds the emergency-services disclaimer (below).                              |
| `experimental` | Reserved for exploratory functions; caution notes.                          |

## Health functions

Records with `safety.medical_relevance: true` require a `health` or higher
level and the health statement above. Health functions are never described as
treatments.

## Emergency functions

Emergency-record statements must include:

> Does NOT replace emergency services, first aid, poison control, or medical
> evaluation. If you believe you have an emergency or poisoning, call your
> local emergency number first.

## Audio safety

Audio implementations and background presets carry:

- a **headphone notice** (`safety.headphone_notice`);
- a **driving warning** (`safety.driving_warning`);
- volume/loudness notes in the technical block.

Background presets must not be presented as producing psychoacoustic or
health effects.

## Content guidelines

- Rehearsals are phrased in "supports / aims to" language — never
  "will cure", "guarantees", "proven to".
- No instructional content may urge ignoring real-world emergencies or medical
  care in favor of a function.
- Keep transcripts original and non-medical.

## Reporting

Use the `safety_concern.yml` issue template, or the private channel described
in `SECURITY.md` for sensitive reports.