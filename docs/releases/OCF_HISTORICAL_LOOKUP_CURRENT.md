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

- OCF-BOD-001 → Brain Flow / `PLUS-BRAIN FLOW`; historical matches: Brain: Repairs & Maintenance; PLUS-FLOW BETTER; Plus Flow Better.
- OCF-BOD-003 → Comfort / `PLUS-COMFORT`; historical matches: De-Discomfort; PLUS-55515; Plus Five Five Five One Five.
- OCF-BOD-004 → Detox / `PLUS-DETOX`; historical matches: De-Tox: Body; PLUS-DETOX; Plus Clean Clear.
- OCF-BOD-006 → Heart: Repairs & Maintenance / `PLUS-HEART-BETTER`; historical matches: Heart: Repairs & Maintenance; PLUS-HEART, BETTER, BETTER; Plus Heart Better Better.
- OCF-BOD-009 → Breathe Better / `PLUS-BREATHE BETTER`; historical matches: Lungs: Repairs & Maintenance; PLUS-BREATH BETTER; Plus Breathe Better.
- OCF-EMO-002 → Offload / `PLUS-OFFLOAD`; historical matches: Off-Loading; PLUS-CLEAR; Plus Fade Fade.
- OCF-EMO-003 → Empathize / `PLUS-EMPATHIZE`; historical matches: Empathizing; PLUS-PROFILE, PROFILE; Plus Profile Profile.
- OCF-EXP-001 → Manifest / `PLUS-MANIFEST`; historical matches: Mobius West; PLUS-PROGRAM; Plus Change Change.
- OCF-EXP-002 → Insulate / `PLUS-INSULATE`; historical matches: Zoning; PLUS-ZONE; Plus Insulate Insulate.
- OCF-PRF-002 → Inner Power / `PLUS-INNER POWER`; historical matches: Eight-Great; PLUS-STRONG; Plus Eight Great.
- OCF-SLP-004 → Sleep Insight / `PLUS-SLEEP INSIGHT`; historical matches: Wake/Know; PLUS-KNOW; Plus Sleep Help.
- OCF-SLP-005 → Sleep Easy / `PLUS-SLEEP EASY`; historical matches: Sleep Easy; PLUS-SLEEP EASY; Plus Quiet Sleep.
