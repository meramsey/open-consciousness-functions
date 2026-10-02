# Native core setup

Use Python≥3.11. From a source checkout:

```bash
python scripts/setup_ocf.py --venv .venv          # dry-run JSON plan, no changes
python scripts/setup_ocf.py --venv .venv --apply  # explicit application
```

The shared planner chooses`bin/python` or`Scripts/python.exe`, creates an unused
virtual environment or reuses a compatible one, installs only ordinary core
Python requirements, then runs structured core doctor. Existing non-venv paths
and incompatible runtimes are rejected; configuration/models/recordings are not
deleted or modified. Repeated pip installation uses satisfied requirements;
no forced upgrade, sudo, shell pipeline or optional model/tool install.

Linux users can obtain Python through their distribution package manager; macOS
may use the official installer/Homebrew; Windows may use the official installer
or winget. These are manual choices, not commands the bootstrap executes.
External audio tools remain selected-workflow dependencies reported by doctor.
After activating the environment, use`python scripts/ocf.py capabilities --json`
and`doctor --workflow ...`; package installation is documented separately.
