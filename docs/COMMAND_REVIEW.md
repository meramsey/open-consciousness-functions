GENERATED FILE — DO NOT EDIT DIRECTLY

# Command Review Report

Command-design review generated from the canonical function records.

55 functions total.

## Commands retained unchanged

31 commands are unchanged:

| OCF ID | Legacy name | Legacy command | Canonical | Modes | Review | Compat |
|---|---|---|---|---|---|---|
| `OCF-AUT-001` | SEE-BE | `PLUS-AUTOMATE` | `PLUS-AUTOMATE` |  | approved | unchanged |
| `OCF-BOD-001` | BRAIN: REPAIRS & MAINTENANCE | `PLUS-FLOW BETTER` | `PLUS-FLOW BETTER` |  | approved | unchanged |
| `OCF-BOD-002` | CIRCULATION | `PLUS-FLOW SMOOTH` | `PLUS-FLOW SMOOTH` |  | approved | unchanged |
| `OCF-BOD-005` | EAT/NO EAT | `PLUS-SATISFIED, SUPPLIED` | `PLUS-SATISFIED, SUPPLIED` |  | approved | unchanged |
| `OCF-BOD-006` | HEART: REPAIRS & MAINTENANCE | `PLUS-HEART, BETTER, BETTER` | `PLUS-HEART, BETTER, BETTER` |  | approved | unchanged |
| `OCF-BOD-007` | HYPERTENSION | `PLUS-BALANCE-BLOODPRESSURE` | `PLUS-BALANCE-BLOODPRESSURE` |  | approved | unchanged |
| `OCF-BOD-008` | IMMUNIZING | `PLUS-ALERT, DESTROY` | `PLUS-ALERT, DESTROY` |  | approved | unchanged |
| `OCF-BOD-009` | LUNGS: REPAIRS & MAINTENANCE | `PLUS-BREATH BETTER` | `PLUS-BREATH BETTER` |  | approved | unchanged |
| `OCF-BOD-011` | PASSAGES | `PLUS-EQUALIZE-HARMONIZE` | `PLUS-EQUALIZE-HARMONIZE` |  | approved | unchanged |
| `OCF-BOD-013` | TUNE-UP | `PLUS-BALANCE, HEAL` | `PLUS-BALANCE, HEAL` |  | approved | unchanged |
| `OCF-COG-001` | ACCESS TO INFORMATION | `PLUS-RETRIEVE` | `PLUS-RETRIEVE` |  | approved | unchanged |
| `OCF-COG-002` | BUY THE NUMBERS | `PLUS-CALCULATE` | `PLUS-CALCULATE` |  | approved | unchanged |
| `OCF-COG-003` | CONTEMPLATION | `PLUS-OPEN` / `PLUS-CLOSED` | `PLUS-OPEN` | `PLUS-CLOSED` | approved | unchanged |
| `OCF-COG-004` | IMPRINT | `PLUS-IMPRINT, IMPRINT` / `PLUS-RECALL` | `PLUS-IMPRINT` | `PLUS-RECALL` | approved | unchanged |
| `OCF-COG-005` | OPTIONS | `PLUS-OPTIONS, CHOICES` | `PLUS-OPTIONS` |  | approved | unchanged |
| `OCF-COG-006` | RECALL | `PLUS-RECALL` | `PLUS-RECALL` |  | approved | unchanged |
| `OCF-COG-007` | THINK FAST | `PLUS-THINK` | `PLUS-THINK` |  | approved | unchanged |
| `OCF-COM-001` | SPEAK UP | `PLUS-SPEAK UP` | `PLUS-SPEAK UP` |  | approved | unchanged |
| `OCF-EMG-001` | EMERGENCY: INJURY | `PLUS-CONTROL, BALANCE, RESTORE` | `PLUS-CONTROL, BALANCE, RESTORE` |  | approved | unchanged |
| `OCF-EMG-002` | EMERGENCY: TOXIC | `PLUS-CLEAR, REMOVE` | `PLUS-CLEAR, REMOVE` |  | approved | unchanged |
| `OCF-EMO-001` | LET GO | `PLUS-LET GO` | `PLUS-LET GO` |  | approved | unchanged |
| `OCF-EMO-003` | EMPATHIZING | `PLUS-PROFILE, PROFILE` | `PLUS-PROFILE, PROFILE` |  | approved | unchanged |
| `OCF-FND-001` | ACCESS TO ENERGY | `PLUS-ENERGIZE` | `PLUS-ENERGIZE` |  | approved | unchanged |
| `OCF-FND-002` | ATTENTION | `PLUS-FOCUS` | `PLUS-FOCUS` |  | approved | unchanged |
| `OCF-FND-003` | RECHARGE | `PLUS-RECHARGE` | `PLUS-RECHARGE` |  | approved | unchanged |
| `OCF-FND-004` | RELAX | `PLUS-RELAX, RELAX` | `PLUS-RELAX` |  | approved | unchanged |
| `OCF-FND-005` | RESET | `PLUS-RESET, RESET` | `PLUS-RESET` |  | approved | unchanged |
| `OCF-FND-006` | RELEASE | `PLUS-RELEASE` | `PLUS-RELEASE` |  | approved | unchanged |
| `OCF-PRF-001` | DO THIS NOW | `PLUS-DO-THIS-NOW` | `PLUS-DO-THIS-NOW` |  | approved | unchanged |
| `OCF-PRF-003` | SYNCHRONIZING | `PLUS-SMOOTH, FAST` | `PLUS-SMOOTH, FAST` |  | approved | unchanged |
| `OCF-PRF-005` | MAKE YOUR DAY | `PLUS-THIS DAY` | `PLUS-THIS DAY` |  | approved | unchanged |


## Commands normalized (proposed vocabulary)

Adjustable-magnitude commands are normalized to the MORE/LESS grammar `N`.

7 commands normalized:

| OCF ID | Legacy name | Legacy command | Canonical | Modes | Review | Compat |
|---|---|---|---|---|---|---|
| `OCF-BOD-010` | NUTRICIA | `PLUS-FOOD MORE` / `PLUS-FOOD LESS` | `PLUS-FOOD MORE` | `PLUS-FOOD LESS` | needs-review | alias-listed |
| `OCF-BOD-012` | SEX DRIVE | `PLUS-SEX GREATER` / `PLUS-SEX LESSER` | `PLUS-SEX MORE` | `PLUS-SEX LESS` | needs-review | alias-listed |
| `OCF-SEN-001` | SENSORY: HEARING | `PLUS-HEAR MORE` / `PLUS-HEAR LESS` | `PLUS-HEAR MORE` | `PLUS-HEAR LESS` | needs-review | alias-listed |
| `OCF-SEN-002` | SENSORY: SEEING | `PLUS-SEE BETTER` | `PLUS-SEE MORE` | `PLUS-SEE LESS` | needs-review | alias-listed |
| `OCF-SEN-003` | SENSORY: SMELL | `PLUS-SMELL GREATER` / `PLUS-SMELL LESSER` | `PLUS-SMELL MORE` | `PLUS-SMELL LESS` | needs-review | alias-listed |
| `OCF-SEN-004` | SENSORY: TASTE | `PLUS-TASTE GREATER` / `PLUS-TASTE LESSER` | `PLUS-TASTE MORE` | `PLUS-TASTE LESS` | needs-review | alias-listed |
| `OCF-SEN-005` | SENSORY: TOUCH | `PLUS-TOUCH GREATER` / `PLUS-TOUCH LESSER` | `PLUS-TOUCH MORE` | `PLUS-TOUCH LESS` | needs-review | alias-listed |


## Commands still requiring review

These commands have a proposed canonical form that has not been approved. Legacy commands are always retained as aliases/metadata.

17 commands requiring review:

| OCF ID | Legacy name | Legacy command | Canonical | Modes | Review | Compat |
|---|---|---|---|---|---|---|
| `OCF-BOD-003` | DE-DISCOMFORT | `PLUS-55515` | `PLUS-COMFORT` |  | review-required | bridge-trainable |
| `OCF-BOD-004` | DE-TOX: BODY | `PLUS-CLEAN, CLEAR` | `PLUS-DETOX` |  | review-required | bridge-trainable |
| `OCF-BOD-014` | REGENERATE | `PLUS-BUILD, LIVE` | `PLUS-REGENERATE` |  | review-required | bridge-trainable |
| `OCF-BOD-015` | SHORT FIX | `PLUS-GO NUMB, GO NUMB` / `PLUS-RELEASE` | `PLUS-NUMB` |  | review-required | bridge-trainable |
| `OCF-EMO-002` | OFF-LOADING | `PLUS-FADE, FADE` | `PLUS-CLEAR` |  | review-required | bridge-trainable |
| `OCF-EXP-001` | MOBIUS WEST | `PLUS-CHANGE, CHANGE` | `PLUS-PROGRAM` |  | review-required | bridge-trainable |
| `OCF-EXP-002` | ZONING | `PLUS-INSULATE, INSULATE` / `PLUS-CANCEL` | `PLUS-ZONE` | `PLUS-CANCEL` | review-required | bridge-trainable |
| `OCF-LIF-001` | DE-HAB | `PLUS-NO MORE, NO MORE` | `PLUS-NO MORE, NO MORE` |  | review-required | bridge-trainable |
| `OCF-PRF-002` | EIGHT-GREAT | `PLUS-EIGHT, GREAT` | `PLUS-STRONG` |  | review-required | bridge-trainable |
| `OCF-PRF-004` | LIGHT FOOT | `PLUS-LIGHTER, LIGHTER` | `PLUS-LIGHT` |  | review-required | bridge-trainable |
| `OCF-PRF-006` | STRONG-QUICK | `PLUS-STRONG-QUICK` | `PLUS-STRONG QUICK` |  | review-required | bridge-trainable |
| `OCF-SLP-001` | RESTORATIVE SLEEP | `PLUS-HEAL, HEAL` | `PLUS-RESTORE` |  | review-required | bridge-trainable |
| `OCF-SLP-002` | SLEEP | `PLUS-20-20` | `PLUS-SLEEP` |  | review-required | bridge-trainable |
| `OCF-SLP-003` | SWEET DREAMS | `PLUS-THEME, DREAM, SLEEP` | `PLUS-DREAM` |  | review-required | bridge-trainable |
| `OCF-SLP-004` | WAKE/KNOW | `PLUS-SLEEP, HELP` | `PLUS-KNOW` |  | review-required | bridge-trainable |
| `OCF-SLP-005` | SLEEP EASY | `PLUS-QUIET, SLEEP` | `PLUS-SLEEP EASY` |  | review-required | bridge-trainable |
| `OCF-SLP-006` | STAY AWAKE | `PLUS-ONE, AWAKE, ALERT, ONE, ONE` | `PLUS-AWAKE` |  | review-required | bridge-trainable |


Review guidance: `docs/COMMAND_GRAMMAR.md` and `docs/NAMING_GUIDELINES.md`.
