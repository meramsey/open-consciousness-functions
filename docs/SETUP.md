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
