# Source checkout and installed-wheel runtime data

Data lookup is independent of the caller's working directory. Source checkout
uses its authoritative directories. Standard wheel installs use
`importlib.resources` to locate the packaged`ocf_tools/data` snapshot. An explicit
`OCF_DATA_ROOT` override must contain schemas/functions and can point to a complete
writable checkout for contributor workflows; set it before starting the process.

Build hook stages only whitelisted declarative runtime trees. No research files,
user recordings, rendered audio, binary models, reference-derived session wording
or Attention's citation-only runtime binding are packaged. Canonical55-function
metadata/evidence remains intact. `package-data-manifest.json` lists included and
omitted files. Packaged templates include only`origin: original-ocf` records;
this does not promote draft content or relabel historical scripts.

```bash
python -m pip wheel . --no-deps --wheel-dir dist
python -m pip install dist/open_consciousness_functions-0.1.0-py3-none-any.whl
ocf doctor --json
ocf functions list --rich --json
ocf validate --all
```

Wheel build/install, discovery from an unrelated directory and full packaged
schema/content validation were actually run on Linux/Python3.12. macOS/Windows
are configured/testable but not locally verified. Zip-app distribution is not
claimed. Packaged data is a read-only-style runtime snapshot; new/edit/index
authoring uses a writable checkout/explicit data root. Default narration output
for a wheel is under the user's`.ocf/rendered`; explicit`--output` is preferred.
