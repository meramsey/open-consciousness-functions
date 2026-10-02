# Core and selected-workflow diagnostics

`ocf doctor --json` exposes schema-defined core/runtime/data checks plus optional
tool detection. Missing optional Farfield/Piper/ffmpeg/Docker does not fail core
metadata/authoring health. Select`--workflow encode|farfield|sbagenx|piper|container`
to make that workflow's tools required. Doctor executes/downloads nothing.

Python≥3.11, YAML/schema dependencies and runtime data are core requirements.
Executable availability is not model, codec, engine-version or OS certification:
rendering preflight still validates those concrete choices. A missing binary is
reported missing rather than guessed unsupported. Native and packaged CLI use the
same diagnostic API; JSON is defined by`schemas/doctor.schema.json`.
