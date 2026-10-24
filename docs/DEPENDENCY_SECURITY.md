# Dependency security boundaries

This policy covers current `main`, not a security certification of every local
environment, native codec or optional engine. Report new vulnerabilities through
the [private reporting process](../SECURITY.md).

## Patched supported versions

- Pillow is pinned to **13.0.0** in artwork, guides and development installs.
  The guides pin constrains ReportLab's existing transitive Pillow dependency;
  Pillow is still not a core dependency. Version 13.0.0 is the first patched
  release for the 41 published Pillow advisories inventoried on 2026-10-24.
  This security-required major upgrade retains OCF's Python 3.11 minimum.
- Build/development setuptools requires **84.1.0 or newer**, excluding the
  vulnerable PackageIndex download/URL handling and later archive/path issues
  permitted by the former `>=68` floor. OCF does not call PackageIndex itself;
  this is installation/build exposure, not an OCF network service.
- Development pytest requires **9.0.3 or newer**, excluding vulnerable temporary
  directory handling permitted by the former `>=8.0` floor.
- Native setup, Docker installation and CI bootstrap **pip 26.2.0** from a wheel
  before installing dependencies. This addresses installer archive, URL and
  entry-point traversal advisories; it does not add pip to OCF runtime requirements.

The minimum patched Pillow/setuptools/pytest versions are tested in an isolated
environment. Other reproducible pins are retained. Updating source does not
upgrade an already existing virtual environment: activate the intended one,
bootstrap pip as shown in [setup](SETUP.md), then reinstall the selected extras.
Existing editions, audio, approved narration, DSP profiles and brand assets do
not need regeneration for this dependency update.

## Execution relevance

### Images and fonts

Pillow is an optional runtime parser, even though GitHub classifies the affected
manifest entries as development dependencies. `audition_exports.copy_cover`
decodes operator-selected JPEG covers. It restricts the decoder to JPEG and
rechecks dimensions before conversion. PNG covers are copied byte-for-byte in
that function; release encoding can subsequently parse images through FFmpeg.

Generated artwork decodes committed PNG assets after inventory/hash verification.
Custom theme files can select local fonts, parsed by fontTools and FreeType.
Header, dimension and hash checks are useful boundaries, not proof that a binary
parser has no vulnerabilities. Patched decoders remain necessary.

No normal OCF path was demonstrated for the critical Pillow EPS/Ghostscript,
FPX or multi-frame mode-transition preconditions. OCF does not expose arbitrary
image formats, TIFF/PDF image saving, Arrow export or ImageMorph as a service.
That narrows reachability; it does not dismiss their dependency alerts. All
affected Pillow pins are upgraded rather than allowlisting particular advisories.

### Guides, metadata and recorded narration

The guide renderer uses escaped text, controlled links and a local TrueType font.
It does not accept ReportLab image flowables or unescaped `<img>` markup. Native
lyrics use optional Mutagen; recording/audio preflight and rendering can invoke
FFmpeg/FFprobe on operator-supplied media. Those native parsers and their system
libraries are not covered by a Python package-only advisory inventory.

Use a dedicated non-root environment and consider `--network none` for Docker
when processing untrusted local inputs. Read-only input mounts and resource
limits are additional containment, not substitutes for native codec updates.

### MCP, engines and CI

OCF's MCP entry point explicitly selects `transport="stdio"`; it does not start
the SDK's HTTP/SSE transports. HTTP dependencies in an optional SDK do not, by
themselves, demonstrate a network-facing OCF service. Explicitly running another
HTTP adapter would require its own exposure review.

Piper, Farfield and SBaGenX are separately installed optional executables/models.
Their native libraries and model assets require separate operator inventory;
installing the OCF Python requirements does not certify them. No engines/models
are installed or downloaded by the security update.

The Docker image remains digest-pinned, uses the established FFmpeg package pin
and runs as the unprivileged `ocf` user. Native package/CPython security tracking
remains separate from GitHub's Python dependency graph.

## Pull-request enforcement

The dependency-review workflow blocks newly introduced **high and critical**
advisories across runtime, development and unknown scopes. It uses immutable
action commits and only `contents: read`. It does not execute PR source code,
write PR comments, disable vulnerability checking or maintain advisory allowlists.
License checking is not enabled: this policy is not an automated legal conclusion.
Required-status/branch-protection settings remain a maintainer responsibility.

## Evidence and remaining uncertainty

Private inventories live in ignored `.ocf-work/security/`. Preserve each GitHub
alert number and manifest relationship while grouping duplicate GHSA identities
for remediation planning. Upstream PyPI/OSV findings and installed versions are
separate evidence; do not present them as authenticated repository alerts.

The initial authenticated inventory contained 82 direct manifest alerts for 41
Pillow advisories across two manifests. Closure must be checked through the API
after GitHub processes the patched commit; never manually dismiss alerts just
to obtain a zero count. A one-item page is not the repository alert total.

An isolated agent HOME can hide a working GitHub keyring configuration. Compare
config-directory locations and the **presence**, never values, of token override
variables. A read-only child process may select the existing normal GitHub config
directory without modifying credentials or changing the server environment.

See [Pillow 13 release/security notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)
and the [Dependabot alerts API](https://docs.github.com/en/rest/dependabot/alerts).
