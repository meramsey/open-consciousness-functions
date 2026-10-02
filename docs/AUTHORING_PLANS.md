# Structured authoring plans

Shipped: `ocf plan FILE --json`. This dry-run validates declarative choices using
existing templates, composition, command ownership, strict locale resources,
state-profile bindings and recording event mappings. An external agent reasons
about the request; OCF does not interpret arbitrary natural-language instructions.

```yaml
schema_version: "1.0"
template: OCF-TPL-SESSION-PILOT-RELAX-001
locale: en-US
narration_source: tts
target_duration_s: 1200
```

`target_duration_s` expresses a request, **not a measured result**. The planner
never pads a draft with invented narration, time-stretches speech or declares
human review complete. The example validates the frozen draft pilot, not a
finished20-minute relaxation product. Recording sources require a package;
slot paths are relative to the plan file. No TTS/DSP execution or downloads occur.
Machine-readable failures have `valid:false` and a nonzero exit status.
Templates/required slots are discoverable through `session list-templates` and
their schema-defined YAML; full interactive wizard/default design remains follow-up.
