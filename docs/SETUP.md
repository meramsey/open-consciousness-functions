# Native core setup

Use Python≥3.11. From a source checkout:

```bash
python scripts/setup_ocf.py --venv .venv          # dry-run JSON plan, no changes
python scripts/setup_ocf.py --venv .venv --apply  # explicit application
```

The shared planner chooses`bin/python` or`Scripts/python.exe`, creates an unused
virtual environment or reuses a compatible one, bootstraps the pinned security
baseline `pip==26.2.0` from a wheel, installs only ordinary core Python
requirements, then runs structured core doctor. Existing non-venv paths
and incompatible runtimes are rejected; configuration/models/recordings are not
deleted or modified. The installer update is visible in the dry-run plan and
runs only with `--apply`; other core requirements reuse satisfied versions.
No sudo, shell pipeline or optional audio engine/model install is performed.

For manual setup, run this after activating the virtual environment and before
installing OCF:

```bash
python -m pip install --only-binary=:all: --upgrade pip==26.2.0
```

Existing environments are not changed by updating source files alone; reinstall
the selected extras to apply their patched pins. See
[dependency security](DEPENDENCY_SECURITY.md) for scope and remaining risks.

Linux users can obtain Python through their distribution package manager; macOS
may use the official installer/Homebrew; Windows may use the official installer
or winget. These are manual choices, not commands the bootstrap executes.
External audio tools remain selected-workflow dependencies reported by doctor.
After activating the environment, use`python scripts/ocf.py capabilities --json`
and`doctor --workflow ...`; package installation is documented separately.

## Existing local audio environment

OCF does not install Piper, voices, or audio tools during discovery. From the
repository root, inspect the existing project interpreter and local voice/tool
installations with:

```bash
.venv/bin/python scripts/ocf.py voice doctor
```

The preflight prefers `OCF_PYTHON`, then a compatible repository `.venv`, the
version selected by `.python-version` through pyenv, and finally a compatible
active Python 3.11+. Piper resolution checks PATH, `.venv` entry points and the
account's existing `~/.local/bin/piper`; it follows the executable's shebang
and checks its installed package without installing anything. A session harness
that changes `HOME` is handled using the OS account home. Set
`OCF_PIPER_EXECUTABLE` or `OCF_VOICE_ASSETS` only when the existing local tools
or models are stored elsewhere. Piper model paths and expected hashes remain
owned by the selected voice profile/cache; discovery never downloads a model.

To validate the configured Amy Medium model and engine, then make one fresh,
short synthesis without writing an audio file:

```bash
.venv/bin/python scripts/ocf.py voice doctor
.venv/bin/python scripts/ocf.py voice smoke OCF-VOICE-9003 --locale en-US
```

For a private complete session, use the regular OCF renderer after preflight:

```bash
.venv/bin/python scripts/ocf.py audio render FUNCTION_ID \
  --voice OCF-VOICE-9003 --pacing sleep
```

If preflight says the executable is found but broken, inspect the reported
interpreter/package details. If it says not found, check the active PATH, the
project `.venv/bin/` (or Windows `.venv/Scripts/`), `OCF_PIPER_EXECUTABLE`, and
the exact shebang interpreter. Only provision a dependency when those checks
establish that the package itself is genuinely absent. Node tooling follows
the active nvm/PATH version and `.nvmrc`; OCF does not change global pyenv/nvm
defaults.
