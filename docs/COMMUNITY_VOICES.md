# Declarative community voice registry foundation

Shipped metadata-only`ocf voice packs --json`, validated by`validate --all`.
Add schema-defined YAML under`audio/voices/registry/`, using
`templates/community-voice.yaml`. No voice pack/model is bundled or downloaded
by this phase. Runtime TTS profiles remain separate; an optional`profile_id`
links metadata to a declarative profile without adding vendor-specific code.

Records separate engine/software license, model license, redistribution
permission, attribution, personality/voice consent and training-data terms.
Unknown means unknown, not permissive. Explicit consent may be granted, denied,
not-applicable or unknown; a denial cannot be advertised as bundled permission.
Bundled status requires recorded model/voice terms, permitted redistribution and
an identified model hash. These checks reject obvious contradictions; they do
not adjudicate licenses or authenticate a contributor's assertions.

Source/provider, versions, locales, engine/format, sample rate, recommended settings,
pronunciation notes and install status are independent fields. Downloadability
does not establish an open license. Model installation, signatures, distribution
service and automatic generation-profile registration remain follow-up; no real
person's voice is cloned or imitated by this registry.
