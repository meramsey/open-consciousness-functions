# Private listening delivery

Private configuration is separate from public defaults and immutable session
editions. The explicit standalone entry point is:

```sh
PYTHONPATH=scripts python -m ocf_tools.private_session --output PRIVATE_OUTPUT --dry-run
PYTHONPATH=scripts python -m ocf_tools.private_session --output PRIVATE_OUTPUT
```

Run production through the existing [independent controller and watchdog](PRODUCTION_SUPERVISION.md),
not as an unattended terminal child. The default configuration is
`$XDG_CONFIG_HOME/ocf/private-session.json` (or `~/.config/ocf/private-session.json`).
`--config`, `--voice` and `--mix-profile` provide explicit overrides. Validate
configuration against `schemas/private-session.schema.json`. Do not commit a
personal configuration, profile, receipt, voice reference or output.

The Learning pathway composes the reviewed standalone template. It does not
assign a function identity, change narration or introduce another DSP engine.
Native-speed selection changes only the runtime narration rate controls; authored
pauses remain. Publication requires a measured ledger matching the composition,
three complete state visits, the designated practice holds, exact resolved
spoken wording, a 44.1 kHz stereo master and zero clipped PCM samples. Failed
scratch remains available. The destination must be new; verified publication
copies are assembled on the destination filesystem before its final rename.
Technical verification is not human listening approval.

## Durable private storage

Use an operator-owned OCF configuration directory and data directory for private
profiles, voices, models, completed editions and review notes. Keep disposable
assembly and cache in the OCF workspace. Preserve originals and verify copied
bytes independently. Do not infer original edition hashes from reconstructed
settings or replace an immutable edition with a reconstruction.

`HF_HOME` and `HF_HUB_CACHE` select durable Hugging Face model storage and are
also honored by voice model fingerprinting. `OCF_VOICE_PROFILE_DIR` and
`OCF_VOICE_ASSETS` select durable private profile and asset directories.
`OCF_CHATTERBOX_PYTHON` selects an explicitly provisioned optional interpreter.
All overrides apply to the private process; public defaults remain unchanged.

A backend dependency constraint conflict must be resolved before claiming a
unified environment is provisioned. In particular, the current Python <3.13
Chatterbox adapter declares NumPy <2, while the project development extra declares
NumPy >=2. Preserve an existing working runtime; do not silently force an
inconsistent installation or weaken the development dependency contract.

## Private listening server

Start `python -m ocf_tools.listening_portal --config PRIVATE_CONFIG` with an
operator-supplied JSON object containing `library`, `host`, `port`, and, for LAN
access, `credentials_file`, `certificate` and `private_key`. A credential file
contains `username:password`, with a password of at least 24 characters.
Protect configuration, credentials and keys with owner-only permissions. Use
`deploy/systemd/ocf-listening-portal.service.in` for bounded restart and graceful
shutdown. Configure its existing production-supervisor owner with
`ocf_tools.listening_portal_worker run/reconcile`, the same private portal config
and status file, and the existing independent watchdog service/timer templates.
The worker checks authenticated readiness every ten seconds; three consecutive
failures trigger bounded controller recovery. Persistent credential provisioning, firewall/VPN changes and linger
require the operator's action-time approval. Never expose this service directly
to the public internet. A locally issued certificate requires explicit client
trust; localhost checks do not establish phone reachability.

Only direct edition directories containing a completed `listening.json` are
considered. Each manifest declares `status: completed`, `technical_verified: true`,
`title`, `edition`, `profile`, a positive `duration_seconds`, and `media` entries.
Each media entry has `role`, a direct-child `file`, `size_bytes`, and `sha256`.
Roles are `audio` (MP3/M4A), `master` (WAV/FLAC), `transcript` (TXT) and optional
`subtitles` (VTT/SRT). Audio, master and transcript are required. Only verified
media entries become opaque playback routes. Do not place voices, models,
references, consent records or credentials in the dedicated listening library.

The server provides HTML5 seeking, download links, a catalog of completed
editions for comparison and separately persisted review notes. It rejects
traversal, symlink paths, corrupt/incomplete editions and arbitrary file reads.
Catalog discovery refreshes on requests; reload the page to see new editions.
The authenticated `/health` endpoint is available for an independent service
health check. TLS handshakes and request reads are bounded. Server logs omit
request paths and credentials.
