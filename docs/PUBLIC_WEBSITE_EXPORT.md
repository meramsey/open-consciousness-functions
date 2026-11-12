# Public website documentation export

The audio-library site builds reader pages from a deterministic, allowlisted
projection of the canonical en-US function resources. The export is not a
second function registry. It contains 58 stable IDs, approved localized titles
and descriptions, active command cues, reviewed command explanations, complete
canonical/reviewed procedure steps, lifecycle metadata, approved optional
relationships, safety notes, and search terms with their original editorial
status.

It intentionally does **not** contain function narration text, source evidence
paths, research observations, private reference material, historical aliases as
active commands, draft procedures, or draft relationship proposals. Display and
spoken cues remain distinct. Discovery terms marked `draft` remain labeled as
draft, not recommendations. The public site obtains transcript text only from
the exact companion asset attached to a published audio edition; it does not
substitute current canonical narration for an older edition's transcript.

From the exact source checkout being used for the site build:

```bash
PYTHONPATH=scripts python -m ocf_tools.public_site_export \
  --source-commit "$(git rev-parse HEAD)" \
  --output .ocf-work/tmp/public-site-guides.json
```

Approved relationships are projected through the existing canonical relationship
service; raw per-locale relationship text is never treated as an approval.
Descriptions, type, direction, dependency, and stable relationship ID are
preserved from that projection. The export schema is
`schemas/public-site-guide-export.schema.json`. The
deterministic build receipt contains the source commit, function-resource
fingerprints, an export content hash, and explicit false flags for excluded
narration/evidence/draft content. The repository integration job checks schema,
identity set, deterministic bytes, status gates, and the excluded-content
boundary. Static-site validation and browser checks belong to the audio
distribution repository.

A valid export is not a release authorization or proof of listening approval.
Existing publication manifests and release checksums remain the only authority
for available audio editions. The website exporter never downloads, changes,
or republishes audio.
