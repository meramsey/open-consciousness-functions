# Portability audit and verification boundary

Core unit contracts are configured in CI on Linux/macOS/Windows with Python3.11/
3.12. External-tool/audio integration has a separate Linux job and skips clearly
when ffmpeg is unavailable. **Configured CI is not remote runtime verification**;
this execution environment verified Linux only.

Audited boundaries: pathlib and argument-list subprocesses in native application
code;`os.pathsep` for Farfield search overrides; temporary files via tempfile;
UTF8 on authoritative YAML/JSON/Markdown. Local reference directories containing
colons are not portable Windows assets and are never runtime dependencies or
packaged recordings. Paths under`/tmp` in historical reports identify prior local
artifacts, not application defaults; use persistent local auditions now.

Remaining issues: source-layout-only packaged data lookup; optional Farfield
source-checkout discovery examines POSIX launcher shebangs, so installed preset
mirrors must remain authoritative. Some source launchers/Makefile developer tasks
use a shell; Python CLI is the cross-platform path. A missing platform-specific
engine must be reported as a workflow capability, not a core failure. These
adapters need dedicated Windows/macOS runtime tests before support certification.
