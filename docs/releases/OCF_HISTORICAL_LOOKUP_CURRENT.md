# Historical lookup and active cue separation

Use the shared catalog and locale services:

```bash
python scripts/ocf.py functions lookup "Mobius West" --locale en-US --json
python scripts/ocf.py functions lookup "Plus Quiet Sleep" --locale en-US --json
```

A match returns the stable function, current localized title/purpose, active display cue, explicit spoken binding when available, origin locales and a labeled match reason. It never selects an activation target. UI fallback is disclosed; absent localized speech is marked requires-locale-review rather than silently borrowing English.

Former primary aliases marked historical-lookup remain identifiable but are excluded from active command guides and rich activation listings. Secondary Cancel, Release, retrieval and access-close operations retain their roles. Original legacy names/phrase arrays and stable IDs remain intact; an old primary identity may have former wording in historical records and approved new wording now.

Discovery normalization uses NFC, case folding and whitespace folding only. It is not an acoustic cue matcher. Technical old-ID compatibility and source history do not establish current spoken support.

## Migrated vocabulary

- OCF-AUT-001 → Automatic Action / `PLUS-AUTOMATE`; historical matches: See-Be.
- OCF-BOD-001 → Brain Flow / `PLUS-BRAIN FLOW`; historical matches: Brain: Repairs & Maintenance; PLUS-FLOW BETTER; Plus Flow Better.
- OCF-BOD-003 → Comfort / `PLUS-COMFORT`; historical matches: De-Discomfort; PLUS-55515; Plus Five Five Five One Five.
- OCF-BOD-004 → Detox / `PLUS-DETOX`; historical matches: De-Tox: Body; PLUS-DETOX; Plus Clean Clear.
- OCF-BOD-005 → Appetite Choice / `PLUS-SATISFIED, SUPPLIED`; historical matches: Eat/No Eat.
- OCF-BOD-006 → Heart Flow / `PLUS-HEART-BETTER`; historical matches: Heart: Repairs & Maintenance; PLUS-HEART, BETTER, BETTER; Plus Heart Better Better; Heart: Repairs & Maintenance.
- OCF-BOD-007 → Blood Pressure Balance / `PLUS-BALANCE BLOOD PRESSURE`; historical matches: Hypertension; PLUS-BALANCE-BLOODPRESSURE.
- OCF-BOD-008 → Immune Readiness / `PLUS-IMMUNE READY`; historical matches: Immunizing; PLUS-ALERT, DESTROY; Plus Alert Destroy.
- OCF-BOD-009 → Breathe Better / `PLUS-BREATHE BETTER`; historical matches: Lungs: Repairs & Maintenance; PLUS-BREATH BETTER; Plus Breathe Better.
- OCF-BOD-011 → Hormonal Transitions / `PLUS-HORMONE BALANCE`; historical matches: Passages; PLUS-EQUALIZE-HARMONIZE; Plus Equalize Harmonize.
- OCF-BOD-013 → Body Tune-Up / `PLUS-BALANCE, HEAL`; historical matches: Tune-Up.
- OCF-BOD-014 → Regenerate / `PLUS-REGENERATE`; historical matches: PLUS-BUILD, LIVE; Plus Build Live.
- OCF-BOD-015 → Temporary Numbing / `PLUS-NUMB`; historical matches: Short Fix; Plus Go Numb Go Numb.
- OCF-COG-001 → Information Access / `PLUS-ACCESS INFO`; historical matches: Access to Information; PLUS-RETRIEVE; Plus Retrieve.
- OCF-COG-002 → Mental Calculation / `PLUS-CALCULATE`; historical matches: Buy the Numbers.
- OCF-COG-004 → Imprint / `PLUS-IMPRINT`; historical matches: Plus Imprint Imprint.
- OCF-COG-005 → Options / `PLUS-OPTIONS`; historical matches: Plus Options Choices.
- OCF-EMG-001 → Injury Response / `PLUS-CONTROL, BALANCE, RESTORE`; historical matches: Emergency: Injury.
- OCF-EMG-002 → Toxic Exposure Response / `PLUS-CLEAR, REMOVE`; historical matches: Emergency: Toxic.
- OCF-EMO-002 → Offload / `PLUS-OFFLOAD`; historical matches: Off-Loading; PLUS-CLEAR; Plus Fade Fade.
- OCF-EMO-003 → Empathize / `PLUS-EMPATHIZE`; historical matches: Empathizing; PLUS-PROFILE, PROFILE; Plus Profile Profile.
- OCF-EXP-001 → Manifest / `PLUS-MANIFEST`; historical matches: Mobius West; PLUS-PROGRAM; Plus Change Change.
- OCF-EXP-002 → Insulate / `PLUS-INSULATE`; historical matches: Zoning; PLUS-ZONE; Plus Insulate Insulate.
- OCF-FND-003 → Quick Recharge / `PLUS-RECHARGE`; historical matches: Recharge.
- OCF-FND-004 → Relax / `PLUS-RELAX`; historical matches: Plus Relax Relax.
- OCF-FND-005 → Reset / `PLUS-RESET`; historical matches: Plus Reset Reset.
- OCF-LIF-001 → Habit Freedom / `PLUS-FREE THIS HABIT`; historical matches: De-Hab; PLUS-NO MORE, NO MORE; Plus No More No More.
- OCF-PRF-002 → Inner Power / `PLUS-INNER POWER`; historical matches: Eight-Great; PLUS-STRONG; Plus Eight Great.
- OCF-PRF-003 → Coordination / `PLUS-SMOOTH, FAST`; historical matches: Synchronizing.
- OCF-PRF-004 → Light Foot / `PLUS-LIGHT STEP`; historical matches: PLUS-LIGHT; Plus Lighter Lighter.
- OCF-SEN-001 → Hearing / `PLUS-HEAR MORE`; historical matches: Sensory: Hearing.
- OCF-SEN-002 → Seeing / `PLUS-SEE BETTER`; historical matches: Sensory: Seeing.
- OCF-SEN-003 → Smell / `PLUS-SMELL MORE`; historical matches: Sensory: Smell.
- OCF-SEN-004 → Taste / `PLUS-TASTE MORE`; historical matches: Sensory: Taste.
- OCF-SEN-005 → Touch / `PLUS-TOUCH MORE`; historical matches: Sensory: Touch.
- OCF-SLP-001 → Restorative Sleep / `PLUS-RESTORATIVE SLEEP`; historical matches: PLUS-RESTORE; Plus Heal Heal.
- OCF-SLP-002 → Sleep / `PLUS-SLEEP`; historical matches: Plus Twenty Twenty.
- OCF-SLP-003 → Dream Theme / `PLUS-DREAM`; historical matches: Sweet Dreams; Plus Theme Dream Sleep.
- OCF-SLP-004 → Sleep Insight / `PLUS-SLEEP INSIGHT`; historical matches: Wake/Know; PLUS-KNOW; Plus Sleep Help.
- OCF-SLP-005 → Sleep Easy / `PLUS-SLEEP EASY`; historical matches: Sleep Easy; PLUS-SLEEP EASY; Plus Quiet Sleep.
- OCF-SLP-006 → Stay Awake / `PLUS-AWAKE`; historical matches: Plus One Awake Alert One One.
