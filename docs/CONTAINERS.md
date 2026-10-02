# Optional CPU generation container

Native operation remains first-class. The Dockerfile pins Python/core Python
dependencies, installs ffmpeg, runs as a non-root UID10001 and copies explicit
runtime data only. No reference recordings/transcripts, user narration, models,
local renders or Attention citation-only template/binding are baked into layers.
The base manifest digest and ffmpeg version are pinned; transitive Debian package
repositories still need snapshot pinning before claiming bit-for-bit image
reproducibility. External Farfield/Piper are optional
and not installed/downloaded automatically.

```bash
docker build -t ocf-local .
docker run --rm ocf-local doctor --json
docker run --rm ocf-local functions list --rich --json
docker run --rm -v /absolute/input:/input:ro -v /absolute/output:/out \
  -v ocf-model-cache:/home/ocf/.ocf ocf-local \
  voice render /input/session.yaml --recordings /input/package.yaml --output /out/narration.wav
```

Replace host mount paths with your actual directories; Docker Desktop supports
the same container paths on macOS/Windows. On Linux an explicit`--user UID:GID`
may be needed for writable bind mounts; ensure the cache volume's permissions
match that identity. The image does not silently chown user assets. CPU is default;
GPU is neither required nor automatically enabled. After build/assets are present,
recorded narration generation does not require runtime network.

All container commands are explicit user invocations, never automatically run by
doctor/planning. Build/run verification is recorded in the Phase2B checkpoint;
static configuration tests alone do not certify Docker or other host platforms.
