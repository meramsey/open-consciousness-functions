# Durable local OCF voice packs

This is a private, gitignored operator store. It is outside `.ocf-work` and is
not managed by `ocf workspace clean`. Pack archives, extracted bundles, source
recordings, consent records, references, and profile metadata must remain local.
Keep independent backups of irreplaceable assets.

For reusable installation, set both supported paths for the current shell:

```bash
export OCF_VOICE_PROFILE_DIR="$PWD/audio/voices/private-packs/profiles"
export OCF_VOICE_ASSETS="$PWD/audio/voices/private-packs/assets"
```

Place source ZIPs and extracted portable bundles in this directory. Inspect and
import them using `docs/VOICE_PACKS.md`. `voice import-profile` verifies bundle
asset hashes, requires a fresh local consent attachment where applicable, and
keeps private profile data local. Successful import is not proof of successful
inference, listening approval, ownership, release authorization, or publication
rights. No private content in this directory is committed.
